"""`answer_spans` and the mask that consumes them — CLAUDE.md §3, §5.

Until the chapter landed, every item carried `answer_spans: []` and the masking
path in `guards.mask_spans` had never run against a real offset. §5 masks those
spans before a chunk reaches Call 2 on `advance` and `explain`, so an empty span
list meant that half of §5's retrieval gate was a no-op: the chunk went out
unmasked and the chapter's own prose named the answer.

That was visible in the logs and nowhere else. Layer 1 caught it on the two
items whose answer is the chapter's topic vocabulary ("congestion control",
"resource allocation") and reported it as the model reconstructing the answer
parametrically — which is exactly the inference §6 says a layer-1 hit licenses,
and it was wrong. The tutor had been handed the answer in the chunk.

These tests pin three things:

  1. the offsets in the committed bank still land on the answer in the chunk
     that would actually be served (spans rot silently when either the corpus
     or the retrieval scorer moves),
  2. masking removes every surface form, not just the exact alias,
  3. the leak the empty spans caused does not come back.
"""
from __future__ import annotations

import json

import pytest

from build import annotate_spans as A
from build import validate as V
from build.config import BUILD
from server import guards, retrieval
from server.schemas import Graph, ItemBank


@pytest.fixture(scope="module")
def bank_and_graph():
    graph = Graph.model_validate_json(BUILD.graph_path.read_text(encoding="utf-8"))
    bank = ItemBank.model_validate_json(BUILD.items_path.read_text(encoding="utf-8"))
    return graph, bank


def _served(graph, node_id):
    node = next(n for n in graph.nodes if n.id == node_id)
    return retrieval.search(f"{node.label} {node.definition}")


# --- the surface -----------------------------------------------------------

def test_surface_includes_the_node_label_not_only_the_aliases():
    labels = {"slow_start": "Slow Start"}
    item = {"answer": "slow_start", "answer_aliases": ["ss phase"]}
    assert A.answer_surface(item, labels) == {"slow start", "ss phase"}


def test_an_edge_answer_puts_both_endpoint_labels_on_the_surface():
    """Naming either endpoint hands over half the edge, so both are masked."""
    labels = {"aimd": "AIMD", "fast_recovery": "Fast Recovery"}
    item = {"answer": "aimd->fast_recovery", "answer_aliases": []}
    assert A.answer_surface(item, labels) == {"aimd", "fast recovery"}


def test_surface_is_case_folded_so_matching_is_not_case_dependent():
    labels = {"red": "RED"}
    assert A.answer_surface({"answer": "red", "answer_aliases": ["Random Early Detection"]},
                            labels) == {"red", "random early detection"}


# --- span finding ----------------------------------------------------------

def test_spans_are_half_open_offsets_into_the_text():
    text = "before Slow Start after"
    (start, end), = A.find_spans(text, {"slow start"})
    assert text[start:end] == "Slow Start"


def test_every_occurrence_is_found_not_only_the_first():
    text = "RED here and RED again and RED once more"
    assert len(A.find_spans(text, {"red"})) == 3


def test_nested_surfaces_are_merged_into_one_span():
    """'fair queuing' inside 'weighted fair queuing' is a real pair in this
    graph. Two overlapping spans would mask the same characters twice and shift
    the second one onto text that was never the answer."""
    text = "the weighted fair queuing discipline"
    spans = A.find_spans(text, {"fair queuing", "weighted fair queuing"})
    assert len(spans) == 1
    assert text[spans[0][0]:spans[0][1]] == "weighted fair queuing"


def test_an_absent_surface_yields_no_spans():
    assert A.find_spans("nothing to see", {"slow start"}) == []


# --- the committed bank ----------------------------------------------------

def test_the_bank_is_no_longer_entirely_unmasked(bank_and_graph):
    """The state this work replaced: 260 items, 0 spans, masking inert."""
    _, bank = bank_and_graph
    assert sum(1 for i in bank.items if i.answer_spans) > 0


def test_every_recorded_span_lands_on_the_answer_in_the_served_chunk(bank_and_graph):
    """Re-derives rather than trusts. An offset that has drifted masks some
    unrelated sentence and leaves the answer in the text, and nothing downstream
    of §5 would say so."""
    graph, bank = bank_and_graph
    labels = {n.id: n.label for n in graph.nodes}

    for item in bank.items:
        if not item.answer_spans:
            continue
        hit = _served(graph, item.node_id)
        assert hit is not None, f"{item.id}: spans recorded but no chunk is served"
        surface = A.answer_surface(item.model_dump(by_alias=True), labels)
        for start, end in item.answer_spans:
            assert 0 <= start < end <= len(hit.chunk.text), f"{item.id}: out of range"
            assert hit.chunk.text[start:end].casefold() in surface, (
                f"{item.id}: span [{start}, {end}] is "
                f"{hit.chunk.text[start:end]!r}, which is not the answer"
            )


def test_masking_removes_the_answer_from_what_call2_would_receive(bank_and_graph):
    """§5's actual requirement. Not 'a span was applied' — the answer is gone."""
    graph, bank = bank_and_graph
    labels = {n.id: n.label for n in graph.nodes}

    for item in bank.items:
        if not item.answer_spans:
            continue
        hit = _served(graph, item.node_id)
        masked = guards.mask_spans(hit.chunk.text, item.answer_spans).casefold()
        leftover = [s for s in A.answer_surface(item.model_dump(by_alias=True), labels)
                    if s in masked]
        assert not leftover, f"{item.id}: {leftover} survived masking"


