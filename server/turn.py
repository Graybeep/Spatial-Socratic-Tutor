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

from server import guards
from server import llm as llm_mod
from server import mastery as mastery_mod
from server import mock_tutor
from server import retrieval
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
    #: Set when guard layer 1 fired. Always logged (§6, §10).
    leak_note: Optional[str] = None

    def reveals_answer(self) -> bool:
        """True when naming the current node would give the answer away.

        For a node_click or mcq item the answer IS item.node_id, so
        graph_state.current_node must stay None until the item is behind us.
        Items whose answer is not on the graph (visually_answerable false -
        CLAUDE.md §3 expects more than half the bank) are safe to locate.

        Also drives `panel_locked`. Both are the same question - "would telling
        the student about this node hand them the answer" - and the answer is a
        property of the ITEM, so it holds for every turn the item is open. It
        must never be recomputed from per-turn state like `expects`.
        """
        return self.item is not None and self.item.visually_answerable

    def item_public(self) -> Optional[ItemPublic]:
        """The stripped item, built in ONE place so the streaming and JSON
        transports can never disagree about what an item exposes."""
        if self.item is None or self.session_complete:
            return None
        return ItemPublic(
            id=self.item.id,
            difficulty=self.item.difficulty,
            scorable=_is_scorable(self.item),
        )


# ---------------------------------------------------------------------------
# selection helpers
# ---------------------------------------------------------------------------

#: What Call 2 may know about the answer, per action. CLAUDE.md §1.5 says Call 2
#: never receives the answer or its aliases; §5 says it receives focus node
#: labels. For a node-answer item those are the same string, so the contract has
#: to be expressed as a FIDELITY CEILING rather than a field whitelist.
#:
#: The same answer has four representations, decreasing in fidelity:
#:
#:     node id  ->  node label  ->  position in a lit set  ->  size of a lit set
#:
#: A guard written against any one of them is blind to the others - which is how
#: this breach, ItemPublic.node_id, and the eval-coverage bug all happened. The
#: ceiling below says how much fidelity each action may carry, and _call2_context
#: enforces it. See docs/writeup/representation-blindness.md.
#:
#: "labels" = full identities. "count" = cardinality only, no identities.
CALL2_FIDELITY = {
    "ask": "safe_label",      # a label, but never one that IS the answer
    "hint_visual": "count",   # the graph points; the text must not name
    "hint_verbal": "count",   # count + answer category, still no identities
    "backtrack": "count",
    "advance": "labels",      # legitimately explains - §5
    "explain": "labels",
    "resolved_with_support": "labels",  # forced reveal, §6 layer 3
}


def _answer_surface(store: GraphStore, item) -> set:
    """Every string that would name the answer at label fidelity.

    Not just the aliases. For an edge answer "a->b", naming either ENDPOINT
    hands over half the edge, so both endpoint labels are on the surface even
    though neither is an alias (edge aliases were deleted as unusable in an
    earlier pass, which would otherwise make edge items look safe here).
    """
    if item is None:
        return set()
    surface = {a.casefold() for a in item.answer_aliases}
    node_ids = {n.id for n in store.graph.nodes}

    if item.answer in node_ids:
        surface.add(store.label(item.answer).casefold())
    elif "->" in item.answer:
        for endpoint in item.answer.split("->"):
            endpoint = endpoint.strip()
            if endpoint in node_ids:
                surface.add(store.label(endpoint).casefold())
    return surface


def _answer_category(item) -> str:
    """The KIND of thing being asked for, carrying no identity.

    "a concept" / "a relationship" tells Call 2 enough to phrase a hint without
    telling it which one. This is the most fidelity hint_verbal may carry.
    """
    if item is None:
        return "an answer"
    return {
        "node_click": "a concept on the map",
        "edge_click": "a relationship between two concepts",
        "mcq": "one of the options",
    }.get(item.type, "an answer")


