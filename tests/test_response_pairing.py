"""A response whose `type` and payload disagree is rejected, not graded.

`StudentResponse` carries one optional payload field per `type`, because each
type uses a different one. That made a mismatched response schema-valid: a body
naming `node_click` and carrying no `node_id` parsed cleanly, reached `turn.py`,
and was graded like any other answer - as a **wrong** one. Measured before the
fix: theta 0.0 -> -0.2395 and `consecutive_failures` 0 -> 1, from a request that
contained no answer at all.

CLAUDE.md §8 requires confirm-or-undo precisely because "a misclick scored as
wrong corrupts mastery". A malformed click corrupted it the same way through a
different door, and the schema's own docstring had claimed the opposite
throughout: *"The server validates the pairing and rejects a mismatch rather
than guessing."*

The shipped client could never produce one - every send site supplies its
payload unconditionally - so this was reachable only by calling the API
directly. That is why it survived: nothing in the demo path exercises it.

Rejection happens at the model boundary rather than in `turn.py`, so FastAPI
answers 422 and the orchestrator never sees a malformed response. There is no
second place to get it right.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.schemas import PAYLOAD_FIELD, StudentResponse

from .conftest import turn

GOOD = {
    "node_click": {"node_id": "tcp_slow_start"},
    "edge_click": {"edge": {"from": "tcp_aimd", "to": "tcp_fast_recovery"}},
    "mcq": {"choice_id": "opt_a"},
    "text": {"text": "slow start"},
}


# --- the pairing itself ----------------------------------------------------

def test_every_type_accepts_its_own_payload():
    """The counterpart test. A validator that only ever rejects is as wrong as
    one that never does, and both look identical from a single direction."""
    for kind, payload in GOOD.items():
        StudentResponse(type=kind, **payload)


def test_a_type_with_no_payload_is_rejected():
    """The bug, as a test. Each of these used to parse and be graded wrong."""
    for kind in PAYLOAD_FIELD:
        with pytest.raises(ValidationError):
            StudentResponse(type=kind)


def test_a_type_carrying_another_types_payload_is_rejected():
    for kind in PAYLOAD_FIELD:
        for other, payload in GOOD.items():
            if other == kind:
                continue
            with pytest.raises(ValidationError):
                StudentResponse(type=kind, **payload)


def test_two_payloads_at_once_is_rejected():
    """A response that names two answers names none. Guessing which one the
    student meant is exactly what the docstring forbids."""
    with pytest.raises(ValidationError):
        StudentResponse(type="node_click", node_id="a", text="b")


def test_blank_strings_do_not_count_as_a_payload():
    """`""` is not an answer. The client already refuses to send empty text;
    this makes the server agree instead of grading whitespace."""
    with pytest.raises(ValidationError):
        StudentResponse(type="text", text="   ")
    with pytest.raises(ValidationError):
        StudentResponse(type="node_click", node_id="")


def test_the_mapping_covers_every_expects_value():
    """A new answer type must land in PAYLOAD_FIELD or the validator would
    raise KeyError on a legitimate response."""
    from server.schemas import Expects
    import typing

    assert set(typing.get_args(Expects)) == set(PAYLOAD_FIELD)


# --- over the wire ---------------------------------------------------------

def test_the_endpoint_answers_422_and_does_not_grade(client, session, store):
    """End to end: the malformed body is refused before `turn.py` sees it, and
    the turn it would have scored never happens."""
    data = turn(client, session)
    assert data["expects"] == "node_click", "fixture drifted; this proved nothing"

    r = client.post("/turn", json={"session_id": session,
                                   "response": {"type": "node_click"}})
    assert r.status_code == 422, r.text

    # The item is untouched: the student is still on the same question.
    again = turn(client, session)
    assert again["item"]["id"] == data["item"]["id"]


def test_a_well_formed_click_still_works_over_the_wire(client, session, store):
    data = turn(client, session)
    item = store.item(data["item"]["id"])
    r = client.post("/turn", json={"session_id": session,
                                   "response": {"type": "node_click",
                                                "node_id": item.answer}})
    assert r.status_code == 200, r.text
