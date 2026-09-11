"""§9.3 — automated extraction against the hand annotation.

    python -m eval.graph_quality
    python -m eval.graph_quality --windows 1,2,3,4 --json eval/results/graph_quality.json

§9.3 asks for precision/recall of automated extraction against
`data/gold_graph.json`, reported **before** the human correction pass, on the
grounds that "reporting 0.6 and stating that you corrected it by hand is more
credible than implying it was automatic".

# What this can and cannot report without a key

The pipeline has two stages and only one of them needs a model:

    chunks + concepts  --(precedence + co-occurrence)-->  CANDIDATES  deterministic
    candidates         --(LLM: prereq | related | none)->  EDGES       needs a key

So the classifier's precision cannot be measured under `BUILD_LLM=mock` — the
mock calls everything within one section `prereq`, which is a property of the
fixture and not of any model. Reporting a number from it would be exactly the
failure this project has now hit twice: a well-formed figure computed over
nothing (docs/writeup/numbers-that-looked-fine.md).

What IS measurable, deterministically and today, is the **recall ceiling**: the
fraction of true prerequisite edges that survive the filter to be asked about at
all. No classifier can beat it, whatever the model. It is an upper bound on
§9.3's recall, and it belongs beside the number rather than being discovered
after the fact.

That turns §9.3 from "cut without a key" into "half of it reports now, and the
half that reports is the half that bounds the other".

# The window is a curve, not a constant

`cooccurrence_window_sections` trades recall against the number of LLM calls.
Reporting one point on that trade hides the shape, and the shape is what tells a
human whether the constant is well chosen. The sweep is the output.

# gold_graph.json is byte-identical to graph.json, and that is not circular here

It was frozen BEFORE any extractor existed (data/SOURCE.md), so scoring the
filter against it is a real test of the filter. It would be circular only if the
graph had been derived from the extractor, which is the ordering §4's fallback
explicitly avoided.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build import extract_edges
from build.config import BUILD
from eval import provenance


def load_inputs():
    """Chunks from the real chapter, concepts from the frozen graph.

    Concepts come from graph.json rather than from extract_concepts, on purpose:
    §9.3 scores the EDGE filter, and feeding it extracted concepts would fold
    concept-extraction error into an edge number and make neither readable.
    """
    chunks_path = Path(BUILD.chunks_path)
    if not chunks_path.exists():
        raise SystemExit(
            f"no corpus at {chunks_path}. Run `python -m build.fetch_chapter && "
            f"python -m build.chunk --html` first; §9.3 measures the filter "
            f"against the real chapter, and there is nothing to measure without it."
        )
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))["chunks"]
    graph = json.loads(Path(BUILD.graph_path).read_text(encoding="utf-8"))
    concepts = [{"id": n["id"], "label": n["label"]} for n in graph["nodes"]]
    gold = json.loads(Path(BUILD.gold_graph_path).read_text(encoding="utf-8"))
    truth = {(e["from"], e["to"]) for e in gold["edges"] if e.get("type") == "prereq"}
    return concepts, chunks, truth


#: Why a true edge never became a candidate. The split matters more than the
#: ceiling does: WINDOW misses are bought back by widening the window, ORDER
#: misses are not recoverable at any window and cap the filter outright.
MISS_ORDER = "wrong order: the prerequisite appears LATER in the text"
MISS_WINDOW = "too far apart for the window"
MISS_UNLOCATED = "concept never located in the chapter text"


def miss_reasons(concepts, chunks, truth, window: int) -> dict:
    """Diagnose every true edge the filter did not offer to the classifier.

    A bare ceiling says the filter loses half the edges. It does not say whether
    that is a knob or a wall, and those need different responses.
    """
    pos = extract_edges.first_appearance(concepts, chunks)
    counts = {MISS_ORDER: [], MISS_WINDOW: [], MISS_UNLOCATED: []}
    for a, b in sorted(truth):
        pa, pb = pos.get(a), pos.get(b)
        if pa is None or pb is None:
            counts[MISS_UNLOCATED].append(f"{a}->{b}")
        elif pa >= pb:
            counts[MISS_ORDER].append(f"{a}->{b}")
        elif pb[0] - pa[0] > window:
            counts[MISS_WINDOW].append(f"{a}->{b}")
    return counts


def ceiling_at(concepts, chunks, truth, window: int) -> dict:
    """Recall ceiling and candidate precision at one window."""
    pairs = extract_edges.candidates(concepts, chunks, window)
    generated = {(c.from_id, c.to_id) for c in pairs}
    kept = generated & truth
    misses = miss_reasons(concepts, chunks, truth, window)

    n_concepts = len(concepts)
    space = n_concepts * (n_concepts - 1)  # ordered pairs

    return {
        "window_sections": window,
        "candidates": len(pairs),
        "pair_space": space,
        "kept_fraction_of_space": round(len(pairs) / space, 4) if space else None,
        "true_edges": len(truth),
        "true_edges_surviving": len(kept),
        # THE CEILING. No classifier can exceed this, so it bounds §9.3's recall.
        "recall_ceiling": round(len(kept) / len(truth), 4) if truth else None,
        # If the classifier were perfect, this is the precision it would reach.
        "candidate_precision": round(len(kept) / len(pairs), 4) if pairs else None,
        "llm_calls": len(pairs),
        "missed": sorted(f"{a}->{b}" for a, b in (truth - generated)),
        "miss_reasons": {k: len(v) for k, v in misses.items()},
        "miss_examples": {k: v[:5] for k, v in misses.items() if v},
        # The ceiling a window of infinity would reach. Everything above this is
        # unreachable by tuning cooccurrence_window_sections.
        "order_capped_ceiling": round(
            (len(truth) - len(misses[MISS_ORDER]) - len(misses[MISS_UNLOCATED])) / len(truth), 4
        ) if truth else None,
    }


def run(windows) -> dict:
    concepts, chunks, truth = load_inputs()
    rows = [ceiling_at(concepts, chunks, truth, w) for w in windows]
    shipped = BUILD.cooccurrence_window_sections

    return {
        "measures": "candidate-generation ceiling only",
        "classifier_measured": False,
        "why": (
            "The prereq|related|none classifier needs a model. Under BUILD_LLM=mock "
            "it calls everything within one section prereq, which is a property of "
            "the fixture. A precision figure from that would be a well-formed number "
            "over nothing."
        ),
        "shipped_window": shipped,
        "windows": rows,
        "provenance": provenance.over(
            population=sorted(f"{a}->{b}" for a, b in truth),
            sampled=sorted(f"{a}->{b}" for a, b in truth),
            observations=sum(r["candidates"] for r in rows),
            unit="gold prereq edges",
        ).as_dict(),
    }


def render(result: dict) -> str:
    L = []
    L.append("CLAUDE.md 9.3 - EXTRACTION AGAINST THE HAND ANNOTATION")
    L.append("=" * 74)
    L.append("")
    L.append("  CANDIDATE GENERATION ONLY. The classifier is not measured: it needs")
    L.append("  a model, and the mock's answer is a property of the fixture.")
    L.append("")
    L.append("  The recall ceiling BOUNDS any extraction run. A classifier that is")
    L.append("  never shown an edge cannot recover it, however good the model is.")
    L.append("")
    L.append(f"  {'window':>7}  {'candidates':>11}  {'of space':>9}  {'ceiling':>8}  {'precision':>10}")
    for r in result["windows"]:
        mark = "  <- shipped" if r["window_sections"] == result["shipped_window"] else ""
        L.append(
            f"  {r['window_sections']:>7}  {r['candidates']:>11}  "
            f"{r['kept_fraction_of_space']:>8.1%}  {r['recall_ceiling']:>7.1%}  "
            f"{r['candidate_precision']:>9.1%}{mark}"
        )
    L.append("")
    shipped = next(r for r in result["windows"]
                   if r["window_sections"] == result["shipped_window"])
    L.append(f"  At the shipped window: {shipped['true_edges_surviving']} of "
             f"{shipped['true_edges']} true prerequisite edges survive to be asked")
    L.append(f"  about, in {shipped['llm_calls']} LLM calls against a pair space of "
             f"{shipped['pair_space']}.")
    L.append("")
    L.append("  WHY THE OTHER EDGES NEVER REACH THE CLASSIFIER")
    L.append("  A window miss is a knob. An ORDER miss is a wall: the chapter names")
    L.append("  the dependent concept before its prerequisite, usually because a")
    L.append("  section heading announces the topic and the body introduces the")
    L.append("  parts afterwards. No window recovers those.")
    L.append("")
    for reason, n in sorted(shipped["miss_reasons"].items(), key=lambda kv: -kv[1]):
        if not n:
            continue
        L.append(f"    {n:>3}  {reason}")
        for ex in shipped["miss_examples"].get(reason, [])[:3]:
            L.append(f"         {ex}")
    L.append("")
    L.append(f"  Ceiling at an INFINITE window: {shipped['order_capped_ceiling']:.1%}. "
             f"That is the wall.")
    L.append("")
    # Interpolated from the measured ceiling, never a literal. The first
    # version of this line hardcoded 0.59, which was the shipped ceiling when it
    # was written; the chunker moved and the sentence went on asserting a figure
    # this eval no longer produces, in the output of the eval that produces it.
    ceiling = shipped["recall_ceiling"]
    example = round(ceiling * 0.9, 2)
    L.append("  REPORT THE CEILING BESIDE ANY RECALL FIGURE, not after it. An")
    L.append(f"  extraction recall of {example} against a ceiling of {ceiling:.2f} is a")
    L.append("  good classifier; against a ceiling of 1.0 it is a poor one, and the")
    L.append("  two are indistinguishable without this number.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CLAUDE.md 9.3")
    ap.add_argument("--windows", type=str, default="1,2,3,4",
                    help="co-occurrence windows to sweep, comma separated")
    ap.add_argument("--json", type=str, default=None, help="also write raw results here")
    args = ap.parse_args(argv)

    windows = [int(w) for w in args.windows.split(",") if w.strip()]
    result = run(windows)
    print(render(result))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"\nraw results -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
