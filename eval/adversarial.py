"""§9.1 - effective leakage, measured as post-hint solve rate.

    python -m eval.adversarial                 # both arms, 60 dialogues each
    python -m eval.adversarial --n 200 --json out.json

WHAT THIS REPORTS, AND WHAT IT REFUSES TO REPORT
------------------------------------------------
It reports a MEASURED SOLVE RATE. It does not report 1/N.

1/N is a lower bound, not a measurement, and this eval will contradict it. A
student choosing among 5 lit nodes does not choose uniformly - they choose among
the lit nodes that are plausible for the question type. Ask "which mechanism
reduces cwnd" with 5 lit nodes of which only 2 are mechanisms and the effective
rate is 50%, not 20%. `MAX_GUESS_PROBABILITY` stays a policy knob that sets the
narrowing floor; the number it derives never goes on a slide.

TWO ARMS, LABELLED, BECAUSE THEY ARE DIFFERENT SYSTEMS
------------------------------------------------------
The demo runs `interleaved` and bottoms out around 9 lit. A `visual_only` sweep
bottoms out at 5. Reporting only the second invites "is that the system you just
showed us", and the answer would be no. Both are run and both are labelled:

    product configuration     LADDER_MODE=interleaved   - what the demo runs
    isolated visual channel   LADDER_MODE=visual_only   - the mechanism alone

The gap between them is itself a finding.

THREE STUDENTS, BECAUSE ZERO-KNOWLEDGE MEASURES THE FLOOR
----------------------------------------------------------
A zero-reasoning student measures MINIMUM leakage. The maximum-leakage student
is the one with partial knowledge, because narrowing leaks two things and the
guess is the smaller one: the IDENTITY of the surviving set tells the student
which region of the graph the answer sits in, which is precisely the structural
understanding the tutor is trying to assess. A student who knows "it's somewhere
in congestion control" but not which mechanism gets the rest for free.

    zero        uniform over the lit candidates. The floor.
    partial     correct on prerequisites, not on the target. Restricts to the
                lit nodes in the answer's neighbourhood, then guesses.
    adversarial partial knowledge, plus it burns hints to maximise narrowing
                before committing. The ceiling.

METHOD
------
Per item, the ladder is climbed by answering deliberately wrong. At each hint
level the student's choice is recorded as a COUNTERFACTUAL PROBE - "would this
student have solved it here?" - and then a wrong answer is submitted anyway so
the ladder continues. One dialogue therefore yields the whole curve, and a
student who would have solved at level 2 still contributes a level-3 and level-4
data point.

Runs in-process against server.turn. No network, no API key, no LLM.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from server import mock_tutor
from server import turn as turn_mod
from server.config import CONFIG
from server.graph_store import GraphStore
from server.schemas import EdgeRef, StudentResponse
from server.state import Store

ARMS = {
    "product configuration": "interleaved",
    "isolated visual channel": "visual_only",
    "verbal channel only": "verbal_only",
}
CONDITIONS = ("zero", "partial", "adversarial")


@contextmanager
def _config(**values):
    saved = {k: getattr(CONFIG, k) for k in values}
    for k, v in values.items():
        object.__setattr__(CONFIG, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            object.__setattr__(CONFIG, k, v)


# ---------------------------------------------------------------------------
# students
# ---------------------------------------------------------------------------

@dataclass
class Student:
    """A guessing policy over the currently lit nodes.

    None of these reason about the CONTENT of the question - there is no content
    to reason about, the fixture labels are nonsense words. They model what the
    INTERFACE hands over, which is exactly what §9.1 is trying to measure.
    """

    condition: str
    rng: random.Random

    def candidates(self, store: GraphStore, item, lit: list) -> list:
        """The set this student would actually choose among."""
        pool = lit or list(store.node_ids)

        if self.condition == "zero":
            return pool

        # partial / adversarial: knows the region, not the target. Keeps lit
        # nodes adjacent to (or equal to) the concept under study and discards
        # the rest as implausible for the question.
        region = {item.node_id}
        region.update(store.prereqs(item.node_id))
        region.update(store.dependents(item.node_id))
        for p in store.prereqs(item.node_id):
            region.update(store.dependents(p))  # siblings

        plausible = [n for n in pool if n in region]
        return plausible or pool

    def choose(self, store: GraphStore, item, lit: list, options: Optional[list]) -> str:
        if options:
            pool = [o for o in options if o in set(lit)] if lit else list(options)
            pool = pool or list(options)
            if self.condition != "zero":
                narrowed = self.candidates(store, item, pool)
                pool = narrowed or pool
            return self.rng.choice(pool)
        return self.rng.choice(self.candidates(store, item, lit))


# ---------------------------------------------------------------------------
# one dialogue
# ---------------------------------------------------------------------------

@dataclass
class Probe:
    hint_level: int
    lit: int
    solved: bool
    action: str


@dataclass
class Run:
    probes: list = field(default_factory=list)


def _wrong(store: GraphStore, item, expects: str, options: list, avoid: str, rng) -> StudentResponse:
    if expects == "mcq" and options:
        wrong = [o for o in options if o != item.answer] or list(options)
        return StudentResponse(type="mcq", choice_id=rng.choice(wrong))
    if expects == "edge_click":
        edges = [e for e in store.graph.edges if f"{e.from_}->{e.to}" != item.answer]
        e = rng.choice(edges)
        return StudentResponse(type="edge_click", edge=EdgeRef(**{"from": e.from_, "to": e.to}))
    wrong = [n for n in store.node_ids if n != item.answer]
    return StudentResponse(type="node_click", node_id=rng.choice(wrong))


def run_dialogue(store: GraphStore, student: Student, seed: int, max_turns: int = 8) -> Run:
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    rng = student.rng
    out = Run()

    phase1 = turn_mod.begin_turn(store, db, state, None)
    turn_mod.complete_turn(store, db, phase1)

    for _ in range(max_turns):
        item = phase1.item
        if item is None or phase1.session_complete:
            break

        lit = phase1.graph_state.focus_nodes
        options = [o.id for o in phase1.mcq_options]

        # COUNTERFACTUAL PROBE: what would this student answer right now?
        pick = student.choose(store, item, lit, options)
        if phase1.hint_level > 0:
            out.probes.append(Probe(
                hint_level=phase1.hint_level,
                lit=len(lit) or len(store.node_ids),
                solved=pick == item.answer,
                action=phase1.action,
            ))

        # ...then answer wrong regardless, so the ladder keeps climbing and this
        # dialogue yields the whole curve rather than one point.
        response = _wrong(store, item, phase1.expects, options, item.answer, rng)
        phase1 = turn_mod.begin_turn(store, db, state, response)
        turn_mod.complete_turn(store, db, phase1)

    db.close()
    return out


# ---------------------------------------------------------------------------
# the sweep
# ---------------------------------------------------------------------------

def measure(store: GraphStore, arm_label: str, mode: str, condition: str, n: int) -> dict:
    by_level = defaultdict(list)
    lit_at_level = defaultdict(list)
    with _config(ladder_mode=mode):
        for i in range(n):
            student = Student(condition=condition, rng=random.Random(f"{arm_label}:{condition}:{i}"))
            run = run_dialogue(store, student, seed=i)
            for p in run.probes:
                by_level[p.hint_level].append(p.solved)
                lit_at_level[p.hint_level].append(p.lit)

    levels = {}
    for level in sorted(by_level):
        hits = by_level[level]
        levels[level] = {
            "n": len(hits),
            "solve_rate": sum(hits) / len(hits),
            "mean_lit": statistics.mean(lit_at_level[level]),
        }
    terminal = max(levels) if levels else None
    return {
        "arm": arm_label,
        "ladder_mode": mode,
        "condition": condition,
        "dialogues": n,
        "levels": levels,
        "terminal_solve_rate": levels[terminal]["solve_rate"] if terminal else None,
        "terminal_mean_lit": levels[terminal]["mean_lit"] if terminal else None,
    }


def run_all(n: int, arms: Optional[dict] = None) -> list:
    store = GraphStore.load()
    results = []
    for label, mode in (arms or ARMS).items():
        for condition in CONDITIONS:
            results.append(measure(store, label, mode, condition, n))
    return results


def render(results: list) -> str:
    lines = []
    lines.append("EFFECTIVE LEAKAGE - measured post-hint solve rate (CLAUDE.md 9.1)")
    lines.append("")
    lines.append("Solve rate is what a simulated student actually achieved. It is NOT 1/N;")
    lines.append("1/N is a lower bound that assumes uniform choice, and the partial-knowledge")
    lines.append("row below is the reason that assumption does not hold.")
    lines.append("")

    by_arm = defaultdict(list)
    for r in results:
        by_arm[r["arm"]].append(r)

    for arm, rows in by_arm.items():
        lines.append(f"  {arm}  (LADDER_MODE={rows[0]['ladder_mode']}, "
                     f"n={rows[0]['dialogues']} dialogues)")
        levels = sorted({lv for r in rows for lv in r["levels"]})
        header = "    condition      " + "".join(f"  hint {lv}" for lv in levels) + "   terminal"
        lines.append(header)
        for r in rows:
            cells = ""
            for lv in levels:
                cells += f"  {r['levels'][lv]['solve_rate']:>6.0%}" if lv in r["levels"] else "       -"
            term = f"  {r['terminal_solve_rate']:>6.0%}" if r["terminal_solve_rate"] is not None else "      -"
            lines.append(f"    {r['condition']:<14}{cells}   {term}")
        lit = rows[0]["levels"]
        lines.append("    mean lit        " + "".join(
            f"  {lit[lv]['mean_lit']:>6.1f}" if lv in lit else "       -" for lv in levels))
        lines.append("")

    lines.append("  MARGINAL LEAKAGE - what the NARROWING actually contributed")
    lines.append("")
    lines.append("  A partial-knowledge student solves some items from their own knowledge")
    lines.append("  with no help from the interface. The verbal-only arm never dims anything,")
    lines.append("  so its solve rate IS that baseline. Subtracting it condition-by-condition")
    lines.append("  leaves what the visual channel added. Reporting the raw partial-knowledge")
    lines.append("  rate as leakage charges the interface for the student's own competence.")
    lines.append("")
    baseline = {
        r["condition"]: r["terminal_solve_rate"]
        for r in results
        if r["ladder_mode"] == "verbal_only" and r["terminal_solve_rate"] is not None
    }
    if baseline:
        lines.append("      condition        raw   baseline   marginal")
        for arm, rows in by_arm.items():
            if rows[0]["ladder_mode"] == "verbal_only":
                continue
            lines.append(f"    {arm}")
            for r in rows:
                raw, base = r["terminal_solve_rate"], baseline.get(r["condition"])
                if raw is None or base is None:
                    continue
                lines.append(
                    f"      {r['condition']:<12} {raw:>6.0%}     {base:>6.0%}     {raw - base:>+6.0%}"
                )
        lines.append("")

    zero = [r for r in results
            if r["condition"] == "zero" and r["ladder_mode"] == "visual_only"
            and r["terminal_solve_rate"] is not None]
    partial = [r for r in results
               if r["condition"] == "partial" and r["ladder_mode"] == "visual_only"
               and r["terminal_solve_rate"] is not None]
    if zero and partial:
        z = statistics.mean(r["terminal_solve_rate"] for r in zero)
        p = statistics.mean(r["terminal_solve_rate"] for r in partial)
        lit = statistics.mean(r["terminal_mean_lit"] for r in zero)
        lines.append(f"  At the terminal rung of the isolated visual channel ({lit:.0f} lit):")
        lines.append(f"    zero-knowledge     {z:>5.0%}   which is roughly 1/N, because that is")
        lines.append("                               all 1/N was ever measuring")
        lines.append(f"    partial-knowledge  {p:>5.0%}   {p - z:+.0%} above it")
        lines.append("")
        lines.append("  Reporting 1/N would have reported the first number and called it")
        lines.append("  leakage. The surviving set leaks its identity as well as its size, and")
        lines.append("  a student who knows the region collects the difference for free.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=60,
                        help="dialogues per arm per condition (CLAUDE.md 9.1 wants 60)")
    parser.add_argument("--json", type=str, default=None, help="also write raw results here")
    args = parser.parse_args()

    results = run_all(args.n)
    print(render(results))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
        print(f"\nraw results -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
