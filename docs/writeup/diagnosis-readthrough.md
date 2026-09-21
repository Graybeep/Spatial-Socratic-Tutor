# §9.5 — the diagnosis read-through

*Two dated readings of the same measurement. **Day 18 (2026-09-21)** is the
live one: Call 1 `openai/gpt-oss-120b`, build `18d220d`, raw in
[`diagnosis_readthrough.json`](../../eval/results/diagnosis_readthrough.json).
**Day 12 (2026-09-15)** is kept below because it is the reason the re-run
happened: Call 1 `qwen/qwen3.8-27b`, raw in
[`diagnosis_readthrough_day12_invalidated.json`](../../eval/results/diagnosis_readthrough_day12_invalidated.json).
Instrument for both: `eval/diagnosis_readthrough.py`.*

> **INVALIDATED 2026-09-16 (day 13), RE-RUN 2026-09-21 (day 18) — read this before anything below.** Every
> number in this document was produced by a Call 1 that **could not see the
> dialogue.** `server/llm.py` formatted history with `for who, text in history`
> over `{"role", "text"}` dicts, which yields the keys, so every entry under
> RECENT TURNS reached the model as the literal line `role: text` — in the live
> tutor, in this read-through, and in `diagnostic_calibration.py`, which builds
> its histories in the same shape. Fixed in `1cfc74a`, pinned by
> `tests/test_history_reaches_the_model.py`.
>
> So "the diagnosis does not track the student" is not a finding about the model.
> It is what a model shown no clicks would say, and the one calibration case it
> got right was the one with no history to read. The **architecture** half —
> the judgement fields are inert, enforced by test — does not depend on the
> model's input and stands. Everything about diagnosis *quality* is withdrawn
> until §9.5 is re-run on the fixed build. Found on the first field of that
> re-run, which said the student's inputs "were text".

CLAUDE.md §9.5 asks for this and says why: it is *"the only way to find out
whether the tutor's model of the student bears any relationship to reality, and
no metric above would catch that failure."* That turns out to be exactly right,
and not in the way we expected.

---

## The day-18 re-run, on the fixed build

*Run 2026-09-21 (day 18). Call 1: `openai/gpt-oss-120b` via Groq, build
`18d220d`. 30 answered turns, three student policies, 10 distinct items,
coverage 1.0. Raw: [`eval/results/diagnosis_readthrough.json`](../../eval/results/diagnosis_readthrough.json);
sheet: [`readthrough-sheet.md`](readthrough-sheet.md).*

> **Scope.** Everything in this section is about **`openai/gpt-oss-120b` running
> the shipped prompt**. The model variable is not isolated and is closed as a
> known gap (report.md §5.6). Every figure below is **directional**: n=12/9/9 on
> the policy table, n=2 per cell on the A/B.

**The day-12 finding reverses.** Same instrument, same three policies, same
ground truth, on a build where the model can see what the student clicked — and,
as it turns out, on a different Call 1 prompt. Which of those two did the work is
answered further down, and it is not the one this file originally said:

| true knowledge | n | `guessing` | `confused_prereq` | `correct` | `on_track` | `stuck` |
|---|---|---|---|---|---|---|
| **zero** — knows nothing | **n=12** | **12** | 0 | 0 | 0 | 0 |
| **partial** — knows the region | **n=9** | 3 | 0 | 4 | 2 | 0 |
| **adversarial** — plays the narrowing | **n=9** | 2 | **4** | 2 | 1 | 0 |

`correct` agreed with the deterministic grade on **30 of 30**.

Set against the table below, which is the same measurement through the
`role: text` bug:

| | day 12 (blind) | day 18 (fixed) |
|---|---|---|
| `zero` → `guessing` | 0 of 12 | **12 of 12** |
| `zero` → `on_track` | 5 of 12 | 0 |
| `confused_prereq` ever used | never, 0 of 30 | 4 |
| server overrode Call 1 where the curriculum moved | 11 of 12 | 6 of 13 |

