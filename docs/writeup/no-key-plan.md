# The report that stands without a key

*Written on day 6, deliberately, while there is still time to act on it. This is
the version of the writeup that needs no API key, no live model and no chapter
we do not already have. If a key arrives, two sections are **added**. Nothing
here is rewritten.*

---

## The decision, with a date on it

> **If no API key is in hand by 2026-09-22 (day 19), `MOCK_MODE` ships.**

Day 19 is already the cut date for §9.3. The two are one decision, not two: both
are blocked on the same missing thing, and discovering on day 24 that we are
writing the no-key version anyway is the expensive way to find out.

`MOCK_MODE=true` is already the default and `main` already runs under it, so
this is not a fallback to be built. It is a decision to stop waiting.

### What ships either way

- the two-call pipeline, with the retrieval gate enforced in both directions
- the frozen 52-node graph, its layout, and the narrowing ladder
- retrieval over the real chapter — TF-IDF, no model call, working today
- §9.1 effective leakage, §9.4 the distractor screen
- every finding in `eval-harness-failures.md`
- the fidelity-ceiling contract
- a demo that runs from a clean clone with no key and no network

### What is lost if the key never lands

| | why |
|---|---|
| §9.3 graph precision/recall | needs an extractor run, which needs a model |
| §9.5 diagnosis read-through | needs 30 real Call 1 `diagnosis` fields |
| "the utterances are model-generated" | they are templates; say so plainly |
| parametric-reconstruction rate | a mock has no weights to reconstruct from |

None of the four is a contribution. Three are measurements of a model we do not
have, and the fourth is a property of the demo rather than of the design.

---

## The four claims that need no model

Every one of these is a finding about **system design**, established by
construction or by deterministic measurement. A live model would illustrate
them. It would not evidence them.

### 1. The answer has more representations than any whitelist can name

`ItemPublic` excluded `answer` and shipped `node_id`. For a `node_click` item
those are the same referent. §5 excluded the answer string and admitted the
label. Same defect, one layer in.

    node id  →  node label  →  position in a lit set  →  size of a lit set

A field whitelist names the first. The information travels in all four. The fix
is a **fidelity ceiling per action**, not a field list — and that is a claim
about contracts between components, which is true or false independently of what
generates the text.

### 2. An evaluation can be healthy in every observable way and measure nothing

Five instances in six days: one-item sampling, an unanswerable half of the
population, a threshold calibrated against no distribution, a degenerate item
bank, and an item template that gave its own answer away. All five passed a full
test suite. All five produced numbers of the right type in the right range.

The generalisation — *every eval output carries the size and identity of what it
sampled, and coverage is asserted, not assumed* — is one line per eval and would
have caught two of the five on day one.

### 3. "Helps by showing less" can be a property of the wiring rather than a claim about behaviour

On `ask`, `hint_visual`, `hint_verbal` and `backtrack`, Call 2 receives an
action, a hint level and a **count**. It has no representation of the answer
available. It cannot name the answer while hinting because it was never told it.

This is the contribution §12 says to protect, and it is architectural. The
leakage numbers that follow describe a system that *cannot* leak in that channel,
rather than one observed not to.

### 4. Narrowing performs reductions that cannot be expressed in one utterance

§9.2's matched-elimination comparison is **cut**, and stays cut. Under the
fidelity ceiling the coarse-granularity claim is enforced by the architecture:
you cannot name 38 excluded nodes in one turn, and the visual channel does it in
one frame. A comparison is not needed to support a claim the contract guarantees.

---

## The numbers we will actually have

All deterministic. All regenerable from a clean clone with no key.

| | source | status |
|---|---|---|
| §9.1 effective leakage, split by item type | `eval/adversarial.py` | measured, n=202, full coverage |
| §9.4 distractor screen | `eval/distractor_screen.py` | measured, 101 click + 159 mcq |
| edge-item candidate counts | `build/validate.py` | measured, 49/49 flagged |
| retrieval gate separation | `server/config.py` | measured, 52 in / 12 out |
| item-bank degeneracy | `build/validate.py` | measured, 159/159 mcq |

The honest framing for §9.1 is the one the split forces: **`node_click`
zero-knowledge leakage at the terminal rung, by arm** — 17% product, 6%
visual-only, 4% verbal-only. Those move with the narrowing, which is what §9.1
was built to measure.

---

## The two sections a key would add

Written as *additions*, so nothing above depends on them.

**§9.3 — extraction precision/recall.** `build/extract_edges.py` runs, its output
is scored against `gold_graph.json`, and the number is reported *before* human
correction. The precedence filter's recall ceiling is already measured at 59% on
the real chapter, so the section has a skeleton and is missing one run.

**§9.5 — diagnosis read-through.** Thirty logged `diagnosis` fields, hand-read.
No metric above would catch a tutor whose model of the student is unrelated to
reality, which is exactly why §9.5 is non-optional *if* it can run at all.

A third, smaller addition: the **parametric reconstruction rate** — Layer 1 hits
on `ask`/`hint_*`, which under the fidelity ceiling can only be the model
producing the answer from its own weights given a count. It is 0% against the
mock, and that figure is a property of the fixture.

---

## What this costs if the key arrives on day 20

Nothing. The two sections slot in, the mock-generated caveat comes out of the
limitations section, and every number above stands unchanged because none of
them was ever measuring the model.

That asymmetry is the whole reason to write this version first.
