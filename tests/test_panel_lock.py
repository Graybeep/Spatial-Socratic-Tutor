"""`panel_locked` - the node panel's eligibility gate.

The node panel shows a node's one-sentence definition, and for a node whose item
asks what that node does, the definition IS the answer, lifted from the chapter.
So it must not open while an item whose answer is a node is under way.

The client's first version of this gate read `expects`: panel opens when the
tutor is not waiting for a point. That is a PER-TURN test of a PER-ITEM
property, and the hole is one turn wide:

    hint level 3, 9 nodes lit
    -> answer wrong on purpose
    -> tutor follows up with something that does not want a click
    -> `expects` is now "text", the panel is live, the narrowing is still up
    -> read the 9 definitions, answer next turn

Today the server pins `expects` to `item.type` for every turn an item is open
(turn.py, `expects = "text" if item is None else item.type`), so that sequence
cannot actually be produced. That is not a defence, it is luck: the client had
no way to know the invariant, nothing asserted it, and one `explain` branch that
sets expects="text" while keeping the item open makes it reachable. The bug was
the dependency, not its current exploitability.

So the server sends the gate, derived from the item, and these tests pin BOTH
halves: the value is right, and it does not track `expects`.

The turn boundary is the same kind of blind spot as the lit set. eval §9.1's
simulated students model what the graph shows at the moment of answering; a
channel that opens between two turns of one item is invisible to them, so no
number here would have caught it.
"""
from __future__ import annotations

import pytest

from server import turn as turn_mod
from server.config import CONFIG
from server.schemas import Call1Decision, GraphState
from tests.conftest import turn, wrong_response


def _visually_answerable(data, store) -> bool:
    return store.item(data["item"]["id"]).visually_answerable


def test_panel_locked_matches_the_item_not_the_turn(client, session, store):
    """Every turn of one item reports the same lock, and it is the item's."""
    data = turn(client, session)
    item_id = data["item"]["id"]
    expected = _visually_answerable(data, store)

    seen = 0
    for _ in range(CONFIG.turn_budget):
        assert data["panel_locked"] == expected, (
            f"turn {data['turn_id']} of item {item_id} reported "
            f"panel_locked={data['panel_locked']}, expected {expected}"
        )
        seen += 1
        data = turn(client, session, wrong_response(data, store))
        if data["item"] is None or data["item"]["id"] != item_id:
            break

    # A one-turn item would make the assertion above vacuous.
    assert seen >= 3, f"only saw {seen} turns on one item; the loop proved nothing"


def test_panel_locked_is_true_for_a_node_answer_item(client, session, store):
    """The case that matters: the answer is a node, so no node may be read."""
    data = turn(client, session)
    if not _visually_answerable(data, store):
        pytest.skip("opening item is not visually_answerable")
    assert data["panel_locked"] is True


def test_panel_locked_is_false_when_the_answer_is_not_on_the_graph(client, session, store):
    """CLAUDE.md §3 expects most of a real bank to be visually_answerable:false.

    Those items cannot be leaked by reading a node - the answer is a
    proposition, not a node - so locking them would cost the student the panel
    for no gain. The fixture is 40% visually_answerable, so this path exists.
    """
    data = turn(client, session)
    for _ in range(CONFIG.turn_budget * 6):
        if data["item"] is not None and not _visually_answerable(data, store):
            assert data["panel_locked"] is False
            return
        data = turn(client, session, wrong_response(data, store))
        if data["session_complete"]:
            break
    pytest.skip("no visually_answerable:false item reached in the budget")


def test_panel_locked_does_not_track_expects():
    """The exploit shape, asserted directly.

    An item that is open with `expects` set to something that is not a click is
    exactly the state the per-turn gate got wrong. It is unreachable through the
    server today; it is constructed here so that if a future action ever makes
    it reachable, this file fails instead of the leak shipping.
    """
    class _Item:
        id = "itm_test"
        visually_answerable = True
        type = "node_click"
        difficulty = 0.4

    phase1 = turn_mod.Phase1(
        state=None,
        decision=Call1Decision(
            student_state="stuck",
            diagnosis="constructed",
            correct=False,
            requested_action="explain",
            requested_hint_level=0,
            focus_nodes=[],
            expects="text",
        ),
        action="explain",
        hint_level=0,
        # The whole point: not a click, item still open.
        expects="text",
        graph_state=GraphState(
            current_node=None, focus_nodes=[], focus_edges=[], dimmed_nodes=[], mastery={}
        ),
        item=_Item(),
    )

    assert phase1.reveals_answer() is True, (
        "panel_locked fell to expects. The gate is a property of the item; a "
        "turn that stops asking for a click does not stop the definition being "
        "the answer."
    )


def test_panel_locked_rides_the_first_stream_event(client, session):
    """It has to be live when the graph becomes interactive, not at `done`.

    Arriving with the utterance would leave the panel open for ~1.4s over an
    already-narrowed graph, which is the only window in the turn that matters.
    """
    import json

    with client.stream(
        "POST", "/turn?stream=true", json={"session_id": session, "response": None}
    ) as r:
        first = {}
        for line in r.iter_lines():
            if line.startswith("data: "):
                first = json.loads(line[len("data: "):])
                break

    assert "panel_locked" in first, "phase 1 does not carry the panel gate"
