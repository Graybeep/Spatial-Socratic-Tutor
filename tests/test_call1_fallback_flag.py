"""A turn says whether its decision came from the model or stood in for it.

When Call 1 fails, turn.py runs the turn on the mock's decision and logs a
`call1_fallback` event. That is right for a student - a degraded turn beats a
dead one - and wrong for anything that reads `decision` as the model's account.
§9.5 is exactly that reader: a run that crosses Groq's daily cap mid-way would
otherwise score "wrong answer at hint_level=2" as the model's diagnosis, next to
real ones, with nothing in the result to say so. The event went to the log; the
caller holding the decision never heard about it.
"""
from __future__ import annotations

from server import llm as llm_mod
from server import turn as turn_mod
from server.state import Store

from .conftest import config_override


def _first_turn(store):
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    item = next(i for n in store.node_ids for i in store.items_for(n))
    state.start_item(item.node_id, item.id)
    db.save(state)
    return turn_mod.begin_turn(store, db, state, None)


def test_a_failed_call1_is_flagged(store, monkeypatch):
    def boom(**_):
        raise llm_mod.LLMError("HTTP 429 DAILY quota exhausted")

    monkeypatch.setattr(llm_mod, "call1", boom)
    with config_override(mock_mode=False):
        phase1 = _first_turn(store)
    assert phase1.call1_fallback is True


def test_a_successful_call1_is_not_flagged(store, monkeypatch):
    captured = {}

    def fake_call1(**kwargs):
        captured.update(kwargs)
        return turn_mod.Call1Decision(
            student_state="on_track", diagnosis="model prose", correct=False,
            requested_action="ask", requested_hint_level=0, focus_nodes=[],
            expects="node_click",
        )

    monkeypatch.setattr(llm_mod, "call1", fake_call1)
    with config_override(mock_mode=False):
        phase1 = _first_turn(store)
    assert captured, "the real Call 1 path was not exercised"
    assert phase1.call1_fallback is False
    assert phase1.decision.diagnosis == "model prose"


def test_mock_mode_is_not_a_fallback(store):
    """MOCK_MODE is a chosen mode, not a failure. Flagging it would make every
    mock run look broken and teach readers to ignore the flag."""
    with config_override(mock_mode=True):
        assert _first_turn(store).call1_fallback is False
