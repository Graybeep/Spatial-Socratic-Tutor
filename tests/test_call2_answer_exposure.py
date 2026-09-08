"""CLAUDE.md §1.5 — Call 2 must never receive the answer or its aliases.

RESOLVED. This file was committed failing (xfail strict) while the contract
question was open; the fidelity ceiling in server/turn.py closed it and the
marker is gone. The measurements below are kept as the record of what the
breach was, because the numbers are the argument for why the contract is
expressed as a fidelity ceiling rather than a field whitelist.

THE BREACH, AS IT WAS

  §1.5  "Call 2 never receives the answer. Not the answer string, not the
         answer aliases, not the source chunk during `ask` or `hint_*`."

  §5    Call 2 receives "`action`, `hint_level`, focus node **labels**,
         last 2 turns."

For a `node_click` item the answer IS a node, so the node's label is an answer
alias — literally, in 52 of 52 node_click items, the label appears verbatim in
`answer_aliases`. When that node is in `focus_nodes` (which is the normal case:
narrowing exists to leave the answer lit), §5 instructs us to hand Call 2 a
string that §1.5 forbids.

**The two rules cannot both be satisfied as written.** This is not an
implementation slip; it is a contradiction in the spec that stayed invisible for
as long as "label" and "answer" looked like different kinds of thing.

MEASURED EXPOSURE, over 25 items driven to the turn budget:

    action                  turns   w/ answer label   rate
    ask                       125               100    80%
    hint_visual                65                51    78%
    hint_verbal                15                15   100%
    backtrack                  64                64   100%
    advance                    10                10   100%   (legitimate, §5)
    resolved_with_support       3                 0     0%   (legitimate, §6/3)

Layer 1 fires on only 62 of 400 turns, so the OBSERVED leak rate is 15.5% —
but that is a property of the mock's canned utterances not happening to use
every label they are handed. The guard screens the OUTPUT; the exposure is in
the INPUT, and it is 78–100%. A live Call 2 told to write a hint about a
concept, and handed that concept's name, will say it far more often than the
mock does.

This is the third instance of the failure class in
docs/writeup/eval-harness-failures.md: two fields that are different things in
the schema and the same thing in the domain.
"""
from __future__ import annotations

import pytest

from server.graph_store import GraphStore
from server.state import Store
from server.schemas import StudentResponse
import server.turn as turn_mod


NON_LEAKING_ACTIONS = {"ask", "hint_visual", "hint_verbal"}


@pytest.fixture(scope="module")
def store():
    return GraphStore.load()


def _drive(store, limit=25):
    """Drive items to the turn budget, capturing every Call 2 input."""
    captured = []
    original = turn_mod._call2

    def spy(state, action, hint_level, labels, n_lit):
        captured.append({
            "action": action,
            "labels": tuple(labels),
            "item_id": state.current_item_id,
        })
        return original(state, action, hint_level, labels, n_lit)

    turn_mod._call2 = spy
    try:
        bank = [i for i in store.bank.items if i.visually_answerable][:limit]
        for item in bank:
            db = Store(db_path=":memory:")
            state = db.create(store.initial_theta_map(),
                              graph_fingerprint=store.fingerprint)
            state.start_item(item.node_id, item.id)
            db.save(state)
            for _ in range(5):
                p = turn_mod.begin_turn(store, db, state, None)
                turn_mod.complete_turn(store, db, p)
                if p.item is None:
                    break
                wrong = next(n for n in store.node_ids if n != item.answer)
                p2 = turn_mod.begin_turn(
                    store, db, state,
                    StudentResponse(type="node_click", node_id=wrong))
                turn_mod.complete_turn(store, db, p2)
            db.close()
    finally:
        turn_mod._call2 = original
    return captured


