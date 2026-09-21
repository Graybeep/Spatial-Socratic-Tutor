"""A model-requested backtrack is honoured only if it closes a gap.

`action` starts as `decision.requested_action`, so a Call 1 asking for
`backtrack` used to get one for free: the utterance said "let us step back",
`backtrack` drew the prerequisite node's chunk, and the curriculum did not move
at all. No `start_item`, no new item, the student still sitting on the node they
were failing. Only the server-initiated branch (two consecutive failures, §7)
ever moved anything.

CLAUDE.md §7 backtracks to close a gap. A prerequisite already at or above
MASTERY_THRESHOLD is not a gap, so a request to step back to one is refused.
Honouring it would send a struggling student to revise something they have
already demonstrated, on the model's say-so - the kind of curriculum decision §5
keeps in Python and out of the model's hands.

Both paths are tested here, because a gate that only ever refuses and a gate
that only ever honours are both wrong and look identical from one direction.
"""
from __future__ import annotations

from server import mastery as mastery_mod
from server import turn as turn_mod
from server.config import CONFIG
from server.state import Store


def _node_with_prereqs(store):
    for nid in store.node_ids:
        if store.prereqs(nid) and turn_mod._pick_item(
                store, _blank_state(store), nid) is not None:
            return nid
    raise AssertionError("no node with prerequisites and an item")


def _blank_state(store):
    db = Store(db_path=":memory:")
    return db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)


def _session_on(store, node_id):
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    item = turn_mod._pick_item(store, state, node_id)
    state.start_item(node_id, item.id)
    db.save(state)
    return db, state, item


def _ask_for_backtrack(monkeypatch):
    """Call 1 requests `backtrack` and nothing else."""
    monkeypatch.setattr(turn_mod, "_call1", lambda *a, **k: (
        turn_mod.Call1Decision(
            student_state="confused_prereq",
            diagnosis="asked to step back",
            correct=False,
            requested_action="backtrack",
            requested_hint_level=1,
            focus_nodes=[],
            expects="node_click",
        ),
        False,
    ))


def test_the_target_is_the_lowest_mastery_prereq(store):
    """Pins the assumption the gate rests on: the gate asks about the node
    `backtrack_target` would pick, not about some other prerequisite."""
    node = _node_with_prereqs(store)
    prereqs = list(store.prereqs(node))
    mastery = {p: 0.9 for p in prereqs}
    mastery[prereqs[-1]] = 0.1
    assert mastery_mod.backtrack_target(store, node, mastery) == prereqs[-1]


def test_a_backtrack_to_an_unmastered_prereq_is_honoured(store, monkeypatch):
    node = _node_with_prereqs(store)
    db, state, item = _session_on(store, node)
    _ask_for_backtrack(monkeypatch)

    # Every prerequisite well below threshold: there is a gap to close.
    for p in store.prereqs(node):
        state.theta_map[p] = -4.0
    db.save(state)

    phase1 = turn_mod.begin_turn(store, db, state, None)

    assert phase1.action == "backtrack"
    assert phase1.backtrack_origin == "model"
    assert state.current_node in store.prereqs(node), (
        "the action said backtrack but the curriculum did not move")
    assert state.current_item_id != item.id
    assert phase1.hint_level == 0, "a backtrack starts the new item at rung 0"


def test_a_backtrack_to_a_mastered_prereq_is_refused(store, monkeypatch):
    node = _node_with_prereqs(store)
    db, state, item = _session_on(store, node)
    _ask_for_backtrack(monkeypatch)

    # Every prerequisite comfortably mastered: nothing to go back for.
    for p in store.prereqs(node):
        state.theta_map[p] = 6.0
    db.save(state)
    assert all(mastery_mod.is_mastered(mastery_mod.mastery(state.theta_map[p]))
               for p in store.prereqs(node))

    phase1 = turn_mod.begin_turn(store, db, state, None)

    assert phase1.action == CONFIG.backtrack_refused_action
    assert phase1.action != "backtrack"
    assert phase1.backtrack_origin == "refused"
    assert state.current_node == node, "a refused backtrack still moved the student"
    assert state.current_item_id == item.id


def test_a_refused_backtrack_does_not_silently_do_nothing(store, monkeypatch):
    """The student is still on the item and the hint counter has already been
    bumped this turn. Degrading to a no-op would spend a rung on silence."""
    node = _node_with_prereqs(store)
    db, state, item = _session_on(store, node)
    _ask_for_backtrack(monkeypatch)
    for p in store.prereqs(node):
        state.theta_map[p] = 6.0
    db.save(state)

    phase1 = turn_mod.begin_turn(store, db, state, None)
    assert phase1.action in ("hint_visual", "hint_verbal", "ask"), (
        f"a refused backtrack degraded to {phase1.action!r}, which is not help")


def test_a_root_node_backtrack_is_refused(store, monkeypatch):
    """No prerequisites at all means no target. `backtrack_target` returns None
    and the old code would still have emitted `backtrack`."""
    root = next((n for n in store.node_ids
                 if not store.prereqs(n)
                 and turn_mod._pick_item(store, _blank_state(store), n) is not None),
                None)
    if root is None:
        import pytest
        pytest.skip("no root node carries an item")
    db, state, item = _session_on(store, root)
    _ask_for_backtrack(monkeypatch)

    phase1 = turn_mod.begin_turn(store, db, state, None)
    assert phase1.action != "backtrack"
    assert phase1.backtrack_origin == "refused"
    assert state.current_node == root


def test_the_server_initiated_backtrack_is_untouched(store, monkeypatch):
    """The two-consecutive-failures rule (§7) is not gated by this change and
    must keep its own origin label, or the containment count conflates them."""
    node = _node_with_prereqs(store)
    db, state, item = _session_on(store, node)
    for p in store.prereqs(node):
        state.theta_map[p] = -4.0
    state.consecutive_failures = CONFIG.consecutive_failures_before_backtrack
    db.save(state)

    # The model asks for a HINT; the server backtracks anyway.
    monkeypatch.setattr(turn_mod, "_call1", lambda *a, **k: (
        turn_mod.Call1Decision(
            student_state="stuck", diagnosis="d", correct=False,
            requested_action="hint_visual", requested_hint_level=1,
            focus_nodes=[], expects="node_click",
        ),
        False,
    ))
    from server.schemas import StudentResponse
    wrong = next(n for n in store.node_ids if n != item.answer)
    phase1 = turn_mod.begin_turn(
        store, db, state, StudentResponse(type="node_click", node_id=wrong))

    assert phase1.action == "backtrack", (
        "the two-failure rule did not fire, so this test proved nothing about "
        "the server path")
    assert phase1.backtrack_origin == "server", (
        "a server-initiated backtrack was labelled as the model's")
