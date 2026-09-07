"""Candidate prerequisite edges from chunks + concepts (CLAUDE.md §4).

    python -m build.extract_edges            # mock LLM, no key needed
    BUILD_LLM=real python -m build.extract_edges

Emits CANDIDATES for the human correction pass. Nothing here writes graph.json:
§4 puts a human between this and the frozen graph, and §1.2 makes the graph
frozen data. The output is a worklist, not a result.

# The pairwise filter is the whole point of this file

§4:

    edge CANDIDATES only where A precedes B in text AND co-occur within 2 sections

Fifty nodes is 1,225 unordered pairs — 2,450 if you ask about both directions,
which a naive implementation does. At one LLM call per pair that is a slow,
expensive way to be told "no" two thousand times. The ordering prior plus the
co-occurrence window cuts it to roughly 150 calls, and both halves are doing
real work:

- **Precedence.** A prerequisite relation is directional and textbooks are
  written in dependency order. If B is explained before A ever appears, B is not
  a prerequisite of A. This alone halves the space and removes the direction the
  model would most often get backwards.
- **Co-occurrence within N sections.** Concepts that never appear near each
  other are not in a prerequisite relation in this chapter, whatever their
  relation in the field. Slow start and Jain's fairness index are both real and
  both here; one is not a prerequisite of the other.

Both are recall/cost trades and they will miss true edges — a genuine
prerequisite explained fifteen sections apart is invisible to this. That is
acceptable because a human pass follows, and because §9.3 reports extraction
quality BEFORE correction: a filter that improves precision at some cost in
recall is exactly what makes that number honest rather than flattering.

# What the LLM does, and what it does not

It classifies a surviving candidate as prereq | related | none. It does not
propose edges, does not see the whole graph, and cannot introduce a cycle -
because it is only ever answering about one ordered pair. Cycle rejection
belongs to build/validate.py, which sees the whole graph.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from build.config import BUILD
from build.llm import MockLLM, get_llm


@dataclass(frozen=True)
class Candidate:
    from_id: str
    to_id: str
    first_section: str
    second_section: str
    distance: int


def _section_index(chunks: list[dict]) -> dict[str, int]:
    """Reading order. Position in the file, not the section number, so a chapter
    whose numbering is not lexicographically ordered still works."""
    return {c["section"]: i for i, c in enumerate(chunks)}


def first_appearance(concepts: list[dict], chunks: list[dict]) -> dict[str, int]:
    """Reading position where each concept's label first occurs.

    Concepts never mentioned in the text get no position and are skipped
    entirely rather than defaulted to 0 — a default would make an unmentioned
    concept look like a prerequisite of everything.
    """
    order = _section_index(chunks)
    out: dict[str, int] = {}
    for c in concepts:
        needle = c["label"].lower()
        for chunk in chunks:
            if needle in chunk["text"].lower() or needle in chunk.get("heading_path", "").lower():
                out[c["id"]] = order[chunk["section"]]
                break
    return out


def candidates(concepts: list[dict], chunks: list[dict], window: int) -> list[Candidate]:
    """Ordered pairs surviving both filters, nearest first.

    Nearest first because if the budget runs out, the pairs most likely to be
    real edges have already been asked about.
    """
    pos = first_appearance(concepts, chunks)
    sections = {i: c["section"] for i, c in enumerate(chunks)}

    out: list[Candidate] = []
    for a in concepts:
        for b in concepts:
            if a["id"] == b["id"]:
                continue
            pa, pb = pos.get(a["id"]), pos.get(b["id"])
            if pa is None or pb is None:
                continue
            if pa >= pb:            # A must PRECEDE B to be its prerequisite
                continue
            distance = pb - pa
            if distance > window:   # and they must appear near each other
                continue
            out.append(Candidate(
                from_id=a["id"], to_id=b["id"],
                first_section=sections.get(pa, ""), second_section=sections.get(pb, ""),
                distance=distance,
            ))
    return sorted(out, key=lambda c: (c.distance, c.from_id, c.to_id))


def _mock_classify(payload: dict) -> dict:
    """Adjacent concepts are prereq, further ones related. Structurally valid,
    pedagogically meaningless — the mock exercises the pipeline, not the
    judgement, and pretending otherwise is how a broken pass looks healthy."""
    return {"relation": "prereq" if payload["distance"] <= 1 else "related"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chunks", type=Path, default=BUILD.chunks_path)
    ap.add_argument("--concepts", type=Path, default=None,
                    help="concepts json; defaults to the nodes of graph.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--window", type=int, default=BUILD.cooccurrence_window_sections)
    args = ap.parse_args(argv)

    if not args.chunks.exists():
        raise SystemExit(
            f"no chunks at {args.chunks}. Run build.chunk first. There is no "
            f"chapter file in the repo yet — the graph was hand-authored "
            f"(data/SOURCE.md), so this pass has nothing to read."
        )

    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))["chunks"]
    source = args.concepts or BUILD.graph_path
    concepts = json.loads(source.read_text(encoding="utf-8"))["nodes"]

    pairs = candidates(concepts, chunks, args.window)
    total_ordered = len(concepts) * (len(concepts) - 1)
    print(f"{len(concepts)} concepts, {len(chunks)} chunks")
    print(f"{total_ordered} ordered pairs -> {len(pairs)} candidates "
          f"({len(pairs) * 100 // max(total_ordered, 1)}% survive the filter)")

    llm = get_llm()
    if isinstance(llm, MockLLM):
        llm.register("classify_edge", _mock_classify)

    classified = []
    for c in pairs:
        out = llm.run("classify_edge", {
            "from": c.from_id, "to": c.to_id, "distance": c.distance,
        })
        if out["relation"] != "none":
            classified.append({"from": c.from_id, "to": c.to_id,
                               "type": out["relation"], "distance": c.distance})

    out_path = args.out or (BUILD.graph_path.parent / "candidate_edges.json")
    out_path.write_text(
        json.dumps({
            "note": (
                "CANDIDATES for the §4 human correction pass. Not a graph. "
                "Nothing here is committed to data/graph.json without review, "
                "and validate.py must pass afterwards (DAG, orphans, granularity)."
            ),
            "generator": "mock" if isinstance(llm, MockLLM) else "real",
            "window_sections": args.window,
            "edges": classified,
        }, indent=2) + chr(10),
        encoding="utf-8",
    )
    print(f"{len(classified)} classified -> {out_path}")
    print("HUMAN CORRECTION PASS IS NEXT. §4 is explicit that this is the actual "
          "work and must not be deferred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
