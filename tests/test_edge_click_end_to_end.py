"""The `edge_click` answer path, driven over HTTP.

Edge items had unit coverage (`test_edge_item_anchors.py` and the eval-side
tests) and none of it went through the endpoint: only `test_session_exit.py` and
`test_response_pairing.py` use the client fixture, and neither answers with an
edge. So grading an edge, the reversed-edge case and the `from`/`to` wire alias
had never been exercised end to end.

**Selection is bypassed on purpose, and the reason is not that edge items are
unreachable.** A correct-answer drive does reach one - measured at turn 22 of 25
- but the item it reaches is `scorable: false`, which is the common case: 32 of
the 49 edge items are determined by their anchor and score nothing. Driving to a
*scorable* edge item is what cannot be arranged from outside, because
`next_node` picks a node and `_pick_item` picks its item and neither takes a
request. So these tests seed `start_item` on a scorable edge item and then use
real requests for everything that matters - grading, mastery, the response
contract. Only the choice of item is forced.

(An earlier version of this docstring said a drive never reaches the path at
all. That came from a wrong-answer drive, which keeps the student on early nodes
and never gets there. The claim was wrong and the conclusion happened to be
right, which is the more dangerous shape of the two.)

The alias matters more than it looks: `from` is a Python keyword, so `EdgeRef`
declares `from_` with `alias="from"`. The client sends `{from, to}`. If that
mapping broke, every edge answer would 422 and the failure would look like a
client bug.
"""
from __future__ import annotations

import pytest

from server import turn as turn_mod

from .conftest import turn


def _scorable_edge_item(store):
    """A scorable edge item, so grading moves theta and is observable.

    Unscorable edge items exist and are the majority (32 of 49 are determined by
    their anchor); they would exercise the transport and prove nothing about
    grading.
    """
    for node_id in store.node_ids:
        for item in store.items_for(node_id):
            if item.type == "edge_click" and turn_mod._is_scorable(item):
                return item
    pytest.skip("no scorable edge item in the bank")


def _serve_edge_item(client, session, db, item):
    """Put the session on `item` and take one turn so it is the open question."""
    turn(client, session)
    state = db.get(session)
    state.start_item(item.node_id, item.id)
    db.save(state)
    data = turn(client, session, {"type": "text", "text": "ask me"})
    assert data["expects"] == "edge_click", "setup failed; this proved nothing"
    return data


def _endpoints(item):
    head, tail = item.answer.split("->")
    return head, tail


def test_a_correct_edge_is_graded_and_moves_mastery(client, session, store):
    from server import main as main_mod

    item = _scorable_edge_item(store)
    _serve_edge_item(client, session, main_mod.DB, item)
    head, tail = _endpoints(item)

    before = main_mod.DB.get(session).theta_map[item.node_id]
    data = turn(client, session, {"type": "edge_click",
                                  "edge": {"from": head, "to": tail}})
    after = main_mod.DB.get(session).theta_map[item.node_id]

    assert data["action"] == "advance"
    assert after > before, "a correct edge answer did not move mastery"


def test_a_reversed_edge_is_wrong(client, session, store):
    """Direction is the whole content of a prerequisite edge. Accepting
    `to -> from` would score a student correct for knowing two concepts are
    related while getting the dependency backwards."""
    from server import main as main_mod

    item = _scorable_edge_item(store)
    _serve_edge_item(client, session, main_mod.DB, item)
    head, tail = _endpoints(item)

    before = main_mod.DB.get(session).theta_map[item.node_id]
    data = turn(client, session, {"type": "edge_click",
                                  "edge": {"from": tail, "to": head}})
    after = main_mod.DB.get(session).theta_map[item.node_id]

    assert data["action"] != "advance"
    assert after < before, "a reversed edge was not graded wrong"


def test_the_wire_alias_is_what_the_client_sends(client, session, store):
    """`from` is a Python keyword; EdgeRef declares `from_` aliased to it. The
    client sends `{from, to}`. A break here would 422 every edge answer and read
    as a client bug."""
    from server import main as main_mod

    item = _scorable_edge_item(store)
    _serve_edge_item(client, session, main_mod.DB, item)
    head, tail = _endpoints(item)

    r = client.post("/turn", json={
        "session_id": session,
        "response": {"type": "edge_click", "edge": {"from": head, "to": tail}},
    })
    assert r.status_code == 200, r.text


def test_the_answer_edge_stays_clickable_without_being_the_only_one(
    client, session, store
):
    """The leak question for the edge channel.

    Both endpoints of an edge answer stay lit at every rung so the answer can be
    clicked at all - that is deliberate. The failure mode is narrowing to the
    answer alone, which would hand it over in the payload the way `node_id` once
    did (see identity-leakage.md). Measured here: the answer is present and it
    has company.
    """
    from server import main as main_mod

    item = _scorable_edge_item(store)
    data = _serve_edge_item(client, session, main_mod.DB, item)
    head, tail = _endpoints(item)

    lit = data["graph_state"]["focus_edges"]
    assert any(e["from"] == head and e["to"] == tail for e in lit), (
        "the answer edge was not clickable")
    assert len(lit) > 1, (
        f"focus_edges narrowed to {len(lit)} - the answer is the payload")


def test_two_failed_edges_backtrack(client, session, store):
    """§7 on the edge path. The two-failure rule is node-level and must not
    depend on the answer type."""
    from server import main as main_mod

    item = _scorable_edge_item(store)
    _serve_edge_item(client, session, main_mod.DB, item)
    head, tail = _endpoints(item)
    wrong = {"type": "edge_click", "edge": {"from": tail, "to": head}}

    first = turn(client, session, wrong)
    assert first["action"] != "backtrack", (
        "backtracked on the FIRST failure; the rule is two consecutive")

    second = turn(client, session, wrong)
    landed = main_mod.DB.get(session).current_node

    assert second["action"] == "backtrack"
    assert landed in store.prereqs(item.node_id), (
        f"backtracked to {landed!r}, which is not a prerequisite of "
        f"{item.node_id!r}")
