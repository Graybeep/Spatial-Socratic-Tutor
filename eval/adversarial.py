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

FOUR ARMS, LABELLED, BECAUSE THEY ARE DIFFERENT SYSTEMS
--------------------------------------------------------
The demo runs `interleaved` and bottoms out around 9 lit. A `visual_only` sweep
bottoms out at 5. Reporting only the second invites "is that the system you just
showed us", and the answer would be no. All four run, all four labelled:

    product configuration     LADDER_MODE=interleaved   - what the demo runs
    isolated visual channel   LADDER_MODE=visual_only   - the mechanism alone
    verbal channel only       LADDER_MODE=verbal_only   - nothing ever dims
    no hints at all           LADDER_MODE=none          - the true baseline

The gap between the first two is itself a finding. The last is what marginal
leakage is measured against - NOT verbal_only, because a verbal hint still
eliminates candidates by name and subtracting it would credit the verbal channel
with everything it gave away.

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
Per item, the ladder is climbed by answering deliberately wrong. At each attempt
the student's choice is recorded as a COUNTERFACTUAL PROBE - "would this student
have solved it here?" - and then a wrong answer is submitted anyway so the ladder
continues. One dialogue therefore yields the whole curve, and a student who would
have solved at attempt 2 still contributes an attempt-3 and attempt-4 data point.

Arms are compared at MATCHED ATTEMPT, not matched hint level: the `none` arm has
no hint levels, so keying on them would exclude the baseline entirely. A dialogue
stops when the turn budget forces a reveal and moves to a new item, because
narrowing resets there and the probe would stop measuring the hinted item.

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
from eval import provenance
from server.schemas import EdgeRef, StudentResponse
from server.state import Store

ARMS = {
    "product configuration": "interleaved",
    "isolated visual channel": "visual_only",
    "verbal channel only": "verbal_only",
    "no hints at all": "none",
}
#: The true no-interface baseline. NOT verbal_only - a verbal hint still
#: eliminates candidates by name, so a marginal figure computed against it
#: charges the visual channel for nothing and credits the verbal one for
#: everything it gave away. Using verbal_only would understate the visual
#: channel's contribution: conservative, but wrong.
BASELINE_ARM = "none"
BASELINE_ARM_LABEL = "no hints at all"
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

    def edge_candidates(self, store: GraphStore, item, lit: list) -> list:
        """The edges this student would choose among, as "from->to" strings.

        SEPARATE FROM `candidates` ON PURPOSE, and the two conditions differ in
        a way that is the whole point of splitting 9.1's rows.

        `zero` uses the narrowing and nothing else: every prereq edge whose
        endpoints are both lit. That is what the INTERFACE handed over.

        `partial`/`adversarial` also read the item prompt, which names the `to`
        endpoint - so their pool is that node's prereq in-edges. That is what
        the ITEM handed over, and on this bank it is a pool of 1 or 2
        (build.validate's edge-anchor check). Crediting narrowing for that would
        be measuring the item bank's leak and calling it the interface's.
        """
        lit_set = set(lit)
        prereq = [e for e in store.graph.edges if e.type == "prereq"]

        if self.condition == "zero":
            pool = [f"{e.from_}->{e.to}" for e in prereq
                    if not lit_set or (e.from_ in lit_set and e.to in lit_set)]
            return pool or [f"{e.from_}->{e.to}" for e in prereq]

        anchored = [f"{p}->{item.node_id}" for p in store.prereqs(item.node_id)]
        narrowed = [a for a in anchored if not lit_set or a.split("->")[0] in lit_set]
        return narrowed or anchored or [f"{e.from_}->{e.to}" for e in prereq]

    def choose(self, store: GraphStore, item, lit: list, options: Optional[list]) -> str:
        if options:
            pool = [o for o in options if o in set(lit)] if lit else list(options)
            pool = pool or list(options)
            if self.condition != "zero":
                narrowed = self.candidates(store, item, pool)
                pool = narrowed or pool
            return self.rng.choice(pool)
        # An edge answer is "from->to". A node id can never equal one, so
        # before this branch existed every edge item scored 0 by construction -
        # 49 of the 101-item population, silently halving the measured rate.
        if item.type == "edge_click":
            return self.rng.choice(self.edge_candidates(store, item, lit))
        return self.rng.choice(self.candidates(store, item, lit))


# ---------------------------------------------------------------------------
# one dialogue
# ---------------------------------------------------------------------------

