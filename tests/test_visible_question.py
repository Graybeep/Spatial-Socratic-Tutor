"""Learners receive the open question without feeding it to Call 2."""
from tests.conftest import turn, correct_response, wrong_response
from server import turn as turn_mod


def test_open_and_advance_show_current_question(client, session, store):
    data = turn(client, session)
    for _ in range(15):
        if data["item"] is None:
            break
        item = store.item(data["item"]["id"])
        assert data["utterance"].endswith("\n\n" + item.prompt.strip())
        data = turn(client, session, correct_response(data, store))


def test_hints_backtracks_and_reveals_show_open_question(client, session, store):
    data = turn(client, session)
    for _ in range(40):
        if data["item"] is None:
            break
        assert data["utterance"].endswith(store.item(data["item"]["id"]).prompt.strip())
        data = turn(client, session, wrong_response(data, store))


def test_authored_question_does_not_enter_speaker_history(client, session, store, monkeypatch):
    seen = []
    original = turn_mod._call2
    def spy(state, *args, **kwargs):
        seen.extend(h["text"] for h in state.history if h["role"] == "tutor")
        return original(state, *args, **kwargs)
    monkeypatch.setattr(turn_mod, "_call2", spy)
    data = turn(client, session)
    prompt = store.item(data["item"]["id"]).prompt
    turn(client, session, wrong_response(data, store))
    assert seen
    assert all(prompt not in text for text in seen)
