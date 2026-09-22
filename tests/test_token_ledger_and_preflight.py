"""The token ledger, and the pre-flight that reads it.

`STATS` counts calls. A quota is denominated in tokens, and a Call 1 on
gpt-oss-120b costs ~2,750 while a Call 2 costs a fraction of that, so
multiplying calls by an average is how a pre-flight passes a machine that is out
of budget. These tests hold the two halves: that spend is recorded truthfully,
including on the responses that failed, and that the checks fail loudly.

The pre-flight exists because every way the recording can go wrong is silent at
the moment it matters - a stale server, a `-dirty` tree, a carried-over
`state.db`, the wrong `MOCK_MODE`, an exhausted daily budget.
"""
from __future__ import annotations

import json
import time

import httpx
import pytest

from server import llm as llm_mod
from server import preflight as PF
from server.config import CONFIG

from .conftest import config_override


# --- the ledger ------------------------------------------------------------

def test_usage_is_normalised_across_both_wire_formats():
    """Anthropic says input/output; Groq says prompt/completion. A ledger that
    understood one would silently record zero for the other provider."""
    assert llm_mod._usage({"usage": {"input_tokens": 10, "output_tokens": 3}}) == (10, 3)
    assert llm_mod._usage({"usage": {"prompt_tokens": 10, "completion_tokens": 3}}) == (10, 3)


def test_a_missing_usage_block_is_zero_not_a_crash():
    """A provider that stops reporting usage must show as zero spend and be
    caught by reconciliation, not take a turn down with it."""
    assert llm_mod._usage({}) == (0, 0)
    assert llm_mod._usage({"usage": {}}) == (0, 0)
    assert llm_mod._usage({"usage": None}) == (0, 0)


