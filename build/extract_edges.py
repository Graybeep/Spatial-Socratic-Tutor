"""Candidate prerequisite edges from chunks + concepts (CLAUDE.md §4).

    python -m build.extract_edges            # mock LLM, no key needed
    BUILD_LLM=real python -m build.extract_edges

Emits CANDIDATES for the human correction pass. Nothing here writes graph.json:
§4 puts a human between this and the frozen graph, and §1.2 makes the graph
frozen data. The output is a worklist, not a result.

# The pairwise filter is the whole point of this file

§4:

    edge CANDIDATES only where A precedes B in text AND co-occur within 2 sections

Fifty-two nodes is 2,652 ordered pairs. At one LLM call per pair that is a slow,
expensive way to be told "no" two thousand times. Measured against the real
chapter the filter keeps 381 — 14% of the space, in the same order as §4's
estimate — and both halves are doing real work:

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

MEASURED, against the hand-authored graph on the real chapter: the filter's
recall CEILING is 59% at window 2 (39 of 66 true prerequisite edges survive to
be asked about) and 63% at window 3. No extraction run can beat that ceiling,
whatever the model does, so it is an upper bound on §9.3's recall and belongs in
the writeup beside the number rather than being discovered afterwards.

It was 21% until the ordering was fixed. Comparing SECTIONS alone discarded
every same-section pair, and 34 of the 66 true edges connect concepts that a
textbook introduces in one section — more than half, thrown away before the
model was asked anything.

# What the LLM does, and what it does not

It classifies a surviving candidate as prereq | related | none. It does not
propose edges, does not see the whole graph, and cannot introduce a cycle -
because it is only ever answering about one ordered pair. Cycle rejection
belongs to build/validate.py, which sees the whole graph.
"""
from __future__ import annotations

import argparse
import json
import re
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


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def first_appearance(concepts: list[dict], chunks: list[dict]) -> dict[str, int]:
    """Reading position where each concept first occurs.

    Concepts that cannot be located get no position and are skipped entirely
    rather than defaulted to 0 — a default would make an unlocatable concept
    look like a prerequisite of everything.

    TWO STRATEGIES, and the order matters.

    `source_sections` first, when the concept carries one. That is where the
    concept was found, recorded by whatever produced it, and it is exact. In a
    real run extract_concepts writes it; here the hand-authored graph carries it.

    Raw label matching is the fallback and it is weak. Measured against the real
    chapter it located only 40 of 52 concepts, because an authored label is a
    tidy noun phrase and prose is not: the graph says "Packet Flow",
    "Window-Based Control", "Jain's Fairness Index"; the text says "flow",
    "window based", "fairness index". Those twelve misses capped the whole
    filter's recall ceiling at 21% — a limit on §9.3 that had nothing to do with
    the model and would have looked like poor extraction.

    So the fallback normalises to word tokens (dropping case, hyphens and
    possessives) and also tries the label's head words, which is what a section
    heading usually carries.
    """
    order = _section_index(chunks)
    normalised = [(c, _norm(c["text"]), _norm(c.get("heading_path", ""))) for c in chunks]
    by_section = {c["section"]: (t, h) for c, t, h in normalised}

    def needles_for(label: str) -> list[str]:
        # Longest first: "congestion window" before "window".
        out = [label]
        words = label.split()
        if len(words) > 1:
            out.append(" ".join(words[-2:]))
            out.append(words[-1])
        return out

    def offset_in(section: str, label: str) -> int:
        text, heading = by_section.get(section, ("", ""))
        for needle in needles_for(label):
            if needle and needle in heading:
                return 0
            idx = text.find(needle) if needle else -1
            if idx >= 0:
                return idx
        return 0

    out: dict[str, tuple] = {}
    for concept in concepts:
        label = _norm(concept["label"])

        section = next(
            (s for s in (concept.get("source_sections") or []) if s in order), None)
        if section is None:
            for needle in needles_for(label):
                hit = next(
                    (chunk for chunk, text, heading in normalised
                     if f" {needle} " in f" {text} " or f" {needle} " in f" {heading} "),
                    None,
                )
                if hit is not None:
                    section = hit["section"]
                    break
        if section is None:
            continue

        out[concept["id"]] = (order[section], offset_in(section, label))
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
            # (section, offset). Comparing SECTIONS alone discarded every
            # same-section pair, and measured against the hand-authored graph
            # that was 34 of 66 true edges - more than half, thrown away before
            # the model was asked anything. A textbook introduces several
            # related concepts in one section, in order, and that order is the
            # evidence; section granularity simply cannot see it.
            if pa >= pb:            # A must PRECEDE B to be its prerequisite
                continue
            distance = pb[0] - pa[0]
            if distance > window:   # and they must appear near each other
                continue
            out.append(Candidate(
                from_id=a["id"], to_id=b["id"],
                first_section=sections.get(pa[0], ""), second_section=sections.get(pb[0], ""),
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
