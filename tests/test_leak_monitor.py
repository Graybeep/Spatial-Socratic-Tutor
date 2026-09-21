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


def _arm(build, mode="mock", driver=LM.UNKNOWN_ORIGIN):
    """Arm key, spelled by the module rather than by this file."""
    return LM.arm_id(build, mode, driver)


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
    result = LM.measure(path, build="abc1234")
    assert result["headline"]["hits"] == 0
    assert result["headline"]["checks"] == 1


# --- the build split -------------------------------------------------------

def test_builds_are_not_pooled(tmp_path):
    path = _log(tmp_path, [
        _turn(code="old", leak_note="leak_monitor_hit: alias 'x' at 1.00"),
        _turn(code="new"),
    ])
    arms = LM.measure(path)["arms"]
    old_arm, new_arm = _arm("old"), _arm("new")
    assert old_arm in arms and new_arm in arms
    assert arms[old_arm]["parametric_reconstruction"]["hits"] == 1
    assert arms[new_arm]["parametric_reconstruction"]["hits"] == 0


def test_unstamped_turns_are_counted_but_never_reach_the_headline(tmp_path):
    """The 17,433 backtrack hits from before the fidelity ceiling are real
    turns and a fixed bug. They belong in the report and not in the result."""
    unstamped = _turn(server_action="backtrack",
                      leak_note="leak_monitor_hit: alias 'x' at 1.00")
    del unstamped["code"]
    path = _log(tmp_path, [unstamped, _turn(mock=False)])

    result = LM.measure(path)
    assert result["unstamped_turns"] == 1
    assert _arm(LM.UNSTAMPED) in result["arms"]
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
    assert _arm("abc1234") in arms
    assert _arm("abc1234", "real") in arms


def test_a_real_turn_produces_a_headline(tmp_path):
    path = _log(tmp_path, [
        _turn(mock=False, item_id=f"itm_{i:04d}") for i in range(1, 5)
    ] + [_turn(mock=False, item_id="itm_0005",
               leak_note="leak_monitor_hit: alias 'slow start' at 1.00")])
    head = LM.measure(path, build="abc1234")["headline"]
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
    cell = LM.measure(path)["arms"][_arm("abc1234")]["parametric_reconstruction"]
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
    assert arms[_arm("abc1234")]["parametric_reconstruction"]["checks"] == 1


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


# --- origin partitioning ------------------------------------------------------


def test_arms_are_split_by_origin(tmp_path):
    """A scripted sweep and a person are two populations, and once a key lands
    they are both `[real]` at the same build (server/origin.py)."""
    records = [
        _turn(mock=False, origin="server", item_id=f"itm_{i:04d}")
        for i in range(4)
    ] + [
        _turn(mock=False, origin="eval:adversarial:visual_only:zero",
              item_id=f"itm_{i:04d}")
        for i in range(4)
    ]
    result = LM.measure(_log(tmp_path, records), build="abc1234")

    keys = sorted(result["arms"])
    assert len(keys) == 2, f"origins were pooled into one arm: {keys}"
    assert any("<server>" in k for k in keys), keys
    assert any("<eval:adversarial" in k for k in keys), keys

    assert result["headline"]["mixed_origins"] is True
    assert "server" in result["headline"]["origins"]


def test_a_turn_without_an_origin_is_not_assumed_human(tmp_path):
    """Everything logged before day 12 has no origin. Calling it `server` would
    put ~650k simulated turns into §9.5's sample pool."""
    record = _turn(mock=False)
    record.pop("origin", None)
    result = LM.measure(_log(tmp_path, [record]), build="abc1234")

    assert LM.UNKNOWN_ORIGIN in result["origins"]
    assert result["headline"]["origins"] == [LM.UNKNOWN_ORIGIN]
    assert "server" not in result["headline"]["origins"]


def test_the_headline_filters_on_fields_not_on_key_spelling(tmp_path):
    """The arm id gained `<origin>`; a filter that matched `endswith("[real]")`
    would have started silently excluding every real arm."""
    result = LM.measure(_log(tmp_path, [
        _turn(mock=False, origin="server", item_id="itm_0001"),
        _turn(mock=True, origin="server", item_id="itm_0002"),
    ]), build="abc1234")
    assert result["headline"]["blocked_by"] is None, (
        "a real stamped turn was not counted; the headline is matching on the "
        "shape of the arm id rather than on its fields"
    )
    assert result["headline"]["checks"] == 1, "a mock turn reached §6.1's number"


# --- templates are not model output ----------------------------------------

