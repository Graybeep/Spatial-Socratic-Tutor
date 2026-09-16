"""The dialogue history reaches both model calls as dialogue, not as "role: text".

state.py stores a turn as `{"role", "text"}`. llm.py unpacked each entry with
`for who, text in history`, and unpacking a two-key dict yields its keys, so every
line of RECENT TURNS arrived at the model as the literal "role: text". Call 1 was
never shown a click; Call 2 never saw the dialogue. Every test passed, because no
test followed a click from turn.py into the text a model actually receives - the
prompt was well-formed and simply empty.

So these tests drive real turns through turn.py and read the prompt string at the
wire. Only `_invoke`, the network, is replaced.
"""
from __future__ import annotations

from server import llm as llm_mod
from server import turn as turn_mod
from server.schemas import StudentResponse
from server.state import Store

from .conftest import config_override


def _capture(monkeypatch):
    prompts = {"call1": [], "call2": []}

    def fake_invoke(cfg, system, user, tool, label):
        prompts[label].append(user)
        if label == "call1":
            return llm_mod.Call1Decision(
                student_state="stuck", diagnosis="d", correct=False,
                requested_action="hint_visual", requested_hint_level=1,
                focus_nodes=[], expects="node_click",
            )
        return llm_mod.Call2Utterance(utterance="Which of the lit ones fits?")

    monkeypatch.setattr(llm_mod, "_invoke", fake_invoke)
    return prompts


def _click_turns(store):
    """Opening turn, then one wrong node click. Returns the clicked label."""
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    item = next(i for n in store.node_ids for i in store.items_for(n)
                if i.type == "node_click")
    state.start_item(item.node_id, item.id)
    db.save(state)

    turn_mod.complete_turn(store, db, turn_mod.begin_turn(store, db, state, None))
    wrong = next(n for n in store.node_ids if n != item.answer)
    response = StudentResponse(type="node_click", node_id=wrong)
    turn_mod.complete_turn(store, db, turn_mod.begin_turn(store, db, state, response))
    return store.label(wrong)


def test_call1_is_shown_the_click(store, monkeypatch):
    prompts = _capture(monkeypatch)
    with config_override(mock_mode=False):
        label = _click_turns(store)
    second = prompts["call1"][1]
    assert f"[clicked {label}]" in second
    assert "role: text" not in second


def test_call2_is_shown_the_last_two_turns(store, monkeypatch):
    prompts = _capture(monkeypatch)
    with config_override(mock_mode=False):
        label = _click_turns(store)
    second = prompts["call2"][1]
    assert f"[clicked {label}]" in second
    assert "role: text" not in second


def test_call1_sees_the_tutor_side_too(store, monkeypatch):
    """A diagnosis of 'no progress after the hint' needs the hint in view."""
    prompts = _capture(monkeypatch)
    with config_override(mock_mode=False):
        _click_turns(store)
    assert "tutor: Which of the lit ones fits?" in prompts["call1"][1]
