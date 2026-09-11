"""The session-level circuit breaker — above CLAUDE.md §7, not inside it.

THE GAP IT CLOSES

§6 layer 3 caps turns on ONE item: 8 turns, forced reveal, zero mastery. §7
routes to the next node, and on two consecutive failures backtracks to the
weakest prerequisite. Both are correct and neither answers "when do we stop".

A student who answers nothing therefore backtracks between a node and its
prerequisite forever. Measured before this existed: **400 turns, 0 nodes
mastered, 2 distinct nodes visited, no exit.** Every per-item guard fired
exactly as designed the whole way.

That is not an edge case for this demo. Its centrepiece is a volunteer stuck on
purpose, watching the graph narrow while the tutor names nothing — the single
input most likely to walk straight into the one path with no exit.

WHERE THE CAP LIVES, AND WHY IT MATTERS

Above §7, reading session-level state only. §7 still answers "which node next";
it is simply not asked once the ceiling is reached. `turns_on_item` resets on
every item, which is what makes it a budget; `forced_reveals` never resets,
which is what makes this a circuit breaker.
"""
from __future__ import annotations

import pytest

from server.config import CONFIG
from server.graph_store import GraphStore
from server.state import Store

from .conftest import config_override, correct_response, turn, wrong_response


def _drive(client, session, store, policy, limit=600):
    data = turn(client, session)
    reveals = 0
    for _ in range(limit):
        if data["resolved_with_support"]:
            reveals += 1
        if data["session_complete"]:
            return data, reveals
        data = turn(client, session, policy(data, store))
    return None, reveals


# --- the breaker -----------------------------------------------------------

def test_a_student_who_answers_nothing_reaches_an_exit(client, session, store):
    """The whole point. Before the breaker this ran 400 turns and never ended."""
    data, _ = _drive(client, session, store, wrong_response)
    assert data is not None, "no exit: the session ran to the drive limit"
    assert data["session_state"] == "concluded"
    assert data["session_end_reason"] == "support_ceiling"


def test_it_trips_at_the_configured_count_not_a_literal(client, session, store):
    with config_override(conclude_after_forced_reveals=2):
        data, reveals = _drive(client, session, store, wrong_response)
    assert reveals == 2, f"expected 2 forced reveals before concluding, saw {reveals}"
    assert data["session_state"] == "concluded"


def test_the_default_is_three(client, session, store):
    data, reveals = _drive(client, session, store, wrong_response)
    assert reveals == CONFIG.conclude_after_forced_reveals


def test_a_conclusion_loads_no_further_item(client, session, store):
    """"A summary, not another item." A terminal turn that still shipped an item
    would put the student back in the loop the breaker exists to leave."""
    data, _ = _drive(client, session, store, wrong_response)
    assert data["item"] is None
    assert data["expects"] == "text"
    assert data["panel_locked"] is False
    assert data["mcq_options"] == []


def test_the_closing_utterance_is_not_the_advance_line(client, session, store):
    """`advance` says "next idea", which on a terminal turn is a promise the
    server cannot keep."""
    data, _ = _drive(client, session, store, wrong_response)
    assert data["utterance"].strip()
    assert "next idea" not in data["utterance"].lower()


# --- the two endings are different news ------------------------------------

def test_finishing_the_graph_is_mastered_not_concluded(client, session, store):
    data, reveals = _drive(client, session, store, correct_response)
    assert data is not None
    assert data["session_state"] == "mastered"
    assert data["session_end_reason"] == "graph_mastered"
    assert reveals == 0


def test_the_two_endings_do_not_share_an_utterance(client, store):
    a = client.post("/session").json()["session_id"]
    strong, _ = _drive(client, a, store, correct_response)
    b = client.post("/session").json()["session_id"]
    weak, _ = _drive(client, b, store, wrong_response)
    assert strong["utterance"] != weak["utterance"], (
        "a student who never finished the chapter is being told they did"
    )


def test_a_terminal_turn_clears_the_item_on_both_paths(client, store):
    """The mastered path used to keep the last answered item, so a finished
    session shipped expects="edge_click" and panel_locked=true beside item=null
    - the client told to collect an answer for something that is not there."""
    for policy in (correct_response, wrong_response):
        sid = client.post("/session").json()["session_id"]
        data, _ = _drive(client, sid, store, policy)
        assert data["item"] is None, policy.__name__
        assert data["expects"] == "text", policy.__name__
        assert data["panel_locked"] is False, policy.__name__


# --- the derived field cannot drift ----------------------------------------

def test_session_complete_is_derived_and_agrees(client, session, store):
    """Two fields answering overlapping questions and assigned separately is the
    failure this repo has hit four times. This one is computed."""
    data = turn(client, session)
    assert data["session_complete"] == (data["session_state"] != "active")
    ended, _ = _drive(client, session, store, wrong_response)
    assert ended["session_complete"] is True
    assert ended["session_state"] == "concluded"


def test_an_active_session_carries_no_end_reason(client, session):
    data = turn(client, session)
    assert data["session_state"] == "active"
    assert data["session_end_reason"] is None


# --- §7 is untouched -------------------------------------------------------

def test_the_breaker_does_not_change_which_node_seven_would_pick(store):
    """The cap sits ABOVE §7. Nothing here may alter next_node or backtrack:
    they answer "which node", and the breaker answers "whether to keep going"."""
    from server import mastery as mastery_mod

    mastery = {n: 0.0 for n in store.node_ids}
    before = mastery_mod.next_node(store, mastery)
    with config_override(conclude_after_forced_reveals=1):
        assert mastery_mod.next_node(store, mastery) == before


def test_backtracking_still_happens_before_the_ceiling(client, session, store):
    """The breaker must not pre-empt §7's teaching behaviour - it only ends the
    session once §6 layer 3 has fired enough times.

    A student who answers nothing never reaches a backtrack at all, and not
    because of the breaker: §7 starts at a root node (`flow`, `throughput`,
    `queuing_delay` are the three with no prerequisites), and `backtrack_target`
    of a root is None. So this has to walk PAST the roots first, then fail - the
    naive version of this test passed vacuously against a claim it never made.
    """
    from server import main as main_mod

    data = turn(client, session)
    # Correct answers until the open item's node actually has a prerequisite.
    for _ in range(60):
        node = main_mod.DB.get(session).current_node
        if node and store.prereqs(node):
            break
        data = turn(client, session, correct_response(data, store))
    else:
        pytest.skip("never reached a node with prerequisites")

    actions = []
    for _ in range(20):
        if data["session_complete"]:
            break
        data = turn(client, session, wrong_response(data, store))
        actions.append(data["action"])
    assert "backtrack" in actions, (
        f"§7 never backtracked from a node that has prerequisites; saw {actions}"
    )


# --- persistence -----------------------------------------------------------

def test_the_reveal_count_survives_a_reload(client, session, store):
    """Session-level state, so it lives in the session row. A counter kept only
    in memory would reset on every process restart and quietly un-break the
    breaker."""
    from server import main as main_mod

    data = turn(client, session)
    for _ in range(20):
        if data["resolved_with_support"] or data["session_complete"]:
            break
        data = turn(client, session, wrong_response(data, store))

    reloaded = main_mod.DB.get(session)
    assert reloaded.forced_reveals >= 1
    assert reloaded.support_ceiling_reached is (
        reloaded.forced_reveals >= CONFIG.conclude_after_forced_reveals
    )
