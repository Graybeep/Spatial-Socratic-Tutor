"""Call 2 gets labels, never identities (CLAUDE.md §5).

§5 says Call 2 receives `action`, `hint_level`, focus node LABELS and the last
two turns - and never the answer, the aliases or the source chunk. The rule that
is easy to lose is the quiet one: *labels*, not node ids.

A node id is an identity. For a node_click or mcq item the answer IS the item's
node, so an id in the Call 2 context is the answer in the clear, in the one
context that has been carefully kept ignorant of it. It is the same leak that
`ItemPublic.node_id` was, one layer further in - and it is the layer where you
stop being able to grep for it, because once a real model is generating the
utterance the id is gone from the output even when it was in the input.

This pins the property where it can be pinned today, against the mock. When
`server/llm.py` lands it must build the Call 2 context at this same call site
and this test must still pass. If a new call path is added, add it here first.

The fixture makes the check meaningful: ids are `n00`..`n49` and labels are
unrelated words, so an id appearing anywhere in the context is unambiguous. A
fixture where label == id would make this vacuous - if that ever changes, this
test needs to change with it.
"""
from __future__ import annotations

import pytest

from server import mock_tutor
from server import turn as turn_mod
from server.config import CONFIG
from tests.conftest import turn, wrong_response


@pytest.fixture()
def call2_spy(monkeypatch):
    """Record every argument Call 2 is handed, then behave normally."""
    seen: list[tuple] = []
    original = mock_tutor.mock_call2

    def spy(action, hint_level, focus_labels, n_lit, chunk=None):
        seen.append((action, hint_level, list(focus_labels), n_lit, chunk))
        return original(action, hint_level, focus_labels, n_lit, chunk)

    monkeypatch.setattr(turn_mod.mock_tutor, "mock_call2", spy)
    return seen


def test_no_node_id_ever_reaches_call_2(client, session, store, call2_spy):
    ids = set(store.node_ids)

    data = turn(client, session)
    for _ in range(CONFIG.turn_budget * 3):
        if data["session_complete"]:
            break
        data = turn(client, session, wrong_response(data, store))

    assert call2_spy, "Call 2 was never invoked; the spy is not attached"

    for action, hint_level, labels, n_lit, chunk in call2_spy:
        for label in labels:
            assert label not in ids, (
                f"Call 2 was handed the node id {label!r} as a label on a "
                f"{action!r} turn. Call 2 must never see an identity - for a "
                f"click item the node IS the answer (CLAUDE.md §5)."
            )
        assert not (ids & {str(action), str(hint_level), str(n_lit)})
        # The chunk is prose from the chapter, so it may legitimately contain a
        # concept's WORDS. What it must never contain is an id, which would mean
        # the pipeline had written an identity into the source text.
        if chunk:
            assert not any(i in chunk for i in ids), (
                f"a node id appeared in the chunk handed to Call 2 on a "
                f"{action!r} turn"
            )


def test_call_2_receives_only_the_documented_arguments():
    """The signature is the guarantee, so pin the signature.

    Widening it is how the item or the answer would arrive - each of them one
    plausible-looking keyword argument away.

    `chunk` was added deliberately, and this assertion was updated in the same
    commit rather than relaxed: §5's gate table has a POSITIVE half (advance and
    explain DO receive source, with answer spans masked) and turn.py had never
    wired it. The mock mirrors `llm.call2`, which already took the parameter and
    asserts the gate on it. The next parameter should trip this test too.
    """
    import inspect

    params = list(inspect.signature(mock_tutor.mock_call2).parameters)
    assert params == ["action", "hint_level", "focus_labels", "n_lit", "chunk"], (
        "Call 2's signature changed. §5 fixes what it may see; adding a "
        "parameter is how the answer gets in."
    )


def test_no_chunk_reaches_the_mock_on_a_hinting_turn(client, session, call2_spy):
    """The gate, checked at the mock's own door rather than only at llm.call2's
    assertion - MOCK_MODE is the default, so this is the path the demo takes."""
    turn(client, session)
    for action, _hint, _labels, _n, chunk in call2_spy:
        if action in {"ask", "hint_visual", "hint_verbal", "backtrack"}:
            assert chunk is None, f"{action} received source text"


def test_the_spy_would_actually_catch_an_id(client, session, store, monkeypatch):
    """A spy that records nothing passes the test above by doing nothing."""
    leaked: list = []
    original = mock_tutor.mock_call2

    def leaky(action, hint_level, focus_labels, n_lit, chunk=None):
        # Deliberately pass ids where labels belong.
        bad = store.node_ids[:2]
        leaked.append(bad)
        return original(action, hint_level, bad, n_lit, chunk)

    monkeypatch.setattr(turn_mod.mock_tutor, "mock_call2", leaky)
    turn(client, session)

    assert leaked, "the leaky stand-in never ran"
    assert set(leaked[0]) <= set(store.node_ids)
