"""Generate data/items.json from data/graph.json (CLAUDE.md §4, five per node).

    python -m build.generate_items            # mock LLM, no key needed
    BUILD_LLM=real python -m build.generate_items
    python -m build.generate_items --check    # report, write nothing

Runs manually, offline, never at runtime. Output is frozen data that a human
reviews afterwards - §4 puts a HUMAN REVIEW pass after this script, and §9.4
exists because four hours over 250 items is 58 seconds each, enough for the key
and not for three distractors.

WHAT THE MOCK CAN AND CANNOT DO

Two of the five items per node are built from the graph alone and need no model
at all: a node_click item whose stem is the node's own definition, and an
edge_click item over an incoming prerequisite. Those are as good under the mock
as they will ever be, because the graph is hand-authored and the definitions are
real.

The other three are mechanism MCQs - "what does this actually do" - whose answer
is a proposition rather than a node. Writing a good one, and three distractors
that are wrong but not obviously wrong, is the part that needs the model and the
chapter text. Under the mock they are structurally valid placeholders and are
marked as such, so the review pass can find them: every generated item carries
`generator`, and `mock` there means "not yet written by anything that read the
chapter".

VISUALLY_ANSWERABLE IS THE LOAD-BEARING FLAG

True only when the answer is a node or an edge on the graph (§3). The mechanism
MCQs are false, which is why the mix here comes out around 40% true - close to
what §3 expects of a real bank, and the ratio §9.1's leakage subset depends on.
build/validate.py enforces the identity invariant that goes with it.

ANSWER_SPANS ARE EMPTY AND THAT IS A KNOWN GAP

§3 wants character offsets of the answer inside the source chunk, and §5 masks
those spans before handing a chunk to Call 2 on `advance` and `explain`. The
graph was hand-authored from the chapter rather than extracted from it, so there
are no offsets to record: there is no chunk file to offset into. Every item here
therefore has `answer_spans: []`, which means span masking is untested rather
than working. See docs/writeup/limitations.md.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from build.config import BUILD
from build.llm import MockLLM, get_llm

SEED = 20260905

#: Mechanism-MCQ shapes for the mock. Answers are propositions, so
#: visually_answerable is false and no dimming can leak them.
MOCK_MECHANISMS = [
    ("it reduces the sending rate when the network signals overload",
     ["it increases the receiver's buffer",
      "it reorders packets at the bottleneck",
      "it shortens the routing path"]),
    ("it reacts to a signal the sender can observe without router support",
     ["it requires every router on the path to agree",
      "it depends on the application declaring its bandwidth",
      "it is negotiated once when the connection opens"]),
    ("it trades some throughput for a shorter queue at the bottleneck",
     ["it trades fairness for a larger congestion window",
      "it trades latency for a higher drop probability",
      "it trades buffer space for a longer timeout"]),
]


def _mock_mechanism(payload: dict) -> dict:
    """Deterministic stand-in for the mechanism-MCQ pass."""
    key, wrong = MOCK_MECHANISMS[payload["k"] % len(MOCK_MECHANISMS)]
    return {"answer": key, "distractors": list(wrong)}


def build_items(graph: dict, llm) -> dict:
    rng = random.Random(SEED)
    nodes = graph["nodes"]
    node_ids = [n["id"] for n in nodes]
    by_id = {n["id"]: n for n in nodes}

    incoming: dict[str, list[str]] = {}
    for e in graph["edges"]:
        if e["type"] == "prereq":
            incoming.setdefault(e["to"], []).append(e["from"])

    generator = "mock" if isinstance(llm, MockLLM) else "real"
    items: list[dict] = []
    # Provenance rides ALONGSIDE the bank, never inside it: Item is a frozen
    # schema with extra="forbid" (§3), and a build-time note is not wire data.
    provenance: dict[str, str] = {}
    n = 0

    for node in nodes:
        nid = node["id"]
        # Distractors are drawn from the same layer of the graph where possible:
        # a distractor from the far side of the chapter is never selected, which
        # §9.4 flags as dead weight - the item is silently 3-choice while being
        # scored as 4-choice.
        siblings = [m for m in node_ids if m != nid and _near(graph, nid, m)]
        pool = siblings if len(siblings) >= 3 else [m for m in node_ids if m != nid]

        for k in range(BUILD.items_per_node):
            n += 1
            item_id = f"itm_{n:04d}"

            if k == 0:
                # The definition IS the stem. No model needed, and it is the
                # best item on the node because the definition is hand-written.
                items.append({
                    "id": item_id,
                    "node_id": nid,
                    "type": "node_click",
                    "prompt": f"Which concept is this: {node['definition']}",
                    "answer": nid,
                    "answer_aliases": _aliases(node["label"]),
                    "distractors": rng.sample(pool, 3),
                    "difficulty": node["difficulty"],
                    "visually_answerable": True,
                    "answer_spans": [],
                })
                provenance[item_id] = "graph"
                continue

            if k == 1 and incoming.get(nid):
                parent = incoming[nid][0]
                items.append({
                    "id": item_id,
                    "node_id": nid,
                    "type": "edge_click",
                    "prompt": (
                        f"Click the link showing what you need to understand "
                        f"before {node['label']}."
                    ),
                    "answer": f"{parent}->{nid}",
                    "answer_aliases": [
                        f"{by_id[parent]['label'].lower()} to {node['label'].lower()}"
                    ],
                    "distractors": rng.sample(pool, 3),
                    "difficulty": round(min(0.95, node["difficulty"] + 0.10), 2),
                    "visually_answerable": True,
                    "answer_spans": [],
                })
                provenance[item_id] = "graph"
                continue

            out = llm.run("mechanism_mcq", {"node": nid, "label": node["label"], "k": k})
            items.append({
                "id": item_id,
                "node_id": nid,
                "type": "mcq",
                "prompt": f"What does {node['label']} actually do?",
                "answer": out["answer"],
                "answer_aliases": [],
                "distractors": list(out["distractors"]),
                "difficulty": round(min(0.95, node["difficulty"] + 0.05), 2),
                "visually_answerable": False,
                "answer_spans": [],
            })
            provenance[item_id] = generator

    return {"version": "1.0", "domain": graph["domain"], "items": items}, provenance


def _near(graph: dict, a: str, b: str) -> bool:
    """True when a and b share a neighbour or an edge - a rough 'same part of
    the chapter' test, so distractors are plausible rather than absurd."""
    adj: dict[str, set] = {}
    for e in graph["edges"]:
        adj.setdefault(e["from"], set()).add(e["to"])
        adj.setdefault(e["to"], set()).add(e["from"])
    return b in adj.get(a, set()) or bool(adj.get(a, set()) & adj.get(b, set()))


