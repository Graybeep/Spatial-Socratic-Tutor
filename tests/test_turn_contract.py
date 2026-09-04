"""The wire contract, and the leak surface.

These are the tests Person B relies on. If one of them fails, the mock server has
stopped matching what the real server will do, and anything built against it is
built against a lie.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from server import main as main_mod
from server.config import CONFIG
from server.graph_store import GraphStore
from server.schemas import TurnResponse
from server.state import Store

# The item bank's secrets. None of these strings may ever appear in a response.
LEAKY_FIELDS = ("prompt", "answer", "answer_aliases", "answer_spans", "distractors")


@pytest.fixture()
def client(tmp_path):
    """A real app over an in-memory DB, with the mock latency removed so the
    suite does not sleep for two seconds per turn.

    CONFIG is a frozen dataclass on purpose (config is read once at startup and
    never mutated at call time), so overriding it needs object.__setattr__ and an
    explicit restore rather than monkeypatch.
    """
    overrides = {
        "mock_call1_delay_s": 0.0,
        "mock_call2_delay_s": 0.0,
        "log_dir": tmp_path / "logs",
    }
    saved = {k: getattr(CONFIG, k) for k in overrides}
    for k, v in overrides.items():
        object.__setattr__(CONFIG, k, v)

    main_mod.STORE = GraphStore.load()
    main_mod.DB = Store(db_path=":memory:")
    try:
        with TestClient(main_mod.app) as c:
            yield c
    finally:
        for k, v in saved.items():
            object.__setattr__(CONFIG, k, v)


@pytest.fixture()
def session(client):
    return client.post("/session").json()["session_id"]


def turn(client, session_id, response=None):
    body = {"session_id": session_id, "response": response}
    r = client.post("/turn", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# guard layer 0 - the whitelist (CLAUDE.md §1.6)
# ---------------------------------------------------------------------------

def test_response_field_set_is_exactly_the_whitelist():
    """Adding a model-authored text field to TurnResponse is a severity-1 bug.
    Update this list only alongside a deliberate schema change."""
    assert set(TurnResponse.model_fields) == {
        "session_id", "turn_id", "schema_version",
        "utterance",
        "action", "hint_level", "expects", "mcq_options",
        "graph_state", "item", "turn_budget",
        "resolved_with_support", "session_complete",
    }


def test_diagnosis_never_reaches_the_client(client, session):
    """Call 1's diagnosis is logged and never rendered (CLAUDE.md §5)."""
    body = json.dumps(turn(client, session))
    assert "diagnosis" not in body
    assert "student_state" not in body
    assert "requested_" not in body


def test_item_payload_carries_no_answer_material(client, session):
    data = turn(client, session)
    assert data["item"] is not None
    assert set(data["item"]) == {"id", "node_id", "difficulty", "scorable"}
    for field in LEAKY_FIELDS:
        assert field not in data["item"]


def test_no_item_prompt_or_answer_string_anywhere_in_the_response(client, session):
    store = main_mod.STORE
    data = turn(client, session)
    body = json.dumps(data)
    item = store.item(data["item"]["id"])
    assert item.prompt not in body, "the item prompt leaked; the utterance IS the question"
    for alias in item.answer_aliases:
        assert alias not in body.lower(), f"answer alias {alias!r} leaked"


# ---------------------------------------------------------------------------
# guard layer 2 - hint monotonicity (CLAUDE.md §6)
# ---------------------------------------------------------------------------

def test_hint_level_never_jumps_and_never_decreases(client, session):
    data = turn(client, session)
    levels = [data["hint_level"]]
    for _ in range(6):
        wrong = _wrong_response(data)
        if wrong is None:
            break
        data = turn(client, session, wrong)
        levels.append(data["hint_level"])
        if data["action"] in {"advance", "backtrack"}:
            break

    for prev, cur in zip(levels, levels[1:]):
        assert cur - prev <= 1, f"hint level jumped: {levels}"
    assert max(levels) <= CONFIG.hint_max


def test_server_ignores_a_model_request_to_skip_levels():
    """The counter lives on the server; the model only asks (CLAUDE.md §1.7)."""
    from server.state import SessionState

    state = SessionState(session_id="s")
    assert state.bump_hint(4) == 1
    assert state.bump_hint(4) == 2
    assert state.bump_hint(0) == 2, "a request to go backwards must not lower it"
    for _ in range(10):
        state.bump_hint(9)
    assert state.hint_level == CONFIG.hint_max


# ---------------------------------------------------------------------------
# guard layer 3 - turn budget (CLAUDE.md §6)
# ---------------------------------------------------------------------------

def test_turn_budget_forces_a_reveal_and_awards_zero_mastery(client, session):
    data = turn(client, session)
    node = data["item"]["node_id"]
    before = data["graph_state"]["mastery"][node]

    resolved = False
    for _ in range(CONFIG.turn_budget + 3):
        wrong = _wrong_response(data)
        if wrong is None:
            break
        data = turn(client, session, wrong)
        assert data["turn_budget"]["used"] <= data["turn_budget"]["max"] + 1
        if data["resolved_with_support"]:
            resolved = True
            break

    assert resolved, "8 turns on one item must force a reveal"
    assert data["graph_state"]["mastery"][node] <= before, "forced reveal must not award mastery"


# ---------------------------------------------------------------------------
# scoring rules (CLAUDE.md §1.4)
# ---------------------------------------------------------------------------

