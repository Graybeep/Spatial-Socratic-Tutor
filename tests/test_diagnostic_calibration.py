"""The constructed cases must actually be different students.

This file tests the INSTRUMENT, not the model. A calibration probe whose two
contrasting cases share nodes would report "cannot discriminate" from two
histories that were not different - a well-formed conclusion over nothing, which
is the failure `docs/writeup/numbers-that-looked-fine.md` is about. The first
draft of `_history` did exactly that.
"""
from __future__ import annotations

import pytest

from eval import diagnostic_calibration as DC
from server.config import CONFIG


def _clicks(store, item, kind):
    return {h["text"] for h in DC._history(store, item, kind) if h["role"] == "student"}


@pytest.fixture()
def probe_items(store):
    items = DC._items_with_prereqs(store, 4)
    assert items, "no node_click item on a node with prereqs; the prereq case is void"
    return items


def test_the_two_contrasting_cases_share_no_nodes(store, probe_items):
    """`scattered` draws from the complement of the prerequisite region."""
    for item in probe_items:
        scattered = _clicks(store, item, "scattered")
        prereq = _clicks(store, item, "prereqs")
        assert scattered and prereq
        assert not (scattered & prereq), (
            f"{item.id}: the 'guessing' and 'prereq confusion' histories share "
            f"{sorted(scattered & prereq)} - these are not two different students"
        )


def test_each_history_has_three_distinct_clicks(store, probe_items):
    """One node clicked three times reads as a broken interface, not a pattern,
    which would make a failure ambiguous."""
    for item in probe_items:
        for kind in ("scattered", "prereqs"):
            assert len(_clicks(store, item, kind)) == 3, f"{item.id}/{kind}"


def test_the_prereq_history_is_actually_in_the_prereq_region(store, probe_items):
    for item in probe_items:
        region = set(store.prereqs(item.node_id))
        for pr in list(region):
            region |= set(store.prereqs(pr)) | set(store.dependents(pr))
        labels = {store.label(n) for n in region}
        clicked = {c.removeprefix("[clicked ").removesuffix("]")
                   for c in _clicks(store, item, "prereqs")}
        assert clicked <= labels, f"{item.id}: {clicked - labels} are not in the region"


def test_the_scattered_history_never_contains_the_answer(store, probe_items):
    for item in probe_items:
        answer_label = store.label(item.answer) if item.answer in set(store.node_ids) else None
        if answer_label:
            assert f"[clicked {answer_label}]" not in _clicks(store, item, "scattered")


def test_the_correct_case_clicks_the_answer(store, probe_items):
    for item in probe_items:
        clicks = _clicks(store, item, "correct")
        assert clicks == {f"[clicked {store.label(item.answer)}]"}


def test_the_opening_turn_has_no_history(store, probe_items):
    assert DC._history(store, probe_items[0], "none") == []


# --- scoring ----------------------------------------------------------------

def _one(out, version="current"):
    """`score` reports per prompt version now; these cases are all one arm."""
    return out["by_prompt"][version]


def _result(case, said, prompt="current"):
    r = DC.Result(case=case, said=said, prompt=prompt)
    spec = next(c for c in DC.CASES if c.name == case)
    r.admissible = said in spec.admissible
    r.specific_hit = said == spec.specific
    return r


def test_answering_stuck_everywhere_scores_admissible_but_not_specific():
    """The degenerate strategy this probe exists to expose: `stuck` is never
    *wrong* about a failing student, and says nothing."""
    results = [_result("scattered_clicks", "stuck"),
               _result("all_clicks_are_prereqs", "stuck")]
    out = DC.score(results)
    assert _one(out)["cases"]["scattered_clicks"]["admissible"] == 1
    assert _one(out)["cases"]["scattered_clicks"]["specific_hits"] == 0
    assert _one(out)["separates_guessing_from_prereq_confusion"] is False
    assert "DOES NOT SEPARATE" in DC.render(out)


def test_distinguishing_the_two_cases_is_reported_as_separation():
    results = [_result("scattered_clicks", "guessing"),
               _result("all_clicks_are_prereqs", "confused_prereq")]
    out = DC.score(results)
    assert _one(out)["separates_guessing_from_prereq_confusion"] is True
    assert "SEPARATES" in DC.render(out)


def test_a_mock_run_is_refused():
    assert CONFIG.mock_mode is True
    import sys
    argv = sys.argv
    sys.argv = ["diagnostic_calibration"]
    try:
        assert DC.main() == 2
    finally:
        sys.argv = argv


def test_the_result_names_the_model():
    out = DC.score([_result("scattered_clicks", "guessing")])
    assert out["call1_model"] == CONFIG.call1.model
    assert _one(out)["provenance"]["code"]


# --- the verdict must not be a finding when there is no data ------------------

def test_an_all_failed_run_is_not_reported_as_a_failure_to_discriminate():
    """Every call 429'd on an exhausted daily budget and the first version
    printed "the diagnosis is not reading the history" - a confident negative
    over zero observations, because two empty distributions compare equal."""
    blocked = [DC.Result(case="scattered_clicks", prompt="current",
                         error="HTTP 429 DAILY quota exhausted"),
               DC.Result(case="all_clicks_are_prereqs", prompt="current",
                         error="HTTP 429 DAILY quota exhausted")]
    out = DC.score(blocked)
    assert _one(out)["separates_guessing_from_prereq_confusion"] is None
    rendered = DC.render(out)
    assert "NOT MEASURED" in rendered
    assert "DOES NOT SEPARATE" not in rendered