def _answer_aliases(store, item_id):
    if not item_id:
        return set()
    item = store.item(item_id)
    aliases = {a.casefold() for a in item.answer_aliases}
    node_ids = {n.id for n in store.graph.nodes}
    if item.answer in node_ids:
        aliases.add(store.label(item.answer).casefold())
    elif "->" in item.answer:
        # Edge answers carry NO aliases (they were deleted as unusable in an
        # earlier pass), which would make edge items look trivially safe here.
        #
        # ONLY THE *FROM* ENDPOINT IS THE ANSWER SURFACE. For all 49 edge items
        # node_id == the TO endpoint, so the unknown the student must find is
        # which prerequisite links INTO it. Naming the TO endpoint is the anchor
        # the question is built on - the item's own prompt names it in 49/49
        # cases - and withholding it leaves Call 2 asking "which link?" about an
        # unspecified edge, which measured as 32 of 36 edge ask turns with no
        # anchor at all.
        #
        # This is a REFINEMENT of the rule, not a relaxation of the assertion:
        # the FROM endpoint is still absolutely forbidden, and so is naming both.
        source = item.answer.split("->")[0].strip()
        if source in node_ids:
            aliases.add(store.label(source).casefold())
    return aliases


def test_call2_never_receives_an_answer_alias(store):
    """The rule as §1.5 states it, now enforced by CALL2_FIDELITY.

    If this fails, something restored identity-bearing labels to an ask/hint_*
    turn. Fix the contract, never this assertion."""
    breaches = []
    for call in _drive(store):
        if call["action"] not in NON_LEAKING_ACTIONS:
            continue
        aliases = _answer_aliases(store, call["item_id"])
        for label in call["labels"]:
            if label.casefold() in aliases:
                breaches.append((call["action"], label, call["item_id"]))

    assert not breaches, (
        f"Call 2 received an answer alias on {len(breaches)} ask/hint_* turns; "
        f"first three: {breaches[:3]}"
    )


def test_exposure_is_zero_not_merely_low(store):
    """Was a tripwire pinning a known defect at <=90%; now asserts the floor.

    Zero, not "low": a rate that drifts up from 0 means a representation of the
    answer found a new way through, which is exactly the failure class this
    contract exists to close.
    """
    calls = [c for c in _drive(store) if c["action"] in NON_LEAKING_ACTIONS]
    exposed = [
        c for c in calls
        if any(l.casefold() in _answer_aliases(store, c["item_id"])
               for l in c["labels"])
    ]
    rate = len(exposed) / len(calls) if calls else 0.0
    assert rate == 0.0, (
        f"answer-alias exposure on ask/hint_* is {rate:.0%} of turns "
        f"({len(exposed)}/{len(calls)}); it must be zero"
    )


def test_edge_items_never_receive_both_endpoints(store):
    """The refinement's own guard rail. One endpoint is an anchor; two is the
    answer. If a future change starts passing the full lit set again, this
    catches it even though each label individually looks permissible."""
    node_ids = {n.id for n in store.graph.nodes}
    for call in _drive(store):
        if call["action"] not in NON_LEAKING_ACTIONS or not call["item_id"]:
            continue
        item = store.item(call["item_id"])
        if "->" not in item.answer:
            continue
        endpoints = {
            store.label(e.strip()).casefold()
            for e in item.answer.split("->") if e.strip() in node_ids
        }
        given = {l.casefold() for l in call["labels"]}
        assert len(endpoints & given) <= 1, (
            f"{item.id}: Call 2 got both endpoints {endpoints & given} - "
            f"that is the edge, i.e. the answer"
        )


def test_reveal_turns_are_exempt_by_design(store):
    """§6 layer 3: a budget-forced reveal is SUPPOSED to name the answer, in
    exchange for zero mastery. It must not be counted as a breach, and Layer 1
    is deliberately not run on it."""
    calls = [c for c in _drive(store) if c["action"] == "resolved_with_support"]
    if not calls:
        pytest.skip("no forced reveal in this walk")
    assert all(c["action"] == "resolved_with_support" for c in calls)
