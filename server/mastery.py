"""Deterministic scoring and selection. CLAUDE.md §7.

No LLM touches anything in this file. The model emits a boolean; Python computes
the number (CLAUDE.md §1.3, guard layer 5). Every function here is pure and
unit-tested.

Constants come from config so nothing is hard-coded (CLAUDE.md §1.10), but they
are read once into module-level names so the formulas below read like the spec.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

from server.config import CONFIG

HINT_MAX = CONFIG.hint_max
K_START = CONFIG.k_start
K_MIN = CONFIG.k_min
K_DECAY = CONFIG.k_decay
THRESHOLD = CONFIG.mastery_threshold
HINT_DIFFICULTY_SLOPE = CONFIG.hint_difficulty_slope
PREREQ_DECAY = CONFIG.prereq_decay


def update(theta: float, difficulty: float, correct: bool, hint_level: int, n_obs: int) -> float:
    """One observation, one theta update.

    A hinted item is an EASIER item - that is the whole trick. Adjusting effective
    difficulty (rather than discounting the observation) means correct-with-hints
    yields a small positive update while wrong-with-hints yields a large negative
    one, which is right: failing *with* help is stronger evidence of not knowing
    than failing without it.

    CLAUDE.md §7 is explicit that `observed = correct * (1 - 0.25 * hint_level)` is
    the wrong form - it goes negative past hint 4, and clamping it to zero throws
    away signal by making a heavily-hinted correct answer identical to a wrong one.
    Do not "simplify" this back into that.
    """
    h = min(hint_level, HINT_MAX)
    d_eff = difficulty - HINT_DIFFICULTY_SLOPE * h
    p = 1 / (1 + math.exp(-(theta - d_eff)))
    k = max(K_MIN, K_START / (1 + K_DECAY * n_obs))
    return theta + k * (float(correct) - p)


def mastery(theta: float) -> float:
    """Theta (unbounded) -> mastery in (0, 1)."""
    return 1 / (1 + math.exp(-theta))


def decay_prereqs(theta_map: dict, prereqs: Iterable[str]) -> dict:
    """Backward propagation on a failed item. CLAUDE.md §7.

    This is what makes the graph do work instead of being decoration. Without it
    you have a mind map with numbers on it.

    Returns a new map; does not mutate the input.
    """
    out = dict(theta_map)
    for node_id in prereqs:
        if node_id in out:
            out[node_id] -= PREREQ_DECAY
    return out


def next_node(graph, mastery_map: dict) -> Optional[str]:
    """Lowest-mastery unmastered node whose prerequisites are all mastered.

    `graph` is anything exposing `.node_ids` and `.prereqs(node_id)` - see
    server/graph_store.py. Returns None when the chapter is complete.

    Relies on the prereq edges forming a DAG (build/validate.py enforces it); a
    cycle would make this loop forever by never producing a ready node.
    """
    ready = [
        n for n in graph.node_ids
        if all(mastery_map.get(p, 0.0) >= THRESHOLD for p in graph.prereqs(n))
    ]
    unmastered = [n for n in ready if mastery_map.get(n, 0.0) < THRESHOLD]
    if not unmastered:
        return None
    # Ties broken by id so selection is reproducible across runs and machines -
    # the eval reruns the same 60 dialogues and needs the same path.
    return min(unmastered, key=lambda n: (mastery_map.get(n, 0.0), n))


def backtrack_target(graph, node_id: str, mastery_map: dict) -> Optional[str]:
    """Lowest-mastery prerequisite of `node_id`. CLAUDE.md §7: two consecutive
    failures on the current node backtracks here."""
    prereqs = list(graph.prereqs(node_id))
    if not prereqs:
        return None
    return min(prereqs, key=lambda n: (mastery_map.get(n, 0.0), n))


def is_mastered(mastery_value: float) -> bool:
    return mastery_value >= THRESHOLD