@dataclass
class Probe:
    #: Number of wrong answers already given on this item. Arms are compared at
    #: MATCHED ATTEMPT, not matched hint level - the `none` arm has no hint
    #: levels, so keying on them would silently exclude the baseline entirely.
    attempt: int
    hint_level: int
    lit: int
    solved: bool
    action: str
    #: The item this probe was drawn on. THE RESAMPLING UNIT for 9.1's error
    #: bars: dialogues are drawn over a bank of ~101 visually-answerable items,
    #: so repeated draws on one item are not independent evidence about the
    #: bank. Bootstrapping dialogues would understate every interval.
    item_id: str = ""
    #: node_click or edge_click. NOT a breakdown for interest's sake: the two
    #: measure different things. A node item's solve rate is what the narrowing
    #: leaked; an edge item's is dominated by the anchor its own prompt names,
    #: and the pooled number is neither quantity.
    item_type: str = ""


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


def run_dialogue(store: GraphStore, student: Student, seed: int,
                 max_turns: int = 8, item_id: Optional[str] = None) -> Run:
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    rng = student.rng
    out = Run()

    # FORCE THE STARTING ITEM. Without this every dialogue probes the same item:
    # the initial theta map is identical across dialogues, so next_node() is
    # deterministic, _pick_item() takes the first unused item on that node, and
    # the first_item guard below then pins the whole dialogue to it. Measured:
    # 60 dialogues, 360 probes, ONE distinct item. The n was 200 draws of the
    # student's RNG against one fixed narrowing, not 200 samples of the bank.
    if item_id is not None:
        forced = store.item(item_id)
        state.start_item(forced.node_id, forced.id)
        db.save(state)

    phase1 = turn_mod.begin_turn(store, db, state, None)
    turn_mod.complete_turn(store, db, phase1)

    attempt = 0
    first_item = phase1.item.id if phase1.item else None
    for _ in range(max_turns):
        item = phase1.item
        if item is None or phase1.session_complete:
            break
        # One dialogue measures ONE item's ladder. Once the turn budget forces a
        # reveal and advances, narrowing resets to nothing and the probe would be
        # measuring a fresh un-hinted item - which showed up as a 50/50-lit
        # column that dragged the terminal figure back to the unhinted rate.
        if item.id != first_item:
            break

        lit = phase1.graph_state.focus_nodes
        options = [o.id for o in phase1.mcq_options]

        # COUNTERFACTUAL PROBE: what would this student answer right now?
        pick = student.choose(store, item, lit, options)
        if attempt > 0:
            out.probes.append(Probe(
                attempt=attempt,
                item_id=item.id,
                item_type=item.type,
                hint_level=phase1.hint_level,
                lit=len(lit) or len(store.node_ids),
                solved=pick == item.answer,
                action=phase1.action,
            ))

        # ...then answer wrong regardless, so the ladder keeps climbing and this
        # dialogue yields the whole curve rather than one point.
        response = _wrong(store, item, phase1.expects, options, item.answer, rng)
        attempt += 1
        phase1 = turn_mod.begin_turn(store, db, state, response)
        turn_mod.complete_turn(store, db, phase1)

    db.close()
    return out


# ---------------------------------------------------------------------------
# the sweep
# ---------------------------------------------------------------------------

def bootstrap_ci(by_item: dict, resamples: int, confidence: float, seed: int) -> dict:
    """Cluster bootstrap over ITEMS for one rate.

    `by_item` maps item_id -> list of booleans (that item's probe outcomes).

    THE UNIT MATTERS AND IT IS NOT THE DIALOGUE. n=200 dialogues are drawn over
    ~101 visually-answerable items, so a dialogue is not an independent draw
    from the population we are generalising to: the population is items. Two
    dialogues that happen to land on the same item share whatever makes that
    item easy or hard. Resampling dialogues would treat those as independent
    evidence and report an interval far narrower than the data supports.

    So we resample ITEMS with replacement and pool all probes belonging to each
    drawn item - the standard cluster bootstrap. The interval widens accordingly,
    which is the honest direction.

    Percentile interval, not bias-corrected: BCa needs a jackknife per resample
    and the extra machinery would not change a conclusion at this precision.
    """
    items = sorted(by_item)
    if not items:
        return {"lo": None, "hi": None, "point": None, "resamples": 0, "items": 0}

    flat = [x for i in items for x in by_item[i]]
    point = sum(flat) / len(flat) if flat else 0.0

    rng = random.Random(seed)
    k = len(items)
    dist = []
    for _ in range(resamples):
        pool = []
        for _ in range(k):
            pool.extend(by_item[items[rng.randrange(k)]])
        if pool:
            dist.append(sum(pool) / len(pool))

    if not dist:
        return {"lo": None, "hi": None, "point": point,
                "resamples": 0, "items": k}

    dist.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = dist[max(0, int(alpha * len(dist)) - 1)]
    hi = dist[min(len(dist) - 1, int((1.0 - alpha) * len(dist)))]
    return {
        "lo": round(lo, 4),
        "hi": round(hi, 4),
        "point": round(point, 4),
        "half_width": round((hi - lo) / 2, 4),
        "resamples": len(dist),
        "items": k,
        "confidence": confidence,
    }


