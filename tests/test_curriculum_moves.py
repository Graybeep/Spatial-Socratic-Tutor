"""eval.curriculum_moves - the §5.6 count, and the mistake it was built to fix.

The hand count behind `report.md` §5.6 reported "the curriculum moved on 13" and
then, two sentences later, said that one of those 13 moved nothing. Both
statements came from the same pass over the same log. The distinction these
tests defend is the one that pass collapsed: a turn that EMITS a curriculum
action is not a turn on which the curriculum MOVED.

The rest are refusals inherited from `eval/leak_monitor.py` - do not pool
builds, do not pool mock with real - which are here because the corresponding
mistakes are already in this project's history.
"""
from __future__ import annotations

import json

from eval import curriculum_moves as CM


def _turn(**kw):
    record = {
        "ts": 0.0,
        "code": "abc1234",
        "session_id": "s1",
        "turn_id": 1,
        "mock": False,
        "server_action": "hint_visual",
        "item_id": "itm_0001",
        "call1": {"requested_action": "hint_visual"},
    }
    record.update(kw)
    return record


def _log(tmp_path, records):
    path = tmp_path / "turns.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n",
                    encoding="utf-8")
    return path


def _only(result):
    assert len(result) == 1, f"expected one partition, got {sorted(result)}"
    return next(iter(result.values()))


# --- the distinction the hand count collapsed ------------------------------

def test_a_backtrack_that_moved_nothing_is_emitted_but_not_moved():
    """The day-19 hole, as a number. This is the whole point of the module."""
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0021"),
        _turn(turn_id=2, item_id="itm_0021", server_action="backtrack",
              call1={"requested_action": "backtrack"}),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["emitted_total"] == 1
    assert arm["moved_total"] == 0, (
        "a backtrack that left the student on the same item was counted as a "
        "curriculum move - this is the day-18 count's error, reproduced")
    assert arm["emitted"]["backtrack:model"] == 1
    assert arm["moved"].get("backtrack:model", 0) == 0


def test_the_stationary_turn_is_named_not_merely_subtracted():
    """A count that differs from another count by one is not a finding until it
    says which turn. The day-19 bug was found by chasing exactly this."""
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0021"),
        _turn(turn_id=2, item_id="itm_0021", server_action="backtrack",
              call1={"requested_action": "backtrack"}),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert len(arm["stationary"]) == 1
    row = arm["stationary"][0]
    assert row["turn_id"] == 2 and row["item_id"] == "itm_0021"
    assert "backtrack" in row["label"]


def test_a_backtrack_that_did_move_counts_in_both():
    """The counterpart. A module that only ever reports `moved` short of
    `emitted` is as wrong as one that never does, and looks identical from the
    day-18 log alone."""
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0021"),
        _turn(turn_id=2, item_id="itm_0001", server_action="backtrack",
              call1={"requested_action": "hint_visual"}),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["emitted_total"] == 1 and arm["moved_total"] == 1
    assert arm["emitted"]["backtrack:server"] == 1
    assert arm["moved"]["backtrack:server"] == 1
    assert arm["stationary"] == []


def test_a_curriculum_action_on_a_first_turn_is_undefined_not_unmoved():
    """Nothing precedes it, so `item_id` cannot have changed. Counting that as
    stationary would invent the very defect the module reports."""
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0001", server_action="advance",
              call1={"requested_action": "advance"}),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["emitted_total"] == 1
    assert arm["moved_total"] == 0
    assert arm["first_turn_moves"] == 1
    assert arm["stationary"] == [], (
        "a first turn was reported as a curriculum action that moved nothing")


