"""eval.leak_monitor — §6.1's rate, and the four ways of getting it wrong.

§6 asks for the layer-1 hit rate and calls it free. It was logged from the start
and never aggregated, so these tests are mostly about what the aggregator must
REFUSE to do: pool builds, pool actions, pool mock with real, or report a rate
over a population that cannot exhibit the phenomenon.

Each refusal is here because the corresponding mistake is already in this
project's history.
"""
from __future__ import annotations

import json

import pytest

from eval import leak_monitor as LM


def _turn(**kw):
    record = {
        "ts": 0.0,
        "code": "abc1234",
        "session_id": "s1",
        "turn_id": 1,
        "mock": True,
        "server_action": "hint_verbal",
        "item_id": "itm_0001",
        "leak_note": None,
    }
    record.update(kw)
    return record


def _log(tmp_path, records):
    path = tmp_path / "turns.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return path


# --- the action split ------------------------------------------------------

def test_the_bucket_split_is_the_server_s_not_a_restatement():
    """If an action moves between buckets it must move in one place, or the
    eval reports a number the running system disagrees with."""
    from server.guards import RECONSTRUCTION_ACTIONS

    for action in RECONSTRUCTION_ACTIONS:
        assert LM.bucket_for(action) == "parametric_reconstruction"
    for action in ("advance", "explain", "resolved_with_support"):
        assert LM.bucket_for(action) == "authorised_naming"


def test_authorised_naming_is_not_pooled_into_the_headline(tmp_path):
    """`advance` is MEANT to name the answer. Pooling it inflates §6's figure."""
    path = _log(tmp_path, [
        _turn(server_action="advance", mock=False, leak_note="leak_monitor_hit: alias 'x' at 1.00"),
        _turn(server_action="hint_verbal", mock=False),
    ])
    result = LM.measure(path)
    assert result["headline"]["hits"] == 0
    assert result["headline"]["checks"] == 1


# --- the build split -------------------------------------------------------

def test_builds_are_not_pooled(tmp_path):
    path = _log(tmp_path, [
        _turn(code="old", leak_note="leak_monitor_hit: alias 'x' at 1.00"),
        _turn(code="new"),
    ])
    arms = LM.measure(path)["arms"]
    assert "old [mock]" in arms and "new [mock]" in arms
    assert arms["old [mock]"]["parametric_reconstruction"]["hits"] == 1
    assert arms["new [mock]"]["parametric_reconstruction"]["hits"] == 0


def test_unstamped_turns_are_counted_but_never_reach_the_headline(tmp_path):
    """The 17,433 backtrack hits from before the fidelity ceiling are real
    turns and a fixed bug. They belong in the report and not in the result."""
    unstamped = _turn(server_action="backtrack",
                      leak_note="leak_monitor_hit: alias 'x' at 1.00")
    del unstamped["code"]
    path = _log(tmp_path, [unstamped, _turn(mock=False)])

    result = LM.measure(path)
    assert result["unstamped_turns"] == 1
    assert f"{LM.UNSTAMPED} [mock]" in result["arms"]
    assert result["headline"]["hits"] == 0


# --- the mock split --------------------------------------------------------

def test_a_mock_only_log_refuses_to_produce_a_headline(tmp_path):
    """A template lookup has no weights. 0% over 10,000 mock turns is not weak
    evidence of no leakage; it is no evidence, and it reads identically."""
    path = _log(tmp_path, [_turn() for _ in range(50)])
    head = LM.measure(path)["headline"]
    assert head["rate"] is None
    assert "real" in head["blocked_by"]


def test_mock_and_real_are_never_pooled(tmp_path):
    path = _log(tmp_path, [_turn(mock=True), _turn(mock=False)])
    arms = LM.measure(path)["arms"]
    assert "abc1234 [mock]" in arms
    assert "abc1234 [real]" in arms


def test_a_real_turn_produces_a_headline(tmp_path):
    path = _log(tmp_path, [
        _turn(mock=False, item_id=f"itm_{i:04d}") for i in range(1, 5)
    ] + [_turn(mock=False, item_id="itm_0005",
               leak_note="leak_monitor_hit: alias 'slow start' at 1.00")])
    head = LM.measure(path)["headline"]
    assert head["checks"] == 5
    assert head["hits"] == 1
    assert head["rate"] == 0.2


# --- sampling --------------------------------------------------------------

def test_every_arm_carries_provenance(tmp_path):
    path = _log(tmp_path, [_turn(), _turn(item_id="itm_0002")])
    for buckets in LM.measure(path)["arms"].values():
        for cell in buckets.values():
            assert "provenance" in cell
            assert cell["provenance"]["distinct"] >= 1


def test_a_rate_over_one_item_is_visible_as_such(tmp_path):
    """§9.1 reported a rate over one item out of 101 for four days. The
    provenance block is what makes that assertable instead of invisible."""
    path = _log(tmp_path, [_turn() for _ in range(200)])
    cell = LM.measure(path)["arms"]["abc1234 [mock]"]["parametric_reconstruction"]
    assert cell["provenance"]["distinct"] == 1
    assert cell["provenance"]["observations"] == 200
    from eval.provenance import Provenance
    prov = Provenance(**{k: v for k, v in cell["provenance"].items()
                         if k in {"population", "distinct", "observations",
                                  "unit", "expect_full"}})
    assert prov.degenerate


# --- reading the file ------------------------------------------------------

def test_turns_with_no_item_are_not_counted_as_clean_checks(tmp_path):
    """screen_utterance only runs when there is an answer to screen against.
    Counting a session-complete turn as a clean check dilutes every rate."""
    path = _log(tmp_path, [_turn(item_id=None), _turn()])
    arms = LM.measure(path)["arms"]
    assert arms["abc1234 [mock]"]["parametric_reconstruction"]["checks"] == 1


def test_non_turn_events_are_counted_separately(tmp_path):
    path = _log(tmp_path, [{"ts": 0, "code": "abc1234", "event": "call2_fallback"}, _turn()])
    result = LM.measure(path)
    assert result["events"] == 1
    assert result["turns"] == 1


def test_a_torn_line_is_reported_not_fatal(tmp_path):
    """§10 forbids silent anything, including a half-written last line from a
    killed run."""
    path = tmp_path / "turns.jsonl"
    path.write_text(json.dumps(_turn()) + "\n{\"ts\": 0, \"cod\n", encoding="utf-8")
    result = LM.measure(path)
    assert result["malformed"] == 1
    assert result["turns"] == 1


def test_a_missing_log_is_an_empty_report_not_a_crash(tmp_path):
    result = LM.measure(tmp_path / "nope.jsonl")
    assert result["turns"] == 0
    assert result["headline"]["rate"] is None


def test_the_matched_alias_is_extracted_for_the_report():
    """A hit concentrated on one surface is a vocabulary problem; one spread
    across the bank is a model problem. They need opposite responses."""
    assert LM._alias_of("leak_monitor_hit: alias 'congestion control' at 1.00") == \
        "congestion control"
    assert LM._alias_of("leak_monitor_hit: similarity 0.91") is None


def test_render_never_quotes_a_rate_it_refused_to_compute(tmp_path):
    path = _log(tmp_path, [_turn() for _ in range(10)])
    text = LM.render(LM.measure(path))
    assert "NOT MEASURABLE" in text
    assert "needs a key" in text