def marginal_ci(treat_by_item: dict, base_by_item: dict, resamples: int,
                confidence: float, seed: int) -> dict:
    """CI for a DIFFERENCE of two rates, resampling the shared item set jointly.

    Marginal leakage is treatment minus the no-hints baseline. Bootstrapping the
    two arms independently and subtracting the intervals would be wrong twice
    over: it ignores that both arms run on the SAME items, and subtracting
    interval endpoints overstates the width of a difference between correlated
    quantities.

    Drawing one item index and taking that item's probes from BOTH arms keeps
    the pairing, so item difficulty - the dominant nuisance term - cancels
    within each resample the way it does in the point estimate.
    """
    items = sorted(set(treat_by_item) & set(base_by_item))
    if not items:
        return {"lo": None, "hi": None, "point": None, "items": 0}

    def rate(d, keys):
        pool = [x for k in keys for x in d.get(k, [])]
        return (sum(pool) / len(pool)) if pool else None

    point_t = rate(treat_by_item, items)
    point_b = rate(base_by_item, items)
    point = None if point_t is None or point_b is None else point_t - point_b

    rng = random.Random(seed)
    k = len(items)
    dist = []
    for _ in range(resamples):
        drawn = [items[rng.randrange(k)] for _ in range(k)]
        t, b = rate(treat_by_item, drawn), rate(base_by_item, drawn)
        if t is not None and b is not None:
            dist.append(t - b)

    if not dist:
        return {"lo": None, "hi": None, "point": point, "items": k}

    dist.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = dist[max(0, int(alpha * len(dist)) - 1)]
    hi = dist[min(len(dist) - 1, int((1.0 - alpha) * len(dist)))]
    return {
        "lo": round(lo, 4),
        "hi": round(hi, 4),
        "point": round(point, 4) if point is not None else None,
        "half_width": round((hi - lo) / 2, 4),
        "crosses_zero": lo <= 0.0 <= hi,
        "resamples": len(dist),
        "items": k,
        "confidence": confidence,
    }


#: Which items 9.1 draws from. "scored" is the population every mastery claim
#: is about. "answerable" is the wider set INCLUDING the 32 determined edge
#: items, kept runnable on purpose: it reproduces the 82% figure the writeup
#: uses to show the metric was measuring nothing, so a reader can check that
#: inference with one flag instead of trusting an archived file.
POPULATIONS = ("scored", "answerable")


def scored_bank(store: GraphStore, population: str = "scored") -> list:
    """The items 9.1 generalises to: visually answerable AND scored.

    NOT the whole visually-answerable set. 32 of the 49 edge items are
    `scorable=false` because the `to` endpoint their prompt names has exactly
    one prereq, so naming it names the answer (build.validate's edge-anchor
    check). They are still shown to a student; they cannot move theta, so they
    are not part of the population any mastery claim is about.

    52 node_click + 17 edge_click = 69. Quote that n and its interval.

    `population="answerable"` drops the scorable filter and returns all 101.
    That run is not a mastery claim and must not be quoted as one; it exists to
    demonstrate the defect.
    """
    items = [i for i in store.bank.items if i.visually_answerable]
    if population == "answerable":
        return items
    return [i for i in items if i.scorable]


