"""Smoke tests for §9.1. Small n - these check the harness, not the numbers.

The numbers are the deliverable and they move when the ladder moves; asserting
them here would just mean editing this file every time the schedule changes.
What must not move is the shape: three conditions, labelled arms, and a
partial-knowledge student who is strictly better informed than a zero-knowledge
one.
"""
from __future__ import annotations

import random

from eval import adversarial
from server.graph_store import GraphStore


def test_all_three_conditions_and_all_arms_run():
    results = adversarial.run_all(n=3)
    assert {r["condition"] for r in results} == set(adversarial.CONDITIONS)
    assert {r["arm"] for r in results} == set(adversarial.ARMS)


def test_arms_are_labelled_not_just_moded():
    """'is that the system you just showed us' has to be answerable from the
    output alone."""
    assert "product configuration" in adversarial.ARMS
    assert adversarial.ARMS["product configuration"] == "interleaved"
    assert adversarial.ARMS["isolated visual channel"] == "visual_only"


def test_probes_are_counterfactual_so_one_dialogue_yields_a_curve():
    """A student who would have solved at level 2 must still produce a level 3
    and level 4 datapoint - the probe records the answer, then submits a wrong
    one regardless."""
    store = GraphStore.load()
    student = adversarial.Student(condition="zero", rng=random.Random(0))
    run = adversarial.run_dialogue(store, student, seed=0)
    levels = [p.hint_level for p in run.probes]
    assert len(levels) >= 3, levels
    assert max(levels) > min(levels), "the ladder never advanced"


def test_partial_knowledge_student_chooses_from_a_smaller_pool(store):
    """The mechanism behind the headline finding: the surviving set's identity
    tells a partial-knowledge student which region the answer is in."""
    item = next(i for i in store.bank.items if store.prereqs(i.node_id))
    lit = list(store.node_ids)
    zero = adversarial.Student("zero", random.Random(1))
    partial = adversarial.Student("partial", random.Random(1))
    assert len(partial.candidates(store, item, lit)) < len(zero.candidates(store, item, lit))


def test_partial_pool_always_contains_the_answer_when_lit_does(store):
    """Otherwise the partial student would score BELOW zero-knowledge and the
    comparison would measure a bug rather than an effect."""
    partial = adversarial.Student("partial", random.Random(2))
    checked = 0
    for item in store.bank.items[:40]:
        if item.answer not in set(store.node_ids):
            continue
        pool = partial.candidates(store, item, list(store.node_ids))
        assert item.answer in pool, f"{item.id}: partial student cannot reach its own answer"
        checked += 1
    assert checked


def test_render_never_reports_one_over_n_as_leakage():
    """The report must not put a derived guess probability on a slide.
    MAX_GUESS_PROBABILITY stays a policy knob; 1/N is a lower bound, and the
    measured rate is the number."""
    text = adversarial.render(adversarial.run_all(n=3))
    assert "solve rate" in text.lower()
    assert "1/N" in text, "the report should say explicitly what it is NOT reporting"
    assert "marginal" in text.lower(), "raw rates overstate what the interface leaks"


def test_verbal_only_arm_supplies_the_no_narrowing_baseline():
    results = adversarial.run_all(n=3)
    verbal = [r for r in results if r["ladder_mode"] == "verbal_only"]
    assert verbal
    for r in verbal:
        assert r["terminal_mean_lit"] == len(GraphStore.load().node_ids), (
            "the baseline arm must never dim anything"
        )


def test_baseline_arm_is_no_hints_not_verbal_only():
    """verbal_only is not a no-help condition: a verbal hint still eliminates
    candidates by name. Subtracting it would credit the verbal channel with
    everything it gave away and understate the visual one."""
    assert adversarial.BASELINE_ARM == "none"
    assert adversarial.ARMS[adversarial.BASELINE_ARM_LABEL] == "none"


