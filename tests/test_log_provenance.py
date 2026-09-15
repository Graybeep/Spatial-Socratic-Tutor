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
import pathlib

import pytest

from server import build_info
from server import config as config_mod
from server import origin
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
    assert record["code"] == build_info.CODE


def test_the_stamp_is_read_once_not_per_turn(client, session, store):
    """Config and provenance are startup values (§13.1). A per-turn subprocess
    would put a git call in the latency budget §5 accounts for."""
    data = turn(client, session)
    turn(client, session, correct_response(data, store))
    stamps = {r["code"] for r in _records(CONFIG.log_dir)}
    assert stamps == {build_info.CODE}


def test_a_missing_git_degrades_to_unknown_and_never_raises(monkeypatch):
    """A log stamp must not be able to fail a turn — a clone without git, or a
    tarball, still has to serve."""
    import subprocess

    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", boom)
    assert build_info.code_fingerprint() == "unknown"


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
    assert build_info.code_fingerprint() == "abc1234-dirty"


def test_the_stamp_never_reaches_the_client(client, session):
    """§1.6: the client renders `utterance` and nothing else, and the response
    field set is a whitelist. Provenance is for the log."""
    data = turn(client, session)
    assert "code" not in data
    assert "code" not in json.dumps(data.get("item") or {})


# --- the log is evidence, so the suite must not write into it -----------------


def _real_log() -> "pathlib.Path":
    """Where a server started from this repo would actually log."""
    return config_mod.ROOT / "logs" / "turns.jsonl"


def test_the_suite_never_writes_to_the_real_turn_log(store):
    """Autouse isolation, asserted rather than assumed (CLAUDE.md §13.2).

    This test takes the `store` fixture and NOT `client`, which is precisely the
    combination that leaked: `store` does not touch config, so before
    `_isolate_the_turn_log` was autouse, driving a turn from here appended to the
    demo's own `logs/turns.jsonl`.
    """
    assert CONFIG.log_dir.resolve() != (config_mod.ROOT / "logs").resolve(), (
        "CONFIG.log_dir points at the real logs/ during a test; "
        "_isolate_the_turn_log is not in effect"
    )

    real = _real_log()
    before = real.stat().st_size if real.exists() else None

    turn_mod._log_event("isolation_probe", {"detail": "must not land in logs/"})

    after = real.stat().st_size if real.exists() else None
    assert after == before, (
        f"the suite wrote {after - (before or 0)} bytes into {real}; "
        "logs/turns.jsonl is §6.1 and §9.5 evidence and no test may append to it"
    )

    written = _records(CONFIG.log_dir)
    assert written and written[-1]["event"] == "isolation_probe", (
        "the event went nowhere at all; this test would pass on a broken logger"
    )


# --- and who drove it ---------------------------------------------------------


def test_turn_records_carry_an_origin(client, session, store):
    """§9.5 reads `diagnosis` to ask whether the tutor's model of the student is
    real. A scripted policy's dialogue answers a different question."""
    data = turn(client, session)
    turn(client, session, correct_response(data, store))

    records = [r for r in _records(CONFIG.log_dir) if "turn_id" in r]
    assert records, "nothing was logged; this test proved nothing"
    for record in records:
        assert record["origin"] == origin.SERVER, (
            f"an ordinary HTTP turn stamped {record['origin']!r}; the default "
            "must be the honest one"
        )


def test_declared_origin_is_stamped_and_restored():
    with origin.declare("eval:probe"):
        turn_mod._log_event("inside", {})
        assert origin.current() == "eval:probe"
    turn_mod._log_event("outside", {})

    by_kind = {r["event"]: r for r in _records(CONFIG.log_dir) if "event" in r}
    assert by_kind["inside"]["origin"] == "eval:probe"
    assert by_kind["outside"]["origin"] == origin.SERVER


def test_a_crashed_driver_does_not_leak_its_origin():
    """A failed eval must not leave the process stamping every later turn."""
    with pytest.raises(RuntimeError):
        with origin.declare("eval:crashes"):
            raise RuntimeError("boom")
    assert origin.current() == origin.SERVER


def test_an_empty_origin_is_refused():
    with pytest.raises(ValueError):
        with origin.declare(""):
            pass


def test_a_real_turn_record_names_the_model(client, session, store):
    """`code` names the build, `origin` the driver; neither implies the model.
    CALL1_MODEL is config, so one commit can be two different models."""
    from .conftest import config_override
    data = turn(client, session)
    turn(client, session, correct_response(data, store))
    records = [r for r in _records(CONFIG.log_dir) if "turn_id" in r]
    assert records
    for r in records:
        assert "call1_model" in r and "provider" in r, sorted(r)

    # Under the mock there is no model, and naming one would be a lie that
    # reads exactly like a real stamp three weeks later.
    assert all(r["call1_model"] is None for r in records), (
        "MOCK_MODE records name a model they did not call"
    )
