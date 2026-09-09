"""build.validate.check_edge_item_anchors — CLAUDE.md §7, and the §1.5 ceiling.

Call 2's fidelity ceiling permits an `ask` on an edge item to name one endpoint
(the `to`). That deviation is fine. What it exposed is that the ITEM was already
handing over the same endpoint in its own prompt, and that a student who knows
the `to` endpoint is choosing among that node's prereqs — not among 73 edges.

These tests pin the candidate-count arithmetic, because the number it produces
is what tells a human which items to re-author.
"""
from __future__ import annotations

import pytest

from build import validate as V
from build.config import BUILD
from server.schemas import Graph, ItemBank


def _graph(edges, n_nodes=6):
    return Graph.model_validate({
        "version": "1.0",
        "domain": "test",
        "nodes": [
            {"id": f"n{i}", "label": f"N{i}", "definition": "d.",
             "source_sections": ["1.1"], "difficulty": 0.5, "x": i * 10, "y": 0}
            for i in range(n_nodes)
        ],
        "edges": [{"from": f, "to": t, "type": ty} for f, t, ty in edges],
    })


def _bank(items):
    return ItemBank.model_validate({"version": "1.0", "domain": "test", "items": items})


def _edge_item(iid, node_id, answer, distractors=(), difficulty=0.5, scorable=True):
    return {
        "id": iid, "node_id": node_id, "type": "edge_click",
        "prompt": "Click the link.", "answer": answer,
        "answer_aliases": [], "distractors": list(distractors),
        "difficulty": difficulty, "visually_answerable": True, "answer_spans": [],
        "scorable": scorable,
    }


def _run(graph, bank):
    rep = V.Report()
    V.check_edge_item_anchors(graph, bank, rep)
    return rep


def test_a_determined_item_that_is_still_scored_is_an_ERROR():
    """The whole point of the demotion. A determined item cannot move theta
    honestly, so leaving it scorable must fail the build, not warn."""
    graph = _graph([("n0", "n1", "prereq")])
    bank = _bank([_edge_item("itm_1", "n1", "n0->n1", difficulty=0.8, scorable=True)])

    rep = _run(graph, bank)

    assert not [w for w in rep.warnings if "DETERMINED" in w]
    determined = [e for e in rep.errors if "DETERMINED" in e]
    assert len(determined) == 1
    assert "1/1" in determined[0] and "SCORED" in determined[0]
    assert "itm_1" in determined[0] and "0.8" in determined[0]


def test_a_determined_item_that_is_demoted_is_only_a_WARN():
    """Excluded, not re-authored: harmless once it cannot reach mastery."""
    graph = _graph([("n0", "n1", "prereq")])
    bank = _bank([_edge_item("itm_1", "n1", "n0->n1", difficulty=0.8, scorable=False)])

    rep = _run(graph, bank)

    assert not rep.errors
    determined = [w for w in rep.warnings if "DETERMINED" in w]
    assert len(determined) == 1 and "scorable=false" in determined[0]


def test_in_degree_two_is_a_coin_flip_not_a_giveaway():
    """Reported, but in the `thin` bucket — the distinction is what tells a
    human whether to re-author the item or only its difficulty."""
    graph = _graph([("n0", "n2", "prereq"), ("n1", "n2", "prereq")])
    bank = _bank([_edge_item("itm_1", "n2", "n0->n2")])

    rep = _run(graph, bank)

    assert not [w for w in rep.warnings if "DETERMINED" in w]
    thin = [w for w in rep.warnings if "fewer" in w]
    assert len(thin) == 1 and "2 candidates" in thin[0]


def test_at_the_floor_nothing_is_flagged():
    graph = _graph([("n0", "n3", "prereq"), ("n1", "n3", "prereq"), ("n2", "n3", "prereq")])
    bank = _bank([_edge_item("itm_1", "n3", "n0->n3")])

    rep = _run(graph, bank)

    assert [w for w in rep.warnings if "[edge anchor]" in w] == []
    assert any("candidate counts" in n for n in rep.notes)


def test_related_edges_are_not_candidates():
    """The exposed endpoint plus 'a prereq of it' is the search space. A
    `related` edge into the anchor is not a prereq and does not widen it."""
    graph = _graph([("n0", "n2", "prereq"), ("n1", "n2", "related")])
    bank = _bank([_edge_item("itm_1", "n2", "n0->n2")])

    rep = _run(graph, bank)

    flagged = [m for m in rep.warnings + rep.errors if "DETERMINED" in m]
    assert flagged, (
        "a related in-edge was counted as a candidate and hid a determined item")


def test_distractor_equal_to_the_true_from_endpoint_is_flagged():
    graph = _graph([("n0", "n3", "prereq"), ("n1", "n3", "prereq"), ("n2", "n3", "prereq")])
    bank = _bank([_edge_item("itm_1", "n3", "n0->n3", distractors=["n0", "n1", "n2"])])

    rep = _run(graph, bank)

    coll = [w for w in rep.warnings if "`from` endpoint among their distractors" in w]
    assert len(coll) == 1 and "itm_1" in coll[0]


def test_an_anchor_that_is_not_the_to_endpoint_is_called_out_not_scored():
    """The whole analysis assumes node_id is the `to`. If it ever is not, say
    so rather than reporting a candidate count derived from the wrong end."""
    graph = _graph([("n1", "n2", "prereq")])
    bank = _bank([_edge_item("itm_1", "n1", "n1->n2")])

    rep = _run(graph, bank)

    assert any("does not end at node_id" in w for w in rep.warnings)
    assert not [w for w in rep.warnings if "DETERMINED" in w]


def test_the_floor_comes_from_config_not_a_literal():
    """§13.1: a human tuning this edits config, not validate.py."""
    graph = _graph([("n0", "n3", "prereq"), ("n1", "n3", "prereq"), ("n2", "n3", "prereq")])
    bank = _bank([_edge_item("itm_1", "n3", "n0->n3")])

    assert not [w for w in _run(graph, bank).warnings if "[edge anchor]" in w]

    original = BUILD.min_edge_item_candidates
    object.__setattr__(BUILD, "min_edge_item_candidates", 4)
    try:
        assert [w for w in _run(graph, bank).warnings if "fewer" in w]
    finally:
        object.__setattr__(BUILD, "min_edge_item_candidates", original)


def test_the_real_bank_has_its_determined_items_demoted_not_scored():
    """A record of the decision, and the guard that keeps it. 32 determined
    items are excluded from mastery; the 17 at two candidates stay scored and
    are a bounded calibration problem."""
    graph = Graph.model_validate_json(BUILD.graph_path.read_text(encoding="utf-8"))
    bank = ItemBank.model_validate_json(BUILD.items_path.read_text(encoding="utf-8"))

    rep = _run(graph, bank)

    assert not rep.errors, f"a determined item is still scored: {rep.errors}"
    determined = [w for w in rep.warnings if "DETERMINED" in w]
    assert determined and "32/49" in determined[0]
    assert "scorable=false" in determined[0]

    scored = [i for i in bank.items if i.type == "edge_click" and i.scorable]
    assert len(scored) == 17
    assert all(len([e for e in graph.edges
                    if e.type == "prereq" and e.to == i.node_id]) == 2 for i in scored)
