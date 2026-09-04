"""MCQ options: the one place item data legitimately reaches the client.

Because MCQ options ARE the key plus its distractors, the blanket claim "no
distractor ever appears in a response" is false and always was. The honest
statement is narrower, and these tests are where it is written down:

  - the item PROMPT never appears, on any turn
  - answer aliases never appear on non-MCQ turns
  - on an MCQ turn, mcq_options is exactly {key} | {distractors}, and nothing
    else about the item crosses the wire
  - the key's position is not guessable

That last one is not cosmetic. Shipping [answer, *distractors] in bank order puts
the key at position 0 every time, which makes every MCQ free and every mastery
number derived from one meaningless.
"""
from __future__ import annotations

import pytest

from server import mock_tutor
from tests.conftest import drive_to_mcq, turn


def test_mcq_options_are_exactly_key_plus_distractors(client, session, store):
    data = drive_to_mcq(client, session, store)
    if data is None:
        pytest.skip("no MCQ item reached in this walk")
    item = store.item(data["item"]["id"])
    ids = {o["id"] for o in data["mcq_options"]}
    assert ids == {item.answer} | set(item.distractors)
    assert all(set(o) == {"id", "label"} for o in data["mcq_options"])


def test_mcq_labels_come_from_the_graph_not_the_item(client, session, store):
    """The §1.6 carve-out is only defensible because these are node labels the
    graph already renders - server-owned data, never model output."""
    data = drive_to_mcq(client, session, store)
    if data is None:
        pytest.skip("no MCQ item reached in this walk")
    for option in data["mcq_options"]:
        assert option["label"] == store.label(option["id"])


def test_mcq_turn_still_leaks_no_prompt(client, session, store):
    data = drive_to_mcq(client, session, store)
    if data is None:
        pytest.skip("no MCQ item reached in this walk")
    item = store.item(data["item"]["id"])
    body = str(data)
    assert item.prompt not in body
    assert set(data["item"]) == {"id", "node_id", "difficulty", "scorable"}


def test_key_position_is_not_fixed(store):
    """Across items, the key must not sit at a constant index."""
    positions = set()
    for item in store.bank.items:
        if item.type != "mcq":
            continue
        options = mock_tutor.mcq_option_ids(item, "sess_fixed")
        positions.add(options.index(item.answer))
        if len(positions) > 1:
            break
    assert len(positions) > 1, "the key is always at the same position"


def test_key_is_not_always_first(store):
    firsts = [
        mock_tutor.mcq_option_ids(i, "sess_fixed")[0] == i.answer
        for i in store.bank.items if i.type == "mcq"
    ]
    assert firsts, "fixture has no mcq items"
    assert not all(firsts), "key is first every time; bank order leaked"


def test_option_order_is_stable_within_a_session(store):
    """Stable across re-renders and reconnects, so 'the student picked option 2'
    means one thing for the whole dialogue and §9.4 stays interpretable."""
    item = next(i for i in store.bank.items if i.type == "mcq")
    first = mock_tutor.mcq_option_ids(item, "sess_abc")
    for _ in range(5):
        assert mock_tutor.mcq_option_ids(item, "sess_abc") == first


def test_option_order_differs_across_sessions(store):
    item = next(i for i in store.bank.items if i.type == "mcq")
    orders = {tuple(mock_tutor.mcq_option_ids(item, f"sess_{i}")) for i in range(12)}
    assert len(orders) > 1, "shuffle ignores the session; order is guessable"


def test_option_order_differs_across_items_in_one_session(store):
    mcqs = [i for i in store.bank.items if i.type == "mcq"][:12]
    orders = {tuple(mock_tutor.mcq_option_ids(i, "sess_abc")) for i in mcqs}
    assert len(orders) > 1


def test_mcq_scores_on_the_key_not_the_position(client, session, store):
    data = drive_to_mcq(client, session, store)
    if data is None:
        pytest.skip("no MCQ item reached in this walk")
    item = store.item(data["item"]["id"])
    node = data["item"]["node_id"]
    before = data["graph_state"]["mastery"][node]
    data = turn(client, session, {"type": "mcq", "choice_id": item.answer})
    assert data["graph_state"]["mastery"][node] > before