def _call2_context(store: GraphStore, state: SessionState, phase1) -> tuple:
    """(labels, n_lit, category) that Call 2 is allowed to see for this action.

    THE FIX FOR THE §1.5 BREACH. Previously this was:

        labels = store.labels(focus_nodes) or [store.label(state.current_node)]

    which had two defects. The main clause handed over every lit label, and the
    answer is normally lit - narrowing exists to leave it lit - so ask/hint_*
    carried an answer alias on 78-100% of turns. The `or` clause was worse and
    was a plain ordering bug: on backtrack, focus_nodes is empty and
    start_item() has ALREADY moved current_node to the backtrack target, so
    Call 2 received the new item's answer as its entire context, 100% of the
    time.

    Now: hint_* and backtrack get cardinality only. `ask` gets a label only if
    that label is not on the answer surface, falling back to a prerequisite and
    then to nothing.
    """
    item = phase1.item
    action = "advance" if phase1.session_complete else phase1.action
    fidelity = CALL2_FIDELITY.get(action, "count")

    focus = phase1.graph_state.focus_nodes
    n_lit = len(focus) or len(store.node_ids)
    category = _answer_category(item)

    if fidelity == "labels":
        return store.labels(focus) or (
            [store.label(state.current_node)] if state.current_node else []
        ), n_lit, category

    if fidelity == "count":
        # No identities at all. The graph has already said which nodes; saying
        # them again in words is the leak the whole architecture exists to
        # avoid, and it is what made "helps by showing less" a claim we asserted
        # rather than a property we enforced.
        return [], n_lit, category

    # "safe_label": ask. Usually the question is about a mechanism, not about
    # the node's name, so a label is only offered when it cannot be the answer.
    surface = _answer_surface(store, item)

    # EDGE ITEMS: ONE ENDPOINT, NEVER BOTH. Flagged for sign-off - this is a
    # deviation from the per-action table, which did not distinguish answer
    # arity, and it should be reverted rather than widened if not wanted.
    #
    # For a NODE answer the label is the entire answer, so withholding it costs
    # nothing but phrasing. For an EDGE answer the answer is a PAIR, and the
    # question ("which prerequisite of X?") cannot be posed without naming one
    # end. Measured under the strict rule: 32 of 36 edge_click ask turns got no
    # anchor at all, which makes 49 of the 101 scored items unaskable - Call 2
    # can only produce "which one is it?" about an unspecified edge.
    #
    # Naming ONE endpoint is a strictly lower fidelity than the answer: the
    # student still has to pick which of that node's prereqs is the link, and
    # the narrowing still does real work. Naming both would be the answer, so
    # only item.node_id is offered and the opposite endpoint stays on the
    # surface. The item's own prompt already names this endpoint in 49/49 cases,
    # so it is an anchor the item was authored around.
    if item is not None and "->" in item.answer:
        anchor = item.node_id
        other = [e.strip() for e in item.answer.split("->") if e.strip() != anchor]
        if anchor and all(store.label(anchor).casefold()
                          != store.label(o).casefold() for o in other):
            return [store.label(anchor)], n_lit, category

    def safe(node_id):
        return node_id and store.label(node_id).casefold() not in surface

    if state.current_node and safe(state.current_node):
        return [store.label(state.current_node)], n_lit, category

    # The node IS the answer. Reach for a prerequisite instead: it situates the
    # question without naming the target.
    if item is not None:
        for prereq in store.prereqs(item.node_id):
            if safe(prereq):
                return [store.label(prereq)], n_lit, category

    return [], n_lit, category


def _is_scorable(item) -> bool:
    """CLAUDE.md §1.4 plus the item's own flag.

    Type is necessary but not sufficient. §1.4 names the three deterministic
    types; an item of one of those types can still be unfit to score, and the
    mcq bank currently is. Both conditions, always - a future bank that sets
    scorable=True on a free-text item must still not score.
    """
    if item is None:
        return False
    return item.type in SCORABLE_EXPECTS and getattr(item, "scorable", True)


def _mastery_map(state: SessionState) -> dict:
    return {n: mastery_mod.mastery(t) for n, t in state.theta_map.items()}


