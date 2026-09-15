# §9.5 — the diagnosis read-through

*Run on day 12 (2026-09-15), the day a key first made it possible. Call 1:
`qwen/qwen3.8-27b` via Groq. 30 answered turns over the scored bank, three
student policies. Raw: [`eval/results/diagnosis_readthrough.json`](../../eval/results/diagnosis_readthrough.json);
instrument: `eval/diagnosis_readthrough.py`.*

CLAUDE.md §9.5 asks for this and says why: it is *"the only way to find out
whether the tutor's model of the student bears any relationship to reality, and
no metric above would catch that failure."* That turns out to be exactly right,
and not in the way we expected.

---

## The headline

**The diagnosis is fluent, specific about the item, and does not track the
student.**

`student_state` against what the student actually knew — 30 answered turns, the
session-opening turn excluded because no response exists yet there and
`on_track` is correct on it:

| true knowledge | `on_track` | `stuck` | `correct` | `guessing` | `confused_prereq` |
|---|---|---|---|---|---|
| **zero** — knows nothing, guesses over the lit set | 5 | 6 | 1 | **0** | **0** |
| **partial** — knows the region, not the target | 6 | 3 | 0 | **0** | **0** |
| **adversarial** — same knowledge, plays the narrowing | 3 | 5 | 0 | 1 | **0** |

Three different true states produce the same distribution. A student who knows
**nothing** is called `on_track` five times in twelve.

**Two of the five available states are dead.** `guessing` was used once in
thirty turns — on an *adversarial* student, not on either of the zero-knowledge
ones it exactly describes. `confused_prereq` was never used at all, on a graph
whose entire premise is prerequisite structure, and against students who were
failing items whose prerequisites they had never seen.

This is not a subtle miscalibration. The `zero` policy is the easiest student in
the world to diagnose: it picks uniformly at random from whatever is lit. Thirty
turns of that produced one `guessing`.

## What the prose looks like while this is happening

The failure is invisible in the writing, which is the part worth dwelling on. A
sample, verbatim:

> *"Two turns in, no correct node click yet on a definition that names 'every
> packet gets equal treatment' and 'no host may ask for a guarantee' — language
> that points squarely at best_effort vs. reservation-based service models.
> Likely candidate confusion is between best_effort and reservation_based."*

That is a good paragraph. It reads the item accurately, quotes the definition,
and names a plausible confusion. It is also **a claim about the item, not about
the student** — and the student in question was drawing uniformly at random, so
there was no confusion between `best_effort` and `reservation_based` to find.

The pattern across all thirty: the model reliably describes **what the item is
about and which nodes are confusable with each other**, then presents that as an
account of the person. Both halves are plausible. Only the first is grounded.

A reviewer reading these fields would not catch this. We did not catch it by
reading them either — it took tabulating the state against a ground truth the
model could not see.

## One checkable factual error

> *"At hint level 0 they were likely scanning the whole **forty-node** map blind."*

The graph has **52** nodes, and `llm.graph_digest` hands Call 1 all 52 of them —
verified, 52 digest lines against 52 store nodes. The model was shown the number
and stated a different one, inside the field a human reads as the authoritative
account of the turn.

This matters more than a rounding slip, because §9.5's whole function is that a
human reads these and believes them. A diagnosis that is confidently wrong about
something checkable is a warning about the parts that are not checkable.

## What we got wrong in our own instrument

Three faults in the harness, all found by the first real run, and one of them
matters for how the above is read:

- **The driver sent a node id as free text.** `Student.choose` returns an id; on
  the two turns where the server expected prose, the driver wrapped that id and
  sent it. The tutor **caught this** — *"the student keeps offering text instead
  of clicking"* — and we filed it as a hallucination until we checked the driver
  and found it was an accurate report of our bug. 2 of 40 turns, so it does not
  explain the table, but it is the one diagnosis in the set that was *more*
  grounded than its readers were.
- **Printing the sheet killed a completed run.** Windows stdout is cp1252, the
  sheet carries `§` and em-dashes, and the crash landed after twenty minutes of
  paced calls. The thirty fields were recovered from `logs/turns.jsonl` by
  filtering on the `origin` stamp added earlier the same day — which is the only
  reason this document exists and not a second day of token budget.
- **The turn log could not name the model that wrote the diagnoses.** `code`
  names the build and `origin` names the driver, and neither implies the model,
  because `CALL1_MODEL` is config. Fixed; records now carry it.

## What this does and does not license

**It does not invalidate the tutor.** Nothing in §2's claims runs through
`student_state`:

- the fidelity ceiling is a property of Call 2's argument list
- narrowing is computed by `mastery.py` and the ladder, deterministically
- `correct` is a boolean Call 1 reads off `items.json`, not a judgement

**It does invalidate one thing we would otherwise have been tempted to claim.**
A diagnosis field that reads this well is exactly the artefact a demo puts on a
slide to show the tutor "understands the student". On this evidence it does not,
and we will not show it that way.

**It also puts a number on a design decision that was made for other reasons.**
§1.3 and §1.5 keep mastery in Python and out of the model's hands, on the
grounds that LLM-scored progress silently corrupts the adaptive path. This is
the first direct evidence for that rule from inside this system rather than from
the literature: had `student_state` been wired to mastery, a student who knew
nothing would have been advanced on the strength of `on_track` five times in
twelve.

## Limits of this read

- **n=30, one model, one chapter.** §9.5 asks for thirty; thirty is what this is.
  The zero/partial/adversarial cells are 12/9/9 and no claim here needs a
  significance test, because the finding is a *near-absence* (0 and 1 uses of two
  states) rather than a difference of rates.
- **`qwen/qwen3.8-27b`, not the model the demo will ship.** `gpt-oss-120b` was
  chosen for Call 1 on diagnosis quality, and its 200,000-token daily budget was
  exhausted before this run. **This read should be repeated on the shipping
  model** — it is one command and one day's budget, and it is on the week-3 list.
- **Scripted students, not people.** The tutor is modelling a policy. A policy is
  what makes ground truth possible at all, and it is also not a learner: a real
  student's confusion has structure that `random.choice` does not. Both halves
  are true and the second is the limit.
