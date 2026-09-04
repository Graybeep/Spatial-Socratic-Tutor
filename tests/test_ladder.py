"""The narrowing ladder. CLAUDE.md §9.1 and §9.2.

The schedule is a research variable, not a constant. These tests pin the
properties the eval depends on; they do not pin the numbers, because sweeping the
numbers is the point.
"""
from __future__ import annotations

import pytest

from server import mock_tutor
from server.config import CONFIG
from tests.conftest import config_override, turn, wrong_response


def hint_sequence(client, session_id, store, limit=6):
    """Drive one item with wrong answers and report (action, hint, lit) per turn."""
    data = turn(client, session_id)
    total = len(store.node_ids)
    out = []
    item_id = data["item"]["id"]
    for _ in range(limit):
        nxt = wrong_response(data, store)
        if nxt is None:
            break
        data = turn(client, session_id, nxt)
        if data["item"] is None or data["item"]["id"] != item_id:
            break
        lit = total - len(data["graph_state"]["dimmed_nodes"])
        out.append((data["action"], data["hint_level"], lit))
    return out


# ---------------------------------------------------------------------------
# the guess-probability floor - the headline risk in §9.1
# ---------------------------------------------------------------------------

def test_floor_is_derived_from_guess_probability():
    with config_override(max_guess_probability=0.2):
        assert CONFIG.candidate_floor == 5
    with config_override(max_guess_probability=0.1):
        assert CONFIG.candidate_floor == 10
    with config_override(max_guess_probability=0.5):
        assert CONFIG.candidate_floor == 2


def test_schedule_is_clamped_up_to_the_floor():
    """A schedule that would narrow to 2 gets raised to the floor.

    2-of-N is a coin flip for a student who never reasons; under §9.1's own
    definition that is ~50% effective leakage from the visual channel alone, and
    it would lose to the verbal baseline the project exists to beat.
    """
    with config_override(narrow_schedule_raw="0,12,6,3,2", max_guess_probability=0.2):
        assert CONFIG.narrow_schedule == [0, 12, 6, 5, 5]
        assert min(n for n in CONFIG.narrow_schedule if n > 0) >= CONFIG.candidate_floor


def test_schedule_is_padded_to_hint_max():
    with config_override(narrow_schedule_raw="0,20"):
        assert len(CONFIG.narrow_schedule) == CONFIG.hint_max + 1
        assert CONFIG.narrow_schedule == [0, 20, 20, 20, 20]


def test_live_ladder_never_narrows_below_the_floor(client, session, store):
    with config_override(ladder_mode="visual_only"):
        seq = hint_sequence(client, session, store)
    assert seq, "expected at least one hint turn"
    for _action, _hint, lit in seq:
        assert lit >= CONFIG.candidate_floor, f"narrowed to {lit}, floor is {CONFIG.candidate_floor}"


def test_schedule_is_swept_not_baked(client, session, store):
    """§9.1 varies the terminal set size; the server must follow the config."""
    with config_override(ladder_mode="visual_only", narrow_schedule_raw="0,30,24,18,12"):
        seq = hint_sequence(client, session, store)
    lits = [lit for _a, _h, lit in seq]
    assert lits[0] == 30, lits
    assert min(lits) == 12, lits


# ---------------------------------------------------------------------------
# ladder modes - §9.2 needs the arms pure
# ---------------------------------------------------------------------------

def test_interleaved_mixes_both_channels(client, session, store):
    with config_override(ladder_mode="interleaved"):
        seq = hint_sequence(client, session, store)
    actions = {a for a, _h, _l in seq}
    assert "hint_visual" in actions and "hint_verbal" in actions


def test_interleaved_bottoms_out_verbal():
    """The last rung says something rather than dimming to the floor and stopping."""
    with config_override(ladder_mode="interleaved"):
        assert mock_tutor.hint_action_for_level(CONFIG.hint_max) == "hint_verbal"


def test_visual_only_narrows_until_the_ladder_is_spent(client, session, store):
    """Every hint is visual WHILE the schedule still has room.

    Once it flattens at the floor, a further hint_visual would dim nothing while
    the tutor implied it had - so the server substitutes hint_verbal. Those
    trailing verbal turns are the no-op guard working, not the mode leaking.
    """
    with config_override(ladder_mode="visual_only"):
        seq = hint_sequence(client, session, store)
    assert seq
    narrowing = [(a, lit) for a, _h, lit in seq]
    # Every turn that actually reduced the lit set must have been visual.
    for i in range(1, len(narrowing)):
        action, lit = narrowing[i]
        _prev_action, prev_lit = narrowing[i - 1]
        if lit < prev_lit:
            assert action == "hint_visual", f"a {action} narrowed the graph"
    assert narrowing[0][0] == "hint_visual"


def test_verbal_only_never_dims_anything(client, session, store):
    """The rendering case the client would otherwise meet for the first time in
    week 4: hints arrive, the graph never changes."""
    with config_override(ladder_mode="verbal_only"):
        data = turn(client, session)
        item_id = data["item"]["id"]
        for _ in range(5):
            nxt = wrong_response(data, store)
            if nxt is None:
                break
            data = turn(client, session, nxt)
            assert data["graph_state"]["dimmed_nodes"] == []
            assert data["graph_state"]["focus_nodes"] == []
            if data["item"] is None or data["item"]["id"] != item_id:
                break