def _pick_item(store: GraphStore, state: SessionState, node_id: str) -> Optional[Item]:
    """First unused SCORABLE item on the node, then any unused, then reuse.

    Scorable-first matters once a type is demoted. With mcq unscored, 3 of the
    ~5 items on a node move no number, and bank order interleaves them - so a
    student answering correctly could work three items before anything credited
    them, and the node would advance on the strength of two. Preferring scorable
    items keeps the adaptive path fed; the rest still teach, in the turns after.
    """
    items = store.items_for(node_id)
    if not items:
        return None
    unused = [i for i in items if i.id not in state.completed_items]
    pool = unused or items
    return next((i for i in pool if _is_scorable(i)), pool[0])


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
    store: GraphStore, state: SessionState, lit_nodes: list, reveal_current: bool
) -> GraphState:
    """dimmed_nodes is AUTHORITATIVE: an empty dimmed set means no narrowing.

    focus_nodes is derived from it and kept for logging and for eval §9.2's
    matched-elimination comparison. The client renders from dimmed_nodes alone,
    so there is no ambiguity between "hint level 0" and "this item is not on the
    graph" (visually_answerable: false) - both are simply "nothing dimmed".
    """
    all_ids = store.node_ids
    current = state.current_node if reveal_current else None
    lit = [n for n in lit_nodes if n in set(all_ids)]
    # No narrowing at all, or a "narrowing" that excludes nothing, is not a
    # narrowing. Collapse both to the empty dimmed set.
    if not lit or len(lit) >= len(all_ids):
        return GraphState(
            current_node=current,
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
        current_node=current,
        focus_nodes=focus,
        focus_edges=focus_edges,
        dimmed_nodes=dimmed,
        mastery={n: round(v, 4) for n, v in _mastery_map(state).items()},
    )


# ---------------------------------------------------------------------------
# the two calls (CLAUDE.md §5), and what happens when they fail
# ---------------------------------------------------------------------------
#
# MOCK_MODE is the default and stays the default. `main` must always run
# (§13.2), and it must run with no API key and no network.
#
# Neither wrapper is allowed to fail a turn. A model that times out or returns
# an unparseable object costs the student a good utterance, not their session:
# Call 1 falls back to the mock's deterministic decision, Call 2 to the canned
# per-action line §5 requires. Every fallback is logged (§10).


def _call1(store, state, item, response, graded) -> Call1Decision:
    if CONFIG.mock_mode:
        return mock_tutor.mock_call1(store, state, item, response, graded)

    try:
        return llm_mod.call1(
            item_prompt=item.prompt,
            answer=item.answer,
            item_type=item.type,
            node_label=store.label(item.node_id),
            graph_digest=llm_mod.graph_digest(store),
            history=state.history[-6:],
            hint_level=state.hint_level,
            turns_on_item=state.turns_on_item,
            mastery_note=f"{mastery_mod.mastery(state.theta_map.get(item.node_id, 0.0)):.2f} "
                         f"on {store.label(item.node_id)}",
        )
    except llm_mod.LLMError as exc:
        # A degraded turn beats a dead one, but never a silent one.
        _log_event("call1_fallback", {"error": str(exc)[:400]})
        return mock_tutor.mock_call1(store, state, item, response, graded)


#: §5's gate table, positive half. Only these two actions may receive source
#: text; `backtrack` gets the prereq node's chunk, which is a different query
#: and is not wired here.
CHUNK_ACTIONS = frozenset({"advance", "explain"})