The prose changed with it. Day 12's diagnoses were specific about the *item* and
silent about the person; day 18's name the clicks:

> *"Student clicked DCTCP and Expected Rate, both in the congestion control
> region, showing no movement toward Soft State or its prerequisites."*

> *"Clicks are on Queuing Delay, Resource Allocation, and Bottleneck Router,
> which are in disparate parts of the map, showing no coherent prerequisite
> focus, suggesting the student is guessing."*

**This run independently reproduced day 13's abandoned partial.** Run 3 on day 13
died to an OS memory kill at field 15, having recorded `zero` → `guessing` ×6 and
`correct` agreeing 15/15. Day 18 hit exactly those numbers at its own field 15
before continuing to 30. That is corroboration across two runs four days apart,
not one lucky sample.

### Two things the re-run does not fix

- **`stuck` was used zero times in thirty.** Flagged first as an instrument
  hypothesis (`--max-turns 3` gives no student time to be stuck), and then
  **partly answered by the day-18 A/B below**: on a constructed case where
  `stuck` is the only defensible answer, the current prompt still does not say
  it. So at least some of this zero is the prompt refusing a state it was told
  to distrust, not the turn budget denying it the chance.
- **`partial` → `guessing` on 3 of 9.** A student who knows the region is not
  guessing. This is the one cell that still looks like real miscalibration.

### What caused it — the prompt, and not what we first said

Day 13 found the `role: text` history bug and this file credited the reversal to
fixing it. That attribution does not survive report.md §5.6's controls,
which holds the model fixed and varies prompt against history across run 1, arm B
and arm A — **without using day 12 at all**, since day 12 is withdrawn for cause
(unreproducible dirty build, model never logged).

`eval/diagnostic_calibration.py` was re-run on day 18 to isolate one of the
three. Same model, same fixed harness, Call 1 prompt swapped for the version
live on day 12 — which `516795d`'s timestamp shows it was, by an hour and three
quarters. Both arms ran all five cases at n=2; the instrument withholds the
comparison unless they do.

**The counter-test comes first, because the other rows flatter the current
prompt.** See *The cost of the fix* below for what it is and why it was built:

| | n | current prompt | pre-falsifiability prompt |
|---|---|---|---|
| **`stuck` when `stuck` is the only answer** | **n=2** | **0/2** | **2/2** |

Then the rest:

| | n | current prompt | pre-falsifiability prompt |
|---|---|---|---|
| scattered clicks → `guessing` | n=2 | 2/2 | **0/2** — said `stuck` |
| all clicks upstream → `confused_prereq` | n=2 | 2/2 | **0/2** — said `stuck` |
| separates the two students | n=4 contrasting | **yes** | **no** |
| `correct` boolean | n=6 | 6/6 | 6/6 |

**The old prompt reproduces the day-12 degeneracy on a fully fixed harness**, and
run 1 on day 13 shows the converse: the current prompt reaches for `guessing`
**on the broken harness**, 2 of 4 turns, where day 12's old prompt managed 1 in
30. Both directions agree. So the history fix is neither necessary nor sufficient
for the reversal and the model change is not isolated at all; the prompt is the
only variable shown to move **state selection**, and the history fix is what
moves **grounding** — whether the state is about the student at all.

### The day-12 calibration run is withdrawn too

*A sharper instrument, and a worse result* below is the day-12
`diagnostic_calibration.py` run, and it is **withdrawn on the same grounds as
the day-12 §9.5 run**: same period, same unreproducible dirty build, model never
logged. It is kept below as history and is not evidence for anything.

What replaces it is the day-18 A/B, measured on a named build and a named model,
and the two halves of the old result fare differently:

- its **`stuck`-to-everything** finding *is* reproduced — by the old prompt, on
  a fixed harness (arm B). The behaviour is real and belongs to that prompt. But
  the claim now rests on arm B, not on the withdrawn run.
- its **`correct` boolean wrong on 2 of 6** is **not** reproduced. Day 18 scores
  6/6 on both prompts. Treat that number as gone, not as superseded by a better
  one.