def test_one_empty_case_is_also_not_a_verdict():
    """Half a comparison is not a comparison."""
    out = DC.score([_result("scattered_clicks", "guessing"),
                    DC.Result(case="all_clicks_are_prereqs", prompt="current",
                              error="timeout")])
    assert _one(out)["separates_guessing_from_prereq_confusion"] is None
    assert "NOT MEASURED" in DC.render(out)


def test_every_case_declares_as_many_turns_as_it_shows_clicks(store, probe_items):
    """A case that says "three turns" while showing one click is incoherent, and
    the model's answer to it is not evidence about the model.

    `answered_correctly` inherited the default turns_on_item=3 with a one-click
    history. qwen answered `stuck` and explained "three turns in with no clear
    right answer" - an accurate reading of a context we had broken. It was
    scored as a model failure until the case was re-read.
    """
    kinds = {"scattered_clicks": "scattered", "all_clicks_are_prereqs": "prereqs",
             "answered_correctly": "correct", "opening_turn": "none",
             "no_pattern_to_name": "text_only"}
    item = probe_items[0]
    for case in DC.CASES:
        clicks = len(_clicks(store, item, kinds[case.name]))
        assert case.turns_on_item == clicks, (
            f"{case.name}: declares turns_on_item={case.turns_on_item} but shows "
            f"{clicks} student response(s). The model is being told one thing "
            f"and shown another."
        )


def test_the_probe_records_the_boolean_that_mastery_uses():
    """`student_state` is a label nothing reads; `correct` is what §7 scores.
    A probe that captures only the label measures the field that cannot hurt."""
    r = DC.Result(case="answered_correctly", said="stuck", correct=True,
                  prompt="current")
    out = DC.score([r])
    assert _one(out)["correct_boolean"] == {"agree": 1, "of": 1}
    assert "`correct` boolean" in DC.render(out)


def test_a_wrong_boolean_is_counted_against():
    r = DC.Result(case="answered_correctly", said="correct", correct=False,
                  prompt="current")
    assert _one(DC.score([r]))["correct_boolean"] == {"agree": 0, "of": 1}


# --- the prompt A/B ----------------------------------------------------------

def test_the_committed_old_prompt_exists_and_differs(store):
    """The A/B is worthless if both arms load the same text."""
    from server import llm
    current = llm.prompt("call1_system.md")
    with DC.use_prompt("pre-falsifiability"):
        old = llm.prompt("call1_system.md")
    assert old != current
    # The change under test: the falsifiability rules and the warning against
    # reaching for `stuck`. If these ever appear in both, the arms have merged.
    assert "cheap answer" in current and "cheap answer" not in old


def test_use_prompt_restores_the_live_prompt(store):
    """A run that dies mid-A/B must not leave the demo serving an old tutor
    contract. The lru_cache is the trap: clearing it on the way in and not on
    the way out leaves the swapped text live."""
    from server import llm
    from server.config import CONFIG

    before_dir = CONFIG.prompts_dir
    before = llm.prompt("call1_system.md")
    try:
        with DC.use_prompt("pre-falsifiability"):
            raise RuntimeError("the run died here")
    except RuntimeError:
        pass
    assert CONFIG.prompts_dir == before_dir
    assert llm.prompt("call1_system.md") == before


def test_results_are_reported_per_prompt_not_pooled():
    """Pooling is what made the day-12/day-18 reversal unattributable: three
    variables moved and the result carried one number."""
    out = DC.score([
        _result("scattered_clicks", "guessing", prompt="current"),
        _result("all_clicks_are_prereqs", "confused_prereq", prompt="current"),
        _result("scattered_clicks", "stuck", prompt="pre-falsifiability"),
        _result("all_clicks_are_prereqs", "stuck", prompt="pre-falsifiability"),
    ])
    assert out["prompts"] == ["current", "pre-falsifiability"]
    assert _one(out, "current")["separates_guessing_from_prereq_confusion"] is True
    assert _one(out, "pre-falsifiability")[
        "separates_guessing_from_prereq_confusion"] is False
    assert out["ab"]["measurable"] is True
    assert out["ab"]["specific_hits"] == {"current": 2, "pre-falsifiability": 0}


def test_an_empty_arm_makes_the_ab_unmeasurable_not_a_win():
    """The same three-valued discipline as the discrimination verdict. An arm
    that produced nothing must not read as the other arm winning."""
    out = DC.score([
        _result("scattered_clicks", "guessing", prompt="current"),
        DC.Result(case="scattered_clicks", prompt="pre-falsifiability",
                  error="HTTP 429 DAILY quota exhausted"),
    ])
    assert out["ab"]["measurable"] is False
    assert out["ab"]["specific_hits"] is None
    assert "NOT MEASURABLE" in DC.render(out)


def test_stuck_is_the_specific_answer_for_exactly_one_case():
    """The counter-test to the current prompt's suspicion of `stuck`. Without a
    case where `stuck` is RIGHT, a prompt that simply never says `stuck` would
    score as an improvement."""
    stuck_cases = [c.name for c in DC.CASES if c.specific == "stuck"]
    assert stuck_cases == ["no_pattern_to_name"], stuck_cases


def test_the_stuck_case_shows_no_clicks_to_read(store, probe_items):
    """`stuck` is the residual: it must be built by REMOVING spatial evidence,
    not by adding a third pattern. If this history contained clicks, a model
    answering `guessing` or `confused_prereq` would be defensible and the case
    would not test what it claims."""
    history = DC._history(store, probe_items[0], "text_only")
    said = [h["text"] for h in history if h["role"] == "student"]
    assert said, "the case shows the model nothing at all"
    assert not any("[clicked" in t for t in said), (
        "the stuck case contains clicks; confused_prereq and guessing both "
        "become defensible and the case stops being about stuck")