def _canned(action="hint_verbal"):
    """A real fallback string, read the way the server reads it."""
    from server.config import CONFIG
    return (CONFIG.prompts_dir / f"fallback_{action}.txt").read_text(
        encoding="utf-8").strip()


def test_a_call2_fallback_turn_is_not_a_clean_check(tmp_path):
    """§6.1 asks whether the MODEL reconstructed an answer from its weights.
    A prompts/fallback_*.txt template has none, so counting it as a screened
    turn that produced no hit inflates the denominator - the same defect as
    pooling mock turns, one layer down."""
    path = _log(tmp_path, [
        _turn(mock=False, item_id="itm_0001", call2_fallback=True,
              utterance=_canned()),
        _turn(mock=False, item_id="itm_0002", call2_fallback=False,
              utterance="A model wrote this one."),
    ])
    result = LM.measure(path, build="abc1234")
    assert result["headline"]["checks"] == 1, (
        "a template utterance was counted as a clean screened turn")
    assert result["template_turns"] == 1


def test_the_exclusion_works_on_logs_older_than_the_flag(tmp_path):
    """`call2_fallback` only exists from 97fe837 on. The day-18 §6.1 population
    predates it, so the text of the canned set is the retroactive test."""
    record = _turn(mock=False, item_id="itm_0001", utterance=_canned())
    record.pop("call2_fallback", None)
    path = _log(tmp_path, [record])
    result = LM.measure(path, build="abc1234")
    assert result["template_turns"] == 1
    assert result["headline"]["rate"] is None, (
        "the only screened turn was a template; there is no rate to report")


def test_layer1s_own_fallback_is_still_a_hit(tmp_path):
    """The one that must NOT be excluded.

    Layer 1 ships the same canned text after a hit whose regeneration also hit.
    Those turns carry a leak_note and are the NUMERATOR. Dropping them by text
    match would delete real detections and report a cleaner system than exists.
    """
    path = _log(tmp_path, [
        _turn(mock=False, item_id="itm_0001", utterance=_canned(),
              leak_note="leak_monitor_hit: alias 'slow start' at 1.00 fell_back"),
    ])
    result = LM.measure(path, build="abc1234")
    assert result["template_turns"] == 0, "a real layer-1 detection was dropped"
    assert result["headline"]["hits"] == 1
    assert result["headline"]["checks"] == 1


def test_an_explicit_false_flag_is_trusted_over_the_text(tmp_path):
    """If the model genuinely wrote something matching the canned text, the
    flag is authoritative. Guessing over a recorded fact is how a monitor
    starts disagreeing with the system it monitors."""
    path = _log(tmp_path, [
        _turn(mock=False, item_id="itm_0001", call2_fallback=False,
              utterance=_canned()),
    ])
    result = LM.measure(path, build="abc1234")
    assert result["template_turns"] == 0
    assert result["headline"]["checks"] == 1


# --- the headline is one build ---------------------------------------------

def test_the_headline_does_not_pool_builds_by_default(tmp_path):
    """Day 18: asked for §6.1 this printed 0/3,334 over 25 arms spanning builds
    that predate the fixes making the monitor able to see, plus an accidental
    live run the schedule records as not being evidence."""
    path = _log(tmp_path, [
        _turn(mock=False, code="old", item_id="itm_0001"),
        _turn(mock=False, code="old", item_id="itm_0002"),
        _turn(mock=False, code="new", item_id="itm_0003"),
    ])
    head = LM.measure(path, build="new")["headline"]
    assert head["checks"] == 1, "builds were pooled into the headline"
    assert head["build"] == "new"
    assert head["builds_not_pooled"] == ["old"], (
        "a build was dropped without the result saying so")


def test_pooling_builds_is_available_but_must_be_asked_for(tmp_path):
    path = _log(tmp_path, [
        _turn(mock=False, code="old", item_id="itm_0001"),
        _turn(mock=False, code="new", item_id="itm_0002"),
    ])
    head = LM.measure(path, pool_builds=True)["headline"]
    assert head["checks"] == 2
    assert head["pooled_builds"] is True


def test_the_headline_build_survives_the_aggregation_loop(tmp_path):
    """Regression. `measure` reuses the name `build` for each record's own
    stamp, so the parameter was clobbered and the headline silently scoped
    itself to whatever the LAST line in the file happened to be."""
    path = _log(tmp_path, [
        _turn(mock=False, code="wanted", item_id="itm_0001"),
        _turn(mock=False, code="zzz_last_line", item_id="itm_0002"),
    ])
    head = LM.measure(path, build="wanted")["headline"]
    assert head["build"] == "wanted"
    assert head["checks"] == 1