def measure(store: GraphStore, arm_label: str, mode: str, condition: str, n: int,
            population: str = "scored") -> dict:
    by_level = defaultdict(list)
    lit_at_level = defaultdict(list)
    #: attempt -> item_id -> outcomes. Kept so the rate at each rung can be
    #: bootstrapped over its true resampling unit; see bootstrap_ci.
    by_item = defaultdict(lambda: defaultdict(list))
    #: item_type -> attempt -> outcomes, for the split below.
    by_type = defaultdict(lambda: defaultdict(list))
    by_type_item = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    # SWEEP THE ITEM BANK. 9.1 runs on the visually-answerable AND SCORED
    # subset (see scored_bank), so that subset is the population, and n
    # dialogues are spread across it rather than spent re-rolling one item.
    # With n < len(bank) this is a sample of items; with n > len(bank) each item
    # is probed round-robin.
    bank = [i.id for i in scored_bank(store, population)]
    with _config(ladder_mode=mode):
        for i in range(n):
            student = Student(condition=condition, rng=random.Random(f"{arm_label}:{condition}:{i}"))
            run = run_dialogue(store, student, seed=i,
                               item_id=bank[i % len(bank)] if bank else None)
            for p in run.probes:
                by_level[p.attempt].append(p.solved)
                lit_at_level[p.attempt].append(p.lit)
                by_item[p.attempt][p.item_id].append(p.solved)
                by_type[p.item_type][p.attempt].append(p.solved)
                by_type_item[p.item_type][p.attempt][p.item_id].append(p.solved)

    levels = {}
    for level in sorted(by_level):
        hits = by_level[level]
        levels[level] = {
            "n": len(hits),
            "solve_rate": sum(hits) / len(hits),
            "mean_lit": statistics.mean(lit_at_level[level]),
        }
    # The deepest attempt is reached by only the few dialogues that got that far,
    # so taking it as "terminal" unconditionally reads noise as signal - it had
    # the flat no-hint baseline swinging 22%-45% across adjacent attempts on
    # single-digit samples. Require a real sample before quoting a rung.
    min_n = max(20, n // 3)
    eligible = [lv for lv, v in levels.items() if v["n"] >= min_n]
    terminal = max(eligible) if eligible else (max(levels) if levels else None)
    return {
        "arm": arm_label,
        "population": population,
        "ladder_mode": mode,
        "condition": condition,
        "dialogues": n,
        "levels": levels,
        "terminal_attempt": terminal,
        "terminal_n": levels[terminal]["n"] if terminal else None,
        "min_n_for_terminal": min_n,
        "terminal_solve_rate": levels[terminal]["solve_rate"] if terminal else None,
        "terminal_mean_lit": levels[terminal]["mean_lit"] if terminal else None,
        # SPLIT BY ITEM TYPE. The pooled figure above answers no question:
        # node items measure the narrowing, edge items measure an anchor the
        # item prompt gives away for free (see build.validate's edge-anchor
        # check - median 1 candidate). Quote the rows, not the pool.
        "by_item_type": {
            itype: {
                "levels": {
                    lv: {"n": len(v), "solve_rate": sum(v) / len(v)}
                    for lv, v in sorted(rows.items())
                },
                "terminal_attempt": terminal,
                "terminal_n": len(rows.get(terminal, [])),
                "terminal_solve_rate": (
                    sum(rows[terminal]) / len(rows[terminal])
                    if terminal in rows and rows[terminal] else None
                ),
                "distinct_items": len(by_type_item[itype].get(terminal, {})),
                "terminal_ci": bootstrap_ci(
                    by_type_item[itype].get(terminal, {}), CONFIG.bootstrap_resamples,
                    CONFIG.bootstrap_confidence, CONFIG.bootstrap_seed
                ) if terminal in rows and rows[terminal] else None,
            }
            for itype, rows in sorted(by_type.items())
        },
        "provenance": provenance.over(
            population=bank,
            sampled=by_item[terminal] if terminal else [],
            observations=sum(len(v) for v in (by_item[terminal].values() if terminal else [])),
            unit="items",
        ).as_dict(),
        "terminal_ci": bootstrap_ci(
            by_item[terminal], CONFIG.bootstrap_resamples,
            CONFIG.bootstrap_confidence, CONFIG.bootstrap_seed) if terminal else None,
        "distinct_items": len(by_item[terminal]) if terminal else 0,
        # Retained so marginal_ci can pair arms on the same items.
        "_by_item_terminal": {k: list(v) for k, v in by_item[terminal].items()} if terminal else {},
    }


def _default_n(n: Optional[int], population: str = "scored") -> int:
    """Two dialogues per item in the chosen population, unless told otherwise."""
    if n is not None:
        return n
    bank = scored_bank(GraphStore.load(), population)
    return max(2 * len(bank), 60)


def run_all(n: int, arms: Optional[dict] = None, population: str = "scored") -> list:
    store = GraphStore.load()
    results = []
    for label, mode in (arms or ARMS).items():
        for condition in CONDITIONS:
            results.append(measure(store, label, mode, condition, n, population))
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
        header = "    condition      " + "".join(f"   try {lv}" for lv in levels) + "   terminal"
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
        lines.append("    probes          " + "".join(
            f"  {lit[lv]['n']:>6d}" if lv in lit else "       -" for lv in levels))
        lines.append(f"    terminal = deepest attempt with n >= {rows[0]['min_n_for_terminal']} "
                     f"(attempt {rows[0]['terminal_attempt']}, n={rows[0]['terminal_n']})")

        # THE SPLIT. Pooling these answers no question - see Probe.item_type.
        types = sorted({t for r in rows for t in r.get("by_item_type", {})})
        if len(types) > 1:
            lines.append("")
            lines.append("    terminal rate BY ITEM TYPE (the pooled row above is neither number)")
            head = "    condition     " + "".join(f"{t:>14}" for t in types)
            lines.append(head)
            for r in rows:
                cells = ""
                for t in types:
                    v = r.get("by_item_type", {}).get(t) or {}
                    rate = v.get("terminal_solve_rate")
                    cells += f"{rate:>13.0%} " if rate is not None else "            - "
                lines.append(f"    {r['condition']:<14}{cells}")
            counts = rows[0].get("by_item_type", {})
            lines.append("    items         " + "".join(
                f"{(counts.get(t) or {}).get('distinct_items', 0):>13d} " for t in types))
            pop = rows[0].get("population", "scored")
            lines.append("    node_click measures the NARROWING. edge_click is dominated by the")
            lines.append("    `to` endpoint the item's own prompt names, so it moves with the")
            lines.append("    item bank rather than with the arm.")
            if pop == "answerable":
                lines.append("    POPULATION=answerable: includes the 32 determined edge items")
                lines.append("    (guess rate 1.0). NOT a mastery claim - this run exists to show")
                lines.append("    that edge_click barely moves across arms.")
            else:
                lines.append("    Scored population: the 32 determined edge items are excluded,")
                lines.append("    so edge_click here is the 17 two-candidate items (~0.5 floor).")
            lines.append("    Quote node_click as 9.1's headline.")
        lines.append("")

    lines.append("  MARGINAL LEAKAGE - what the NARROWING actually contributed")
    lines.append("")
    lines.append("  A partial-knowledge student solves some items from their own knowledge")
    lines.append("  with no help at all. The 'no hints at all' arm measures exactly that, and")
    lines.append("  subtracting it condition-by-condition leaves what the interface added.")
    lines.append("  Reporting the raw rate as leakage charges the interface for the student's")
    lines.append("  own competence.")
    lines.append("")
    lines.append("  The baseline is the no-hint arm, NOT verbal-only: a verbal hint still")
    lines.append("  eliminates candidates by name, so subtracting it would credit the verbal")
    lines.append("  channel with everything it gave away and understate the visual one.")
    lines.append("")
    baseline = {
        r["condition"]: r["terminal_solve_rate"]
        for r in results
        if r["arm"] == BASELINE_ARM_LABEL and r["terminal_solve_rate"] is not None
    }
    if baseline:
        lines.append("      condition        raw   baseline   marginal")
        for arm, rows in by_arm.items():
            if rows[0]["ladder_mode"] == BASELINE_ARM:
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
    # DEFAULT COVERS THE BANK. 9.1 says "60 dialogues, not 30", which was about
    # statistical power when a dialogue was the unit. Once measure() sweeps
    # items, the unit is the item and 60 dialogues cover 60 of 101 - a silently
    # partial run. Default is two dialogues per item; --n still overrides.
    parser.add_argument("--n", type=int, default=None,
                        help="dialogues per arm per condition (CLAUDE.md 9.1 wants 60)")
    parser.add_argument("--json", type=str, default=None, help="also write raw results here")
    parser.add_argument("--population", choices=POPULATIONS, default="scored",
                        help="scored = the 69 items mastery is computed from "
                             "(default). answerable = all 101, including the 32 "
                             "determined edge items; reproduces the 82% figure "
                             "and is NOT a mastery claim.")
    args = parser.parse_args()

    results = run_all(_default_n(args.n, args.population), population=args.population)
    print(render(results))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            # Strip the per-item probe map: it is an intermediate the CI
            # needs in-process, not a result, and it inflates the file ~8x.
            json.dump([{k: v for k, v in r.items() if not k.startswith("_")}
                       for r in results], fh, indent=2)
        print(f"\nraw results -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
