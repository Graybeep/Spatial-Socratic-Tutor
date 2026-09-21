"""A turn says whether the MODEL wrote its utterance or a template did.

The sibling of `test_call1_fallback_flag.py`, one call over, and the reason is
§6.1 rather than §9.5. When Call 2 fails, turn.py ships a canned string from
`prompts/fallback_*.txt` and logs a `call2_fallback` event. That is right for a
student and wrong for the answer monitor: §6.1 asks whether the model
reconstructed an answer from its own weights, and a template has no weights.

Measured on day 18: `gpt-oss-20b` invented a tool name on 4 of 40 turns and 2 of
those exhausted the retry, so 2 real-mode turns carried a template utterance with
nothing in the turn record to say so. `eval/leak_monitor.py` would have counted
them as clean screened turns - denominator inflation in the flattering direction,
which is exactly the failure `numbers-that-looked-fine.md` is about.

The event was already in the log. What was missing is the flag ON THE TURN, and
a per-turn question cannot be answered by a separate line that carries no
session_id or turn_id to join on.
"""
from __future__ import annotations

import json

from server import llm as llm_mod
from server import turn as turn_mod
from server.config import CONFIG
from server.state import Store

from .conftest import config_override


def _drive_one_turn(store):
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    item = next(i for n in store.node_ids for i in store.items_for(n))
    state.start_item(item.node_id, item.id)
    db.save(state)
    phase1 = turn_mod.begin_turn(store, db, state, None)
    response = turn_mod.complete_turn(store, db, phase1)
    return phase1, response


def _logged_turns():
    """Every turn record written this test, from the isolated log."""
    path = CONFIG.log_dir / "turns.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if "turn_id" in record:
            out.append(record)
    return out


def _a_working_call1(monkeypatch):
    monkeypatch.setattr(llm_mod, "call1", lambda **_: turn_mod.Call1Decision(
        student_state="on_track", diagnosis="model prose", correct=False,
        requested_action="ask", requested_hint_level=0, focus_nodes=[],
        expects="node_click",
    ))


def test_a_failed_call2_is_flagged_on_the_turn(store, monkeypatch):
    _a_working_call1(monkeypatch)

    def boom(**_):
        raise llm_mod.LLMError("HTTP 400 tool_use_failed: invented tool name 'json'")

    monkeypatch.setattr(llm_mod, "call2", boom)
    with config_override(mock_mode=False):
        phase1, response = _drive_one_turn(store)

    assert phase1.call2_fallback is True
    # And the shipped utterance really is the template, not model prose.
    assert response.utterance.strip()


def test_the_flag_reaches_the_turn_record(store, monkeypatch):
    """The whole point. A flag the log does not carry cannot be read back."""
    _a_working_call1(monkeypatch)
    monkeypatch.setattr(llm_mod, "call2", lambda **_: (_ for _ in ()).throw(
        llm_mod.LLMError("HTTP 400 tool_use_failed")))
    with config_override(mock_mode=False):
        _drive_one_turn(store)

    turns = _logged_turns()
    assert turns, "no turn record was written"
    assert turns[-1]["call2_fallback"] is True
    assert turns[-1]["mock"] is False, (
        "the turn is real-mode: that is precisely why the flag is needed")


def test_a_successful_call2_is_not_flagged(store, monkeypatch):
    _a_working_call1(monkeypatch)

    class _Utterance:
        utterance = "Which of these two comes first?"

    monkeypatch.setattr(llm_mod, "call2", lambda **_: _Utterance())
    with config_override(mock_mode=False):
        phase1, response = _drive_one_turn(store)

    assert phase1.call2_fallback is False
    assert response.utterance == "Which of these two comes first?"
    assert _logged_turns()[-1]["call2_fallback"] is False


def test_mock_mode_is_not_a_fallback(store):
    """MOCK_MODE is a chosen mode, not a failure - and the record already says
    `mock: true`. Flagging it here would double-count and teach readers that the
    flag means nothing."""
    with config_override(mock_mode=True):
        phase1, _ = _drive_one_turn(store)
    assert phase1.call2_fallback is False
    assert _logged_turns()[-1]["call2_fallback"] is False


def test_a_fallback_during_layer1_regeneration_is_flagged(store, monkeypatch):
    """The subtle one.

    Layer 1 regenerates on a hit. If the FIRST Call 2 succeeds and names the
    answer, and the REGENERATION then fails, the utterance that ships is a
    template - but the first call succeeded, so a flag taken from the first
    result alone would report the turn as the model's work.

    The first utterance is built FROM the item's own answer so layer 1 is
    guaranteed to fire. A version of this test that merely hoped for a hit would
    pass without exercising the branch, which is the failure mode in
    docs/writeup/numbers-that-looked-fine.md.
    """
    _a_working_call1(monkeypatch)
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    item = next(i for n in store.node_ids for i in store.items_for(n))
    state.start_item(item.node_id, item.id)
    db.save(state)

    answer, _aliases, _context = turn_mod._layer1_terms(store, item)
    calls = {"n": 0}

    class _Said:
        def __init__(self, text):
            self.utterance = text

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Said(f"It is {answer}.")
        raise llm_mod.LLMError("HTTP 400 on the regeneration")

    monkeypatch.setattr(llm_mod, "call2", flaky)
    with config_override(mock_mode=False):
        phase1 = turn_mod.begin_turn(store, db, state, None)
        turn_mod.complete_turn(store, db, phase1)

    assert calls["n"] > 1, (
        "layer 1 did not fire, so the regeneration branch was never reached "
        "and this test proved nothing")
    assert phase1.call2_fallback is True, (
        "a regeneration that fell back shipped a template unflagged")
    assert _logged_turns()[-1]["call2_fallback"] is True
