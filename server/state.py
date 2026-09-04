"""Student state in sqlite. CLAUDE.md §2.

THE SERVER OWNS ALL COUNTERS (CLAUDE.md §1.7). `hint_level`, `turns_on_item` and
`n_obs` live here and are advanced by the server alone. The model requests; this
module decides. Anything the model sent arrives prefixed `requested_` and is
treated as a suggestion.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from server.config import CONFIG

class StaleSessionError(RuntimeError):
    """A session whose mastery refers to a graph that has since been replaced."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id            TEXT PRIMARY KEY,
    graph_fingerprint     TEXT NOT NULL DEFAULT '',
    created_at            REAL NOT NULL,
    updated_at            REAL NOT NULL,
    turn_id               INTEGER NOT NULL DEFAULT 0,
    current_node          TEXT,
    current_item_id       TEXT,
    hint_counter          INTEGER NOT NULL DEFAULT 0,
    visual_narrow_level   INTEGER NOT NULL DEFAULT 0,
    turns_on_item         INTEGER NOT NULL DEFAULT 0,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    theta_map             TEXT NOT NULL DEFAULT '{}',
    n_obs                 TEXT NOT NULL DEFAULT '{}',
    completed_items       TEXT NOT NULL DEFAULT '[]',
    history               TEXT NOT NULL DEFAULT '[]',
    session_complete      INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass
class SessionState:
    session_id: str
    #: Content hash of the graph this session's mastery rows refer to.
    graph_fingerprint: str = ""
    turn_id: int = 0
    current_node: Optional[str] = None
    current_item_id: Optional[str] = None
    # Monotonic within an item, reset on item change. Guard layer 2.
    hint_counter: int = 0
    # How far the VISUAL channel has narrowed on this item. Separate from
    # hint_counter because a verbal hint raises the hint level without dimming
    # anything - confounding the two is exactly what makes eval 9.2 unrunnable.
    # Monotonic within an item; only a hint_visual advances it.
    visual_narrow_level: int = 0
    turns_on_item: int = 0
    consecutive_failures: int = 0
    theta_map: dict = field(default_factory=dict)
    n_obs: dict = field(default_factory=dict)
    completed_items: list = field(default_factory=list)
    #: Rolling dialogue history. Call 1 gets the last 6, Call 2 the last 2
    #: (CLAUDE.md §5). Entries are {"role": "tutor"|"student", "text": str}.
    history: list = field(default_factory=list)
    session_complete: bool = False

    # --- counters: the server's job, not the model's ------------------------

    def bump_hint(self, requested_level: int) -> int:
        """Guard layer 2 - hint monotonicity.

        +1 per turn at most, never decreases within an item, capped at HINT_MAX.
        A model asking to jump from 0 to 4 gets 1. A model asking to go back down
        to 0 gets whatever it already had.
        """
        if requested_level > self.hint_counter:
            self.hint_counter = min(self.hint_counter + 1, CONFIG.hint_max)
        return min(self.hint_counter, CONFIG.hint_max)

    @property
    def hint_level(self) -> int:
        return min(self.hint_counter, CONFIG.hint_max)

    @property
    def budget_exhausted(self) -> bool:
        """Guard layer 3 - turn budget."""
        return self.turns_on_item >= CONFIG.turn_budget

    def start_item(self, node_id: str, item_id: str) -> None:
        self.current_node = node_id
        self.current_item_id = item_id
        self.hint_counter = 0
        self.visual_narrow_level = 0
        self.turns_on_item = 0

    def record_history(self, role: str, text: str, keep: int = 12) -> None:
        self.history.append({"role": role, "text": text})
        del self.history[:-keep]

    def recent(self, n: int) -> list:
        return self.history[-n:]


