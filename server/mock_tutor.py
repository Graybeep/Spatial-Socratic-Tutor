"""Scripted stand-in for Call 1 and Call 2. CLAUDE.md §11, days 1-2:
"freeze schemas, mock the server so Person B is never blocked".

No network calls, no API key. Emits objects that validate against the same
Call1Decision / Call2Utterance schemas the real server/llm.py will emit in week 2,
so swapping the real calls in is a two-line change in turn.py and touches nothing
Person B built against.

What is faithfully mocked:
  - the narrowing ladder, driven by CONFIG.narrow_schedule - a research variable
    the eval sweeps, never a constant
  - the three ladder modes §9.2 needs to run its arms pure
  - server-owned counters, hint monotonicity, turn budget
  - deterministic grading of clicks and MCQ
  - the Call 1 -> graph -> Call 2 latency profile (see main.py streaming)

What is NOT mocked, deliberately: retrieval, the answer monitor, and any actual
diagnosis. Every mock `diagnosis` is prefixed MOCK:: so a stale line can never be
mistaken for model output during the week-3 read-through (§9.5).
"""
from __future__ import annotations

import hashlib
import json
import random
from functools import lru_cache
from typing import Optional

from server.config import CONFIG
from server.graph_store import GraphStore
from server.schemas import Call1Decision, Call2Utterance, Item, StudentResponse
from server.state import SessionState

#: Every diagnosis this module produces starts with this. §9.5 hand-reads 30
#: diagnosis fields; a mock line that slipped in unmarked would be read as the
#: tutor's real model of the student and quietly corrupt the only check that
#: catches that failure.
MOCK_PREFIX = "MOCK:: "


