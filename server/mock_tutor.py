"""Scripted stand-in for Call 1 and Call 2. CLAUDE.md §11, days 1-2:
"freeze schemas, mock the server so Person B is never blocked".

This module makes NO network calls and needs NO API key. It emits objects that
validate against the same Call1Decision / Call2Utterance schemas the real
server/llm.py will emit in week 2, so swapping the real calls in is a one-line
change in turn.py and touches nothing Person B built against.

What is faithfully mocked:
  - the narrowing sequence (focus_nodes shrinks as hint_level rises) - the demo
    mechanism, so the client must be built against real numbers
  - server-owned counters, hint monotonicity, turn budget
  - deterministic grading of clicks and MCQ
  - the Call 1 -> graph -> Call 2 latency profile (see main.py streaming)

What is NOT mocked, deliberately: retrieval, the answer monitor, and any actual
diagnosis. `diagnosis` here is a canned string; the week-3 read-through (§9.5)
needs real model output and mock text would only pollute the logs.
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Optional

from server.config import CONFIG
from server.graph_store import GraphStore
from server.schemas import Call1Decision, Call2Utterance, Item, StudentResponse
from server.state import SessionState


@lru_cache(maxsize=1)
def _templates() -> dict:
    return json.loads((CONFIG.prompts_dir / "mock_utterances.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def fallback_utterance(action: str) -> str:
    """One of the six canned fallbacks required by CLAUDE.md §5, for a Call 2
    timeout after the graph has already reacted."""
    path = CONFIG.prompts_dir / f"fallback_{action}.txt"
    return path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# grading - deterministic only (CLAUDE.md §1.4)
# ---------------------------------------------------------------------------

def grade(item: Item, response: Optional[StudentResponse]) -> Optional[bool]:
    """True/False for a deterministic item, None for anything unscorable.

    None means "do not touch mastery". Free text always returns None: CLAUDE.md
    §1.4 - free-text answers are for teaching and dialogue only, never scored.
    A mock that scored them would teach Person B's client the wrong contract.
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


def mcq_option_ids(item: Item, seed: int) -> list:
    """Answer plus distractors in a stable shuffled order.

    Seeded per item so the option order is identical on every run - the eval
    reruns the same dialogues and a reshuffle would change what "the student
    picked option 2" means, which would quietly break the distractor screen
    (CLAUDE.md §9.4).
    """
    options = [item.answer] + list(item.distractors)
    rng = random.Random(f"{seed}:{item.id}")
    rng.shuffle(options)
    return options


# ---------------------------------------------------------------------------
# narrowing - the mechanism the whole project is about
# ---------------------------------------------------------------------------

def focus_for_hint(store: GraphStore, item: Item, hint_level: int) -> list:
    """The node set left lit at a given hint level.

    An empty list means NO narrowing - the whole graph stays lit. That is the
    level-0 state, not "dim everything".

    The sequence is deliberately monotone: each level's set is a subset of the
    previous one. A hint that re-lit a node it had already excluded would let a
    student recover eliminated candidates, and would make eval §9.2's
    "same named excluded set" incoherent.
    """
    if hint_level <= 0:
        return []

    answer_nodes = [item.answer] if item.answer in set(store.node_ids) else []
    candidates = answer_nodes + [d for d in item.distractors if d != item.answer]
    context = store.prereqs(item.node_id) + store.dependents(item.node_id)

    if hint_level == 1:
        lit = candidates + [c for c in context if c not in candidates]
    elif hint_level == 2:
        lit = candidates
    elif hint_level == 3:
        lit = candidates[:3]
    else:
        lit = candidates[:2]

    if item.node_id not in lit:
        lit = [item.node_id] + lit
    # Preserve order, drop duplicates.
    seen, out = set(), []
    for n in lit:
        if n not in seen and n in store._nodes:
            seen.add(n)
            out.append(n)
    return out


# ---------------------------------------------------------------------------
# Call 1 stand-in
# ---------------------------------------------------------------------------

def mock_call1(
    store: GraphStore,
    state: SessionState,
    item: Item,
    response: Optional[StudentResponse],
) -> Call1Decision:
    """Returns a schema-valid decision. Everything here is a REQUEST - the server
    still applies guards and decides (CLAUDE.md §1.7)."""
    correct = grade(item, response)

    if response is None:
        action, student_state, diagnosis = "ask", "on_track", "mock: session or item opened"
        requested_hint = 0
    elif correct is True:
        action, student_state, diagnosis = "advance", "correct", "mock: deterministic item answered correctly"
        requested_hint = state.hint_level
    elif correct is False:
        # Alternate visual and verbal so the client exercises both paths.
        action = "hint_visual" if state.hint_level % 2 == 0 else "hint_verbal"
        student_state = "guessing" if state.hint_level >= 2 else "stuck"
        diagnosis = f"mock: wrong click at hint_level={state.hint_level}"
        requested_hint = state.hint_level + 1
    else:
        # Free text. Never scored - it moves the dialogue, not the mastery.
        action, student_state = "hint_verbal", "confused_prereq"
        diagnosis = "mock: free-text turn, unscored per CLAUDE.md 1.4"
        requested_hint = state.hint_level + 1

    projected_hint = min(requested_hint, CONFIG.hint_max)
    focus = focus_for_hint(store, item, projected_hint) if action.startswith("hint") else []
    if action in {"advance", "explain"}:
        focus = [item.node_id]

    return Call1Decision(
        student_state=student_state,
        diagnosis=diagnosis,
        correct=bool(correct) if correct is not None else False,
        requested_action=action,
        requested_hint_level=projected_hint,
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