def test_the_committed_spans_are_what_the_annotator_would_write(bank_and_graph):
    """Idempotence, and the rot alarm. Fails if chunks.json or the retrieval
    scorer changes without `python -m build.annotate_spans` being re-run."""
    graph, bank = bank_and_graph
    raw = json.loads(BUILD.items_path.read_text(encoding="utf-8"))
    recomputed, _, _ = A.annotate(json.loads(BUILD.graph_path.read_text(encoding="utf-8")),
                                  json.loads(BUILD.items_path.read_text(encoding="utf-8")))
    for before, after in zip(raw["items"], recomputed["items"]):
        assert before["answer_spans"] == after["answer_spans"], before["id"]


def test_validate_reports_no_span_errors_on_the_real_bank(bank_and_graph):
    graph, bank = bank_and_graph
    rep = V.Report()
    V.check_answer_spans(graph, bank, rep)
    assert rep.errors == []


def test_annotating_twice_changes_nothing(bank_and_graph):
    graph_raw = json.loads(BUILD.graph_path.read_text(encoding="utf-8"))
    once, _, _ = A.annotate(graph_raw, json.loads(BUILD.items_path.read_text(encoding="utf-8")))
    twice, _, _ = A.annotate(graph_raw, json.loads(json.dumps(once)))
    assert A.dumps(once) == A.dumps(twice)


def test_the_production_path_masks_it_too(bank_and_graph):
    """Through `turn._chunk_for`, which is what actually runs on `advance` and
    `explain` — the masking is only worth anything if the wiring reaches it."""
    from server import turn as turn_mod
    from server.graph_store import GraphStore

    graph, bank = bank_and_graph
    store = GraphStore.load()
    labels = {n.id: n.label for n in graph.nodes}

    checked = 0
    for item in bank.items:
        if not item.answer_spans:
            continue
        for action in ("advance", "explain"):
            chunk = turn_mod._chunk_for(store, None, action, store.item(item.id))
            if chunk is None:
                continue
            low = chunk.casefold()
            for phrase in A.answer_surface(item.model_dump(by_alias=True), labels):
                assert phrase not in low, f"{item.id} on {action}: {phrase!r} reached Call 2"
            checked += 1
    assert checked > 0, "no chunk ever reached Call 2; this test proved nothing"


# --- validate's alarms -----------------------------------------------------

def _tiny(spans, answer="n1", aliases=("n1 label",)):
    graph = Graph.model_validate({
        "version": "1.0", "domain": "test",
        "nodes": [
            {"id": "n0", "label": "N0", "definition": "d.", "source_sections": ["1.1"],
             "difficulty": 0.5, "x": 0, "y": 0},
            {"id": "n1", "label": "N1", "definition": "d.", "source_sections": ["1.1"],
             "difficulty": 0.5, "x": 10, "y": 0},
        ],
        "edges": [{"from": "n0", "to": "n1", "type": "prereq"}],
    })
    bank = ItemBank.model_validate({
        "version": "1.0", "domain": "test",
        "items": [{
            "id": "itm_0001", "node_id": "n1", "type": "node_click",
            "prompt": "Click it.", "answer": answer, "answer_aliases": list(aliases),
            "distractors": ["n0"], "difficulty": 0.5,
            "visually_answerable": True, "answer_spans": spans, "scorable": True,
        }],
    })
    return graph, bank


def test_spans_on_a_node_with_no_retrievable_chunk_are_an_error(monkeypatch):
    """Offsets into a chunk that never ships mask nothing and hide that they
    mask nothing."""
    graph, bank = _tiny(spans=[[0, 4]])
    monkeypatch.setattr(retrieval, "search", lambda query: None)
    rep = V.Report()
    V.check_answer_spans(graph, bank, rep)
    assert any("retrieval refuses a chunk" in e for e in rep.errors)


def test_a_stale_span_is_an_error(monkeypatch):
    """The corpus moved under the recorded offsets."""
    graph, bank = _tiny(spans=[[999, 1000]])
    chunk = retrieval.Chunk(id="c", section="1.1", heading_path="H", text="about N1 here")
    monkeypatch.setattr(retrieval, "search",
                        lambda query: retrieval.Retrieved(chunk=chunk, score=0.9))
    rep = V.Report()
    V.check_answer_spans(graph, bank, rep)
    assert any("do not match the chunk" in e or "outside the" in e for e in rep.errors)


def test_a_correct_span_passes(monkeypatch):
    text = "a sentence about N1 in the chapter"
    graph, bank = _tiny(spans=[[list(A.find_spans(text, {"n1"}))[0][0],
                                list(A.find_spans(text, {"n1"}))[0][1]]],
                        aliases=())
    chunk = retrieval.Chunk(id="c", section="1.1", heading_path="H", text=text)
    monkeypatch.setattr(retrieval, "search",
                        lambda query: retrieval.Retrieved(chunk=chunk, score=0.9))
    rep = V.Report()
    V.check_answer_spans(graph, bank, rep)
    assert rep.errors == []
