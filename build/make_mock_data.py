"""Generate the MOCK graph.json and items.json fixtures.

NOT part of the real pipeline. CLAUDE.md §4 describes the real build (PDF ->
concepts -> edges -> human correction -> freeze_layout). This exists only so the
mock server and Person B's client have something schema-valid to render on day 2,
before Person A's chapter graph lands in week 1.

TWO DECISIONS THAT LOOK ODD AND ARE NOT:

1. FIFTY nodes, matching CLAUDE.md §3's 40-60 bound - not a convenient dozen.
   Dimming contrast, layout density, viewport fit, zoom behaviour and label
   truncation all get tuned against whatever the client renders on day 2, and
   none of that tuning survives the jump from 16 nodes to 50 with 45 dimmed.
   Building the client against a small fixture guarantees the week-3 surprise
   the mock exists to prevent.

2. JUNK labels, not real TCP concepts. Real-looking labels invite tuning the
   layout to content that is about to be replaced wholesale, and invite reading
   pedagogical meaning into a graph that has none. The labels vary in length on
   purpose, to stress truncation.

Person A overwrites data/graph.json and data/items.json with the real chapter and
deletes this file. Nothing imports it at runtime.

    python -m build.make_mock_data
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from build.config import BUILD

ROOT = Path(__file__).resolve().parent.parent

SEED = 6180339
N_LAYERS = 8

X_SPACING = 210
Y_SPACING = 155
X_MARGIN = 120
Y_MARGIN = 90

ONSETS = ["k", "t", "m", "v", "s", "dr", "fl", "th", "gr", "pr", "n", "l", "br", "st"]
NUCLEI = ["a", "e", "i", "o", "u", "ae", "ei", "ou", "ia"]
CODAS = ["n", "r", "l", "st", "th", "sk", "m", "ng", "rd", ""]
SUFFIXES = ["", "", "", " phase", " window", " limit", " state", " pass", " bound"]


def _word(rng: random.Random) -> str:
    syllables = rng.choice([1, 2, 2, 3])
    out = ""
    for _ in range(syllables):
        out += rng.choice(ONSETS) + rng.choice(NUCLEI) + rng.choice(CODAS)
    return out.capitalize()


def build_graph() -> dict:
    rng = random.Random(SEED)

    # 50 nodes spread over 8 layers, widths chosen to look like a real dagre
    # output rather than a grid.
    widths = [4, 6, 7, 8, 8, 7, 6, 4]
    assert sum(widths) == 50, sum(widths)

    layers: list = []
    n = 0
    used_labels = set()
    for row, width in enumerate(widths):
        layer = []
        for _ in range(width):
            label = _word(rng) + rng.choice(SUFFIXES)
            while label in used_labels:
                label = _word(rng) + rng.choice(SUFFIXES)
            used_labels.add(label)
            layer.append((f"n{n:02d}", label))
            n += 1
        layers.append(layer)

    widest = max(widths)
    nodes = []
    for row, layer in enumerate(layers):
        offset = (widest - len(layer)) * X_SPACING / 2
        for col, (nid, label) in enumerate(layer):
            nodes.append({
                "id": nid,
                "label": label,
                "definition": f"Placeholder definition for {label}. Regenerated fixture, not source text.",
                "source_sections": [f"{row + 1}.{col + 1}"],
                # Difficulty rises with depth, jittered so selection has
                # something to discriminate on.
                "difficulty": round(min(0.95, 0.1 + row * 0.1 + rng.uniform(-0.04, 0.04)), 2),
                "x": round(X_MARGIN + offset + col * X_SPACING, 1),
                "y": round(Y_MARGIN + row * Y_SPACING, 1),
            })

    # Prereq edges only ever point from an earlier layer to a later one, so the
    # result is a DAG by construction. build/validate.py checks it anyway.
    edges = []
    seen = set()
    for row in range(1, len(layers)):
        parents = layers[row - 1]
        for idx, (nid, _) in enumerate(layers[row]):
            # 1-2 parents, biased to the nodes sitting roughly above.
            near = sorted(parents, key=lambda p, i=idx: abs(parents.index(p) - i))
            for parent, _label in near[: rng.choice([1, 1, 2])]:
                if (parent, nid) not in seen:
                    seen.add((parent, nid))
                    edges.append({"from": parent, "to": nid, "type": "prereq"})

    # Every node needs at least one edge - validate.py rejects orphans.
    connected = {e["from"] for e in edges} | {e["to"] for e in edges}
    for row in range(1, len(layers)):
        for nid, _ in layers[row]:
            if nid not in connected:
                parent = layers[row - 1][0][0]
                edges.append({"from": parent, "to": nid, "type": "prereq"})
                connected.add(nid)
    for nid, _ in layers[0]:
        if nid not in connected and len(layers) > 1:
            child = layers[1][0][0]
            edges.append({"from": nid, "to": child, "type": "prereq"})

    # A few lateral 'related' edges, which are not prereqs and must not affect
    # next-node selection.
    for row in layers:
        if len(row) >= 3:
            a, b = rng.sample(row, 2)
            edges.append({"from": a[0], "to": b[0], "type": "related"})

    return {
        "version": "1.0",
        "domain": "MOCK_fixture_50",
        "nodes": nodes,
        "edges": edges,
    }


# Mechanism questions: the answer is a proposition, not a node, so
# visually_answerable is false. CLAUDE.md 3 expects MOST of a real bank to look
# like this - "why does TCP halve cwnd on loss" is a mechanism, not a node - and
# a fixture that is 100% node-answerable never exercises the path where
# graph_state.current_node is populated. Option ids ARE the strings here;
# GraphStore.label falls through to the raw value for a non-node id, so no schema
# change is needed to carry them.
MECHANISM_TEMPLATES = [
    ("Because the {a} is treated as evidence of congestion.",
     ["Because the receiver ran out of buffer space.",
      "Because the round-trip time estimate expired.",
      "Because the sender exhausted its send window."]),
    ("It grows once per round trip rather than once per acknowledgement.",
     ["It grows once per acknowledgement rather than once per round trip.",
      "It stays fixed until a loss event occurs.",
      "It halves on every acknowledgement received."]),
    ("The sender has no estimate of available capacity yet.",
     ["The receiver has not advertised a window yet.",
      "The retransmission timer has not been initialised.",
      "The connection is still in the handshake."]),
]


def build_items(graph: dict) -> dict:
    rng = random.Random(SEED + 1)
    node_ids = [n["id"] for n in graph["nodes"]]
    by_id = {n["id"]: n for n in graph["nodes"]}
    incoming = {}
    for e in graph["edges"]:
        if e["type"] == "prereq":
            incoming.setdefault(e["to"], []).append(e["from"])

    items = []
    n = 0
    for node in graph["nodes"]:
        nid = node["id"]
        pool = [m for m in node_ids if m != nid]

        for k in range(BUILD.items_per_node):
            n += 1
            distractors = rng.sample(pool, 3)

            # 3 of 5 items are mechanism MCQs -> visually_answerable false, which
            # is the majority CLAUDE.md 3 expects and the path where
            # current_node is safe to populate.
            if k >= 2:
                key, wrong = MECHANISM_TEMPLATES[(k - 2) % len(MECHANISM_TEMPLATES)]
                key = key.format(a=node["label"].lower())
                items.append({
                    "id": f"itm_{n:04d}",
                    "node_id": nid,
                    "type": "mcq",
                    "prompt": f"Mechanism question about {node['label']}.",
                    "answer": key,
                    "answer_aliases": [],
                    "distractors": list(wrong),
                    "difficulty": round(min(0.95, node["difficulty"] + 0.05), 2),
                    "visually_answerable": False,
                    "answer_spans": [],
                })
                continue

            # One edge_click per node where an incoming prereq edge exists.
            if k == 1 and incoming.get(nid):
                parent = incoming[nid][0]
                items.append({
                    "id": f"itm_{n:04d}",
                    "node_id": nid,
                    "type": "edge_click",
                    "prompt": f"Click the edge leading into {node['label']}.",
                    "answer": f"{parent}->{nid}",
                    "answer_aliases": [f"{by_id[parent]['label'].lower()} to {node['label'].lower()}"],
                    "distractors": distractors,
                    "difficulty": round(min(0.95, node["difficulty"] + 0.1), 2),
                    "visually_answerable": True,
                    "answer_spans": [],
                })
                continue

            kind = "node_click"
            items.append({
                "id": f"itm_{n:04d}",
                "node_id": nid,
                "type": kind,
                "prompt": f"Which concept is described as: {node['definition']}",
                "answer": nid,
                "answer_aliases": [
                    node["label"].lower(),
                    node["label"].lower().replace(" ", "-"),
                ],
                "distractors": distractors,
                "difficulty": round(min(0.95, max(0.05, node["difficulty"] + rng.uniform(-0.05, 0.05))), 2),
                "visually_answerable": True,
                "answer_spans": [],
            })

    return {"version": "1.0", "domain": graph["domain"], "items": items}


def main() -> None:
    graph = build_graph()
    items = build_items(graph)
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    (data / "graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    (data / "items.json").write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")

    xs = [n["x"] for n in graph["nodes"]]
    ys = [n["y"] for n in graph["nodes"]]
    print(f"wrote {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, {len(items['items'])} items")
    print(f"canvas extent: {max(xs) - min(xs):.0f} x {max(ys) - min(ys):.0f}")
    longest = max(graph["nodes"], key=lambda n: len(n["label"]))
    print(f"longest label: {longest['label']!r} ({len(longest['label'])} chars)")


if __name__ == "__main__":
    main()