### The cost of the fix, found by a case built to look for it

The current prompt tells the model that `stuck` is the cheap answer and to be
suspicious of reaching for it. A new case tests the obvious failure mode of that
instruction: a history where `stuck` is the *only* defensible specific answer —
three wrong free-text replies and **no clicks at all**, so neither the scatter
`guessing` needs nor the upstream clustering `confused_prereq` needs exists.

| | current prompt | pre-falsifiability prompt |
|---|---|---|
| `stuck` when `stuck` is right | **0/2** — said `guessing` | 2/2 |

The current prompt cannot reach for `stuck` when nothing else fits. Overall it
still wins on specificity (8/10 against 6/10), and without this case that would
have been the whole story.

`n=2` per cell. This is a signal worth acting on before the demo, not a
measurement to quote.

---

## The day-12 headline — superseded, kept because it is the reason the re-run happened

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

These are analysed as a pattern in their own right in
**[instrument-failures.md](instrument-failures.md)** — the harness producing
confident verdicts about the tutor while itself broken, twice plausibly enough to
act on.

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

## A sharper instrument, and a worse result

§9.5 tabulates against a *policy* label, which is a soft ground truth: "this
student knows the region" does not say what the single right diagnosis of turn 3
was, so a defender can always claim the model saw something the tabulation did
not. `eval/diagnostic_calibration.py` removes that defence by constructing
histories where one answer is forced by the clicks themselves — a student whose
three clicks are scattered across unrelated regions is guessing; a student whose
three clicks are all in the prerequisite region is confused about the
prerequisite. The two node sets are disjoint, asserted by test.

On `qwen/qwen3.8-27b`, 2 items per case:

| case | n | admissible | specific | what it said |
|---|---|---|---|---|
| `scattered_clicks` | 2 | 2 | 0 | `stuck` ×2 |
| `all_clicks_are_prereqs` | 2 | 2 | 0 | `stuck` ×2 |
| `answered_correctly` | 2 | 0 | 0 | `on_track` ×1, `stuck` ×1 |
| `opening_turn` | 2 | 2 | **2** | `on_track` ×2 |

`admissible` is any defensible state and is deliberately generous — `stuck` is
never *wrong* about a failing student. `specific` is the state the evidence
actually supports. **The model scores full marks on admissibility and almost zero
on discrimination**, which is the signature of a diagnosis that is not reading
the history: two unambiguously different students, one distribution.

The one case it gets right is `opening_turn` — the case with **no history to
read**.

It also got the `correct` boolean wrong on **2 of 6** constructed histories,
while being shown the answer.

---

## The inertness claim, in three parts

These are three different statements and the difference between them matters.
Collapsing them produces either false alarm or false comfort.

### 1. The diagnosis is unreliable — **no longer supported as written**

> **Superseded by the day-18 re-run.** This part was the day-12 reading. On the
> fixed build `student_state` tracks the student (`zero` → `guessing` 12/12) and
> `correct` agreed with the deterministic grade 30 of 30, not "wrong a third of
> the time". The forced-answer half was re-run on day 18 as a prompt A/B: the
> `stuck`-to-everything behaviour reproduces **under the old prompt on a fully
> fixed harness**, so it is a property of that prompt rather than of the model;
> the `correct` boolean scores 6/6 on both prompts, so that half is withdrawn
> outright rather than reassigned.
>
> Parts 2 and 3 below do not depend on the diagnosis being unreliable and are
> unaffected. That is the point of stating them separately: the architecture was
> built so that this part could go either way without anything downstream moving.

The day-12 text, kept for the record: on two instruments, one using policy labels
and one using forced-answer constructed cases, `student_state` did not track the
student, and `correct` — a boolean the model is handed the answer for — was wrong
a third of the time on unambiguous input.

### 2. The architecture makes it inert

Every judgement field Call 1 emits is written, logged, and **read by nothing**:

| field | what consumes it | what is used instead |
|---|---|---|
| `student_state` | nothing | — |
| `correct` | nothing | `mock_tutor.grade()`, a string comparison against `items.json` |
| `focus_nodes` | nothing | `mock_tutor.lit_nodes(store, item, state.visual_narrow_level)` |

