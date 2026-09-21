"""Can Call 1 tell two students apart when the difference is unambiguous?

    python -m eval.diagnostic_calibration                     # all cases
    python -m eval.diagnostic_calibration --model openai/gpt-oss-120b
    python -m eval.diagnostic_calibration --json out.json

WHY THIS EXISTS, AND WHY IT IS NOT §9.5

§9.5 ran whole dialogues and tabulated `student_state` against the *policy* that
generated the student. It found no correlation. But a policy label is a soft
ground truth: "this student knows the region" does not tell you what the single
right diagnosis of turn 3 was, so a defender can always say the model saw
something the tabulation did not.

This removes that defence. Each case is a **constructed history** where one
answer is forced by the content of the clicks themselves:

    a student whose three clicks are scattered across unrelated regions of the
    graph is guessing, and a student whose three clicks are all direct
    prerequisites of the answer is confused about the prerequisite

Those are different students. A diagnostic that cannot separate them is not
miscalibrated, it is not reading the history at all.

COST, AND WHY IT IS SHAPED THIS WAY

One Call 1 per case and no Call 2 - roughly 2,900 tokens each, against a 200,000
token-per-day-per-model budget. A §9.5 dialogue run costs ~170,000 and mostly
re-measures turns that agree with each other. Ten constructed cases cost ~29,000
and every one of them is a case the model can fail distinctly.

ADMISSIBLE SETS, NOT SINGLE ANSWERS

Each case lists every state a reasonable tutor could give. They are deliberately
generous: `stuck` is admissible almost everywhere, because a student who is
failing IS stuck and saying so is never *wrong*. What the cases test is whether
the model ever reaches for the SPECIFIC state the evidence supports. A model that
answers `stuck` to all ten scores 10/10 on admissibility and 0/10 on
discrimination, and both numbers are reported, because the second is the one that
matters.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from server import llm
from server import origin
from server.config import CONFIG
from server.graph_store import GraphStore
from eval import provenance


@dataclass
class Case:
    """A history whose correct diagnosis is forced by its content."""

    name: str
    why: str
    #: states a reasonable tutor could give
    admissible: tuple
    #: the state the evidence specifically supports - the discrimination test
    specific: Optional[str]
    turns_on_item: int = 3
    hint_level: int = 1
    mastery: float = 0.30


def _history(store: GraphStore, item, kind: str) -> list:
    """Build the clicked-node history for a case.

    The text is what a client would have recorded: the tutor's question and the
    student's clicks, in order.
    """
    answer = item.answer
    prereqs = list(store.prereqs(item.node_id))

    # THE PREREQUISITE REGION, computed once. `scattered` picks from its
    # COMPLEMENT, because the two cases only mean anything if their node sets are
    # disjoint - the first draft let "Packet Flow" appear in both, which would
    # have produced a confident "the model cannot discriminate" from two
    # histories that were not actually different.
    # TWO DIFFERENT SETS, and conflating them was a real bug.
    #
    # `upstream` is what the PREREQ case draws from: the node's prerequisites,
    # their prerequisites, and their other dependents (its siblings). All of it
    # is genuinely before-or-beside the answer, which is what "confused about the
    # prerequisite" has to mean. Including the node's own DEPENDENTS here - which
    # the first version did - put downstream concepts in a history claiming
    # upstream confusion.
    upstream = set(prereqs)
    for pr in prereqs:
        upstream |= set(store.prereqs(pr)) | set(store.dependents(pr))
    upstream -= {item.node_id, answer}

    # `related` is the exclusion zone for the SCATTERED case, and is deliberately
    # wider: anything with a graph relationship to the answer, downstream too.
    related = upstream | {item.node_id, answer} | set(store.dependents(item.node_id))

    ordered_region = [n for n in store.node_ids if n in upstream]
    far = [n for n in store.node_ids if n not in related]

    if kind == "scattered":
        picks = far[:3]
    elif kind == "prereqs":
        picks = ordered_region[:3] or far[:3]
    elif kind == "correct":
        picks = [answer]
    elif kind == "none":
        return []
    elif kind == "text_only":
        # NO CLICKS. The student types on-topic prose and is wrong each time.
        #
        # This is the case where `stuck` is the residual rather than the cheap
        # answer, and it is built by REMOVING evidence rather than by adding a
        # different pattern. `confused_prereq` needs clicks clustered upstream;
        # `guessing` needs clicks scattered across unrelated regions. Neither
        # has anything to read here, because there is no spatial evidence at
        # all - and the prompt defines `stuck` as exactly that residual: "no
        # pattern you can name".
        #
        # Free text is never scored (§1.4). It is still dialogue the tutor sees,
        # and a student who types instead of clicking is not hypothetical.
        said = [
            "is it something about how the sender decides how fast to go?",
            "i think it's the part where the router tells you it's full",
            "something to do with the window getting smaller?",
        ]
        out = []
        for text in said:
            out.append({"role": "tutor", "text": item.prompt})
            out.append({"role": "student", "text": text})
        return out
    else:
        raise ValueError(kind)

    out = []
    for p in picks:
        out.append({"role": "tutor", "text": item.prompt})
        out.append({"role": "student", "text": f"[clicked {store.label(p)}]"})
    return out


CASES = (
    Case(
        name="scattered_clicks",
        why="three clicks on unrelated regions of the graph - no pattern to find",
        admissible=("guessing", "stuck"),
        specific="guessing",
    ),
    Case(
        name="all_clicks_are_prereqs",
        why="every click is a direct prerequisite of the answer",
        admissible=("confused_prereq", "stuck"),
        specific="confused_prereq",
    ),
    Case(
        name="answered_correctly",
        why="the student clicked the answer",
        admissible=("correct",),
        specific="correct",
        # ONE CLICK, SO ONE TURN. This case inherited the default 3 and told the
        # model "three turns on item" while showing it a single click. The model
        # answered `stuck` and wrote "three turns in with no clear right answer",
        # which was a reasonable reading of a context we had made incoherent. The
        # row was scored as a model failure until the case was re-read.
        turns_on_item=1,
    ),
    Case(
        name="no_pattern_to_name",
        why=("three wrong free-text answers and no clicks at all - there is no "
             "spatial pattern to read, which is what `stuck` is FOR"),
        # Generous, per this module's convention. `guessing` is defensible on a
        # student who is wrong three times; what is being tested is whether the
        # model can still REACH for `stuck` when it is the honest residual.
        admissible=("stuck", "guessing"),
        specific="stuck",
        turns_on_item=3,
        hint_level=3,
    ),
    Case(
        name="opening_turn",
        why="no response exists yet; there is nothing to diagnose",
        admissible=("on_track",),
        specific="on_track",
        turns_on_item=0,
        hint_level=0,
    ),
)

#: Items chosen so `prereqs` is non-empty - the prereq case is meaningless on a
#: root node, and picking blind would silently degrade it into the scattered one.
def _items_with_prereqs(store: GraphStore, n: int) -> list:
    out = []
    for nid in store.node_ids:
        if not store.prereqs(nid):
            continue
        items = [i for i in store.items_for(nid) if i.type == "node_click"]
        if items:
            out.append(items[0])
        if len(out) >= n:
            break
    return out


@dataclass
class Result:
    case: str = ""
    #: WHICH PROMPT PRODUCED THIS. The day-12 read-through and the day-18 one
    #: differ by model, by the history fix AND by this, so a result that cannot
    #: name its prompt cannot attribute anything.
    prompt: str = ""
    item_id: str = ""
    said: str = ""
    action: str = ""
    #: The boolean §7 computes mastery from. `student_state` is a label nothing
    #: reads; THIS is the one that would corrupt the adaptive path, so a probe
    #: that records the label and not the boolean measures the wrong field.
    correct: Optional[bool] = None
    admissible: bool = False
    specific_hit: bool = False
    diagnosis: str = ""
    error: str = ""


#: Committed so the A/B is reproducible. `prompts/` is the LIVE prompt and is
#: config (§13.1); these are historical artefacts kept as eval fixtures, the
#: same way data/ holds frozen inputs. Extracted with
#: `git show 516795d^:prompts/call1_system.md`.
PROMPT_VERSIONS = {
    "current": None,
    "pre-falsifiability": "call1_system.pre-falsifiability.md",
}


def _prompt_dir() -> Path:
    return Path(__file__).resolve().parent / "prompt_versions"


@contextlib.contextmanager
def use_prompt(version: str):
    """Run the block with `prompts/call1_system.md` swapped for `version`.

    Copies the whole prompts directory rather than editing it in place: a run
    that dies mid-way must not leave the demo serving a three-week-old tutor
    contract. `llm.prompt` is lru_cached, so the cache is cleared on the way in
    AND on the way out - forgetting the second is how the next block silently
    keeps the previous version.
    """
    name = PROMPT_VERSIONS[version]
    if name is None:
        yield version
        return

    source = _prompt_dir() / name
    if not source.exists():
        raise FileNotFoundError(f"no committed prompt fixture at {source}")

    original = CONFIG.prompts_dir
    with tempfile.TemporaryDirectory() as td:
        staged = Path(td)
        for f in original.iterdir():
            if f.is_file():
                shutil.copy2(f, staged / f.name)
        shutil.copy2(source, staged / "call1_system.md")
        object.__setattr__(CONFIG, "prompts_dir", staged)
        llm.prompt.cache_clear()
        try:
            yield version
        finally:
            object.__setattr__(CONFIG, "prompts_dir", original)
            llm.prompt.cache_clear()


def run(model: Optional[str], repeats: int, pace_s: float,
        prompts: tuple = ("current",)) -> list:
    store = GraphStore.load()
    digest = llm.graph_digest(store)
    items = _items_with_prereqs(store, repeats)
    if model:
        object.__setattr__(CONFIG, "call1", type(CONFIG.call1)(
            model=model, max_tokens=CONFIG.call1.max_tokens,
            effort=CONFIG.call1.effort, timeout_s=90.0))

    kinds = {"scattered_clicks": "scattered", "all_clicks_are_prereqs": "prereqs",
             "answered_correctly": "correct", "opening_turn": "none",
             "no_pattern_to_name": "text_only"}
    results = []
    last = 0.0
    with origin.declare("eval:diagnostic_calibration"):
      for version in prompts:
        with use_prompt(version):
          for case in CASES:
            for item in items:
                if pace_s:
                    wait = pace_s - (time.monotonic() - last)
                    if wait > 0:
                        time.sleep(wait)
                last = time.monotonic()

                r = Result(case=case.name, item_id=item.id, prompt=version)
                try:
                    d = llm.call1(
                        item_prompt=item.prompt, answer=item.answer,
                        item_type=item.type,
                        node_label=store.label(item.node_id),
                        graph_digest=digest,
                        history=_history(store, item, kinds[case.name]),
                        hint_level=case.hint_level,
                        turns_on_item=case.turns_on_item,
                        mastery_note=f"{case.mastery:.2f} mastery on this node",
                    )
                    r.said = d.student_state
                    r.action = d.requested_action
                    r.correct = d.correct
                    r.diagnosis = d.diagnosis
                    r.admissible = d.student_state in case.admissible
                    r.specific_hit = d.student_state == case.specific
                except Exception as exc:  # noqa: BLE001 - reported, not raised
                    r.error = f"{type(exc).__name__}: {str(exc)[:160]}"
                results.append(r)
                print(f"  [{version:18}] {case.name:22} {item.id} -> "
                      f"{r.said or r.error[:40]}",
                      file=sys.stderr, flush=True)
    return results


def score(results: list) -> dict:
    """One block per prompt version, plus the A/B comparison between them.

    Reported PER PROMPT rather than pooled, because pooling is what made the
    day-12/day-18 reversal unattributable in the first place: three variables
    moved at once and the result had one number.
    """
    versions = []
    for r in results:
        if r.prompt not in versions:
            versions.append(r.prompt)

    by_prompt = {v: _score_one([r for r in results if r.prompt == v])
                 for v in versions}

    out = {
        "call1_model": CONFIG.call1.model,
        "provider": CONFIG.llm_provider,
        "prompts": versions,
        "by_prompt": by_prompt,
    }

    # The A/B, stated only where both arms actually produced data. Two empty
    # arms compare equal, and this module has already shipped that bug once.
    if len(versions) == 2:
        a, b = versions
        pa, pb = by_prompt[a], by_prompt[b]
        measurable = pa["measured"] and pb["measured"]
        out["ab"] = {
            "arms": [a, b],
            "measurable": measurable,
            "specific_hits": None if not measurable else {
                a: pa["specific_hits_total"], b: pb["specific_hits_total"]},
            "of": None if not measurable else pa["scored_total"],
            "discriminates": None if not measurable else {
                a: pa["separates_guessing_from_prereq_confusion"],
                b: pb["separates_guessing_from_prereq_confusion"]},
            "stuck_when_stuck_is_right": None if not measurable else {
                a: pa["cases"].get("no_pattern_to_name", {}).get("specific_hits"),
                b: pb["cases"].get("no_pattern_to_name", {}).get("specific_hits")},
        }
    return out


def _score_one(results: list) -> dict:
    done = [r for r in results if not r.error]
    by_case: dict = {}
    for case in CASES:
        rs = [r for r in done if r.case == case.name]
        by_case[case.name] = {
            "why": case.why,
            "specific": case.specific,
            "n": len(rs),
            "admissible": sum(1 for r in rs if r.admissible),
            "specific_hits": sum(1 for r in rs if r.specific_hit),
            "said": {s: sum(1 for r in rs if r.said == s) for s in sorted({r.said for r in rs})},
        }

    #: THE NUMBER THAT MATTERS. Can the model separate the two cases that are
    #: unambiguously different students? A model answering `stuck` everywhere
    #: scores full marks on admissibility and zero here.
    #:
    #: THREE-VALUED ON PURPOSE. True / False / None, where None means "not
    #: measured". A two-valued version reported `False` - rendered as "the
    #: diagnosis is not reading the history" - from a run where every call had
    #: failed on an exhausted token budget, because two empty distributions
    #: compare equal. That is this project's own recurring failure (see
    #: docs/writeup/numbers-that-looked-fine.md) reproduced inside the instrument
    #: built to catch it, and it is exactly the shape that survives into a slide.
    scattered = by_case.get("scattered_clicks", {}).get("said", {})
    prereqs = by_case.get("all_clicks_are_prereqs", {}).get("said", {})
    if not scattered or not prereqs:
        discriminates = None
    else:
        discriminates = scattered != prereqs

    #: The boolean, scored against what the constructed history actually shows.
    #: Only `answered_correctly` has a true answer; every other case is a wrong
    #: or absent click.
    truth = {"answered_correctly": True, "scattered_clicks": False,
             "all_clicks_are_prereqs": False}
    graded = [r for r in done if r.case in truth]
    correct_agreement = {
        "agree": sum(1 for r in graded if r.correct is truth[r.case]),
        "of": len(graded),
    }

    return {
        "measured": bool(done),
        "n": len(done),
        "correct_boolean": correct_agreement,
        "cases": by_case,
        "specific_hits_total": sum(1 for r in done if r.specific_hit),
        "scored_total": len(done),
        "errors": [asdict(r) for r in results if r.error],
        "separates_guessing_from_prereq_confusion": discriminates,
        "provenance": provenance.over(
            population=[r.item_id for r in results],
            sampled=[r.item_id for r in done],
            observations=len(done), unit="cases", expect_full=False,
        ).as_dict(),
    }


def render(result: dict) -> str:
    L = [f"Call 1 diagnostic calibration - {result['call1_model']} "
         f"via {result['provider']}",
         f"prompts under test: {', '.join(result['prompts'])}",
         ""]

    for version in result["prompts"]:
        block = result["by_prompt"][version]
        L.append(f"--- prompt: {version} " + "-" * max(0, 52 - len(version)))
        L.append("")
        L.append(f"{'case':26}{'n':>3}{'admissible':>12}{'specific':>10}"
                 f"   what it said")
        for name, c in block["cases"].items():
            L.append(f"{name:26}{c['n']:>3}{c['admissible']:>12}"
                     f"{c['specific_hits']:>10}   {c['said']}")
        L.append("")
        cb = block["correct_boolean"]
        if cb["of"]:
            L.append(f"  `correct` boolean (the field §7 actually scores): "
                     f"{cb['agree']}/{cb['of']}")
        verdict = block["separates_guessing_from_prereq_confusion"]
        if verdict is None:
            L.append("  NOT MEASURED - one or both contrasting cases returned "
                     "nothing.")
            L.append("  This is not a finding about the model. A verdict needs "
                     "both distributions;")
            L.append("  with either empty there is nothing to compare.")
        elif verdict:
            L.append("  SEPARATES a scattered guesser from a prerequisite "
                     "confusion.")
        else:
            L.append("  DOES NOT SEPARATE a scattered guesser from a "
                     "prerequisite confusion:")
            L.append("  two unambiguously different students, one distribution.")
        if block["errors"]:
            L.append(f"  {len(block['errors'])} call(s) failed: "
                     f"{block['errors'][0]['error']}")
        L.append("")

    L.append("  admissible = any defensible state (`stuck` is admissible almost "
             "everywhere)")
    L.append("  specific   = the state the evidence actually supports")
    L.append("")

    ab = result.get("ab")
    if ab:
        a, b = ab["arms"]
        L.append("A/B (same model, same fixed harness, prompt is the only "
                 "variable)")
        if not ab["measurable"]:
            L.append("  NOT MEASURABLE - an arm produced no scored cases. Two "
                     "empty arms")
            L.append("  compare equal, and this module has shipped that bug "
                     "once already.")
        else:
            L.append(f"  specific diagnoses: {a} {ab['specific_hits'][a]}"
                     f"/{ab['of']}   vs   {b} {ab['specific_hits'][b]}"
                     f"/{ab['of']}")
            L.append(f"  separates the two students: {a} "
                     f"{ab['discriminates'][a]}   vs   {b} "
                     f"{ab['discriminates'][b]}")
            sw = ab["stuck_when_stuck_is_right"]
            L.append(f"  says `stuck` when `stuck` IS right: {a} {sw[a]}"
                     f"   vs   {b} {sw[b]}")
            L.append("")
            L.append("  The last row is the counter-test. The current prompt "
                     "tells the model to")
            L.append("  be suspicious of `stuck`; a prompt that made it unable "
                     "to say `stuck` when")
            L.append("  `stuck` is the honest answer would score well above and "
                     "still be worse.")
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None, help="override CALL1_MODEL")
    parser.add_argument("--repeats", type=int, default=2,
                        help="items per case; each is one Call 1 (~2,900 tokens)")
    parser.add_argument("--pace-s", type=float, default=25.0)
    parser.add_argument("--prompts", default="current",
                        help="comma-separated prompt versions to sweep. "
                             f"Known: {','.join(PROMPT_VERSIONS)}. "
                             "Use 'current,pre-falsifiability' for the A/B.")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:  # pragma: no cover
            pass

    if CONFIG.mock_mode:
        print("MOCK_MODE is on. The mock picks student_state from a rule, so this "
              "would measure mock_tutor.py. Set MOCK_MODE=false.", file=sys.stderr)
        return 2

    versions = tuple(v.strip() for v in args.prompts.split(",") if v.strip())
    unknown = [v for v in versions if v not in PROMPT_VERSIONS]
    if unknown:
        print(f"unknown prompt version(s): {unknown}. "
              f"Known: {sorted(PROMPT_VERSIONS)}", file=sys.stderr)
        return 2

    results = run(args.model, args.repeats, args.pace_s, versions)
    result = score(results)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"result": result, "results": [asdict(r) for r in results]},
                      fh, indent=2)
    print(render(result))
    if args.json:
        print(f"\nraw -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
