"""Every logged turn says which build wrote it — CLAUDE.md §10, and §9's evidence.

`logs/turns.jsonl` is never truncated. §9.1, §9.4 and §9.5 all read it, so it is
a corpus written by many versions of `server/turn.py`, and aggregating it whole
pools them without saying so.

The concrete case: guard layer 1 fired on 17,433 `backtrack` turns before the
Call 2 fidelity ceiling landed, because backtrack was handed the target node's
label. `backtrack` is in `RECONSTRUCTION_ACTIONS`, so a pass over the whole file
reports those as the model reconstructing the answer parametrically — §6's
headline number, at 24%, from a bug that is fixed and whose current rate is zero.

`eval/provenance.py` exists because a result that carries its value but not its
sampling cannot be trusted. These tests hold the same line one layer down.
"""
from __future__ import annotations

import json

import pytest

from server import turn as turn_mod
from server.config import CONFIG

from .conftest import correct_response, turn


def _records(log_dir):
    path = log_dir / "turns.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_every_turn_record_carries_a_code_stamp(client, session, store):
    data = turn(client, session)
    for _ in range(4):
        data = turn(client, session, correct_response(data, store))

    records = _records(CONFIG.log_dir)
    assert records, "nothing was logged; this test proved nothing"
    for record in records:
        assert record.get("code"), f"unstamped record: {sorted(record)}"


def test_non_turn_events_are_stamped_too(client, session, store):
    """A fallback or a guard trip is evidence in the same file (§10)."""
    turn_mod._log_event("test_event", {"detail": "x"})
    record = _records(CONFIG.log_dir)[-1]
    assert record["event"] == "test_event"
    assert record["code"] == turn_mod.CODE


def test_the_stamp_is_read_once_not_per_turn(client, session, store):
    """Config and provenance are startup values (§13.1). A per-turn subprocess
    would put a git call in the latency budget §5 accounts for."""
    data = turn(client, session)
    turn(client, session, correct_response(data, store))
    stamps = {r["code"] for r in _records(CONFIG.log_dir)}
    assert stamps == {turn_mod.CODE}


def test_a_missing_git_degrades_to_unknown_and_never_raises(monkeypatch):
    """A log stamp must not be able to fail a turn — a clone without git, or a
    tarball, still has to serve."""
    import subprocess

    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", boom)
    assert turn_mod._code_fingerprint() == "unknown"


def test_an_uncommitted_tree_says_so(monkeypatch):
    """`-dirty` is the difference between "this number came from a commit you
    can check out" and "this number came from someone's working copy"."""
    import subprocess

    class Result:
        def __init__(self, out):
            self.stdout = out

    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        return Result("abc1234\n") if "rev-parse" in args else Result(" M server/turn.py\n")

    monkeypatch.setattr(subprocess, "run", fake)
    assert turn_mod._code_fingerprint() == "abc1234-dirty"


def test_the_stamp_never_reaches_the_client(client, session):
    """§1.6: the client renders `utterance` and nothing else, and the response
    field set is a whitelist. Provenance is for the log."""
    data = turn(client, session)
    assert "code" not in data
    assert "code" not in json.dumps(data.get("item") or {})
