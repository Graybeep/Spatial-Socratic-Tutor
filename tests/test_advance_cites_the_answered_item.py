"""On `advance`, Call 2 cites the item just answered - never the one now open.

Routing runs before Call 2, so by the time complete_turn builds the chunk,
phase1.item is the NEXT question. _chunk_for was handed that item. Measured on
day 13: answering "Packet Flow" delivered the chapter's passage on router
queuing, masked, while "Queuing Delay" was the open item. §5's retrieval gate
exists because a chunk "leaks the answer in higher fidelity than any single
field would"; span masking removes the name and leaves the explanation.

The existing exposure tests checked that no chunk contains `item.answer`
verbatim - an id like "queuing_delay", which prose never contains - so they
passed throughout.
"""
from __future__ import annotations

from server import retrieval
from server import turn as turn_mod
from server.schemas import StudentResponse
from server.state import Store


def _drive_correct(store, monkeypatch, turns=40):
    """Answer node_click items correctly; record every advance chunk request."""
    seen = []
    orig = turn_mod._chunk_for

    def spy(store_, state, action, item):
        out = orig(store_, state, action, item)
        seen.append({"action": action, "item": item, "chunk": out})
        return out

    monkeypatch.setattr(turn_mod, "_chunk_for", spy)
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    db.save(state)
    p = turn_mod.begin_turn(store, db, state, None)
    turn_mod.complete_turn(store, db, p)
    records = []
    for _ in range(turns):
        if p.item is None or p.session_complete or p.expects != "node_click":
            break
        answered = p.item
        p = turn_mod.begin_turn(store, db, state,
                                StudentResponse(type="node_click", node_id=answered.answer))
        seen.clear()
        turn_mod.complete_turn(store, db, p)
        for s in seen:
            if s["action"] == "advance":
                records.append({**s, "answered": answered, "open": p.item})
    return records


def test_advance_is_exercised_and_still_cites(store, monkeypatch):
    assert retrieval.corpus_size() > 0
    records = _drive_correct(store, monkeypatch)
    assert records, "no advance turns"
    assert any(r["chunk"] for r in records), "advance never cites the chapter any more"


def test_the_advance_chunk_is_never_about_the_open_item(store, monkeypatch):
    for r in _drive_correct(store, monkeypatch):
        if r["open"] is None or r["item"] is None:
            continue
        assert r["item"].id != r["open"].id
        assert r["item"].node_id != r["open"].node_id


def test_the_advance_chunk_is_about_the_answered_item(store, monkeypatch):
    for r in _drive_correct(store, monkeypatch):
        if r["item"] is not None:
            assert r["item"].id == r["answered"].id


def test_no_chunk_when_the_open_item_sits_on_the_answered_node(store):
    """Constructed, because a correct answer rarely re-serves its own node."""
    item = next(i for n in store.node_ids for i in store.items_for(n)
                if i.type == "node_click")

    class P:
        answered_item = item
    P.item = item
    assert turn_mod._chunk_subject(store, P, "advance") is None


def test_explain_still_cites_the_open_item(store):
    item = next(i for n in store.node_ids for i in store.items_for(n))

    class P:
        answered_item = None
    P.item = item
    assert turn_mod._chunk_subject(store, P, "explain") is item