def test_movement_is_tracked_per_session_not_across_the_file():
    """Two sessions interleaved in one log must not read as one another's
    previous item. `logs/turns.jsonl` is append-only and concurrent."""
    log = _log(_tmp(), [
        _turn(session_id="s1", turn_id=1, item_id="itm_0001"),
        _turn(session_id="s2", turn_id=1, item_id="itm_0099"),
        _turn(session_id="s1", turn_id=2, item_id="itm_0001",
              server_action="backtrack", call1={"requested_action": "backtrack"}),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["moved_total"] == 0, (
        "s2's item was read as s1's previous item, so a stationary turn "
        "looked like a move")
    assert arm["sessions"] == 2


# --- the origin label ------------------------------------------------------

def test_the_logged_origin_is_used_when_the_record_carries_one():
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0021"),
        _turn(turn_id=2, item_id="itm_0001", server_action="backtrack",
              call1={"requested_action": "hint_visual"}, backtrack_origin="server"),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["emitted"]["backtrack:server"] == 1
    assert arm["origin_disagreements"] == []


def test_a_logged_origin_that_contradicts_the_record_is_reported():
    """A field that has drifted from the behaviour it names is worth more as a
    visible complaint than as a quiet default."""
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0021"),
        _turn(turn_id=2, item_id="itm_0001", server_action="backtrack",
              call1={"requested_action": "backtrack"}, backtrack_origin="server"),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert len(arm["origin_disagreements"]) == 1
    row = arm["origin_disagreements"][0]
    assert row["logged"] == "server" and row["inferred"] == "model"


def test_a_pre_day_19_record_still_gets_an_origin():
    """Every record before day 19 predates the field. The historical corpus is
    the one the §5.6 count is over, so inference has to work without it."""
    record = _turn(server_action="backtrack", call1={"requested_action": "backtrack"})
    assert "backtrack_origin" not in record
    assert CM.infer_origin(record) == "model"
    record["call1"] = {"requested_action": "hint_visual"}
    assert CM.infer_origin(record) == "server"


def test_the_inference_cannot_separate_a_coincident_two_failure_backtrack():
    """The documented bound, pinned so the docstring cannot quietly become
    false. A §7 two-failure backtrack on a turn where Call 1 also asked to step
    back reads as the model's, because `requested_action` is all there is to
    read. This is the ambiguity `backtrack_origin` was added to remove, and on
    pre-day-19 records it makes `backtrack:model` an upper bound."""
    coincident = _turn(server_action="backtrack",
                       call1={"requested_action": "backtrack"})
    assert CM.infer_origin(coincident) == "model"

    # With the field present the server's move is attributed correctly, and the
    # disagreement is surfaced rather than hidden.
    coincident["backtrack_origin"] = "server"
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0026"),
        dict(coincident, turn_id=2, item_id="itm_0021"),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["emitted"]["backtrack:server"] == 1
    assert len(arm["origin_disagreements"]) == 1


def test_a_turn_that_did_not_backtrack_has_no_origin():
    assert CM.infer_origin(_turn(server_action="advance")) is None
    assert CM.infer_origin(_turn(server_action="hint_verbal")) is None


def test_the_origin_vocabulary_matches_the_server_s():
    """The eval and the server must not disagree about which labels exist."""
    import inspect

    from server import turn as turn_mod

    source = inspect.getsource(turn_mod)
    for origin in CM.ORIGINS:
        assert f'backtrack_origin = "{origin}"' in source, (
            f"eval names an origin {origin!r} that server/turn.py never writes")


# --- the override count ----------------------------------------------------

def test_the_override_count_is_reported_against_both_denominators():
    """`diagnosis-readthrough.md` quoted this with the day-12 and day-18 columns
    using different denominators - 12 moved against 13 emitted - and the two
    coincide often enough that the mismatch survived being read. Reporting both
    is what stops them drifting apart again."""
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0021"),
        # server overrode: asked for a hint, got a backtrack, and it moved.
        _turn(turn_id=2, item_id="itm_0001", server_action="backtrack",
              call1={"requested_action": "hint_visual"}),
        # server agreed: asked to advance, advanced.
        _turn(turn_id=3, item_id="itm_0002", server_action="advance",
              call1={"requested_action": "advance"}),
        # emitted but stationary, and an override.
        _turn(turn_id=4, item_id="itm_0002", server_action="backtrack",
              call1={"requested_action": "hint_verbal"}),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["emitted_total"] == 3 and arm["moved_total"] == 2
    assert arm["overrode_emitted"] == 2
    assert arm["overrode_moved"] == 1, (
        "a stationary override was counted against the moved denominator")


def test_agreement_is_not_counted_as_an_override():
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0021"),
        _turn(turn_id=2, item_id="itm_0001", server_action="advance",
              call1={"requested_action": "advance"}),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["moved_total"] == 1
    assert arm["overrode_moved"] == 0 and arm["overrode_emitted"] == 0


# --- the refusals ----------------------------------------------------------

def test_builds_are_not_pooled_by_default():
    """The rule under measurement changed on day 19. Pooling counts two
    different servers as one."""
    log = _log(_tmp(), [
        _turn(code="old", turn_id=1, item_id="itm_0021"),
        _turn(code="old", turn_id=2, item_id="itm_0021", server_action="backtrack",
              call1={"requested_action": "backtrack"}),
        _turn(code="new", turn_id=1, item_id="itm_0021"),
        _turn(code="new", turn_id=2, item_id="itm_0001", server_action="backtrack",
              call1={"requested_action": "backtrack"}),
    ])
    result = CM.measure(path=log, build=None)
    assert len(result) == 2, f"builds were pooled: {sorted(result)}"
    assert result["old:real"]["moved_total"] == 0
    assert result["new:real"]["moved_total"] == 1


def test_pooling_builds_is_opt_in_and_says_so():
    log = _log(_tmp(), [
        _turn(code="old", turn_id=1, item_id="itm_0021"),
        _turn(code="new", turn_id=2, item_id="itm_0001", server_action="advance",
              call1={"requested_action": "advance"}),
    ])
    result = CM.measure(path=log, build=None, pool_builds=True)
    assert len(result) == 1
    assert next(iter(result.values()))["build"] == "pooled"


def test_mock_and_real_are_never_summed():
    """In MOCK_MODE `requested_action` is a template lookup, so an agreement
    rate over it is a property of prompts/ and not of any model."""
    log = _log(_tmp(), [
        _turn(mock=True, session_id="m1", turn_id=1, item_id="itm_0021"),
        _turn(mock=True, session_id="m1", turn_id=2, item_id="itm_0001",
              server_action="advance", call1={"requested_action": "advance"}),
        _turn(mock=False, session_id="r1", turn_id=1, item_id="itm_0021"),
        _turn(mock=False, session_id="r1", turn_id=2, item_id="itm_0001",
              server_action="advance", call1={"requested_action": "advance"}),
    ])
    result = CM.measure(path=log, build="abc1234")
    assert set(result) == {"abc1234:mock", "abc1234:real"}
    assert result["abc1234:mock"]["moved_total"] == 1
    assert result["abc1234:real"]["moved_total"] == 1


def test_a_count_over_one_session_is_flagged_as_unsound():
    """`eval/provenance.py`'s degenerate check, reused rather than re-derived.
    The §5.6 claim generalises over sessions; one session is not a sample."""
    log = _log(_tmp(), [
        _turn(turn_id=1, item_id="itm_0021"),
        _turn(turn_id=2, item_id="itm_0001", server_action="advance",
              call1={"requested_action": "advance"}),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["sessions"] == 1
    assert arm["provenance_problem"], (
        "a count over a single session reported no sampling problem")


def test_non_turn_events_are_not_counted_as_turns():
    """`_log_event` writes guard and fallback events to the same file."""
    log = _log(_tmp(), [
        {"ts": 0.0, "code": "abc1234", "event": "guard_trip", "detail": "x"},
        _turn(turn_id=1, item_id="itm_0001"),
    ])
    arm = _only(CM.measure(path=log, build="abc1234"))
    assert arm["turns"] == 1


def test_an_empty_or_missing_log_renders_an_explanation_not_a_crash():
    assert CM.measure(path=_tmp() / "nothing.jsonl") == {}
    assert "no turns matched" in CM.render({})


# --- helpers ---------------------------------------------------------------

def _tmp():
    """A fresh directory per call. `tmp_path` is a fixture and these helpers are
    called from inside the test bodies, so this stands in for it."""
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp())
