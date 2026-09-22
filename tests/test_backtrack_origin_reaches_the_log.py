"""`backtrack_origin` is only worth having if it reaches `logs/turns.jsonl`.

The day-19 gate was found by counting curriculum moves in the day-18 log and
discovering that one `backtrack` could not be attributed: the log recorded that
the curriculum moved backwards, not which rule moved it. The field exists so the
next count is attributable.

`tests/test_backtrack_needs_a_gap.py` pins the gate's decision on `Phase1`. That
is one end of the wire. Nothing held the other: `_log` could stop writing the
field, or write it for the wrong turns, and every gate test would stay green
while the next count silently repeated the day-18 problem.

So these tests assert on the written record, not on `Phase1`, and they run a
complete turn (`begin_turn` + `complete_turn`) because `_log` is only reached by
the second.
"""
from __future__ import annotations

import json

from server import mastery as mastery_mod
from server import turn as turn_mod
from server.config import CONFIG
from server.schemas import StudentResponse
from server.state import Store


def _records():
    path = CONFIG.log_dir / "turns.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line]


def _turn_records():
    """Turn records only. `_log_event` writes guard and fallback events to the
    same file, and those carry no `turn_id`."""
    return [r for r in _records() if "turn_id" in r]


def _blank_state(store):
    db = Store(db_path=":memory:")
    return db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)


def _node_with_prereqs(store):
    for nid in store.node_ids:
        if store.prereqs(nid) and turn_mod._pick_item(
                store, _blank_state(store), nid) is not None:
            return nid
    raise AssertionError("no node with prerequisites and an item")


def _session_on(store, node_id):
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    item = turn_mod._pick_item(store, state, node_id)
    state.start_item(node_id, item.id)
    db.save(state)
    return db, state, item


def _requests(monkeypatch, action, student_state="confused_prereq"):
    monkeypatch.setattr(turn_mod, "_call1", lambda *a, **k: (
        turn_mod.Call1Decision(
            student_state=student_state,
            diagnosis="d",
            correct=False,
            requested_action=action,
            requested_hint_level=1,
            focus_nodes=[],
            expects="node_click",
        ),
        False,
    ))


def _full_turn(store, db, state, response=None):
    phase1 = turn_mod.begin_turn(store, db, state, response)
    turn_mod.complete_turn(store, db, phase1)
    return phase1


def test_an_honoured_model_backtrack_is_logged_as_the_models(store, monkeypatch, no_latency):
    node = _node_with_prereqs(store)
    db, state, item = _session_on(store, node)
    _requests(monkeypatch, "backtrack")
    for p in store.prereqs(node):
        state.theta_map[p] = -4.0
    db.save(state)

    phase1 = _full_turn(store, db, state)
    assert phase1.action == "backtrack", "setup failed; this test proved nothing"

    record = _turn_records()[-1]
    assert record["backtrack_origin"] == "model"
    assert record["server_action"] == "backtrack"


def test_a_refused_backtrack_is_logged_as_refused(store, monkeypatch, no_latency):
    """The refusal is the case the log could not see before, and the one a
    count of curriculum moves must not mistake for a move."""
    node = _node_with_prereqs(store)
    db, state, item = _session_on(store, node)
    _requests(monkeypatch, "backtrack")
    for p in store.prereqs(node):
        state.theta_map[p] = 6.0
    db.save(state)

    phase1 = _full_turn(store, db, state)
    assert phase1.action != "backtrack", "setup failed; this test proved nothing"

    record = _turn_records()[-1]
    assert record["backtrack_origin"] == "refused"
    assert record["server_action"] != "backtrack", (
        "a refused backtrack logged an action that a count reads as a move")
    assert record["call1"]["requested_action"] == "backtrack", (
        "the model's request is what makes this record a refusal rather than "
        "an ordinary hint; a count cannot see the gate fire without it")


def test_the_two_failure_backtrack_is_logged_as_the_servers(store, monkeypatch, no_latency):
    node = _node_with_prereqs(store)
    db, state, item = _session_on(store, node)
    for p in store.prereqs(node):
        state.theta_map[p] = -4.0
    state.consecutive_failures = CONFIG.consecutive_failures_before_backtrack
    db.save(state)
    _requests(monkeypatch, "hint_visual", student_state="stuck")

    wrong = next(n for n in store.node_ids if n != item.answer)
    phase1 = _full_turn(
        store, db, state, StudentResponse(type="node_click", node_id=wrong))
    assert phase1.action == "backtrack", "the two-failure rule did not fire"

    record = _turn_records()[-1]
    assert record["backtrack_origin"] == "server", (
        "the §7 rule moved the curriculum and the log credited the model")


def test_a_turn_that_moved_nothing_backwards_logs_no_origin(store, monkeypatch, no_latency):
    """The field has to be absent on ordinary turns, or every count that filters
    on its presence counts the whole session."""
    node = _node_with_prereqs(store)
    db, state, item = _session_on(store, node)
    _requests(monkeypatch, "hint_visual", student_state="on_track")

    phase1 = _full_turn(store, db, state)
    assert phase1.action != "backtrack", "setup failed; this test proved nothing"

    record = _turn_records()[-1]
    assert record["backtrack_origin"] is None


def test_the_three_origins_are_the_only_values_written(store, monkeypatch, no_latency):
    """Pins the vocabulary a count will group by. A fourth spelling appearing
    later is a silent new bucket."""
    node = _node_with_prereqs(store)

    db, state, _ = _session_on(store, node)
    _requests(monkeypatch, "backtrack")
    for p in store.prereqs(node):
        state.theta_map[p] = -4.0
    db.save(state)
    _full_turn(store, db, state)

    db, state, _ = _session_on(store, node)
    for p in store.prereqs(node):
        state.theta_map[p] = 6.0
    db.save(state)
    _full_turn(store, db, state)

    db, state, _ = _session_on(store, node)
    _requests(monkeypatch, "hint_visual", student_state="on_track")
    _full_turn(store, db, state)

    written = {r["backtrack_origin"] for r in _turn_records()}
    assert written <= {"model", "server", "refused", None}, sorted(
        str(v) for v in written)
    assert {"model", "refused"} <= written, (
        f"the fixture did not exercise both gate outcomes: {sorted(str(v) for v in written)}")
