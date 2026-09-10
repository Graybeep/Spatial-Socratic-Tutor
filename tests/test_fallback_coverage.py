"""Every action that reaches Call 2 has a canned fallback — CLAUDE.md §5.

§5: "Required: six canned fallback utterances, one per action, for Call 2
timeout after the graph has already reacted."

Seven things reach `_call2`, not six. The six in the `Action` literal, plus
`resolved_with_support`, which is not an Action but is passed as one on a §6
layer 3 forced reveal. That seventh had no file, so:

    _call2(state, "resolved_with_support", ...)
      -> llm.call2 raises LLMError (timeout)
      -> except: fallback_utterance("resolved_with_support")
      -> FileNotFoundError

out of the one handler whose entire job is to not fail, on the turn the student
is most frustrated. Unreachable under MOCK_MODE, because `mock_call2` never
raises; unreachable without a key, because `llm.call2` is never called. It would
have fired first on the day the key landed.

The lesson is the one this repo keeps relearning: a set enumerated in prose ("the
six actions") drifts from the set the code actually produces, and only a test
that asks the CODE for its members notices.
"""
from __future__ import annotations

import pytest

from server import mock_tutor
from server.config import CONFIG
from server.turn import CALL2_FIDELITY


def test_every_action_call2_can_receive_has_a_fallback():
    """Enumerated from CALL2_FIDELITY, which is the set turn.py actually passes
    to _call2 — not from a list in a docstring."""
    missing = []
    for action in CALL2_FIDELITY:
        path = CONFIG.prompts_dir / f"fallback_{action}.txt"
        if not path.exists():
            missing.append(action)
    assert not missing, f"no canned fallback for {missing}; §5 requires one per action"


@pytest.mark.parametrize("action", sorted(CALL2_FIDELITY))
def test_each_fallback_is_non_empty_and_sayable(action):
    text = mock_tutor.fallback_utterance(action)
    assert text.strip(), f"{action}'s fallback is blank"
    assert len(text) > 20, f"{action}'s fallback is too short to be an utterance"


def test_the_reveal_fallback_exists_because_it_is_the_one_that_would_have_crashed():
    """Pinned by name. A future tidy-up that folds resolved_with_support back
    into the Action literal must not take its file with it."""
    text = mock_tutor.fallback_utterance("resolved_with_support")
    assert text.strip()


def test_an_unknown_action_degrades_instead_of_raising(caplog):
    """The general form. The fallback handler must never be the thing that
    fails — it is what runs when something else already has."""
    text = mock_tutor.fallback_utterance("an_action_nobody_has_written_yet")
    assert text == mock_tutor.fallback_utterance(CONFIG.fallback_default_action)


def test_the_degraded_choice_is_config_not_a_literal():
    """§13.1. And it must point at a file that exists, or the degradation path
    degrades into the same crash."""
    assert (CONFIG.prompts_dir / f"fallback_{CONFIG.fallback_default_action}.txt").exists()


def test_no_fallback_names_a_node_on_the_graph(store):
    """A canned line is shipped when guard layer 1 has already fired, so it is
    the last thing standing between a leak and the student. None of them may
    carry an identity."""
    labels = {n.label.casefold() for n in store.graph.nodes}
    for action in CALL2_FIDELITY:
        text = mock_tutor.fallback_utterance(action).casefold()
        named = sorted(l for l in labels if l in text)
        assert not named, f"fallback_{action} names {named}"
