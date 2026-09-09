"""§9.3 — eval/graph_quality.py.

The eval reports a CEILING, not a score, and the tests below mostly pin that
distinction: a ceiling that quietly became a recall figure would be quoted as
extraction quality and would be wrong by roughly a factor of two.
"""
from __future__ import annotations

import json

import pytest

from build.config import BUILD
from eval import graph_quality
from eval import provenance


@pytest.fixture(scope="module")
def result():
    return graph_quality.run([1, 2, 3, 4])


def test_the_classifier_is_not_measured_and_says_so(result):
    """Under BUILD_LLM=mock the classifier calls everything within one section
    prereq. A precision figure from that describes the fixture."""
    assert result["classifier_measured"] is False
    assert "measures" in result and "ceiling" in result["measures"]
    assert result["why"]


def test_the_ceiling_rises_with_the_window(result):
    """It is a curve, and the direction is the sanity check: a wider window can
    only admit more candidates, so recall cannot fall."""
    rows = sorted(result["windows"], key=lambda r: r["window_sections"])
    ceilings = [r["recall_ceiling"] for r in rows]
    assert ceilings == sorted(ceilings), ceilings
    counts = [r["candidates"] for r in rows]
    assert counts == sorted(counts), counts


def test_precision_falls_as_the_window_widens(result):
    """The trade the window buys. If both rose, the filter would be free and
    something in the measurement is wrong."""
    rows = sorted(result["windows"], key=lambda r: r["window_sections"])
    precisions = [r["candidate_precision"] for r in rows]
    assert precisions[0] > precisions[-1], precisions


def test_every_true_edge_is_accounted_for(result):
    """kept + the three miss reasons must equal the gold edge count, or the
    breakdown is hiding a category."""
    for row in result["windows"]:
        accounted = row["true_edges_surviving"] + sum(row["miss_reasons"].values())
        assert accounted == row["true_edges"], (row["window_sections"], row)


def test_the_order_wall_is_reported_and_is_above_the_window_ceiling(result):
    """An infinite window still cannot recover an edge the text states
    backwards. That bound is what tells a human the window is not the fix."""
    for row in result["windows"]:
        assert row["order_capped_ceiling"] >= row["recall_ceiling"]
        assert row["miss_reasons"][graph_quality.MISS_ORDER] > 0, (
            "no order misses at all would mean the textbook is perfectly ordered; "
            "verify before believing it"
        )


def test_the_shipped_window_is_one_of_the_rows(result):
    assert result["shipped_window"] == BUILD.cooccurrence_window_sections
    assert any(r["window_sections"] == result["shipped_window"]
               for r in result["windows"])


def test_the_result_declares_what_it_sampled(result):
    """The generalized rule: every eval output carries its provenance and the
    coverage is asserted, not assumed."""
    prov = provenance.Provenance(**{k: v for k, v in result["provenance"].items()
                                    if k in {"population", "distinct", "observations",
                                             "unit", "expect_full"}})
    provenance.check(prov)
    assert prov.population > 0


def test_it_scores_against_the_gold_graph_not_the_working_graph():
    """gold_graph.json must never be edited (data/SOURCE.md). If the two files
    ever diverge, this eval must follow the gold one."""
    gold = json.loads(BUILD.gold_graph_path.read_text(encoding="utf-8"))
    _, _, truth = graph_quality.load_inputs()
    gold_prereq = {(e["from"], e["to"]) for e in gold["edges"] if e.get("type") == "prereq"}
    assert truth == gold_prereq


def test_render_names_the_ceiling_as_a_bound(result):
    text = graph_quality.render(result)
    assert "ceiling" in text.lower()
    assert "CANDIDATE GENERATION ONLY" in text
    # The line that stops someone quoting it as extraction quality.
    assert "BOUNDS" in text or "bounds" in text
