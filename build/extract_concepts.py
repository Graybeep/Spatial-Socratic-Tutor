"""Candidate concepts from chunks (CLAUDE.md §4, pass 1).

    python -m build.extract_concepts            # mock LLM, no key needed
    BUILD_LLM=real python -m build.extract_concepts

Emits CANDIDATES for the human pass. Writes no graph — §1.2 makes graph.json
frozen data and §4 puts a human between this and it.

# Deliberately thin, on purpose

The advice this was written under: do not over-invest here before seeing real
extracted text. Every judgement this pass makes — what counts as one concept,
how to phrase a definition, which mentions are the same idea — depends on what
the chunker actually produces from a real chapter, and there is no chapter in
the repo yet.

So this is the shape of the pass and its plumbing: read chunks, ask per chunk,
canonicalise, write candidates. The prompt is one paragraph and will be wrong.
That is cheaper to discover than to predict.

# Canonicalisation is a stub, and says so

§4 merges candidates whose embeddings exceed `merge_cosine` (0.88), with a human
confirming each merge. Embeddings are a dependency we do not have (§1.8), so
what runs is exact-match-after-normalisation, which merges "Slow Start" with
"slow start" and nothing harder. Near-duplicates therefore survive to the human
pass rather than being merged silently — the conservative direction, and
visible: the report prints how many pairs are suspiciously similar by token
overlap so the reviewer knows where to look.

# The granularity rule is the one worth enforcing early

§3 rejects "TCP" sitting beside "the 0.5 multiplicative decrease factor". A
graph mixing those is not a graph you can narrow usefully — dimming to eight
candidates means nothing when one of them subsumes three others. Nothing here
can judge that, so build/validate.py enforces what is mechanically checkable and
the human pass does the rest.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build.config import BUILD
from build.llm import MockLLM, get_llm

_WORD = re.compile(r"[a-z0-9]+")


def normalise(label: str) -> str:
    return " ".join(_WORD.findall(label.lower()))


def slug(label: str) -> str:
    return "_".join(_WORD.findall(label.lower()))[:40]


def canonicalise(candidates: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Merge exact duplicates; FLAG near-duplicates instead of merging them.

    Returns (kept, suspicious_pairs). The flagging is token-overlap, not
    embedding cosine — see the module docstring. It exists so the human pass has
    a worklist rather than having to eyeball fifty labels for near-synonyms.
    """
    kept: dict[str, dict] = {}
    for c in candidates:
        key = normalise(c["label"])
        if key not in kept:
            kept[key] = c

    items = list(kept.items())
    suspicious: list[tuple[str, str]] = []
    for i, (ka, _) in enumerate(items):
        ta = set(ka.split())
        for kb, _ in items[i + 1:]:
            tb = set(kb.split())
            if not ta or not tb:
                continue
            # Over the SMALLER label, not the union. Jaccard scores
            # "congestion window" against "effective window" at 0.33 and misses
            # the shared-head-noun case that near-duplicates in this domain
            # almost always take. This errs towards flagging, which is the
            # right direction for a review worklist: a spurious pair costs the
            # reviewer a glance, a missed one costs a duplicate node in a
            # frozen graph.
            overlap = len(ta & tb) / min(len(ta), len(tb))
            if overlap >= 0.5:
                suspicious.append((ka, kb))

    return list(kept.values()), suspicious


def _mock_concepts(payload: dict) -> dict:
    """One concept per chunk, named after its heading.

    Structurally valid and pedagogically empty. A cleverer mock would be worse:
    it would make the pipeline look like it was extracting something.
    """
    heading = payload["heading_path"] or payload["section"]
    return {"concepts": [{
        "id": slug(heading),
        "label": heading,
        "definition": payload["text"][:160].strip(),
        "source_sections": [payload["section"]],
    }]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chunks", type=Path, default=BUILD.chunks_path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if not args.chunks.exists():
        raise SystemExit(
            f"no chunks at {args.chunks}. Run build.chunk first. There is no "
            f"chapter file in the repo yet — the graph was hand-authored "
            f"(data/SOURCE.md), so this pass has nothing to read."
        )

    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))["chunks"]

    llm = get_llm()
    if isinstance(llm, MockLLM):
        llm.register("extract_concepts", _mock_concepts)

    raw: list[dict] = []
    for chunk in chunks:
        out = llm.run("extract_concepts", chunk)
        raw.extend(out["concepts"])

    kept, suspicious = canonicalise(raw)

    print(f"{len(chunks)} chunks -> {len(raw)} candidates -> {len(kept)} after "
          f"exact-duplicate merge")
    if not (BUILD.min_nodes <= len(kept) <= BUILD.max_nodes):
        print(f"NOTE {len(kept)} concepts is outside §3's "
              f"{BUILD.min_nodes}-{BUILD.max_nodes} band; the human pass has to "
              f"split or merge to land inside it.")
    if suspicious:
        print(f"{len(suspicious)} near-duplicate pairs to review by hand "
              f"(no embeddings, so nothing was merged automatically):")
        for a, b in suspicious[:10]:
            print(f"  {a!r} ~ {b!r}")

    out_path = args.out or (BUILD.graph_path.parent / "candidate_concepts.json")
    out_path.write_text(
        json.dumps({
            "note": (
                "CANDIDATES for the §4 human pass. Not a graph. Definitions need "
                "rewriting to one sentence at uniform granularity (§3), and the "
                "count must land in the 40-60 band before freezing."
            ),
            "generator": "mock" if isinstance(llm, MockLLM) else "real",
            "concepts": kept,
            "review_near_duplicates": [list(p) for p in suspicious],
        }, indent=2) + chr(10),
        encoding="utf-8",
    )
    print(f"wrote {out_path}")
    print("HUMAN PASS IS NEXT, then build.extract_edges, then validate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
