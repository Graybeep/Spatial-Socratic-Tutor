"""Turn orchestrator. CLAUDE.md §5.

    1. load student_state from sqlite
    2. assemble Call 1 context
    3. CALL 1  -> decision object
    4. server applies guards, updates counters, decides final action
    5. graph_state returned/streamed IMMEDIATELY
    6. CALL 2  -> utterance only
    7. mastery.update() in Python
    8. next_node() in Python
    9. log everything

Split into begin_turn (steps 1-5) and complete_turn (step 6), so the transport in
main.py can flush graph_state before Call 2 starts. CLAUDE.md §8: the graph reacts
on Call 1 return and never blocks on the text.

ONE DELIBERATE DEVIATION from the numbered list above: deterministic scoring
(step 7) runs inside begin_turn, not after Call 2. This is a correctness fix, not
a cosmetic one - `advance` vs `backtrack` and next_node() all READ mastery, so
scoring after the action decision would route the tutor on last turn's state.
It also means the mastery recolour and the dimming land in the same frame instead
of the colour trailing a turn behind. Everything §7 specifies about HOW it is
scored is unchanged.

STEP 4 IS ORDERED, AND THE ORDER IS LOAD-BEARING:

    4a. grade          - pure, mutates nothing
    4b. guards         - decide the final action AND whether this turn may score
    4c. score          - only if 4b allowed it
    4d. route          - advance / backtrack / next_node, reading fresh mastery
    4e. narrow         - only a visual hint moves the narrowing level

4b must precede 4c. A turn-budget forced reveal awards zero mastery (§6 layer 3);
if scoring ran first, a `correct: true` arriving on the turn the guard overturns
the action would credit an answer the tutor just gave away. 4c must precede 4d for
the reason above. Do not collapse these.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

from server import mastery as mastery_mod
from server import mock_tutor
from server.config import CONFIG
from server.graph_store import GraphStore
from server.schemas import (
    SCORABLE_EXPECTS,
    Call1Decision,
    EdgeRef,
    GraphState,
    Item,
    ItemPublic,
    MCQOption,
    StudentResponse,
    TurnBudget,
    TurnResponse,
)
from server.state import SessionState, Store


@dataclass
class Phase1:
    """Everything decided before Call 2 runs."""

    state: SessionState
    decision: Call1Decision
    action: str
    hint_level: int
    expects: str
    graph_state: GraphState
    item: Optional[Item]
    mcq_options: list = field(default_factory=list)
    resolved_with_support: bool = False
    session_complete: bool = False
    scored: Optional[bool] = None

    def item_public(self) -> Optional[ItemPublic]:
        """The stripped item, built in ONE place so the streaming and JSON
        transports can never disagree about what an item exposes."""
        if self.item is None or self.session_complete:
            return None
        return ItemPublic(
            id=self.item.id,
            node_id=self.item.node_id,
            difficulty=self.item.difficulty,
            scorable=self.item.type in SCORABLE_EXPECTS,
        )


# ---------------------------------------------------------------------------
# selection helpers
# ---------------------------------------------------------------------------

def _mastery_map(state: SessionState) -> dict:
    return {n: mastery_mod.mastery(t) for n, t in state.theta_map.items()}


def _pick_item(store: GraphStore, state: SessionState, node_id: str) -> Optional[Item]:
    """First unused item on the node, else the least recently used one."""
    items = store.items_for(node_id)
    if not items:
        return None
    unused = [i for i in items if i.id not in state.completed_items]
    return unused[0] if unused else items[0]


def _advance_to_next_node(store: GraphStore, state: SessionState) -> Optional[Item]:
    node_id = mastery_mod.next_node(store, _mastery_map(state))
    if node_id is None:
        state.session_complete = True
        state.current_item_id = None
        return None
    item = _pick_item(store, state, node_id)
    if item is None:
        state.session_complete = True
        return None
    state.start_item(node_id, item.id)
    state.consecutive_failures = 0
    return item


def _build_graph_state(
    store: GraphStore, state: SessionState, lit_nodes: list
) -> GraphState:
    """dimmed_nodes is AUTHORITATIVE: an empty dimmed set means no narrowing.

    focus_nodes is derived from it and kept for logging and for eval §9.2's
    matched-elimination comparison. The client renders from dimmed_nodes alone,
    so there is no ambiguity between "hint level 0" and "this item is not on the
    graph" (visually_answerable: false) - both are simply "nothing dimmed".
    """
    all_ids = store.node_ids
    lit = [n for n in lit_nodes if n in set(all_ids)]
    # No narrowing at all, or a "narrowing" that excludes nothing, is not a
    # narrowing. Collapse both to the empty dimmed set.
    if not lit or len(lit) >= len(all_ids):
        return GraphState(
            current_node=state.current_node,
            focus_nodes=[],
            focus_edges=[],
            dimmed_nodes=[],
            mastery={n: round(v, 4) for n, v in _mastery_map(state).items()},
        )

    focus = lit
    dimmed = [n for n in all_ids if n not in set(focus)]
    focus_set = set(focus)
    focus_edges = [
        EdgeRef(**{"from": e.from_, "to": e.to})
        for e in store.graph.edges
        if e.from_ in focus_set and e.to in focus_set
    ]
    return GraphState(
        current_node=state.current_node,
        focus_nodes=focus,
        focus_edges=focus_edges,
        dimmed_nodes=dimmed,
        mastery={n: round(v, 4) for n, v in _mastery_map(state).items()},
    )


# ---------------------------------------------------------------------------
# steps 1-5
# ---------------------------------------------------------------------------

def begin_turn(
    store: GraphStore,
    db: Store,
    state: SessionState,
    response: Optional[StudentResponse],
) -> Phase1:
    state.turn_id += 1

    if state.current_item_id is None and not state.session_complete:
        _advance_to_next_node(store, state)

    if state.session_complete or state.current_item_id is None:
        gs = _build_graph_state(store, state, [])
        return Phase1(
            state=state,
            decision=Call1Decision(
                student_state="correct",
                diagnosis="session complete: no unmastered node with satisfied prereqs",
                correct=True,
                requested_action="advance",
                requested_hint_level=0,
                focus_nodes=[],
                expects="text",
            ),
            action="advance",
            hint_level=0,
            expects="text",
            graph_state=gs,
            item=None,
            session_complete=True,
        )

    item = store.item(state.current_item_id)
    state.turns_on_item += 1

    if response is not None:
        state.record_history("student", _describe_response(store, response))

    # --- step 4a: grade. Pure. Mutates nothing. ----------------------------
    graded = mock_tutor.grade(item, response)

    # --- step 3: Call 1 ----------------------------------------------------
    decision = mock_tutor.mock_call1(store, state, item, response, graded)

    # --- step 4b: guards decide the final action AND whether we may score ---
    # Guard layer 2: the server owns the counter, the model only asked.
    hint_level = state.bump_hint(decision.requested_hint_level)
    action = decision.requested_action

    # Guard layer 3: turn budget. A forced reveal awards ZERO mastery, so it has
    # to be settled before scoring runs - otherwise a correct answer arriving on
    # the same turn would be credited for something the tutor gave away.
    resolved_with_support = graded is not True and state.budget_exhausted

    scorable = (
        graded is not None
        and response is not None
        and response.type in SCORABLE_EXPECTS
        and not resolved_with_support
    )

    # --- step 4c: score. Guard layer 5: Python computes the number. --------
    if scorable:
        _apply_mastery(store, state, item, graded, hint_level)

    # --- step 4d: route. Reads the mastery written immediately above. ------
    session_complete = False
    if resolved_with_support:
        action = "advance"
        state.completed_items.append(item.id)
    elif graded is True:
        action = "advance"
        state.completed_items.append(item.id)
        state.consecutive_failures = 0
    elif (
        graded is False
        and state.consecutive_failures >= CONFIG.consecutive_failures_before_backtrack
    ):
        # Two consecutive failures on the node -> its weakest prereq
        # (CLAUDE.md §7). _apply_mastery has already run, so this reads the
        # theta that includes this turn's failure and its prereq decay.
        target = mastery_mod.backtrack_target(store, item.node_id, _mastery_map(state))
        if target is not None:
            next_item = _pick_item(store, state, target)
            if next_item is not None:
                action = "backtrack"
                state.start_item(target, next_item.id)
                state.consecutive_failures = 0
                item = next_item
                hint_level = 0

    if action == "advance":
        next_item = _advance_to_next_node(store, state)
        if next_item is None:
            session_complete = True
        else:
            item = next_item
            hint_level = 0

    # --- step 4e: narrow. Only a visual hint moves the level. --------------
    if item is not None and action.startswith("hint"):
        if mock_tutor.narrows(action):
            state.visual_narrow_level = min(
                state.visual_narrow_level + 1, CONFIG.hint_max
            )
        lit = mock_tutor.lit_nodes(store, item, state.visual_narrow_level)
    else:
        # advance, backtrack, ask, explain: no narrowing. current_node carries
        # "where we are"; dimming is reserved for the hint channel alone.
        lit = []

    expects = "text" if item is None else item.type
    graph_state = _build_graph_state(store, state, lit)

    mcq_options = []
    if expects == "mcq" and item is not None:
        mcq_options = [
            MCQOption(id=n, label=store.label(n))
            for n in mock_tutor.mcq_option_ids(item, state.session_id)
        ]

    return Phase1(
        state=state,
        decision=decision,
        action=action,
        hint_level=hint_level,
        expects=expects,
        graph_state=graph_state,
        item=item,
        mcq_options=mcq_options,
        resolved_with_support=resolved_with_support,
        session_complete=session_complete or state.session_complete,
        scored=graded,
    )


def _describe_response(store: GraphStore, response: StudentResponse) -> str:
    if response.type == "node_click":
        return f"[clicked {store.label(response.node_id or '')}]"
    if response.type == "edge_click" and response.edge is not None:
        return f"[clicked edge {store.label(response.edge.from_)} -> {store.label(response.edge.to)}]"
    if response.type == "mcq":
        return f"[chose {store.label(response.choice_id or '')}]"
    return response.text or ""


def _apply_mastery(
    store: GraphStore, state: SessionState, item: Item, correct: bool, hint_level: int
) -> None:
    node_id = item.node_id
    n_obs = state.n_obs.get(node_id, 0)
    state.theta_map[node_id] = mastery_mod.update(
        theta=state.theta_map.get(node_id, 0.0),
        difficulty=item.difficulty,
        correct=correct,
        hint_level=hint_level,
        n_obs=n_obs,
    )
    state.n_obs[node_id] = n_obs + 1

    if not correct:
        state.consecutive_failures += 1
        # Backward propagation - what makes the graph do work (CLAUDE.md §7).
        state.theta_map = mastery_mod.decay_prereqs(state.theta_map, store.prereqs(node_id))


# ---------------------------------------------------------------------------
# step 6
# ---------------------------------------------------------------------------

def complete_turn(store: GraphStore, db: Store, phase1: Phase1) -> TurnResponse:
    state = phase1.state
    action = "advance" if phase1.session_complete else phase1.action

    labels = store.labels(phase1.graph_state.focus_nodes) or (
        [store.label(state.current_node)] if state.current_node else []
    )
    n_lit = len(phase1.graph_state.focus_nodes) or len(store.node_ids)

    if phase1.resolved_with_support:
        utterance = mock_tutor.mock_call2("resolved_with_support", 0, labels, n_lit).utterance
    else:
        utterance = mock_tutor.mock_call2(action, phase1.hint_level, labels, n_lit).utterance

    state.record_history("tutor", utterance)

    response = TurnResponse(
        session_id=state.session_id,
        turn_id=state.turn_id,
        utterance=utterance,
        action=action,
        hint_level=phase1.hint_level,
        expects=phase1.expects,
        mcq_options=phase1.mcq_options,
        graph_state=phase1.graph_state,
        item=phase1.item_public(),
        turn_budget=TurnBudget(used=state.turns_on_item, max=CONFIG.turn_budget),
        resolved_with_support=phase1.resolved_with_support,
        session_complete=phase1.session_complete,
    )

    db.save(state)
    _log(phase1, response)
    return response


# ---------------------------------------------------------------------------
# step 9 - log everything (CLAUDE.md §5, §10: no silent anything)
# ---------------------------------------------------------------------------

def _log(phase1: Phase1, response: TurnResponse) -> None:
    """One jsonl line per turn holding the FULL Call 1 output.

    `diagnosis` is here and nowhere else - it is what the week-3 read-through
    (§9.5) reads, and it must never reach the client. dimmed_nodes is logged
    verbatim because eval §9.2 matches hints by the excluded set.
    """
    CONFIG.log_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.time(),
        "session_id": response.session_id,
        "turn_id": response.turn_id,
        "mock": CONFIG.mock_mode,
        "call1": phase1.decision.model_dump(),
        "server_action": response.action,
        "server_hint_level": response.hint_level,
        "scored": phase1.scored,
        "ladder_mode": CONFIG.ladder_mode,
        "narrow_schedule": CONFIG.narrow_schedule,
        "visual_narrow_level": phase1.state.visual_narrow_level,
        "n_lit": len(response.graph_state.focus_nodes) or None,
        "resolved_with_support": response.resolved_with_support,
        "item_id": phase1.item.id if phase1.item else None,
        "focus_nodes": response.graph_state.focus_nodes,
        "dimmed_nodes": response.graph_state.dimmed_nodes,
        "utterance": response.utterance,
    }
    path = CONFIG.log_dir / "turns.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
