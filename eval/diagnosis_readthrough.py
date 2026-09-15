"""CLAUDE.md §9.5 — the diagnosis read-through.

    python -m eval.diagnosis_readthrough                 # 30 fields, real model
    python -m eval.diagnosis_readthrough --n 10          # a cheaper sample
    python -m eval.diagnosis_readthrough --json out.json

§9.5 asks a human to hand-read 30 logged `diagnosis` fields, and says plainly
that it is the only way to find out whether the tutor's model of the student
bears any relationship to reality — no metric above it would catch that failure.

This module does not replace that read. It does the part a human cannot do
cheaply: produce the thirty fields against a real model, with the context needed
to judge each one on the page next to it, and compute the two things that ARE
checkable so the human read starts from evidence rather than from scratch.

WHY THE STUDENTS ARE SCRIPTED, AND WHAT THAT COSTS
--------------------------------------------------
A scripted student is not a person, and a tutor's model of a policy is not a
model of a learner. That limitation is real and is reported rather than argued
away — `docs/writeup/limitations.md` already lists a human pilot under *what
would change our minds*.

What a scripted student buys is the thing a human read cannot get at all:
**ground truth**. Reading thirty diagnoses of a real student, nobody can say
whether "confused about the prerequisite" was true — the student's actual
knowledge is not observable. Here it is, exactly, by construction:

    zero        guesses uniformly over whatever the interface lit. Knows nothing.
    partial     knows the REGION (the node, its prereqs, dependents, siblings)
                but not the target.
    adversarial same knowledge, plays to the narrowing.

The tutor never sees the label. It sees clicks. So "did the tutor call a
zero-knowledge student `guessing`?" is a fair question with a checkable answer.

DIFFERENT DRIVING LOOP FROM §9.1, ON PURPOSE
--------------------------------------------
`adversarial.run_dialogue` answers WRONG every turn regardless of what the
student would have picked, because §9.1 needs the hint ladder to keep climbing
so one dialogue yields the whole curve. Reusing it here would be a measurement
error: a tutor shown nothing but failures has no reason to ever say anything but
`stuck`, and the read-through would conclude the diagnosis is degenerate when
what was degenerate was the input. Here the student answers honestly, so
`correct`, `on_track` and `guessing` are all reachable.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

from server import origin
from server import turn as turn_mod
from server.config import CONFIG
from server.graph_store import GraphStore
from server.schemas import EdgeRef, StudentResponse
from server.state import Store
from eval import provenance
from eval.adversarial import Student, scored_bank

#: The conditions swept, in the order they are reported. Each is a different
#: TRUE knowledge state, which is what makes the contingency table meaningful.
CONDITIONS = ("zero", "partial", "adversarial")


@dataclass
class Field:
    """One logged diagnosis, with everything needed to judge it."""

    n: int = 0
    item_id: str = ""
    item_type: str = ""
    node_label: str = ""
    item_prompt: str = ""
    turn: int = 0
    hint_level: int = 0
    lit: int = 0
    #: ground truth
    condition: str = ""
    student_pick: str = ""
    pick_correct: bool = False
    #: what the tutor said
    tutor_correct: Optional[bool] = None
    tutor_state: str = ""
    tutor_action: str = ""
    focus_nodes: list = field(default_factory=list)
    diagnosis: str = ""


def _response(store: GraphStore, item, expects: str, pick: str) -> StudentResponse:
    """The student's actual choice, as the wire type the server asked for."""
    if expects == "mcq":
        return StudentResponse(type="mcq", choice_id=pick)
    if expects == "edge_click":
        src, _, dst = pick.partition("->")
        return StudentResponse(type="edge_click", edge=EdgeRef(**{"from": src, "to": dst}))
    if expects == "node_click":
        return StudentResponse(type="node_click", node_id=pick)
    return StudentResponse(type="text", text=pick)


