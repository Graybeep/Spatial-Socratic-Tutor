"""`student_state` must never reach a decision. CLAUDE.md §1.3, §1.5.

WHY THIS FILE EXISTS

§9.5 measured the tutor's `student_state` against a ground truth the model could
not see and found it uncorrelated: a student who knew nothing was called
`on_track` 5 times in 12, `guessing` was used once in 30 turns on the wrong
student, and `confused_prereq` never. See docs/writeup/diagnosis-readthrough.md.

The system survived that finding for one reason: nothing reads the field. That
was a design decision (§1.3 keeps mastery in Python; §1.5 lets the model emit a
boolean and nothing else) but it was NOT enforced anywhere - it was true because
nobody had wired it up yet, and a later "improvement" that branched on
`student_state` would have been a plausible-looking change that quietly made
every curriculum decision a function of a hallucinated label.

These tests make the isolation a property of the codebase instead of an accident
of its history. They are cheap, they need no key, and they fail loudly the first
time someone reaches for the field.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from server.config import ROOT
from server.schemas import Call1Decision

#: Modules that may MENTION the field: the schema defines it, the mock produces
#: it, turn.py constructs and logs it. Nothing may BRANCH on it.
DECISION_MODULES = ["turn.py", "mastery.py", "guards.py", "state.py", "main.py"]


def _module_ast(name: str) -> ast.Module:
    return ast.parse((ROOT / "server" / name).read_text(encoding="utf-8"))


def _reads_of(tree: ast.Module, field: str) -> list:
    """Every place `<something>.field` is READ (loaded), with line numbers.

    A Store is an assignment (`d.student_state = x`) and is fine; a Load is
    somebody using the value, which is what must not happen.
    """
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Attribute)
            and n.attr == field
            and isinstance(n.ctx, ast.Load)]


@pytest.mark.parametrize("module", DECISION_MODULES)
def test_no_decision_module_reads_student_state(module):
    """The field is logged evidence, not an input.

    §9.5 found it uncorrelated with the student. If this test fails, some
    decision is now a function of that label - check what it gates before
    deleting this assertion.
    """
    hits = _reads_of(_module_ast(module), "student_state")
    assert not hits, (
        f"server/{module} reads `.student_state` at line(s) {hits}. That field "
        f"does not track the student (docs/writeup/diagnosis-readthrough.md): "
        f"a student who knew nothing was called on_track 5/12. Nothing may "
        f"branch on it."
    )


def test_the_curriculum_transitions_are_not_the_models_to_make():
    """advance and backtrack are assigned by the server, from `graded` and the
    mastery map - not taken from `requested_action`.

    Measured over §9.5's 40 turns: the server overrode Call 1 on 11 of the 12
    turns where the curriculum actually moved. This test pins the mechanism that
    produced that number.
    """
    src = (ROOT / "server" / "turn.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Find every `action = "advance"` / `action = "backtrack"` assignment.
    assigned = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "action":
                    assigned.add(node.value.value)

    assert {"advance", "backtrack"} <= assigned, (
        "turn.py no longer assigns advance/backtrack itself. If these now come "
        "from the model's requested_action, curriculum movement has become a "
        "function of a field §9.5 showed does not track the student."
    )


def test_mastery_is_computed_without_any_model_field():
    """§1.3: the model may emit a boolean; Python computes the number.

    `mastery.py` must not import the decision schema at all - the cheapest
    possible statement of 'no model output reaches the score'.
    """
    src = (ROOT / "server" / "mastery.py").read_text(encoding="utf-8")
    for forbidden in ("Call1Decision", "student_state", "requested_action",
                      "diagnosis", "llm"):
        assert forbidden not in src, (
            f"server/mastery.py references {forbidden!r}. §1.3 and §1.5 keep the "
            f"number out of the model's hands; §9.5 is why that matters."
        )


def test_the_schema_still_offers_no_place_to_put_a_score():
    """Re-asserted here because it is the other half of the same guarantee: the
    model cannot report a mastery estimate even if something wanted to read one."""
    props = set(Call1Decision.model_json_schema()["properties"])
    assert "correct" in props
    assert not (props & {"score", "mastery", "confidence", "probability", "theta",
                         "ability", "estimate"})
