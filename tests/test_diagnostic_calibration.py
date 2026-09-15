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

def _result(case, said):
    r = DC.Result(case=case, said=said)
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
    assert out["cases"]["scattered_clicks"]["admissible"] == 1
    assert out["cases"]["scattered_clicks"]["specific_hits"] == 0
    assert out["separates_guessing_from_prereq_confusion"] is False
    assert "DOES NOT SEPARATE" in DC.render(out)


def test_distinguishing_the_two_cases_is_reported_as_separation():
    results = [_result("scattered_clicks", "guessing"),
               _result("all_clicks_are_prereqs", "confused_prereq")]
    out = DC.score(results)
    assert out["separates_guessing_from_prereq_confusion"] is True
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
    assert out["provenance"]["code"]