def test_a_ledger_write_never_raises(monkeypatch):
    """The same rule the build stamp follows: logging must not be able to fail a
    turn. A read-only logs directory still serves; it just cannot pre-flight."""
    def boom(*a, **k):
        raise OSError("read-only file system")

    # Patched at the serialisation step, which every path through the writer
    # reaches, so this cannot pass by failing to bite.
    monkeypatch.setattr(llm_mod.json, "dumps", boom)
    llm_mod._write_ledger(CONFIG.call1, "call1",
                          {"usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    assert PF.read_ledger() == [], "the write was supposed to have failed"


# --- the ledger records what was actually spent ----------------------------

OK_BODY = {
    "choices": [{"message": {"tool_calls": [{"function": {
        "name": "say", "arguments": json.dumps({"utterance": "Which lit one fits?"})}}]}}],
    "usage": {"prompt_tokens": 900, "completion_tokens": 100},
}
#: A 200 whose tool call is unparseable. The tokens were still spent.
GARBLED_BODY = {
    "choices": [{"message": {"tool_calls": [{"function": {
        "name": "say", "arguments": "{not json"}}]}}],
    "usage": {"prompt_tokens": 700, "completion_tokens": 50},
}


def _wire(monkeypatch, *responses):
    queue = list(responses)

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, headers=None, json=None):
            status, body = queue.pop(0)
            return httpx.Response(status, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm_mod.httpx, "Client", FakeClient)


@pytest.fixture()
def _groq():
    with config_override(llm_provider="groq", groq_api_key="g-key",
                         llm_max_retries=1, mock_mode=False):
        yield


def test_a_successful_call_is_ledgered(monkeypatch, _groq):
    _wire(monkeypatch, (200, OK_BODY))
    llm_mod.call2(action="ask", hint_level=0, focus_labels=[], n_lit=52, recent=[])

    rows = PF.read_ledger()
    assert len(rows) == 1
    row = rows[0]
    assert row["call"] == "call2"
    assert row["prompt_tokens"] == 900 and row["completion_tokens"] == 100
    assert row["total_tokens"] == 1000
    assert row["model"] == CONFIG.call2.model
    assert row["provider"] == "groq"


def test_a_response_that_failed_to_parse_is_still_ledgered(monkeypatch, _groq):
    """The point of writing before extraction. A ledger that only recorded
    successes would under-report exactly the days that went badly."""
    _wire(monkeypatch, (200, GARBLED_BODY), (200, OK_BODY))
    llm_mod.call2(action="ask", hint_level=0, focus_labels=[], n_lit=52, recent=[])

    rows = PF.read_ledger()
    assert len(rows) == 2, "the unparseable response cost tokens and was not recorded"
    assert sum(r["total_tokens"] for r in rows) == 750 + 1000


# --- the window ------------------------------------------------------------

def _row(ts, model, total, call="call1"):
    return {"ts": ts, "call": call, "model": model, "provider": "groq",
            "prompt_tokens": total, "completion_tokens": 0, "total_tokens": total}


def test_window_spend_counts_only_the_named_model():
    now = time.time()
    rows = [_row(now, "a", 100), _row(now, "b", 999)]
    assert PF.window_spend(rows, "a", now=now) == 100


def test_window_spend_excludes_anything_older_than_24h():
    now = time.time()
    rows = [_row(now - 60, "a", 100), _row(now - PF.WINDOW_S - 60, "a", 999)]
    assert PF.window_spend(rows, "a", now=now) == 100


def test_the_budget_check_fails_when_a_take_would_not_fit():
    now = time.time()
    model = CONFIG.call1.model
    with config_override(tpd_limit=100_000, take_budget=40_000):
        rows = [_row(now, model, 70_000)]
        check = PF.check_token_budget(rows, now=now)
        assert not check.ok, "30,000 left against a 40,000 take budget passed"
        assert "70,000" in check.detail


def test_the_budget_check_passes_when_a_take_fits():
    now = time.time()
    model = CONFIG.call1.model
    with config_override(tpd_limit=100_000, take_budget=40_000):
        check = PF.check_token_budget([_row(now, model, 10_000)], now=now)
        assert check.ok and not check.undecided


def test_an_empty_ledger_warns_rather_than_passing_silently():
    """Zero spend is the truth on a machine that has not called out, and it is
    also what a broken ledger looks like. It must not read as a clean pass."""
    check = PF.check_token_budget([], now=time.time())
    assert check.undecided, "an empty ledger was reported as a verified pass"


# --- the freeze ------------------------------------------------------------

def test_a_model_call_inside_the_window_fails_the_freeze_check():
    now = time.time()
    check = PF.check_no_recent_eval([_row(now - 3600, "any", 10)], now=now)
    assert not check.ok
    assert "1.0h ago" in check.detail


def test_an_old_model_call_does_not_fail_the_freeze_check():
    now = time.time()
    check = PF.check_no_recent_eval([_row(now - PF.WINDOW_S - 1, "any", 10)], now=now)
    assert check.ok


# --- the declared mode -----------------------------------------------------

def test_mock_mode_must_be_declared_not_merely_observed():
    """`MOCK_MODE` is read once at startup and both settings look alike. A
    pre-flight that printed the value without comparing it to an intention
    would pass every configuration."""
    with config_override(mock_mode=True):
        assert not PF.check_mock_mode(None).ok


def test_mock_mode_mismatch_fails():
    with config_override(mock_mode=False):
        assert not PF.check_mock_mode(True).ok
        assert PF.check_mock_mode(False).ok


# --- state.db --------------------------------------------------------------

def test_a_carried_over_state_db_fails(tmp_path):
    db = tmp_path / "state.db"
    db.write_bytes(b"x")
    assert not PF.check_fresh_state(db).ok
    assert PF.check_fresh_state(tmp_path / "absent.db").ok


# --- the report ------------------------------------------------------------

def test_the_report_pairs_call1_and_call2_into_turns():
    model = CONFIG.call1.model
    rows = [
        _row(0, model, 2_000, call="call1"),
        _row(0, CONFIG.call2.model, 500, call="call2"),
        _row(0, model, 4_000, call="call1"),
        _row(0, CONFIG.call2.model, 1_000, call="call2"),
    ]
    out = PF.report(rows)
    assert "mean 3,750" in out or "mean 3750" in out
    assert "max 5,000" in out


def test_the_report_says_so_when_no_turn_is_complete():
    out = PF.report([_row(0, CONFIG.call1.model, 2_000, call="call1")])
    assert "no complete turn" in out


def test_the_report_on_an_empty_ledger_is_an_instruction_not_a_zero():
    out = PF.report([])
    assert "empty" in out and "TAKE_BUDGET" in out


# --- wiring ----------------------------------------------------------------

def test_a_failing_check_makes_the_run_not_ready():
    checks = PF.run(expect_mock=None)
    assert any(not c.ok and not c.undecided for c in checks), (
        "MOCK_MODE was not declared and nothing failed")


def test_take_budget_and_tpd_are_config_not_literals():
    """CLAUDE.md §13.1. A pre-flight threshold typed into the check is a
    threshold nobody can change on the day."""
    assert isinstance(CONFIG.tpd_limit, int)
    assert isinstance(CONFIG.take_budget, int)
    with config_override(tpd_limit=1, take_budget=1):
        assert CONFIG.tpd_limit == 1
