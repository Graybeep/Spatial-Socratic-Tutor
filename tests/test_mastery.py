"""Mastery is the one place a bug is invisible. CLAUDE.md §7.

These tests encode the arguments the spec makes, not just the arithmetic - in
particular the reason the naive `correct * (1 - 0.25*hint)` form was rejected.
"""
from __future__ import annotations

import math

from server import mastery
from server.mastery import HINT_MAX, THRESHOLD, mastery as to_mastery, update


class FakeGraph:
    def __init__(self, prereqs):
        self._prereqs = prereqs
        self.node_ids = list(prereqs)

    def prereqs(self, node_id):
        return self._prereqs.get(node_id, [])


def test_correct_raises_theta_wrong_lowers_it():
    assert update(0.0, 0.5, True, 0, 0) > 0.0
    assert update(0.0, 0.5, False, 0, 0) < 0.0


def test_hinted_correct_gains_less_than_unhinted_correct():
    """A hint makes the item easier, so getting it right proves less."""
    unhinted = update(0.0, 0.5, True, 0, 0)
    hinted = update(0.0, 0.5, True, 3, 0)
    assert 0 < hinted < unhinted


def test_hinted_wrong_loses_more_than_unhinted_wrong():
    """The core claim in CLAUDE.md §7: failing WITH help is stronger evidence of
    not knowing than failing without it."""
    unhinted = update(0.0, 0.5, False, 0, 0)
    hinted = update(0.0, 0.5, False, 3, 0)
    assert hinted < unhinted < 0


def test_heavily_hinted_correct_is_not_identical_to_wrong():
    """The failure mode of the rejected `1 - 0.25*hint` form: at hint 4 it
    collapses a correct answer onto a wrong one and throws the signal away."""
    correct = update(0.0, 0.5, True, HINT_MAX, 0)
    wrong = update(0.0, 0.5, False, HINT_MAX, 0)
    assert correct > wrong
    assert correct > 0.0


def test_hint_level_is_clamped_at_hint_max():
    assert update(0.0, 0.5, True, HINT_MAX, 0) == update(0.0, 0.5, True, HINT_MAX + 7, 0)


def test_learning_rate_decays_with_observations():
    first = abs(update(0.0, 0.5, True, 0, 0))
    later = abs(update(0.0, 0.5, True, 0, 20))
    assert later < first
    # ...but never to zero: k floors at K_MIN so the model stays responsive.
    assert abs(update(0.0, 0.5, True, 0, 10_000)) > 0.0


def test_mastery_is_bounded_and_monotone():
    assert 0.0 <= to_mastery(-50) < 0.01
    # Saturates to exactly 1.0 in float64 well before theta 50; that is fine, the
    # point is it never exceeds the [0,1] range the client colours from.
    assert 0.99 < to_mastery(50) <= 1.0
    assert to_mastery(0.0) == 0.5
    assert to_mastery(1.0) > to_mastery(0.0)


def test_decay_prereqs_does_not_mutate_input():
    original = {"a": 0.5, "b": 0.5, "c": 0.5}
    out = mastery.decay_prereqs(original, ["a", "b"])
    assert original == {"a": 0.5, "b": 0.5, "c": 0.5}
    assert out["a"] < 0.5 and out["b"] < 0.5
    assert out["c"] == 0.5


def test_decay_prereqs_ignores_unknown_nodes():
    assert mastery.decay_prereqs({"a": 0.5}, ["nope"]) == {"a": 0.5}


def test_next_node_respects_prerequisites():
    graph = FakeGraph({"root": [], "mid": ["root"], "leaf": ["mid"]})
    unmastered = {"root": 0.1, "mid": 0.1, "leaf": 0.1}
    # Only root is ready; mid and leaf are gated even though they score lower.
    assert mastery.next_node(graph, unmastered) == "root"

    mastered_root = {"root": 0.9, "mid": 0.2, "leaf": 0.1}
    assert mastery.next_node(graph, mastered_root) == "mid"


def test_next_node_picks_lowest_mastery_among_ready():
    graph = FakeGraph({"a": [], "b": [], "c": []})
    assert mastery.next_node(graph, {"a": 0.5, "b": 0.2, "c": 0.4}) == "b"


def test_next_node_is_deterministic_on_ties():
    graph = FakeGraph({"a": [], "b": [], "c": []})
    tied = {"a": 0.3, "b": 0.3, "c": 0.3}
    assert mastery.next_node(graph, tied) == "a"
    assert all(mastery.next_node(graph, tied) == "a" for _ in range(10))


def test_next_node_returns_none_when_everything_is_mastered():
    graph = FakeGraph({"a": [], "b": ["a"]})
    assert mastery.next_node(graph, {"a": 0.9, "b": 0.9}) is None


def test_backtrack_target_is_weakest_prereq():
    graph = FakeGraph({"leaf": ["p1", "p2"], "p1": [], "p2": []})
    assert mastery.backtrack_target(graph, "leaf", {"p1": 0.8, "p2": 0.3}) == "p2"
    assert mastery.backtrack_target(graph, "p1", {}) is None


def test_repeated_correct_answers_cross_threshold():
    """Sanity: a student who keeps answering correctly does eventually master a
    node. A sign error anywhere above would show up here."""
    theta = 0.0
    for n in range(12):
        theta = update(theta, 0.4, True, 0, n)
    assert to_mastery(theta) >= THRESHOLD