def test_free_text_never_moves_mastery(client, session):
    data = turn(client, session)
    before = dict(data["graph_state"]["mastery"])
    data = turn(client, session, {"type": "text", "text": "I think it is slow start"})
    assert data["graph_state"]["mastery"] == before, "free text was scored; CLAUDE.md §1.4"


def test_a_correct_click_raises_mastery_on_that_node(client, session):
    data = turn(client, session)
    node = data["item"]["node_id"]
    before = data["graph_state"]["mastery"][node]
    answer = main_mod.STORE.item(data["item"]["id"]).answer
    data = turn(client, session, {"type": "node_click", "node_id": answer})
    assert data["graph_state"]["mastery"][node] > before


def test_a_wrong_click_lowers_mastery_and_decays_prereqs(client, session):
    store = main_mod.STORE
    data = turn(client, session)
    node = data["item"]["node_id"]
    before = dict(data["graph_state"]["mastery"])
    wrong = _wrong_response(data)
    data = turn(client, session, wrong)
    assert data["graph_state"]["mastery"][node] < before[node]
    for prereq in store.prereqs(node):
        assert data["graph_state"]["mastery"][prereq] < before[prereq]


# ---------------------------------------------------------------------------
# the visual channel (CLAUDE.md §8, eval §9.2)
# ---------------------------------------------------------------------------

def test_focus_and_dimmed_partition_the_graph(client, session):
    store = main_mod.STORE
    data = turn(client, session)
    for _ in range(4):
        gs = data["graph_state"]
        focus, dimmed = set(gs["focus_nodes"]), set(gs["dimmed_nodes"])
        assert not (focus & dimmed), "a node cannot be both lit and dimmed"
        if focus:
            assert focus | dimmed == set(store.node_ids)
        else:
            assert not dimmed, "empty focus means no narrowing, so nothing is dimmed"
        wrong = _wrong_response(data)
        if wrong is None:
            break
        data = turn(client, session, wrong)


def test_narrowing_is_monotone_within_an_item(client, session):
    """A hint must never re-light a node it already excluded - otherwise a student
    can recover eliminated candidates, and eval §9.2's excluded set is meaningless."""
    data = turn(client, session)
    item_id = data["item"]["id"]
    previous = None
    for _ in range(4):
        wrong = _wrong_response(data)
        if wrong is None:
            break
        data = turn(client, session, wrong)
        if data["item"] is None or data["item"]["id"] != item_id:
            break
        focus = set(data["graph_state"]["focus_nodes"])
        if previous is not None and focus and previous:
            assert focus <= previous, f"narrowing widened: {previous} -> {focus}"
        if focus:
            previous = focus


def test_mastery_map_covers_every_node(client, session):
    store = main_mod.STORE
    data = turn(client, session)
    assert set(data["graph_state"]["mastery"]) == set(store.node_ids)
    assert all(0.0 <= v <= 1.0 for v in data["graph_state"]["mastery"].values())


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------

def test_graph_endpoint_returns_frozen_layout(client):
    data = client.get("/graph").json()
    assert data["nodes"], "graph must not be empty"
    for node in data["nodes"]:
        assert isinstance(node["x"], (int, float))
        assert isinstance(node["y"], (int, float))
    assert all("from" in e and "to" in e for e in data["edges"])


def test_layout_is_identical_across_requests(client):
    """CLAUDE.md §8: nodes never move. If they do, the spatial claim evaporates."""
    first = client.get("/graph").json()["nodes"]
    second = client.get("/graph").json()["nodes"]
    assert [(n["id"], n["x"], n["y"]) for n in first] == [(n["id"], n["x"], n["y"]) for n in second]


def test_stream_sends_graph_state_before_utterance(client, session):
    """The whole latency argument (CLAUDE.md §5, §8) in one assertion."""
    with client.stream("POST", "/turn?stream=true", json={"session_id": session, "response": None}) as r:
        assert r.status_code == 200
        events = [line[len("event: "):] for line in r.iter_lines() if line.startswith("event: ")]
    assert events == ["graph_state", "utterance", "done"]


def test_unknown_session_is_404(client):
    assert client.post("/turn", json={"session_id": "nope", "response": None}).status_code == 404


def test_unknown_response_field_is_rejected(client, session):
    r = client.post("/turn", json={
        "session_id": session,
        "response": {"type": "text", "text": "hi", "sneaky": 1},
    })
    assert r.status_code == 422


def test_session_ids_are_distinct(client):
    a = client.post("/session").json()["session_id"]
    b = client.post("/session").json()["session_id"]
    assert a != b


# ---------------------------------------------------------------------------

def _wrong_response(data):
    """A deliberately wrong answer of whatever type the server expects."""
    store = main_mod.STORE
    expects = data["expects"]
    if data["item"] is None:
        return None
    answer = store.item(data["item"]["id"]).answer
    if expects == "node_click":
        wrong = next(n for n in store.node_ids if n != answer)
        return {"type": "node_click", "node_id": wrong}
    if expects == "mcq":
        wrong = next(o["id"] for o in data["mcq_options"] if o["id"] != answer)
        return {"type": "mcq", "choice_id": wrong}
    if expects == "edge_click":
        edge = next(e for e in store.graph.edges if f"{e.from_}->{e.to}" != answer)
        return {"type": "edge_click", "edge": {"from": edge.from_, "to": edge.to}}
    return {"type": "text", "text": "no idea"}