class Store:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        path = str(db_path or CONFIG.state_db_path)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add any column missing from an existing state.db.

        CREATE TABLE IF NOT EXISTS does nothing to a table that already exists,
        so adding a field to SCHEMA leaves every developer's on-disk database one
        column behind and every write failing with `no such column`. The tests
        all run on ":memory:" and never see it, which is exactly why this needs to
        be handled here rather than by remembering to delete the file.

        Additive only: this never drops or rewrites a column. Student state is
        disposable demo data, but silently destroying it mid-session is still the
        wrong default.
        """
        existing = {r["name"] for r in self._conn.execute("PRAGMA table_info(sessions)")}
        for line in SCHEMA.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith(("CREATE", ")", ";")):
                continue
            name, _, definition = line.partition(" ")
            if name and name not in existing and definition.strip():
                self._conn.execute(
                    f"ALTER TABLE sessions ADD COLUMN {name} {definition.strip()}"
                )

    def close(self) -> None:
        self._conn.close()

    def create(
        self,
        initial_theta: dict,
        session_id: Optional[str] = None,
        graph_fingerprint: str = "",
    ) -> SessionState:
        state = SessionState(
            session_id=session_id or f"sess_{uuid.uuid4().hex[:12]}",
            graph_fingerprint=graph_fingerprint,
            theta_map=dict(initial_theta),
            n_obs={k: 0 for k in initial_theta},
        )
        now = time.time()
        self._conn.execute(
            "INSERT INTO sessions (session_id, graph_fingerprint, created_at, updated_at, "
            "theta_map, n_obs) VALUES (?, ?, ?, ?, ?, ?)",
            (state.session_id, state.graph_fingerprint, now, now,
             json.dumps(state.theta_map), json.dumps(state.n_obs)),
        )
        self._conn.commit()
        return state

    def get(self, session_id: str, graph_fingerprint: Optional[str] = None) -> Optional[SessionState]:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        if graph_fingerprint is not None and row["graph_fingerprint"] != graph_fingerprint:
            # Person A swaps graph.json for the real chapter and every theta key
            # in this row now names a node that no longer exists. Failing here
            # with a sentence beats a KeyError deep inside next_node().
            raise StaleSessionError(
                f"session {session_id} was created against a different graph "
                f"({row['graph_fingerprint'] or 'unknown'}, now {graph_fingerprint}). "
                f"Its mastery refers to nodes that no longer exist. "
                f"Start a new session, or delete {CONFIG.state_db_path.name} to reset."
            )
        return SessionState(
            session_id=row["session_id"],
            graph_fingerprint=row["graph_fingerprint"],
            turn_id=row["turn_id"],
            current_node=row["current_node"],
            current_item_id=row["current_item_id"],
            hint_counter=row["hint_counter"],
            visual_narrow_level=row["visual_narrow_level"],
            turns_on_item=row["turns_on_item"],
            consecutive_failures=row["consecutive_failures"],
            theta_map=json.loads(row["theta_map"]),
            n_obs=json.loads(row["n_obs"]),
            completed_items=json.loads(row["completed_items"]),
            history=json.loads(row["history"]),
            session_complete=bool(row["session_complete"]),
        )

    def save(self, state: SessionState) -> None:
        self._conn.execute(
            "UPDATE sessions SET graph_fingerprint=?, updated_at=?, turn_id=?, current_node=?, current_item_id=?, "
            "hint_counter=?, visual_narrow_level=?, turns_on_item=?, consecutive_failures=?, "
            "theta_map=?, n_obs=?, "
            "completed_items=?, history=?, session_complete=? WHERE session_id=?",
            (
                state.graph_fingerprint,
                time.time(),
                state.turn_id,
                state.current_node,
                state.current_item_id,
                state.hint_counter,
                state.visual_narrow_level,
                state.turns_on_item,
                state.consecutive_failures,
                json.dumps(state.theta_map),
                json.dumps(state.n_obs),
                json.dumps(state.completed_items),
                json.dumps(state.history),
                int(state.session_complete),
                state.session_id,
            ),
        )
        self._conn.commit()
