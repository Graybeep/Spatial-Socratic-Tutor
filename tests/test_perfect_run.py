"""What a flawless student does to the graph, and what the demo can promise.

Measured on day 13 (docs/schedule.md): answering every item correctly masters
ZERO nodes in the first 15 turns and one by turn 20. A three-minute walkthrough
is 15-25 turns, so §8's "mastery recolours nodes" is not a change the video can
show. That is a scripting fact, not a defect - §7 fixes the constants and the
learning rate decays with n_obs on purpose.

These tests pin the invariants a perfect run must hold, NOT the exact curve. A
test asserting "0 mastered at turn 15" would fail the day someone legitimately
improves the item bank, which is the wrong thing to make hard.
"""
from __future__ import annotations

import pytest

from server.config import CONFIG
from server import mastery as M
from .conftest import correct_response, turn


def _drive(client, session, store, n):
    """n turns of perfect play; returns the mastery map after each."""
    snapshots = []
    data = turn(client, session)
    for _ in range(n):
        if data.get("session_complete") or data.get("item") is None:
            break
        data = turn(client, session, correct_response(data, store))
        snapshots.append(dict(data["graph_state"]["mastery"]))
    return snapshots


def test_two_correct_answers_cross_the_threshold_from_a_standing_start():
    """§7's intended shape. If this changes, the demo-pacing note in
    docs/schedule.md is stale and the video script needs re-reading."""
    for difficulty in (0.3, 0.4, 0.5, 0.6):
        theta = 0.0
        for n in range(2):
            theta = M.update(theta, difficulty, True, 0, n)
        assert M.mastery(theta) >= CONFIG.mastery_threshold, (
            f"difficulty {difficulty}: two correct answers no longer reach "
            f"mastery {CONFIG.mastery_threshold}"
        )


def test_one_correct_answer_does_not():
    """The other half. A single observation crossing the bar would make mastery
    a participation trophy, and `next_node` would advance off one lucky click."""
    theta = M.update(0.0, 0.4, True, 0, 0)
    assert M.mastery(theta) < CONFIG.mastery_threshold


def test_perfect_play_never_lowers_a_mastery(client, session, store):
    """Prereq decay fires only on failure (§7), so nothing should go down.

    This is the invariant worth guarding: a perfect run that silently walked a
    node backwards would corrupt `next_node` selection and be invisible on screen
    at demo length, because so little moves in 25 turns anyway.
    """
    snapshots = _drive(client, session, store, 25)
    assert len(snapshots) >= 10, "the session stalled; a perfect run should continue"
    for before, after in zip(snapshots, snapshots[1:]):
        dropped = {k: (before[k], after[k]) for k in before
                   if after.get(k, 0) < before[k] - 1e-9}
        assert not dropped, f"mastery fell during perfect play: {dropped}"


def test_perfect_play_does_make_progress(client, session, store):
    """Slow is the finding; stuck would be a bug."""
    snapshots = _drive(client, session, store, 25)
    first, last = snapshots[0], snapshots[-1]
    assert sum(last.values()) > sum(first.values()), (
        "25 correct answers moved no mastery at all"
    )


def test_narrowing_is_what_the_demo_can_actually_show(client, session, store):
    """The video is scripted around this, not around mastery colour: the map
    narrows on the turn after the first wrong answer, long before any node
    changes colour (docs/schedule.md, day 13)."""
    data = turn(client, session)
    answer = store.item(data["item"]["id"]).answer
    wrong = next(n for n in store.node_ids if n != answer)
    data = turn(client, session, {"type": "node_click", "node_id": wrong})

    lit = data["graph_state"]["focus_nodes"]
    dimmed = data["graph_state"]["dimmed_nodes"]
    assert dimmed, "nothing dimmed after a wrong answer; the demo has no visual"
    assert 0 < len(lit) < len(store.node_ids)