def collect(n: int, seed: int, max_turns: int, pace_s: float = 0.0,
            checkpoint=None) -> list:
    """Drive dialogues until `n` diagnoses exist, round-robin over conditions.

    PACING IS NOT POLITENESS. One turn costs ~4,250 tokens (Call 1 ~2,750 plus
    Call 2) against a free tier of 8,000 per minute, so an unpaced run requests
    about twice as fast as the budget refills. It does not degrade gracefully:
    the debt accumulates, `_retry_after` waits grow to the 60s ceiling, and the
    run spends its whole wall clock in the limiter. Sleeping BEFORE the request
    costs the same time and arrives with a budget.

    `checkpoint` is called with the fields so far after every one. A 20-minute
    run that writes only at the end loses everything to a kill - which is how
    the first attempt at this ended, with 1,451 bytes of log and no fields.
    """
    store = GraphStore.load()
    bank = scored_bank(store, "scored")
    fields: list = []
    dialogue = 0
    last_call = 0.0

    def pace():
        nonlocal last_call
        if pace_s:
            wait = pace_s - (time.monotonic() - last_call)
            if wait > 0:
                time.sleep(wait)
        last_call = time.monotonic()

    while len(fields) < n:
        condition = CONDITIONS[dialogue % len(CONDITIONS)]
        item = bank[dialogue % len(bank)]
        student = Student(condition=condition, rng=random.Random(seed + dialogue))
        dialogue += 1

        # Declared per condition so the read-through's own turns are separable
        # in logs/turns.jsonl from a person's and from §9.1's sweep. See
        # server/origin.py: `mock` stops separating these the moment a key lands,
        # which is the moment this module can run at all.
        with origin.declare(f"eval:diagnosis_readthrough:{condition}"):
            db = Store(db_path=":memory:")
            state = db.create(store.initial_theta_map(),
                              graph_fingerprint=store.fingerprint)
            state.start_item(item.node_id, item.id)
            db.save(state)

            pace()
            phase1 = turn_mod.begin_turn(store, db, state, None)
            turn_mod.complete_turn(store, db, phase1)

            for t in range(max_turns):
                if phase1.item is None or phase1.session_complete:
                    break
                current = phase1.item
                lit = phase1.graph_state.focus_nodes
                options = [o.id for o in phase1.mcq_options]

                pick = student.choose(store, current, lit, options)
                response = _response(store, current, phase1.expects, pick)

                pace()
                phase1 = turn_mod.begin_turn(store, db, state, response)
                turn_mod.complete_turn(store, db, phase1)

                d = phase1.decision
                fields.append(Field(
                    n=len(fields) + 1,
                    item_id=current.id,
                    item_type=current.type,
                    node_label=store.node(current.node_id).label,
                    item_prompt=current.prompt,
                    turn=t + 1,
                    hint_level=phase1.hint_level,
                    lit=len(lit) or len(store.node_ids),
                    condition=condition,
                    student_pick=pick,
                    pick_correct=pick == current.answer,
                    tutor_correct=d.correct,
                    tutor_state=d.student_state,
                    tutor_action=d.requested_action,
                    focus_nodes=list(d.focus_nodes),
                    diagnosis=d.diagnosis,
                ))
                if checkpoint is not None:
                    checkpoint(fields)
                print(f"  [{len(fields)}/{n}] {condition:<12} {current.id} "
                      f"turn {t + 1} -> {d.student_state}/{d.requested_action}",
                      file=sys.stderr, flush=True)
                if len(fields) >= n:
                    break
            db.close()

    return fields


def score(fields: list) -> dict:
    """The two things that are checkable without a human.

    NEITHER IS §9.5. §9.5 is the read. These bound it: if `correct` disagrees
    with what the student actually clicked, nothing below it can be trusted,
    and if `student_state` is constant across three different true knowledge
    states then the diagnosis is a label rather than a judgement.
    """
    agree = sum(1 for f in fields if f.tutor_correct == f.pick_correct)
    by_condition: dict = defaultdict(Counter)
    for f in fields:
        by_condition[f.condition][f.tutor_state] += 1

    states = sorted({f.tutor_state for f in fields})
    actions = Counter(f.tutor_action for f in fields)

    #: Does the diagnosis move with the truth at all? A single state covering
    #: every condition is the degenerate case worth catching.
    distinct_states = len(states)

    return {
        "fields": len(fields),
        # WHICH MODEL SAID THIS. §9.5 is a judgement about a specific model's
        # account of a student, and the fields outlive the run that produced
        # them. `provenance` already carries the build; the model is the other
        # half and is not derivable from it, because CALL1_MODEL is config.
        "call1_model": CONFIG.call1.model,
        "call2_model": CONFIG.call2.model,
        "provider": CONFIG.llm_provider,
        "correct_agreement": {
            "agree": agree,
            "of": len(fields),
            "rate": round(agree / len(fields), 4) if fields else None,
        },
        "state_by_true_condition": {c: dict(v) for c, v in sorted(by_condition.items())},
        "distinct_states": distinct_states,
        "states_seen": states,
        "actions": dict(actions.most_common()),
        "provenance": provenance.over(
            population=[f.item_id for f in fields],
            sampled=[f.item_id for f in fields],
            observations=len(fields),
            unit="diagnoses",
            expect_full=False,
        ).as_dict(),
    }


