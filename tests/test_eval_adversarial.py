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