@lru_cache(maxsize=1)
def _templates() -> dict:
    return json.loads((CONFIG.prompts_dir / "mock_utterances.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def fallback_utterance(action: str) -> str:
    """One of the six canned fallbacks required by CLAUDE.md §5, for a Call 2
    timeout after the graph has already reacted."""
    return (CONFIG.prompts_dir / f"fallback_{action}.txt").read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# grading - deterministic only (CLAUDE.md §1.4)
# ---------------------------------------------------------------------------

def grade(item: Item, response: Optional[StudentResponse]) -> Optional[bool]:
    """True/False for a deterministic item, None for anything unscorable.

    PURE. Grading does not touch mastery and does not mutate state - the caller
    decides whether this observation is allowed to score at all, because a
    turn-budget forced reveal must not credit a revealed answer (CLAUDE.md §6
    layer 3).

    None means "do not touch mastery". Free text always returns None:
    CLAUDE.md §1.4 - free-text answers are for teaching and dialogue only.
    """
    if response is None:
        return None
    if response.type == "node_click":
        return response.node_id == item.answer
    if response.type == "edge_click" and response.edge is not None:
        # edge_click answers are stored as "src->dst" in items.json.
        return f"{response.edge.from_}->{response.edge.to}" == item.answer
    if response.type == "mcq":
        return response.choice_id == item.answer
    return None


def mcq_option_ids(item: Item, session_id: str) -> list:
    """Answer plus distractors, shuffled stably per (session, item).

    Seeded on the session AND the item, for two reasons:

      - stable across re-renders and reconnects within a session, so "the student
        picked option 2" means one thing for the whole dialogue and the
        distractor screen (§9.4) stays interpretable;
      - not guessable and not constant across items, so position 0 is not always
        the key. Shipping [answer, *distractors] in bank order would make every
        MCQ free and every mastery number derived from one meaningless.
    """
    options = [item.answer] + [d for d in item.distractors if d != item.answer]
    seed = hashlib.sha256(f"{session_id}:{item.id}".encode()).hexdigest()
    random.Random(seed).shuffle(options)
    return options


# ---------------------------------------------------------------------------
# narrowing - the mechanism the whole project is about
# ---------------------------------------------------------------------------

def candidate_order(store: GraphStore, item: Item) -> list:
    """A stable elimination order for one item: survivors first, casualties last.

    The lit set at any level is a PREFIX of this list, which makes narrowing
    monotone by construction - a node once excluded can never come back. That
    matters twice over: a student must not be able to recover eliminated
    candidates, and eval §9.2 matches a visual hint against a verbal one by the
    named excluded set, which is only coherent if the sets nest.

    Order: the answer, then its distractors, then graph neighbours, then
    everything else by a per-item stable hash (not by node id, or every item
    would eliminate the graph in the same order and a student would learn the
    ladder rather than the material).
    """
    ordered: list = []
    seen = set()

    def push(node_id: str) -> None:
        if node_id in store._nodes and node_id not in seen:
            seen.add(node_id)
            ordered.append(node_id)

    push(item.answer if item.answer in store._nodes else item.node_id)
    for d in item.distractors:
        push(d)
    for n in store.prereqs(item.node_id) + store.dependents(item.node_id):
        push(n)

    rest = [n for n in store.node_ids if n not in seen]
    rest.sort(key=lambda n: hashlib.sha256(f"{item.id}:{n}".encode()).hexdigest())
    for n in rest:
        push(n)
    return ordered


def lit_nodes(store: GraphStore, item: Item, narrow_level: int) -> list:
    """Nodes left lit at a given narrowing level.

    An empty list means NO narrowing - the whole graph stays lit. That is the
    level-0 state, not "dim everything".
    """
    schedule = CONFIG.narrow_schedule
    target = schedule[min(narrow_level, len(schedule) - 1)] if narrow_level > 0 else 0
    if target <= 0:
        return []
    order = candidate_order(store, item)
    if target >= len(order):
        return []
    return order[:target]


def hint_action_for_level(level: int) -> str:
    """Which hint channel fires at this level, per CONFIG.ladder_mode.

    interleaved is production. The last rung is verbal on purpose: the ladder
    should bottom out having said something, not having dimmed to the guess-
    probability floor and stopped.
    """
    mode = CONFIG.ladder_mode
    if mode == "visual_only":
        return "hint_visual"
    if mode == "verbal_only":
        return "hint_verbal"
    if level >= CONFIG.hint_max:
        return "hint_verbal"
    return "hint_visual" if level % 2 == 1 else "hint_verbal"


def narrows(action: str) -> bool:
    """Only a visual hint moves the narrowing level.

    A verbal hint must NOT narrow further, or the two channels are confounded and
    §9.2 cannot attribute an elimination to either one. It still inherits
    whatever dimming is already in force for the item.
    """
    return action == "hint_visual" and CONFIG.ladder_mode != "verbal_only"


# ---------------------------------------------------------------------------
# Call 1 stand-in
# ---------------------------------------------------------------------------

def mock_call1(
    store: GraphStore,
    state: SessionState,
    item: Item,
    response: Optional[StudentResponse],
    graded: Optional[bool],
) -> Call1Decision:
    """A schema-valid decision. Everything here is a REQUEST - the server applies
    guards and decides (CLAUDE.md §1.7). `graded` is passed in rather than
    recomputed so Call 1 and the guards agree on one grading."""
    if response is None:
        action, student_state = "ask", "on_track"
        diagnosis = "session or item opened"
        requested_hint = state.hint_level
    elif graded is True:
        action, student_state = "advance", "correct"
        diagnosis = "deterministic item answered correctly"
        requested_hint = state.hint_level
    elif graded is False:
        requested_hint = state.hint_level + 1
        action = hint_action_for_level(min(requested_hint, CONFIG.hint_max))
        student_state = "guessing" if state.hint_level >= 2 else "stuck"
        diagnosis = f"wrong answer at hint_level={state.hint_level}"
    else:
        requested_hint = state.hint_level + 1
        action = hint_action_for_level(min(requested_hint, CONFIG.hint_max))
        student_state = "confused_prereq"
        diagnosis = "free-text turn, unscored per CLAUDE.md 1.4"

    projected = min(requested_hint, CONFIG.hint_max)
    if action.startswith("hint"):
        level = state.visual_narrow_level + 1 if narrows(action) else state.visual_narrow_level
        focus = lit_nodes(store, item, level)
    elif action in {"advance", "explain"}:
        focus = []
    else:
        focus = lit_nodes(store, item, state.visual_narrow_level)

    return Call1Decision(
        student_state=student_state,
        diagnosis=MOCK_PREFIX + diagnosis,
        correct=bool(graded) if graded is not None else False,
        requested_action=action,
        requested_hint_level=projected,
        focus_nodes=focus,
        expects="text" if action == "explain" else item.type,
    )


# ---------------------------------------------------------------------------
# Call 2 stand-in
# ---------------------------------------------------------------------------

def mock_call2(action: str, hint_level: int, focus_labels: list, n_lit: int) -> Call2Utterance:
    """Receives only what the real Call 2 receives: action, hint_level and focus
    node LABELS (CLAUDE.md §5). No item, no answer, no chunk - the signature is
    the guarantee."""
    templates = _templates().get(action) or []
    if not templates:
        return Call2Utterance(utterance=fallback_utterance(action))
    text = templates[min(hint_level, len(templates) - 1)]
    return Call2Utterance(
        utterance=text.format(
            labels=", ".join(focus_labels),
            first=focus_labels[0] if focus_labels else "this idea",
            n=n_lit,
        )
    )
