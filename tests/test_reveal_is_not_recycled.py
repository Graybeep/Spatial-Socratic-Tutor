"""A forced reveal closes an item. It must not reopen it, and must not follow the
student into the next one.

Found on day 13, once history began reaching Call 2 (1cfc74a). Three defects,
all behind one ordering: routing runs BEFORE Call 2, and a reveal was treated
as if it had not.

1. The revealed node came straight back - it had just failed eight turns, so it
   was the lowest-mastery ready node. 28 of 32 reveals in a simulated drive
   re-served the very item. A student clicking what the tutor had just said was
   credited at hint 0: layer 3's zero-mastery reveal, repaid on the next turn.

2. That reopened item's first hint turn handed Call 2 the reveal line in its
   "last two turns" - "That's it: Packet Flow" while Packet Flow was the open
   answer. §1.5, through a channel no exposure test looked at, because until
   1cfc74a the channel carried "role: text".

3. The reveal's own label was read from current_node - the NEXT item's node -
   under advance's fidelity, because routing had already rewritten the action.
   It named the revealed concept only when the next item sat on the same node;
   otherwise it named another concept, or nothing. advance's safe_label did keep
   the NEXT item's answer out, so this was a wrong reveal, not a leak. Fixing (1)
   alone made every reveal wrong: measured, it named nothing.
"""
from __future__ import annotations

import random

from server import llm as llm_mod
from server import turn as turn_mod
from server.schemas import StudentResponse
from server.state import Store

from .conftest import config_override


def _fail_to_reveal(store, seed=0):
    """Wrong clicks until the budget forces a reveal on the first node_click item.
    Returns (db, state, phase1 and response of the reveal turn, revealed item)."""
    rng = random.Random(seed)
    db = Store(db_path=":memory:")
    state = db.create(store.initial_theta_map(), graph_fingerprint=store.fingerprint)
    item = next(i for n in store.node_ids for i in store.items_for(n)
                if i.type == "node_click" and turn_mod._is_scorable(i))
    state.start_item(item.node_id, item.id)
    db.save(state)
    p = turn_mod.begin_turn(store, db, state, None)
    turn_mod.complete_turn(store, db, p)
    for _ in range(40):
        wrong = rng.choice([n for n in store.node_ids if n != item.answer])
        p = turn_mod.begin_turn(store, db, state,
                                StudentResponse(type="node_click", node_id=wrong))
        r = turn_mod.complete_turn(store, db, p)
        if p.resolved_with_support:
            return db, state, p, r, item
    raise AssertionError("the turn budget never forced a reveal")


def test_the_revealed_node_does_not_come_straight_back(store):
    _, state, p, _, revealed = _fail_to_reveal(store)
    assert p.revealed_item.id == revealed.id
    assert p.item is not None, "a ready node other than the revealed one exists"
    assert p.item.node_id != revealed.node_id
    assert state.current_node != revealed.node_id


def test_the_reveal_names_what_was_revealed(store):
    _, _, p, r, revealed = _fail_to_reveal(store)
    assert store.label(revealed.answer).casefold() in r.utterance.casefold()


def test_the_reveal_never_names_the_item_it_hands_over_to(store):
    """The labels a reveal gets are the revealed item's, never the open one's.

    Not a regression test for a breach that happened - safe_label covered this
    before. It pins the property now that the reveal has full-label fidelity and
    nothing else standing between it and current_node."""
    for seed in range(5):
        db, state, p, _, revealed = _fail_to_reveal(store, seed)
        labels, _, _ = turn_mod._call2_context(store, state, p)
        opened = turn_mod._answer_surface(store, p.item)
        revealed_surface = turn_mod._answer_surface(store, revealed)
        leaked = {l.casefold() for l in labels} & (opened - revealed_surface)
        assert not leaked, f"seed {seed}: reveal handed Call 2 {leaked}"


def test_the_reveal_is_tagged_in_history(store):
    _, state, _, r, _ = _fail_to_reveal(store)
    last = state.history[-1]
    assert last["role"] == "tutor" and last.get("reveal") is True
    # History holds the speaker's words only. The response also carries the
    # next item's question, appended after the history entry was written.
    assert r.utterance.startswith(last["text"] + "\n\n")
    assert not any(e.get("reveal") for e in state.history[:-1])


def test_call2_is_never_handed_a_reveal_line(monkeypatch):
    """Enforced inside llm.call2, so no caller can forget it."""
    seen = []

    def fake_invoke(cfg, system, user, tool, label):
        seen.append(user)
        return llm_mod.Call2Utterance(utterance="Which lit one fits?")

    monkeypatch.setattr(llm_mod, "_invoke", fake_invoke)
    with config_override(llm_provider="groq", groq_api_key="g-key"):
        llm_mod.call2(action="hint_visual", hint_level=1, focus_labels=[], n_lit=9,
                      recent=[
                          {"role": "tutor", "text": "That's it: Packet Flow.", "reveal": True},
                          {"role": "student", "text": "[clicked Throughput]"},
                      ])
    assert "Packet Flow" not in seen[0]
    assert "[clicked Throughput]" in seen[0]


def test_call1_still_sees_the_reveal(store, monkeypatch):
    """Call 1 is given the answer anyway (§5); hiding the reveal from it would
    only blind its diagnosis of the turn after."""
    seen = []

    def fake_invoke(cfg, system, user, tool, label):
        seen.append(user)
        return llm_mod.Call1Decision(
            student_state="stuck", diagnosis="d", correct=False,
            requested_action="ask", requested_hint_level=0,
            focus_nodes=[], expects="node_click")

    monkeypatch.setattr(llm_mod, "_invoke", fake_invoke)
    with config_override(llm_provider="groq", groq_api_key="g-key"):
        llm_mod.call1(item_prompt="q", answer="a", item_type="node_click",
                      node_label="L", graph_digest="", hint_level=0,
                      turns_on_item=0, mastery_note="",
                      history=[{"role": "tutor", "text": "That's it: Packet Flow.",
                                "reveal": True}])
    assert "That's it: Packet Flow." in seen[0]
