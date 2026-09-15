"""The Call 1 prompt must make the diagnosis capable of being wrong.

Measured on day 12 (docs/writeup/diagnosis-readthrough.md): the model answered
`stuck` to a scattered guesser and to a prerequisite confusion alike - two
unambiguously different students, one label - and `confused_prereq` never
appeared in 30 turns. `stuck` is never wrong about a failing student, so a prompt
that attaches no cost to it is a prompt that asks for nothing falsifiable.

These are prompt tests, not model tests. They cannot show the model complies;
only `eval/diagnostic_calibration.py` against a real model can do that. What they
pin is that the INSTRUCTION does not quietly disappear in a later edit - the
prompt is a file in `prompts/`, edited by hand, with nothing else watching it.

THE SCHEMA IS NOT AN OPTION HERE. CLAUDE.md §13.1 freezes the Call 1 output
schema after day 2, so this cannot be enforced by adding an `evidence` field. It
has to live in the instruction and be checked by measurement.
"""
from __future__ import annotations

import pytest

from server import llm

PROMPT = "call1_system.md"


@pytest.fixture(scope="module")
def prompt() -> str:
    return llm.prompt(PROMPT).lower()


def test_stuck_is_named_as_the_residual_and_given_a_cost(prompt):
    """A state that cannot be contradicted carries no information."""
    assert "residual" in prompt
    assert "never *wrong*" in prompt or "never wrong" in prompt, (
        "the prompt no longer says why `stuck` is the cheap answer"
    )


def test_the_two_discriminable_states_are_defined_by_click_LOCATION(prompt):
    """The measured failure was not miscalibration, it was that the prompt never
    told the model to look at WHERE the wrong clicks fell."""
    assert "upstream" in prompt, "confused_prereq is not tied to click location"
    assert "scattered" in prompt, "guessing is not tied to click location"


def test_confused_prereq_must_name_the_prerequisite(prompt):
    assert "name the prerequisite" in prompt, (
        "`confused_prereq` no longer has to name anything, so it cannot be wrong"
    )


def test_the_diagnosis_must_carry_a_claim_that_could_be_wrong(prompt):
    assert "could turn out to be wrong" in prompt
    assert "would read identically for a different student" in prompt, (
        "the prompt no longer rules out a diagnosis that fits any student"
    )


def test_every_state_in_the_schema_is_still_documented(prompt):
    """A state the prompt stops describing is a state the model stops using."""
    from server.schemas import Call1Decision
    states = Call1Decision.model_json_schema()["properties"]["student_state"]["enum"]
    missing = [s for s in states if s not in prompt]
    assert not missing, f"states in the schema but not in the prompt: {missing}"


def test_the_prompt_still_forbids_a_score(prompt):
    """§1.3 - re-asserted here because this file edits the prompt that could.

    Checks for the PROHIBITION, not for the absence of the words. The first
    version of this test banned "percentage" outright and failed on the sentence
    forbidding percentages, which is a test that cannot tell an instruction from
    its opposite.
    """
    assert "must not invent one" in prompt
    for forbidden_thing in ("a score", "a percentage", "a confidence",
                            "a mastery estimate"):
        assert forbidden_thing in prompt, (
            f"the prompt no longer names {forbidden_thing!r} as forbidden"
        )
