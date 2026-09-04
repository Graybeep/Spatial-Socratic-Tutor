"""The wire contract, and the leak surface.

These are the tests Person B relies on. If one of them fails, the mock server has
stopped matching what the real server will do, and anything built against it is
built against a lie.

Fixtures live in conftest.py. MCQ leak scoping lives in test_mcq.py; the ladder
lives in test_ladder.py.
"""
from __future__ import annotations

import json

from server import main as main_mod
from server.config import CONFIG
from server.schemas import TurnResponse
from tests.conftest import config_override, turn, wrong_response


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
    for field in ("prompt", "answer", "answer_aliases", "answer_spans", "distractors"):
        assert field not in data["item"]


def test_item_prompt_never_appears_on_any_turn(client, session):
    """Unconditional. The tutor's `utterance` IS the question; the bank's prompt
    text is Call 1's input and must never be rendered."""
    store = main_mod.STORE
    data = turn(client, session)
    for _ in range(6):
        item = store.item(data["item"]["id"]) if data["item"] else None
        if item is not None:
            assert item.prompt not in json.dumps(data)
        nxt = wrong_response(data, store)
        if nxt is None:
            break
        data = turn(client, session, nxt)


def test_no_alias_leaks_and_no_options_ship_on_a_non_mcq_turn(client, session):
    """SCOPED ON PURPOSE, and the scope is the honest version of this claim.

    Two things this deliberately does NOT assert, because both are false:

    - "no distractor id appears anywhere in the response". Every node id appears
      in graph_state.mastery, which covers all 50 nodes, and every node id is
      already public from GET /graph. A substring search for distractor ids finds
      them there and means nothing. What matters is that distractors are never
      shipped as a DISTINGUISHED SET on a turn that did not ask for one - which
      is what the mcq_options assertion below actually checks.
    - "no answer alias appears on an MCQ turn". The options ARE the key plus its
      distractors, and their labels are the aliases. test_mcq.py pins what MCQ is
      allowed to expose.
    """
    store = main_mod.STORE
    data = turn(client, session)
    checked = 0
    for _ in range(8):
        if data["item"] is not None and data["expects"] != "mcq":
            item = store.item(data["item"]["id"])
            body = json.dumps(data).lower()
            assert not data["mcq_options"], "mcq_options shipped on a non-mcq turn"
            for alias in item.answer_aliases:
                assert alias not in body, f"answer alias {alias!r} leaked"
            checked += 1
        nxt = wrong_response(data, store)
        if nxt is None:
            break
        data = turn(client, session, nxt)
    assert checked, "no non-mcq turn was exercised"


# ---------------------------------------------------------------------------
# guard layer 2 - hint monotonicity (CLAUDE.md §6)
# ---------------------------------------------------------------------------

def test_hint_level_never_jumps_and_never_decreases(client, session):
    data = turn(client, session)
    levels = [data["hint_level"]]
    for _ in range(6):
        wrong = wrong_response(data, main_mod.STORE)
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
        wrong = wrong_response(data, main_mod.STORE)
        if wrong is None:
            break
        data = turn(client, session, wrong)
        assert data["turn_budget"]["used"] <= data["turn_budget"]["max"] + 1
        if data["resolved_with_support"]:
            resolved = True
            break

    assert resolved, "8 turns on one item must force a reveal"
    assert data["graph_state"]["mastery"][node] <= before, "forced reveal must not award mastery"


def test_forced_reveal_does_not_credit_a_correct_answer_on_the_same_turn(client, session):
    """STEP 4 ORDERING. The guard must resolve the action BEFORE scoring runs.

    Burn the budget down, then answer correctly on the turn the guard fires. If
    scoring ran before the guard overturned the action, this correct answer would
    be credited for an item the tutor was about to give away.
    """
    store = main_mod.STORE
    data = turn(client, session)
    node = data["item"]["node_id"]

    # Spend the budget without ever answering correctly.
    for _ in range(CONFIG.turn_budget - 1):
        nxt = wrong_response(data, store)
        if nxt is None or data["resolved_with_support"]:
            break
        data = turn(client, session, nxt)
        if data["item"] is None or data["item"]["node_id"] != node:
            break

    if data["item"] is None or data["resolved_with_support"]:
        return  # already resolved; the assertion above covers that path

    before = data["graph_state"]["mastery"][data["item"]["node_id"]]
    scored_node = data["item"]["node_id"]
    answer = store.item(data["item"]["id"]).answer
    data = turn(client, session, {"type": "node_click", "node_id": answer})

    if data["resolved_with_support"]:
        assert data["graph_state"]["mastery"][scored_node] == before, (
            "a forced reveal credited the answer; guards must settle before scoring"
        )


def test_scoring_precedes_routing(client, session):
    """The other half of the ordering: `advance` and next_node() read mastery, so
    scoring has to have already run or the tutor routes on last turn's state."""
    store = main_mod.STORE
    data = turn(client, session)
    node = data["item"]["node_id"]
    answer = store.item(data["item"]["id"]).answer
    data = turn(client, session, {"type": "node_click", "node_id": answer})
    # The advance decision and the mastery bump must be visible in the same
    # response, not split across two turns.
    assert data["action"] == "advance"
    assert data["graph_state"]["mastery"][node] > 0.5


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
    wrong = wrong_response(data, main_mod.STORE)
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
        wrong = wrong_response(data, main_mod.STORE)
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
        wrong = wrong_response(data, main_mod.STORE)
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


def test_stream_phase1_carries_everything_the_client_needs_to_interact(client, session):
    """Pins the SSE phase-1 payload against client/src/types.ts::GraphStatePhase.

    The graph has to become INTERACTIVE on this event, not merely repaint. If
    `expects`, `item` or `mcq_options` were withheld until `done`, the student
    would face a narrowed graph they cannot click for another ~1.4s, which throws
    away most of what the two-call split bought.
    """
    with client.stream(
        "POST", "/turn?stream=true", json={"session_id": session, "response": None}
    ) as r:
        assert r.status_code == 200
        frames, cur = [], {}
        for line in r.iter_lines():
            if line.startswith("event: "):
                cur = {"event": line[len("event: "):]}
            elif line.startswith("data: "):
                cur["data"] = json.loads(line[len("data: "):])
                frames.append(cur)

    assert [f["event"] for f in frames] == ["graph_state", "utterance", "done"]

    phase1 = frames[0]["data"]
    assert set(phase1) == {
        "session_id", "turn_id", "action", "hint_level", "expects", "item",
        "mcq_options", "turn_budget", "resolved_with_support", "session_complete",
        "graph_state",
    }
    assert set(phase1["graph_state"]) == {
        "current_node", "focus_nodes", "focus_edges", "dimmed_nodes", "mastery",
    }
    assert set(frames[1]["data"]) == {"utterance"}
    assert set(frames[2]["data"]) == set(TurnResponse.model_fields)


def test_stream_and_json_transports_agree(client, store):
    """Two transports, one contract. If they drift, whichever one the client did
    not build against becomes a trap."""
    a = client.post("/session").json()["session_id"]
    b = client.post("/session").json()["session_id"]

    plain = client.post("/turn", json={"session_id": a, "response": None}).json()

    with client.stream(
        "POST", "/turn?stream=true", json={"session_id": b, "response": None}
    ) as r:
        done = None
        for line in r.iter_lines():
            if line.startswith("data: "):
                done = json.loads(line[len("data: "):])

    assert set(plain) == set(done)
    assert plain["expects"] == done["expects"]
    assert plain["action"] == done["action"]
    assert set(plain["graph_state"]) == set(done["graph_state"])
