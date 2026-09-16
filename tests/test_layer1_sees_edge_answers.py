"""Guard layer 1 can see an edge item's answer.

Layer 1 matched utterances against `answer_aliases` and the raw answer string.
Edge items have no aliases (deleted as unusable) and their answer is an id pair,
so on day 13 an utterance naming the FROM endpoint was caught on 0 of 49 edge
items - half the scored bank - and naming both endpoints on 5 of 49. Layer 1 is
the only live check on parametric reconstruction, and eval/leak_monitor.py reads
its notes, so the §6.1 rate was blind on those items too.

Measured over the whole bank rather than a hand-picked item: recall on the
FROM endpoint, no false positive on the anchor `ask` is licensed to name, and
node items unchanged.
"""
from __future__ import annotations

import pytest

from server import guards
from server import turn as turn_mod


def _hit(store, item, utterance):
    answer, aliases, context = turn_mod._layer1_terms(store, item)
    return bool(guards.check_answer_leak(utterance, answer, aliases, context))


def _edge_items(store):
    return [i for i in store.bank.items if "->" in i.answer]


def _from_label(store, item):
    return store.label(item.answer.split("->")[0].strip())


def test_the_bank_has_edge_items_to_test(store):
    assert len(_edge_items(store)) >= 40


def test_naming_the_from_endpoint_is_caught_on_every_edge_item(store):
    missed = [i.id for i in _edge_items(store)
              if not _hit(store, i, f"Think about how {_from_label(store, i)} feeds into this.")]
    assert not missed, f"layer 1 cannot see the answer on {len(missed)} edge items: {missed[:5]}"


def test_naming_only_the_anchor_is_not_a_hit(store):
    """The TO endpoint is what `ask` names to pose the question at all."""
    flagged = [i.id for i in _edge_items(store)
               if _hit(store, i, f"Which prerequisite leads into {store.label(i.node_id)}?")]
    assert not flagged, f"false positives on the licensed anchor: {flagged}"


def test_node_items_are_screened_exactly_as_before(store):
    node_ids = set(store.node_ids)
    for item in store.bank.items:
        if item.answer not in node_ids:
            continue
        answer, aliases, context = turn_mod._layer1_terms(store, item)
        assert answer == item.answer
        assert aliases == list(item.answer_aliases)
        assert context == [n.label for n in store.graph.nodes if n.id != item.node_id]
        assert _hit(store, item, f"It is {store.label(item.answer)}.")


@pytest.mark.parametrize("seed", range(3))
def test_the_live_turn_screens_with_these_terms(store, monkeypatch, seed):
    """Wired, not just defined: a Call 2 that names an edge item's FROM endpoint
    on a hint turn is replaced, in the real turn loop."""
    from server.schemas import StudentResponse
    from server.state import Store

    item = _edge_items(store)[seed]
    leak = f"It starts from {_from_label(store, item)}."
    monkeypatch.setattr(turn_mod, "_call2", lambda *a, **k: leak)

    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    state.start_item(item.node_id, item.id)
    db.save(state)
    turn_mod.complete_turn(store, db, turn_mod.begin_turn(store, db, state, None))
    wrong = next(n for n in store.node_ids
                 if n not in item.answer.replace("->", " ").split())
    p = turn_mod.begin_turn(store, db, state, StudentResponse(type="node_click", node_id=wrong))
    r = turn_mod.complete_turn(store, db, p)
    assert r.utterance != leak
    assert p.leak_note and "fell_back" in p.leak_note
