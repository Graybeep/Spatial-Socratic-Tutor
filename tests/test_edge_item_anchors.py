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


def test_a_from_endpoint_in_the_distractors_is_NOT_flagged():
    """It used to be, and that was MCQ reasoning applied to the wrong field.

    `distractors` is an option set only for `mcq`. For a click item it is a
    narrowing-order hint - `mock_tutor.candidate_order` pushes the answer, then
    the distractors, then graph neighbours - and an edge item is never served as
    MCQ, so the list is never shown as choices. For an edge `src->dst` the source
    is by definition a prerequisite of the target and stays lit regardless, so
    listing it is redundant rather than leaky: measured, 14 of the 17 scored edge
    items stay answerable at every rung WITHOUT the listing.

    What replaced it is `check_edge_answers_survive_narrowing`, which asks the
    question that has a wrong answer.
    """
    graph = _graph([("n0", "n3", "prereq"), ("n1", "n3", "prereq"), ("n2", "n3", "prereq")])
    bank = _bank([_edge_item("itm_1", "n3", "n0->n3", distractors=["n0", "n1", "n2"])])

    rep = _run(graph, bank)

    coll = [w for w in rep.warnings if "`from` endpoint among their distractors" in w]
    assert not coll, (
        "the retired MCQ-semantics warning is back; it fires on 10 items in the "
        "shipped bank, none of which is a defect"
    )


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


# --- the check that replaced it ----------------------------------------------


def test_the_shipped_bank_keeps_every_edge_answer_clickable():
    """`focus_edges` needs BOTH endpoints lit. An edge item that loses one is not
    a hard item - it is one the interface made unanswerable, and §7 still scores
    the student's wrong click against them."""
    from build import validate as V
    from server.graph_store import GraphStore
    from server import mock_tutor
    from server.config import CONFIG

    store = GraphStore.load()
    edge_items = [i for i in store.bank.items if i.type == "edge_click"]
    assert edge_items, "no edge items; this test proved nothing"

    broken = []
    for item in edge_items:
        src, _, dst = item.answer.partition("->")
        for level in range(1, CONFIG.hint_max + 2):
            lit = mock_tutor.lit_nodes(store, item, level)
            if lit and (src not in lit or dst not in lit):
                broken.append((item.id, item.answer, level, len(lit)))
                break
    assert not broken, f"edge answers unreachable under narrowing: {broken}"


def test_a_narrowing_that_drops_an_endpoint_is_caught(monkeypatch):
    """The guard must be able to fail, or it guards nothing.

    NARROW_SCHEDULE is a research variable - docs/schedule.md books a projector
    test that may change it - and narrowing harder is exactly the edit that would
    break an edge item silently.
    """
    from build import validate as V
    from server.graph_store import GraphStore
    from server.config import CONFIG

    store = GraphStore.load()
    edge = next(i for i in store.bank.items if i.type == "edge_click")

    # TWO lit nodes, which is the tightest the interface will ever go:
    # `candidate_floor` is max(2, ...), so one lit node is unreachable by
    # construction - and rightly, since a single lit node IS the answer.
    #
    # At two, `candidate_order` yields [target, first distractor]. Unless that
    # distractor happens to be the edge's source, the answer edge loses an
    # endpoint and stops being clickable. That is the regression this guards.
    from tests.conftest import config_override
    with config_override(narrow_schedule_raw="0,2", max_guess_probability=0.5):
        assert CONFIG.narrow_schedule[1] == 2, (
            f"could not construct a two-node rung; got {CONFIG.narrow_schedule}"
        )
        rep = V.Report()
        V.check_edge_answers_survive_narrowing(store.graph, store.bank, rep)

    assert any("[edge narrowing]" in w for w in rep.warnings), (
        "narrowing to a single lit node left every edge answer intact, which is "
        "impossible - the check is not looking at the lit set"
    )
