"""Regressions for two defects the existing 179 tests did not catch.

Both were invisible for the same reason: every assertion was about the SHAPE of
the eval output (keys present, rates in [0,1], arms labelled) and none was about
what the eval had actually sampled. A number computed over one item has the same
shape as a number computed over a hundred.
"""
from __future__ import annotations

import random

import pytest

from eval.adversarial import (
    Student, run_dialogue, measure, bootstrap_ci, marginal_ci, _config,
)
from eval import distractor_screen
from server.config import CONFIG
from server.graph_store import GraphStore


@pytest.fixture(scope="module")
def store():
    return GraphStore.load()


# ---------------------------------------------------------------------------
# 9.1 sampled one item out of 101
# ---------------------------------------------------------------------------

def test_dialogues_cover_many_items(store):
    """THE REGRESSION. Before the item sweep, 60 dialogues produced 360 probes
    over exactly ONE item: the initial theta map is identical per dialogue, so
    next_node() is deterministic and _pick_item() returns the same item, after
    which the first_item guard pinned the dialogue to it. Every 9.1 figure was a
    property of itm_0001.
    """
    result = measure(store, "product configuration", "interleaved", "partial", n=60)
    assert result["distinct_items"] > 1, (
        "every dialogue probed the same item - 9.1 is measuring one item, not "
        "the bank, and its confidence interval is undefined"
    )
    assert result["distinct_items"] >= 20


def test_dialogue_honours_forced_item(store):
    bank = [i.id for i in store.bank.items if i.visually_answerable]
    target = bank[7]
    student = Student(condition="partial", rng=random.Random(1))
    with _config(ladder_mode="interleaved"):
        run = run_dialogue(store, student, seed=3, item_id=target)
    assert run.probes, "forced dialogue produced no probes"
    assert {p.item_id for p in run.probes} == {target}


def test_probes_carry_item_id(store):
    student = Student(condition="zero", rng=random.Random(2))
    with _config(ladder_mode="interleaved"):
        run = run_dialogue(store, student, seed=1)
    assert all(p.item_id for p in run.probes), "probe without an item_id cannot be resampled"


# ---------------------------------------------------------------------------
# the bootstrap resamples ITEMS, not dialogues
# ---------------------------------------------------------------------------

def test_bootstrap_widens_with_between_item_variance():
    """Two banks, same pooled rate, different spread across items. The cluster
    bootstrap must report a wider interval for the one whose items disagree; a
    dialogue-level bootstrap would call them identical.
    """
    tight = {f"i{k}": [True, False] for k in range(20)}          # every item 0.5
    split = {f"i{k}": [True, True] if k % 2 else [False, False]  # items 0 or 1
             for k in range(20)}
    a = bootstrap_ci(tight, 400, 0.95, seed=1)
    b = bootstrap_ci(split, 400, 0.95, seed=1)
    assert a["point"] == b["point"] == 0.5
    assert b["half_width"] > a["half_width"] * 3


def test_bootstrap_single_item_is_degenerate():
    """One item is one cluster: the interval collapses. This is the signature
    the single-item bug would have shown had anything been looking.
    """
    ci = bootstrap_ci({"only": [True, False, True, False]}, 200, 0.95, seed=1)
    assert ci["items"] == 1
    assert ci["half_width"] == 0.0


def test_marginal_pairs_on_items():
    """A constant per-item offset must come back with a tight interval around
    that offset - item difficulty cancels within each resample when the two arms
    are drawn on the same items.
    """
    base = {f"i{k}": [k % 2 == 0] * 4 for k in range(30)}
    treat = {f"i{k}": [True] * 4 for k in range(30)}
    m = marginal_ci(treat, base, 600, 0.95, seed=1)
    assert m["point"] == pytest.approx(0.5, abs=0.02)
    assert not m["crosses_zero"]


# ---------------------------------------------------------------------------
# 9.4
# ---------------------------------------------------------------------------

def test_screen_flags_the_fixture_mcq_bank(store):
    """data/items.json currently carries 3 distinct mcq option sets over 159
    items. If this test starts failing because the count went UP, the bank was
    regenerated and that is the good outcome - update the expectation.
    """
    _, struct = distractor_screen.structural_screen(store)
    assert struct["distinct_option_sets"] < struct["items"]


def test_screen_reports_effective_candidate_set(store):
    """The narrowing lights candidate_floor nodes, but some are outside any
    plausible region. The screen must report the LIVE count, because that is
    what sets the real guess probability.
    """
    _, behav = distractor_screen.behavioural_screen(store, trials=100, seed=1)
    assert behav["mean_live"] < behav["mean_lit"]
    assert behav["effective_guess_probability"] > behav["policy_ceiling"]


def test_screen_suppresses_bank_level_rules_from_per_item_list(store):
    """A rule firing on every item is one finding, not 159. Guards the report
    against regressing to the 216-row version nobody can action.
    """
    result = distractor_screen.run(trials=50)
    per_item = [f for f in result["_objects"] if f.rule not in distractor_screen.BANK_LEVEL]
    assert len(per_item) < 40