def _aliases(label: str) -> list[str]:
    low = label.lower()
    out = {low, low.replace(" ", "-"), low.replace("'", "")}
    return sorted(a for a in out if a)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", default=BUILD.graph_path, type=Path)
    ap.add_argument("--out", default=BUILD.items_path, type=Path)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args(argv)

    graph = json.loads(args.graph.read_text(encoding="utf-8"))

    llm = get_llm()
    if isinstance(llm, MockLLM):
        llm.register("mechanism_mcq", _mock_mechanism)

    bank, provenance = build_items(graph, llm)
    items = bank["items"]
    visual = sum(1 for i in items if i["visually_answerable"])
    by_gen: dict[str, int] = {}
    for gen in provenance.values():
        by_gen[gen] = by_gen.get(gen, 0) + 1

    print(f"{len(items)} items over {len(graph['nodes'])} nodes "
          f"({BUILD.items_per_node} per node)")
    print(f"visually_answerable: {visual}/{len(items)} ({visual * 100 // len(items)}%)")
    print(f"by generator: {by_gen}")
    if by_gen.get("mock"):
        print(f"NOTE {by_gen['mock']} items are mock placeholders awaiting a real "
              f"pass over the chapter; they are marked generator=mock.")

    if args.check:
        print("--check: nothing written")
        return 0

    args.out.write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")

    # The §4 human-review worklist. A sidecar rather than a field on the item,
    # because items.json must stay exactly to the frozen Item schema.
    review = args.out.parent / "items_review.json"
    payload = {
        "generated_from": args.graph.name,
        "note": (
            "generator=mock means the item was not written by anything that "
            "read the chapter. Those need the §4 human review pass before any "
            "number is reported from them."
        ),
        "provenance": provenance,
    }
    review.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    print(f"wrote {review}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