def render_sheet(fields: list) -> str:
    """The thing a human actually reads. One field per block, context first."""
    L = ["CLAUDE.md §9.5 - diagnosis read-through",
         f"Call 1: {CONFIG.call1.model} via {CONFIG.llm_provider}",
         "",
         "Read the diagnosis against the three lines above it. The question is",
         "not 'is it well written' but 'does it describe THIS student'.",
         ""]
    for f in fields:
        L.append(f"--- {f.n:>2} ----------------------------------------------------------")
        L.append(f"  item      {f.item_id} ({f.item_type}) on '{f.node_label}', turn {f.turn}, hint {f.hint_level}, {f.lit} lit")
        L.append(f"  TRUTH     student knows: {f.condition:<12} clicked {f.student_pick!r} -> {'RIGHT' if f.pick_correct else 'wrong'}")
        L.append(f"  tutor     correct={f.tutor_correct}  state={f.tutor_state}  action={f.tutor_action}")
        L.append(f"  focus     {f.focus_nodes}")
        L.append(f"  DIAGNOSIS {f.diagnosis}")
        L.append("")
    return "\n".join(L)


def render(result: dict) -> str:
    L = ["", "=" * 62, "WHAT IS CHECKABLE WITHOUT A HUMAN (this is not §9.5, it bounds it)", "=" * 62, ""]
    L.append(f"Call 1 (wrote every diagnosis below): {result['call1_model']} "
             f"via {result['provider']}")
    L.append("")
    ca = result["correct_agreement"]
    L.append(f"`correct` vs what the student actually clicked: {ca['agree']}/{ca['of']}"
             + (f" = {ca['rate']:.0%}" if ca["rate"] is not None else ""))
    if ca["rate"] is not None and ca["rate"] < 1.0:
        L.append("  ^ Call 1 SEES the answer. Anything below 100% is a scoring")
        L.append("    problem, and §7's mastery update is computed from this boolean.")
    L.append("")
    L.append("student_state against the student's TRUE knowledge state:")
    L.append("")
    conditions = list(result["state_by_true_condition"])
    states = result["states_seen"]
    L.append("    " + "true \\ said".ljust(14) + "".join(s.rjust(18) for s in states))
    for c in conditions:
        row = result["state_by_true_condition"][c]
        L.append("    " + c.ljust(14) + "".join(str(row.get(s, 0)).rjust(18) for s in states))
    L.append("")
    # ONLY A FINDING IF THE CONDITIONS WERE ACTUALLY SWEPT. At n=3 the
    # round-robin never leaves `zero`, and "one state across one condition" is
    # not degeneracy, it is a sample of one. Warning on it would be the same
    # error as `numbers-that-looked-fine.md`: a well-formed complaint about
    # nothing.
    if result["distinct_states"] <= 1 and len(conditions) > 1:
        L.append(f"  ONE STATE ACROSS {len(conditions)} TRUE CONDITIONS. The diagnosis is a")
        L.append("  constant, not a judgement - nothing downstream reads a real signal.")
    elif len(conditions) < len(CONDITIONS):
        L.append(f"  Only {len(conditions)} of {len(CONDITIONS)} conditions sampled "
                 f"({', '.join(conditions)}). Raise --n before reading the table")
        L.append("  as a claim about whether the diagnosis tracks the truth.")
    L.append(f"actions requested: {result['actions']}")
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=30,
                        help="diagnoses to collect (§9.5 asks for 30)")
    parser.add_argument("--seed", type=int, default=CONFIG.bootstrap_seed)
    parser.add_argument("--max-turns", type=int, default=3,
                        help="turns per dialogue before moving to a new item")
    parser.add_argument("--pace-s", type=float, default=32.0,
                        help="minimum seconds between turns. Default keeps one "
                             "~4,250-token turn inside an 8,000/min budget; 0 "
                             "disables it for a provider without one.")
    parser.add_argument("--json", type=str, default=None)
    parser.add_argument("--sheet", type=str, default=None,
                        help="write the human-readable sheet here")
    args = parser.parse_args()

    if CONFIG.mock_mode:
        print("MOCK_MODE is on. §9.5 reads the MODEL's account of the student;\n"
              "the mock's `diagnosis` is a formatted string from mock_tutor.py and\n"
              "reading thirty of them measures that template. Set MOCK_MODE=false.",
              file=sys.stderr)
        return 2

    def checkpoint(so_far):
        if args.json:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump({"result": score(so_far),
                           "fields": [asdict(f) for f in so_far]}, fh, indent=2)

    fields = collect(args.n, args.seed, args.max_turns, args.pace_s,
                     checkpoint if args.json else None)
    result = score(fields)
    sheet = render_sheet(fields)

    print(sheet)
    print(render(result))

    if args.sheet:
        with open(args.sheet, "w", encoding="utf-8") as fh:
            fh.write(sheet + "\n" + render(result) + "\n")
        print(f"\nsheet -> {args.sheet}")
    if args.json:
        payload = {"result": result, "fields": [asdict(f) for f in fields]}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"raw -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