And the routing is not the model's either. Over §9.5's 40 turns, **the server
overrode Call 1 on 11 of the 12 turns where the curriculum actually moved**:

```
Call 1 asked for  ->  server did     n
     hint_visual  ->  advance        6   <-- OVERRIDDEN
     hint_visual  ->  backtrack      3   <-- OVERRIDDEN
             ask  ->  advance        1   <-- OVERRIDDEN
         advance  ->  backtrack      1   <-- OVERRIDDEN
```

`advance` is gated on the deterministic grade; `backtrack` on
`mastery_mod.backtrack_target` over the Python mastery map; the lit set on the
ladder and a server-owned counter. The narrowing — this project's actual
contribution (§12) — is computed, not chosen.

**This is not a claim that the model does not matter.** `requested_action`
survives wherever the curriculum does *not* move, which is most turns: it selects
`ask` vs `hint_visual` vs `hint_verbal` vs `explain`. A student is therefore
getting **the wrong flavour of help**, chosen on a reading of them that is
uncorrelated with who they are. That is a real defect with a real cost to the
demo. What it is not is a corrupted adaptive path.

### 3. The inertness is now enforced, not incidental

Part 2 was true on day 12 **by accident**. §1.3 and §1.5 say mastery stays in
Python, but nothing in the codebase stopped a later change from branching on
`student_state` — and such a change would have looked like an improvement, passed
every one of the 364 tests then green, and made every within-item decision a
function of a field we have now measured to be uncorrelated with the student.

`tests/test_student_state_is_inert.py` makes it a property. Eleven tests walk the
AST of the decision modules and fail on any *read* of the three fields, on
`mastery.py` referencing the model at all, and on `_build_graph_state` being
handed the model's `focus_nodes`.

They are mutation-tested, which is what earns this part its place as a separate
claim rather than a restatement of part 2. Planting the exact change the guard
exists to stop:

```python
action = decision.requested_action
if decision.student_state == 'guessing':
    action = 'backtrack'
```

fails with `server/turn.py reads .student_state at line(s) [548]`. Planting
`lit = decision.focus_nodes` fails
`test_the_narrowing_is_not_chosen_by_the_model`. A guard that has never been
shown to fail is not a guard.

---

## What this does and does not license

Part 2 above establishes that §2's claims do not run through any of this. Three
consequences that do not follow from it, and are worth stating separately.

**It invalidates one thing we would otherwise have been tempted to claim.** A
diagnosis field that reads this well is exactly the artefact a demo puts on a
slide to show the tutor "understands the student". On this evidence it does not,
and we will not show it that way.

**It puts a number on a design decision that was made for other reasons.** §1.3
and §1.5 keep mastery in Python and out of the model's hands, on the grounds that
LLM-scored progress silently corrupts the adaptive path. That rule was adopted
from the literature; this is the first direct evidence for it from inside this
system. Two numbers, and the second is the sharper one:

- had `student_state` been wired to routing, a student who knew nothing would
  have been advanced on the strength of `on_track` five times in twelve
- had `correct` been wired to mastery, **2 of 6** unambiguous observations would
  have moved θ in the wrong direction — and Call 1 *is shown the answer*, which
  is the strongest form of the input a scorer could get

**It leaves a real defect unfixed.** `requested_action` still selects the flavour
of help within an item, on a reading of the student that does not track them. The
architecture contains the damage; it does not repair it. The fix is the prompt —
a diagnosis that carries no cost for answering `stuck` to everything is a
diagnosis that cannot be wrong, and what we measured is exactly that. See
`prompts/call1_system.md`.

## Limits of this read

- **The prompt is about to change.** Everything above measures
  `prompts/call1_system.md` as it stood on day 12, which offers the model no cost
  for answering `stuck`. A re-measurement is queued behind the rewrite rather
  than run before it, because measuring a prompt you have already decided to
  replace buys a row and not an answer.
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
