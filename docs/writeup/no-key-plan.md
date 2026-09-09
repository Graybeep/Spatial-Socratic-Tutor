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
- §9.1 effective leakage over the 69-item scored bank, §9.4 the distractor screen
- every finding in [representation-blindness.md](representation-blindness.md)
  and [numbers-that-looked-fine.md](numbers-that-looked-fine.md)
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

Full section: **[representation-blindness.md](representation-blindness.md)**.
Three instances, one mechanism.

`ItemPublic` excluded `answer` and shipped `node_id`. For a `node_click` item
those are the same referent. §5 excluded the answer string and admitted the
label. Same defect, one layer in. And the fidelity ceiling permitted an edge
item's `to` endpoint as *strictly lower fidelity* than the answer — on a graph
where 32 of 49 anchors have exactly one prereq, so it **is** the answer.

    node id  →  node label  →  position in a lit set  →  size of a lit set

A field whitelist names the first. The information travels in all four, and the
third instance adds the sharper form: **fidelity is a property of the
representation *given the data*, so it has to be measured against the data
rather than argued from the schema.**

The fix is a **fidelity ceiling per action**, not a field list — a claim about
contracts between components, true or false independently of what generates the
text.

### 2. An evaluation can be healthy in every observable way and measure nothing

Full section: **[numbers-that-looked-fine.md](numbers-that-looked-fine.md)**.
Two instances sharing one property — valid output shape, and no test asserting
on the sampling underneath it or the score distribution it was aggregating —
plus one adjacent case of the same shape in a guard constant.

- **the sample was one item.** 360 probes over 1 of 101 items, reported as
  n=200. A rate over one item has the same shape as a rate over a hundred.
- **half the population could not register a result.** A node-id answer can
  never equal an edge's `"from->to"`, so 49 of 101 items scored exactly 0.000 on
  every run, diluting every pooled rate.
- *adjacent:* `RETRIEVAL_SCORE_FLOOR` at 0.35, set before any corpus existed,
  refused 100% of in-domain queries while the ranking underneath was correct.

The generalisation has two lines, and both are asserted in code rather than
recommended:

1. *every eval output carries the size and identity of what it sampled, and
   coverage is asserted, not assumed* (`eval/provenance.py`) — would have caught
   the first on day one.
2. *every stratum of the population must be able to register a result*
   (`check_strata_answerable`, run by `measure()` before it reports) — catches
   the second, which provenance structurally cannot, because provenance records
   what was sampled and this was a failure of what could be scored.

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
| §9.1 effective leakage, split by item type | `eval/adversarial.py` | measured, **69 items**, n=138, coverage 1.0 |
| §9.4 distractor screen | `eval/distractor_screen.py` | measured, 101 click + 159 mcq |
| edge-item candidate counts | `build/validate.py` | measured, 32 determined + 17 coin-flip |
| retrieval gate separation | `server/config.py` | measured, 52 in / 12 out |
| item-bank degeneracy | `build/validate.py` | measured, 159/159 mcq |

### The population is 69, not 101

Every §9.1 number generalises to the **scored** bank: 52 `node_click` + 17
`edge_click`. The other 32 edge items are `scorable: false` — their anchor has
exactly one prereq, so the guess rate is 1.0 and §7's logistic reaches p = 1
only as `d_eff → -∞`; there is no difficulty value that represents "free". They
are excluded from mastery, by the same mechanism and with the same reversibility
as the MCQ demotion, and `build/validate.py` **errors** if one is ever scored
again.

Quote 69 and its interval. Not 101, and not the 260-item bank.

### §9.1's headline

`node_click`, zero-knowledge, terminal rung (attempt 1, n=104 probes over 52
items), with cluster-bootstrap 95% intervals over items:

| arm | rate | 95% CI |
|---|---|---|
| product configuration | **12.5%** | [6.7, 19.2] |
| isolated visual channel | 3.8% | [1.0, 7.7] |
| verbal channel only | 1.0% | [0.0, 2.9] |
| no hints at all (baseline) | 3.8% | [1.0, 7.7] |

**Report this straight, including the part that does not flatter the thesis.**
Marginal over the no-hint baseline, `node_click` only:

| arm | zero | partial | adversarial |
|---|---|---|---|
| product configuration | **+8.7** | +4.8 | +4.8 |
| isolated visual channel | +0.0 | −9.6 | +4.8 |
| verbal channel only | −2.9 | −5.8 | −5.8 |

Only the product arm separates from baseline, and only clearly at zero
knowledge. **The visual channel alone contributed nothing measurable here**: 3.8%
against a 3.8% baseline. At 52 items the intervals are ±6–7 points, so
differences under about 10 points are not resolvable — which §9.1 anticipated
("below ~15 percentage points, differences at n=30 are noise") and which the
scored bank makes concrete rather than hypothetical.

This does not weaken claims 3 and 4, and that is the point of having written
them as architectural rather than empirical. "The tutor cannot name the answer
while hinting" is a property of Call 2's argument list. "Narrowing performs
reductions that cannot be expressed in one utterance" is a property of what fits
in a turn. Neither needs the visual channel to win a leakage race, and we should
not imply it did.

### The demonstration worth putting on a slide

The single clearest result is not a leakage rate. It is the evidence that a
metric was measuring nothing — `edge_click` solve rate, partial-knowledge, at
the attempt-1 rung, across all four arms:

| arm | lit nodes | `edge_click` |
|---|---|---|
| product configuration | 12.0 | 84% |
| isolated visual channel | 12.0 | 82% |
| verbal channel only | 52.0 | 82% |
| no hints at all | 52.0 | **80%** |

Nothing is narrowed in the last two rows, and no hint is given at all in the
last. A reader checks the inference in one line: **a rate that does not move
when the narrowing is removed was never measuring the narrowing.** Reproduce
with `python -m eval.adversarial --population answerable`, which is kept
runnable for exactly this and is not a mastery claim.

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