def test_no_hint_arm_never_hints(store):
    """The baseline has to actually be a baseline."""
    from tests.conftest import config_override

    with config_override(ladder_mode="none"):
        student = adversarial.Student("zero", random.Random(0))
        run = adversarial.run_dialogue(store, student, seed=0)
        assert run.probes
        for p in run.probes:
            assert not p.action.startswith("hint"), f"baseline arm emitted {p.action}"
            assert p.hint_level == 0, "hint level climbed in an arm with no hints"
            assert p.lit == len(store.node_ids), "the baseline arm dimmed something"


def test_a_dialogue_measures_one_item(store):
    """Once the turn budget forces a reveal and advances, narrowing resets and a
    probe would be measuring a fresh un-hinted item. That showed up as a
    fully-lit column dragging the terminal figure back to the unhinted rate."""
    student = adversarial.Student("zero", random.Random(3))
    run = adversarial.run_dialogue(store, student, seed=3)
    assert run.probes
    attempts = [p.attempt for p in run.probes]
    assert attempts == sorted(attempts)
    assert len(set(attempts)) == len(attempts), "an attempt index repeated"


def test_terminal_requires_an_adequate_sample():
    """The deepest attempt is reached by few dialogues, so quoting it
    unconditionally reads noise as signal."""
    results = adversarial.run_all(n=3)
    for r in results:
        if r["terminal_attempt"] is not None:
            assert r["min_n_for_terminal"] >= 20


# ---------------------------------------------------------------------------
# edge items were unsolvable by construction (§9.1)
# ---------------------------------------------------------------------------

def test_student_returns_an_edge_answer_for_an_edge_item():
    """A node id can never equal "from->to". Before the edge branch existed,
    every edge item scored 0 - 49 of the 101-item population."""
    store = GraphStore.load()
    item = next(i for i in store.bank.items if i.type == "edge_click")

    for condition in ("zero", "partial", "adversarial"):
        student = adversarial.Student(condition=condition, rng=random.Random(0))
        pick = student.choose(store, item, list(store.node_ids), [])
        assert "->" in pick, f"{condition} answered an edge item with a node id"


def test_an_edge_item_is_actually_solvable_now():
    store = GraphStore.load()
    item = next(i for i in store.bank.items if i.type == "edge_click")
    student = adversarial.Student(condition="partial", rng=random.Random(0))

    picks = {student.choose(store, item, list(store.node_ids), []) for _ in range(40)}

    assert item.answer in picks, "the true answer is not reachable by the student"


def test_the_anchored_pool_is_the_prereqs_of_the_named_endpoint():
    """The item prompt names the `to` endpoint, so a student who reads it is
    choosing among that node's prereq in-edges - not among 73 edges."""
    store = GraphStore.load()
    item = next(i for i in store.bank.items if i.type == "edge_click")
    student = adversarial.Student(condition="partial", rng=random.Random(0))

    pool = set(student.edge_candidates(store, item, list(store.node_ids)))

    assert pool == {f"{p}->{item.node_id}" for p in store.prereqs(item.node_id)}


def test_the_zero_student_does_not_use_the_anchor():
    """`zero` is the interface-only floor. If it read the prompt too, the
    node/edge split would stop separating item leakage from narrowing leakage."""
    store = GraphStore.load()
    item = next(i for i in store.bank.items
                if i.type == "edge_click" and len(store.prereqs(i.node_id)) == 1)
    student = adversarial.Student(condition="zero", rng=random.Random(0))

    pool = student.edge_candidates(store, item, list(store.node_ids))

    assert len(pool) > 1, "the zero student collapsed onto the anchored pool"


def test_measure_splits_the_terminal_rate_by_item_type():
    store = GraphStore.load()
    row = adversarial.measure(store, "t", "interleaved", "partial", n=8)

    split = row["by_item_type"]
    assert set(split) <= {"node_click", "edge_click", "mcq"}
    for v in split.values():
        assert v["terminal_solve_rate"] is None or 0.0 <= v["terminal_solve_rate"] <= 1.0
        assert v["distinct_items"] >= 0