def _chunk_for(store: GraphStore, state, action: str, item) -> Optional[str]:
    """The masked, delimited chunk for this turn, or None.

    §5's table has two halves and only the restrictive one was built: llm.call2
    asserts that no chunk reaches `ask`/`hint_*`, and nothing ever passed one on
    `advance`/`explain` either, so the tutor could not cite the chapter at all.

    The query is the node's label plus its definition, which is what
    RETRIEVAL_SCORE_FLOOR was calibrated against - a label alone scores about
    half as much and falls under the floor on the weaker nodes.

    Answer spans are masked before delimiting, and both happen inside
    retrieval.chunk_for_call2 in that order (offsets refer to the unprefixed
    text). Guard layer 4 turns a miss into None, and the caller must then say
    the chapter does not cover it rather than answering anyway.
    """
    if action not in CHUNK_ACTIONS or item is None:
        return None
    node = store.node(item.node_id)
    return retrieval.chunk_for_call2(
        f"{node.label} {node.definition}", item.answer_spans)


def _call2(state, action: str, hint_level: int, labels: list, n_lit: int,
           chunk: Optional[str] = None) -> str:
    if CONFIG.mock_mode:
        return mock_tutor.mock_call2(action, hint_level, labels, n_lit, chunk).utterance

    try:
        # No item, no answer, no aliases. `chunk` is None on every action but
        # advance and explain, and llm.call2 asserts that rather than trusting
        # this caller (§5).
        return llm_mod.call2(
            action=action,
            hint_level=hint_level,
            focus_labels=labels,
            n_lit=n_lit,
            recent=state.history[-2:],
            chunk=chunk,
        ).utterance
    except llm_mod.LLMError as exc:
        _log_event("call2_fallback", {"action": action, "error": str(exc)[:400]})
        return mock_tutor.fallback_utterance(action)


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
        gs = _build_graph_state(store, state, [], reveal_current=True)
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
    decision = _call1(store, state, item, response, graded)

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
        and _is_scorable(item)
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
    graph_state = _build_graph_state(
        store, state, lit, reveal_current=not (item is not None and item.visually_answerable)
    )

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

    labels, n_lit, answer_category = _call2_context(store, state, phase1)

    if phase1.resolved_with_support:
        # The budget forced a reveal, which is SUPPOSED to name the answer
        # (§6 layer 3, zero mastery in exchange). Layer 1 is not run on it:
        # screening this turn would trip on the system working correctly.
        utterance = _call2(state, "resolved_with_support", 0, labels, n_lit)
        leak_note = None
    else:
        chunk = _chunk_for(store, state, action, phase1.item)
        utterance = _call2(state, action, phase1.hint_level, labels, n_lit, chunk)
        leak_note = None
        if phase1.item is not None:
            utterance, leak_note = guards.screen_utterance(
                utterance,
                phase1.item.answer,
                phase1.item.answer_aliases,
                regenerate=lambda: _call2(
                    state, action, phase1.hint_level, labels, n_lit, chunk),
                fallback=mock_tutor.fallback_utterance(action),
                action=action,
                # Every other concept name on the map. Without these, a hint
                # naming the lit node "Flow Control" would be recorded as
                # leaking the answer "Flow" - both are nodes here.
                context_phrases=[
                    n.label for n in store.graph.nodes
                    if n.id != phase1.item.node_id
                ],
            )

    phase1.leak_note = leak_note
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
        panel_locked=phase1.reveals_answer(),
    )

    db.save(state)
    _log(phase1, response)
    return response


# ---------------------------------------------------------------------------
# step 9 - log everything (CLAUDE.md §5, §10: no silent anything)
# ---------------------------------------------------------------------------

def _log_event(kind: str, payload: dict) -> None:
    """A non-turn event: a fallback, a retry, a guard trip.

    §10 forbids silent retries and silent guard triggers. These go to the same
    jsonl as the turns so a single file is the whole record of a session.
    """
    CONFIG.log_dir.mkdir(parents=True, exist_ok=True)
    record = {"ts": time.time(), "event": kind, **payload}
    with (CONFIG.log_dir / "turns.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + chr(10))


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
        # Guard layer 1. None when it did not fire. The rate is a result
        # (§6): post-split, a hit means the model reconstructed the answer
        # parametrically, because Call 2 never saw it.
        "leak_note": phase1.leak_note,
        "llm": llm_mod.stats_snapshot() if not CONFIG.mock_mode else None,
    }
    path = CONFIG.log_dir / "turns.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