def test_verbal_hints_do_not_narrow(client, session, store):
    """Confounding the channels is what makes §9.2 unrunnable: a verbal hint that
    also dims cannot have its elimination attributed to either channel."""
    with config_override(ladder_mode="interleaved"):
        seq = hint_sequence(client, session, store)
    for i in range(1, len(seq)):
        action, _hint, lit = seq[i]
        _prev_action, _prev_hint, prev_lit = seq[i - 1]
        if action == "hint_verbal":
            assert lit == prev_lit, f"a verbal hint narrowed {prev_lit} -> {lit}"


# ---------------------------------------------------------------------------
# monotonicity
# ---------------------------------------------------------------------------

def test_narrowing_is_monotone_and_nests(client, session, store):
    """Each lit set must be a subset of the previous one. A student must not be
    able to recover an eliminated candidate, and §9.2's excluded sets are only
    coherent if they nest."""
    with config_override(ladder_mode="visual_only"):
        data = turn(client, session)
        item_id = data["item"]["id"]
        previous = None
        for _ in range(5):
            nxt = wrong_response(data, store)
            if nxt is None:
                break
            data = turn(client, session, nxt)
            if data["item"] is None or data["item"]["id"] != item_id:
                break
            lit = set(store.node_ids) - set(data["graph_state"]["dimmed_nodes"])
            if previous is not None:
                assert lit <= previous, f"narrowing widened: {len(previous)} -> {len(lit)}"
            previous = lit


def test_candidate_order_is_a_stable_prefix_chain(store):
    """lit_nodes at every level is a prefix of one fixed order, which is what
    makes nesting structural rather than incidental."""
    item = store.bank.items[0]
    order = mock_tutor.candidate_order(store, item)
    assert order[0] == item.answer
    assert len(order) == len(store.node_ids)
    assert set(order) == set(store.node_ids)
    with config_override(narrow_schedule_raw="0,30,20,10,5"):
        sets = [mock_tutor.lit_nodes(store, item, lvl) for lvl in range(1, 5)]
    for lit in sets:
        assert lit == order[: len(lit)]


def test_candidate_order_differs_across_items(store):
    """Eliminating in the same order for every item would let a student learn the
    ladder instead of the material."""
    a, b = store.bank.items[0], store.bank.items[7]
    assert mock_tutor.candidate_order(store, a) != mock_tutor.candidate_order(store, b)


def test_answer_survives_every_narrowing_level(store):
    """A hint that dims the answer is worse than no hint."""
    node_ids = set(store.node_ids)
    for item in store.bank.items[:40]:
        # Only meaningful where the answer IS a node. Edge answers and
        # proposition answers (visually_answerable false, the majority of a real
        # bank per CLAUDE.md 3) have no node to survive the dimming.
        if not item.visually_answerable or item.answer not in node_ids:
            continue
        for level in range(1, CONFIG.hint_max + 1):
            lit = mock_tutor.lit_nodes(store, item, level)
            if lit:
                assert item.answer in lit, f"{item.id} level {level} dimmed its own answer"


@pytest.mark.parametrize("mode", ["interleaved", "visual_only", "verbal_only"])
def test_every_mode_produces_a_valid_turn(client, session, store, mode):
    with config_override(ladder_mode=mode):
        data = turn(client, session)
        assert data["action"] in {
            "ask", "hint_visual", "hint_verbal", "advance", "backtrack", "explain"
        }


# ---------------------------------------------------------------------------
# the no-op visual hint
# ---------------------------------------------------------------------------

def test_a_spent_ladder_substitutes_a_verbal_hint(client, session, store):
    """A hint_visual that dims nothing is worse than no hint.

    Clamping guarantees this case exists: 0,12,6,3,2 becomes 0,12,6,5,5, so the
    last rung would leave the graph untouched while the tutor said "narrowing
    further". On a projector that reads as a broken demo; to a student it reads
    as being lied to.
    """
    with config_override(ladder_mode="visual_only", narrow_schedule_raw="0,12,6,3,2",
                         max_guess_probability=0.2):
        assert CONFIG.narrow_schedule == [0, 12, 6, 5, 5]
        seq = hint_sequence(client, session, store)

    for i in range(1, len(seq)):
        action, _hint, lit = seq[i]
        _pa, _ph, prev_lit = seq[i - 1]
        if action == "hint_visual":
            assert lit < prev_lit, (
                f"hint_visual left the lit set at {lit}; it must narrow or "
                f"give way to hint_verbal"
            )


def test_would_narrow_is_false_once_the_schedule_flattens(store):
    item = store.bank.items[0]
    with config_override(narrow_schedule_raw="0,12,6,3,2", max_guess_probability=0.2):
        assert mock_tutor.would_narrow(store, item, 0) is True
        assert mock_tutor.would_narrow(store, item, 1) is True
        assert mock_tutor.would_narrow(store, item, 2) is True
        assert mock_tutor.would_narrow(store, item, 3) is False  # 5 -> 5


def test_verbal_only_never_reports_a_narrowing_opportunity(store):
    item = store.bank.items[0]
    with config_override(ladder_mode="verbal_only"):
        assert mock_tutor.would_narrow(store, item, 0) is False
