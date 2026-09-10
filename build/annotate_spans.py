"""Populate `answer_spans` in data/items.json against the real chapter corpus.

    python -m build.annotate_spans --check    # report, write nothing
    python -m build.annotate_spans            # rewrite data/items.json in place

Runs manually, offline, never at runtime (§1.2, §4). Idempotent: running it
twice produces the same file.

WHY THIS IS NOT PART OF generate_items.py
-----------------------------------------
`data/items.json` has been through the §4 human-correction pass. It carries
decisions no generator knows about - the mcq `scorable` demotion, the edge items
excluded after the anchor measurement. Regenerating the bank to add one field
would discard all of them. So this script ANNOTATES the existing file and
touches nothing else: it reads `answer`, `answer_aliases` and `node_id`, and it
writes `answer_spans`. Any item whose spans it cannot compute keeps `[]`.

WHY IT CALLS THE SERVER'S OWN RETRIEVAL
---------------------------------------
§3 defines `answer_spans` as "character offsets of the answer inside the source
chunk". At runtime the source chunk is whatever `retrieval.search` returns for
that node, so offsets are only meaningful against THAT chunk. Reimplementing the
scorer here would let the build's idea of the chunk drift from the server's, and
the failure would be silent: masking would blank the wrong characters and the
answer would survive in the text handed to Call 2.

So this imports `server.retrieval` and asks it, exactly as `turn._chunk_for`
does, with the same query (`label` + `definition`). That is the one place the
build pipeline is allowed to depend on runtime behaviour, and it is a dependency
on a FROZEN input (§1.2: chunks.json is frozen data and the scorer is
deterministic), not on request state. `build/validate.py` re-derives every span
and fails if this stops being true.

WHAT THE SURFACE IS
-------------------
Not just the aliases. For an edge answer "a->b", naming either endpoint hands
over half the edge, so both endpoint labels are masked too - the same surface
`server/turn.py` screens Call 2 against, for the same reason.

WHAT THIS CANNOT DO
-------------------
Literal matching only. A chunk that explains slow start without ever writing the
words "slow start" is not masked, and no offset-based scheme could mask it. The
count of items that come back empty is printed and is the honest measure of how
far span masking gets you; the retrieval gate above it (§5: no chunk at all on
`ask` and `hint_*`) is the coarser and more important guarantee.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build.config import BUILD


def answer_surface(item: dict, labels: dict) -> set:
    """Every string that would name this item's answer at label fidelity.

    Mirrors `server/turn._answer_surface`. Duplicated rather than imported
    because §1.9 makes the schemas the contract between the layers, not the
    helpers - and `build/validate.py` asserts the two agree on real items, which
    is a stronger check than a shared import would give.
    """
    surface = {a.casefold() for a in item.get("answer_aliases", [])}
    answer = item.get("answer", "")

    if answer in labels:
        surface.add(labels[answer].casefold())
    elif "->" in answer:
        for endpoint in answer.split("->"):
            endpoint = endpoint.strip()
            if endpoint in labels:
                surface.add(labels[endpoint].casefold())

    return {s for s in surface if s}


def find_spans(text: str, surface: set) -> list:
    """Half-open [start, end) offsets of every surface string in `text`.

    Overlapping and nested matches are merged, so masking a span never lands
    inside another one and `[...]` is never emitted twice for one occurrence -
    "fair queuing" inside "weighted fair queuing" is the case this graph
    actually produces.
    """
    hits = []
    low = text.casefold()
    for phrase in surface:
        for match in re.finditer(re.escape(phrase), low):
            hits.append((match.start(), match.end()))

    hits.sort()
    merged: list = []
    for start, end in hits:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return [[a, b] for a, b in merged]


def spans_for_item(item: dict, nodes: dict, labels: dict) -> tuple:
    """(spans, chunk_id, reason). `reason` is None when spans were computed."""
    from server import retrieval

    node = nodes.get(item["node_id"])
    if node is None:
        return [], None, "node not in graph"

    hit = retrieval.search(f"{node['label']} {node.get('definition', '')}")
    if hit is None:
        # Guard layer 4 refused. There is no chunk at runtime either, so there
        # is nothing to mask and nothing to record.
        return [], None, "retrieval gate refused"

    spans = find_spans(hit.chunk.text, answer_surface(item, labels))
    if not spans:
        return [], hit.chunk.id, "answer absent from the served chunk"
    return spans, hit.chunk.id, None


def annotate(graph: dict, bank: dict) -> tuple:
    nodes = {n["id"]: n for n in graph["nodes"]}
    labels = {n["id"]: n["label"] for n in graph["nodes"]}

    reasons: dict = {}
    served: dict = {}
    for item in bank["items"]:
        spans, chunk_id, reason = spans_for_item(item, nodes, labels)
        item["answer_spans"] = spans
        served[item["id"]] = chunk_id
        if reason:
            reasons[item["id"]] = reason
    return bank, reasons, served


def dumps(bank: dict) -> str:
    """`indent=2`, but with each span pair on one line.

    `data/items.json` is frozen data that a human reads during the §4 review
    pass. Default indenting explodes every `[start, end]` onto four lines and
    turns a two-number annotation into the largest thing in the item.
    """
    text = json.dumps(bank, indent=2, ensure_ascii=False)
    return re.sub(
        r"\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]",
        lambda m: f"[{m.group(1)}, {m.group(2)}]",
        text,
    ) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", default=BUILD.graph_path, type=Path)
    ap.add_argument("--items", default=BUILD.items_path, type=Path)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args(argv)

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    bank = json.loads(args.items.read_text(encoding="utf-8"))
    before = sum(1 for i in bank["items"] if i.get("answer_spans"))

    bank, reasons, served = annotate(graph, bank)
    items = bank["items"]
    with_spans = [i for i in items if i["answer_spans"]]

    by_type: dict = {}
    for item in with_spans:
        by_type[item["type"]] = by_type.get(item["type"], 0) + 1

    by_reason: dict = {}
    for reason in reasons.values():
        by_reason[reason] = by_reason.get(reason, 0) + 1

    print(f"corpus: {args.items.name} over {BUILD.chunks_path.name}")
    print(f"spans populated: {len(with_spans)}/{len(items)} items "
          f"(was {before}) - {by_type}")
    print(f"empty: {len(reasons)} - {by_reason}")

    masked = [
        sum(b - a for a, b in i["answer_spans"]) for i in with_spans
    ]
    if masked:
        masked.sort()
        print(f"characters masked per item: median {masked[len(masked) // 2]}, "
              f"max {masked[-1]}")

    if args.check:
        print("--check: nothing written")
        return 0

    # newline="\n" so a Windows run does not rewrite every line ending and bury
    # the annotation in CRLF churn (.gitattributes normalises, this avoids the
    # round trip entirely).
    with args.items.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(bank))
    print(f"wrote {args.items}")
    print("now run: python -m build.validate")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
