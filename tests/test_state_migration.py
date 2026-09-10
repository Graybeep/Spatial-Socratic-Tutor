"""Schema drift on an EXISTING state.db.

Every other test runs on ":memory:", which is born at the current schema and so
can never see this class of failure. This one writes a real file at an older
schema first, which is the only way to catch it.

Found the hard way: adding visual_narrow_level made every POST /session return
500 against a state.db created before it, while the whole suite stayed green.
"""
from __future__ import annotations

import sqlite3

import pytest

from server.state import SessionState, StaleSessionError, Store

OLD_SCHEMA = """
CREATE TABLE sessions (
    session_id            TEXT PRIMARY KEY,
    created_at            REAL NOT NULL,
    updated_at            REAL NOT NULL,
    turn_id               INTEGER NOT NULL DEFAULT 0,
    current_node          TEXT,
    current_item_id       TEXT,
    hint_counter          INTEGER NOT NULL DEFAULT 0,
    turns_on_item         INTEGER NOT NULL DEFAULT 0,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    theta_map             TEXT NOT NULL DEFAULT '{}',
    n_obs                 TEXT NOT NULL DEFAULT '{}',
    completed_items       TEXT NOT NULL DEFAULT '[]',
    history               TEXT NOT NULL DEFAULT '[]',
    session_complete      INTEGER NOT NULL DEFAULT 0
);
"""


@pytest.fixture()
def stale_db(tmp_path):
    path = tmp_path / "state.db"
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    conn.execute(
        "INSERT INTO sessions (session_id, created_at, updated_at, theta_map, n_obs) "
        "VALUES ('sess_old', 0, 0, '{\"a\": 0.25}', '{\"a\": 3}')"
    )
    conn.commit()
    conn.close()
    return path


def test_opening_a_stale_db_adds_the_missing_column(stale_db):
    store = Store(db_path=stale_db)
    columns = {
        r["name"] for r in store._conn.execute("PRAGMA table_info(sessions)")
    }
    assert "visual_narrow_level" in columns
    store.close()


def test_a_stale_db_can_still_be_written_after_migration(stale_db):
    store = Store(db_path=stale_db)
    state = store.create({"a": 0.0, "b": 0.0})
    state.visual_narrow_level = 3
    state.turn_id = 7
    store.save(state)

    reloaded = store.get(state.session_id)
    assert reloaded is not None
    assert reloaded.visual_narrow_level == 3
    assert reloaded.turn_id == 7
    store.close()


def test_migration_preserves_existing_rows(stale_db):
    """Migration must not DESTROY an old row. Whether the server will USE it is
    a separate question, answered by the fingerprint checks below - the row is
    still there to be inspected, exported or replayed."""
    store = Store(db_path=stale_db)
    old = store.get("sess_old", code_fingerprint="")
    assert old is not None, "migration dropped an existing session"
    assert old.theta_map == {"a": 0.25}
    assert old.n_obs == {"a": 3}
    assert old.visual_narrow_level == 0, "new column should default, not corrupt"
    assert old.code_fingerprint == "", "a pre-stamp row must not claim a build"
    store.close()


def test_a_row_written_before_the_stamp_is_refused(stale_db):
    """The case that motivated this: a server left running across a code change
    resumes sessions whose mastery was computed by the old logic. The graph
    fingerprint cannot see it - the graph did not move."""
    store = Store(db_path=stale_db)
    with pytest.raises(StaleSessionError) as exc:
        store.get("sess_old")
    assert "different build" in str(exc.value)
    assert "before the stamp existed" in str(exc.value)
    store.close()


def test_a_matching_graph_does_not_excuse_a_mismatched_build(stale_db):
    """Both guards run, and the graph one passing means nothing about the other."""
    store = Store(db_path=stale_db)
    row = store._conn.execute(
        "SELECT graph_fingerprint FROM sessions WHERE session_id='sess_old'"
    ).fetchone()
    with pytest.raises(StaleSessionError) as exc:
        store.get("sess_old", graph_fingerprint=row["graph_fingerprint"],
                  code_fingerprint="some-other-build")
    assert "different build" in str(exc.value)
    store.close()


def test_a_session_written_by_this_build_loads(stale_db):
    store = Store(db_path=stale_db)
    state = store.create({"a": 0.0})
    store.save(state)
    assert store.get(state.session_id) is not None
    store.close()


def test_migration_is_idempotent(stale_db):
    Store(db_path=stale_db).close()
    store = Store(db_path=stale_db)  # second open must not fail
    state = store.create({"a": 0.0})
    store.save(state)
    assert store.get(state.session_id) is not None
    store.close()


def test_a_fresh_db_needs_no_migration(tmp_path):
    store = Store(db_path=tmp_path / "fresh.db")
    state = store.create({"a": 0.0})
    store.save(state)
    assert isinstance(store.get(state.session_id), SessionState)
    store.close()


def test_the_endpoint_returns_409_on_a_build_mismatch(client, session):
    """End to end: the drift check has to reach the client as a recoverable
    state, not a 500. A demo that dies here looks broken; one that says "start a
    new session" looks careful."""
    from server import main as main_mod

    main_mod.DB._conn.execute(
        "UPDATE sessions SET code_fingerprint='a-different-build' WHERE session_id=?",
        (session,),
    )
    main_mod.DB._conn.commit()

    r = client.post("/turn", json={"session_id": session, "response": None})
    assert r.status_code == 409
    assert "different build" in r.json()["detail"]
