# A tutor that helps by showing less

*Spatial Socratic Tutor — four weeks, one person, one chapter. This is the spine
of the report: the claim, what was built, what was measured, and what the
measurements do and do not support. Each section links to the detailed writeup
that carries its evidence; nothing important is asserted here that is not argued
there.*

*The command that produces each number is given beside it. **Most of them
regenerate from a clean clone with no API key** — §5.2, §5.3, §5.4 and §5.7 are
deterministic or mock-driven and need neither key nor network.*

***Two do not, and it would be a poor report that blurred the difference.***
*§5.5's `0/34` and every figure in §5.6 come from live `gpt-oss-120b` runs. They
need an API key, and §5.5's also needs `logs/turns.jsonl`, which is gitignored —
on a clean clone `eval.leak_monitor` correctly reports `NOT MEASURABLE` rather
than inventing a number. The raw outputs of those runs are committed under
[`eval/results/`](../../eval/results/) so the figures can be **checked** without
a key even though they cannot be **regenerated** without one.*

---

## 1. The claim

LLM tutors leak answers because their only way to help is to say more. Every
additional sentence of help is additional surface for the answer to appear on,
and the tutor's only lever for "help harder" is "say more".

This system gives the tutor a second lever. It shows a frozen concept graph of
the chapter, and its way of helping harder is to **dim the nodes that cannot be
the answer**. The student's search space narrows without the tutor saying
anything new.

The contribution we claim is narrow and is not "graph-based tutoring", which
exists (GraphMASAL, TutorLLM, Auto-HKG, ALEKS). It is **the visual as a shared
referent in the dialogue**: pointing as an answer, and dimming as a non-verbal
hint channel. Feature parity with the systems above is worth nothing and we do
not seek it.

## 2. What we actually claim, in order of how well it is supported

We put this second, before the architecture, because the ordering is the
honest part. Two of these are properties of the construction and hold whatever
model is behind the API. Two are measurements, and one of those went against us.

| # | claim | kind | status |
|---|---|---|---|
| 1 | The tutor **cannot** name the answer while hinting | architectural | holds by construction |
| 2 | Narrowing performs reductions **not expressible in one utterance** | architectural | holds by construction |
| 3 | A non-verbal channel creates a non-verbal **leak** channel that text metrics cannot see | demonstrated on our own system | holds, generalisation is by analogy |
| 4 | Visual narrowing beats a verbal hint | empirical | **not supported.** See §5.2 |

**Claim 4 is the one a reader expects a project like this to make, and we are
not making it.** The demo's value does not rest on it, which is why claims 1–3
are stated as properties of the wiring rather than as observed behaviour.

### 2.1 Claim 1 — it cannot name the answer while hinting

On `ask`, `hint_visual`, `hint_verbal` and `backtrack`, the utterance-generating
call receives an action, a hint level, a **count** of lit nodes, and the
*category* of the answer ("a concept on the map"). It has no representation of
the answer available. It cannot name the answer while hinting because it was
never told it.

That is a property of an argument list, not a behaviour we observed and are
extrapolating from. The leakage numbers in §5 therefore describe a system that
*cannot* leak in that channel, rather than one measured not to.

Getting this right took four attempts, and the record of the three failures is
the most transferable thing in this report:
**[representation-blindness.md](representation-blindness.md)**.

### 2.2 Claim 2 — some reductions do not fit in a sentence

At the coarse rungs the interface removes 40 of 52 candidates in one frame. You
cannot name 40 excluded nodes in one turn of dialogue. This is a statement about
what fits in an utterance, not a comparison we won, and it is the structural
argument for the spatial interface: there is a class of reduction the verbal
channel cannot perform at all, at any quality of prose.

### 2.3 Claim 3 — identity leakage

Giving a tutor a non-verbal channel gives it a matching non-verbal leak channel,
and text-based leakage metrics report zero on it.

Our own system shipped the answer in the clear, on every item whose answer was a
node or an edge — 101 of 260 items — while a whitelist serializer and a test
suite asserting that no answer string, alias, prompt or span appears in any
response were **green throughout**. The answer was a node *identity*, and the
payload named that identity in a different field. String comparison cannot see
it.

Full argument, and why any tutor that can *point* has this failure mode:
**[identity-leakage.md](identity-leakage.md)**.

## 3. What was built

One endpoint, `POST /turn`, and two hand-written model calls per turn. No agent
framework; the five agents of the original design collapsed into one pipeline
plus retrieval plus two deterministic functions, which we regard as a result
rather than a compromise.

Two providers sit behind one seam (`LLM_PROVIDER`): Anthropic's Messages API and
Groq's OpenAI-compatible endpoint. Only the wire format differs — URL, auth
header, body shape, and where the forced tool call lands in the response. The
*schema* does not: both are handed the same pydantic model under a forced tool
call, and a response that fails validation fails identically on either. The
shipped demo runs on Groq; see §8.

```
student response
   │
   ├─ Call 1 ── diagnosis + requested action ── sees the answer
   │
   ├─ server applies guards, owns every counter, decides the real action
   │
   ├─ graph_state streamed IMMEDIATELY  ← the graph moves here, ~1s
   │
   └─ Call 2 ── utterance only ── NEVER sees the answer while hinting
```

The split is the mechanism. Call 1 needs the answer to diagnose; Call 2 writes
the words and is structurally denied it. The graph reacts on Call 1's return,
before any text exists, so narrowing is visibly not a consequence of the
sentence.

Seven guard layers (0–6) sit over this, ordered by how much they actually save:

| # | layer | mechanism |
|---|---|---|
| 0 | structural | one text field renders; whitelist at the serializer |
| 1 | answer monitor | post-split a *monitor*, not a guard — see §5.5 |
| 2 | hint monotonicity | server counter, +1/turn, never decreases within an item |
| 3 | turn budget | 8 turns on an item → forced reveal, zero mastery |
| 4 | retrieval gate | no chunk above threshold → say the chapter does not cover it |
| 5 | mastery isolation | the model emits a boolean; Python computes the number |
| 6 | chunk delimiting | retrieved text marked as untrusted; the PDF is an injection surface |

Mastery is a **Rasch-form** logistic — ability minus effective difficulty, with
no discrimination parameter — updated by an Elo-style rule whose learning rate
decays with the number of observations on that node. It is computed in Python,
never by a model, and only on deterministic items (node click, edge click). Free
text teaches and is never scored.

A hint makes the item *easier* rather than discounting the observation, so
correct-with-hints yields a small positive update and wrong-with-hints a large
negative one — failing *with* help is stronger evidence of not knowing than
failing without it. A failed item decays each prerequisite's θ by 0.05, which is
what makes the graph do work rather than decorate the screen.

**A session can also end.** Above §7's routing sits a circuit breaker: after
three forced reveals in one session the tutor concludes rather than loading
another item. Without it, a student who answers nothing backtracks between a
node and its prerequisite indefinitely — measured at 400 turns, 0 nodes
mastered, 2 distinct nodes, no exit, with every per-item guard firing correctly
the whole way.

## 4. The chapter and the graph

Peterson & Davie, *Computer Networks: A Systems Approach*, chapter 6 (Congestion
Control), CC BY 4.0. 52 nodes, 73 edges, 15 section-level chunks over §§6.1–6.4.
Attribution and the reason 6.5 is absent: [`data/SOURCE.md`](../../data/SOURCE.md).

**The graph is hand-authored, and the gold annotation was frozen before any
extractor existed.** We say this plainly rather than implying automation. The
extraction pipeline exists and is measured (§5.3), but the shipped graph is
curated — which is what the comparable published systems use.

Layout is frozen at build time and written into `graph.json`. Nodes never move.
A node that moves on a mastery update costs the student the spatial memory the
entire claim rests on.

## 5. The measurements

### 5.1 What the population is

Three populations, named here once so every count below can say which it
means:

| population | n | what it is |
|---|---|---|
| **full bank** | **260 items** | everything in `items.json` |
| **click items** | **101 items** | 52 `node_click` + 49 `edge_click`; the visually-answerable ones |
| **scored bank** | **69 items** | 52 `node_click` + 17 `edge_click`; the only items that move mastery |

Every §9.1 figure generalises to the **scored bank (69 items)**. Not the 101
click items, and not the 260-item bank.

The other 32 edge items are `scorable: false`. Their named anchor has exactly
one prerequisite, so naming it names the answer; the guess rate is 1.0 and no
difficulty value represents "free". 159 MCQ items are also unscored: they carry
three distinct option sets between them, and the key is the longest option in
159/159 against a chance rate of 25%.

Quote 69 and its interval.

### 5.2 §9.1 — effective leakage

`python -m eval.adversarial` · 138 dialogues per cell · 95% percentile **cluster**
bootstrap over items, 2000 resamples · `node_click` stratum, terminal rung

Leakage is measured as **post-hint solve rate**: after the hint, can a simulated
student that performs no reasoning produce the answer? Measuring it as "does the
answer string appear in the utterance" would score visual hints at 0% by
construction and a reviewer would kill it in ten seconds.

| arm | zero | partial | adversarial |
|---|---|---|---|
| product configuration | .125 [.067, .192] | .308 [.221, .404] | .288 [.202, .385] |
| isolated visual channel | .038 [.010, .077] | .163 [.096, .240] | .288 [.192, .385] |
| verbal channel only | .010 [.000, .029] | .202 [.115, .288] | .183 [.115, .260] |
| no hints at all | .038 [.010, .077] | .260 [.183, .356] | .240 [.164, .327] |

Marginal over the no-hints baseline, paired on item:

| arm | condition | marginal | 95% CI |
|---|---|---|---|
| **product configuration** | **zero** | **+.086** | **[+.019, +.164]** |
| product configuration | partial | +.048 | [−.067, +.173] |
| product configuration | adversarial | +.048 | [−.058, +.164] |
| isolated visual channel | zero | +.000 | [−.058, +.058] |
| isolated visual channel | partial | −.096 | [−.192, +.000] |
| isolated visual channel | adversarial | +.048 | [−.086, +.183] |
| verbal channel only | zero | −.029 | [−.067, +.010] |
| verbal channel only | partial | −.058 | [−.192, +.077] |
| verbal channel only | adversarial | −.058 | [−.173, +.067] |

**Exactly one marginal in the grid is distinguishable from zero.** The shipped
configuration hands a zero-knowledge student +8.6 points over no hints at all.
Every other cell crosses zero, in both directions.

**The isolated visual channel contributed nothing measurable**: .038 against a
.038 baseline at zero knowledge. Only the interleaved configuration, which uses
both channels, separates from baseline at all.

At **52 items (the `node_click` stratum of the 69-item scored bank)** the
half-widths are 6–7 points, so these arms are underpowered
rather than demonstrated null — but that cuts both ways, and here it cuts
against us. **We are not claiming the visual arm won.** It did not, on this
bank, at this *n*.

The direction of the one real effect was also not what we predicted. The
measurable leakage is to the student who knows *nothing* — for whom a
five-candidate lit set is a genuine reduction from fifty. A partially
knowledgeable student has already narrowed the field themselves, so the
interface tells them less. That is a coherent mechanism and a better result for
the thesis than the one we lost; we did not predict it and do not present it as
though we had.

Never report `1/N` as leakage. It is a lower bound assuming uniform choice, and
the measured partial-knowledge rate runs well above it.

### 5.3 §9.3 — graph extraction, reported as a ceiling

`python -m eval.graph_quality` · deterministic, no key · 66 gold prerequisite edges

The classifier half needs a model we do not have. The half that does not is the
**candidate-generation ceiling**, and it bounds the other: edge extraction only
asks the model about pairs where A precedes B in the text and the two co-occur
within N sections.

At the shipped window of 2 sections, that filter passes **30 of 66** true edges
— a recall ceiling of **45%**. No extraction run can score above it, however
good the classifier.

Widening the window does not rescue it: 1/2/3/4 sections give 23/30/32/35, and
at an **infinite** window it stops at 49 of 66 — **74.2%**. The residual is not a
knob. 17 edges are missed because the chapter names the dependent concept
*before* its prerequisite, typically where a heading announces a topic and the
body introduces the parts afterwards. The window is tunable; the ordering
assumption is a wall.

**Report the ceiling beside any recall figure, not after it.** A recall of 0.41
against a ceiling of 0.45 is a good classifier; against a ceiling of 1.0 it is a
poor one, and the two are indistinguishable without this number.

### 5.4 §9.4 — distractor screen

`python -m eval.distractor_screen` · no key, no chapter, no network · the full
bank: **101 click + 159 MCQ = 260 items**, coverage 1.0

A bad distractor corrupts mastery *more quietly* than a wrong key, because
nothing downstream flags it. Two screens, because the bank has two kinds of
option set and one behavioural test is degenerate on the other half:

- **Behavioural**, over the **101 click items**: at the terminal rung the mean lit
  set is 3.11 nodes but the mean *live* set — candidates a region-filtering
  student would actually consider — is 2.37. Nominal guess probability .322,
  **effective .613**. The interface narrows further than its own policy floor
  believes.
- **Structural**, over the **159 MCQ items** (all unscored): 3 distinct option
  sets across 159 items, and key-is-longest in 159/159 against a 25% chance rate. That is a
  generator habit, not a bank.

**212 items of the 260-item full bank** flagged for human review. The MCQ bank is demoted to unscored rather
than deleted, so a real bank is a flag flip.

### 5.5 §6.1 — the parametric-reconstruction rate, re-measured on a monitor that can see

`python -m eval.leak_monitor`

Because Call 2 never saw the answer on a hinting turn, a layer-1 hit there means
the model reconstructed the answer from its own weights. §6 calls this a free
and genuinely interesting number.

**It was blank until day 12, and the instrument said why.** `MOCK_MODE`'s Call 2
is a template lookup with no weights to reconstruct from, so a 0% over mock turns
is not weak evidence of no leakage — it is no evidence, and on a slide it reads
identically to the real thing. The aggregator returned `rate: null` and printed
`NOT MEASURABLE` for six days rather than a zero.

**An earlier day-12 figure for this rate is withdrawn**, on the same grounds as
every other day-12 number: an unreproducible dirty build and a model that was
never logged (§5.6). Its value is not repeated, because a withdrawn number
quoted often enough becomes the benchmark its replacement has to argue against.

Two instrument defects were live in it, and both are fixed:

1. **The monitor could not see edge answers.** An edge item's answer is an id
   pair with no aliases, and layer 1 caught an utterance naming its FROM
   endpoint on **0 of 49 edge_click items** — the edge half of the **101 click
   items** (§5.1), of which 17 sit in the **69-item scored bank**. The monitor
   screens all 49 regardless of whether the item scores, because unscored items
   are still served (`turn.py:_pick_item` prefers scorable and falls back).
   Fixed in `522defc`: 49 of 49, no false positive on the anchor `ask` is
   licensed to name.
2. **Call 2 was shown no history** — every past turn arrived as the literal line
   `role: text` — so the model being monitored had less to reconstruct from than
   the shipping one does. Fixed in `1cfc74a`.

**Re-measured 2026-09-21 (day 18), build `18d220d`, Call 2 on `gpt-oss-20b`:**

```
parametric_reconstruction    0 hits / 34 checks    over 10 distinct items
authorised_naming            0 hits /  6 checks
canned fallbacks in denominator: 0
```

- **n=34, and the *one-sided* 95% upper bound is 8.4%.** (Two-sided, it is
  10.3%; the one-sided figure is the right one for a bound on a rate that
  cannot go below zero, and it is the smaller of the two, so quoting it is not
  the flattering choice.) That is a loose bound, and the
  looseness is the honest shape of the result: the only build carrying **both**
  instrument fixes is this one, so the admissible population is 34 screened
  turns and no more. A tighter bound is available only by pooling in builds
  where the monitor was half-blind, which would be a smaller number bought by
  counting turns on which a hit could not have been detected. **Zero hits in 34
  screened turns is compatible with a reconstruction rate as high as roughly one
  turn in twelve.** It is not evidence of a low rate; it is the absence of
  evidence of a high one, on a small sample.
- **It is one build and three arms**, the three §9.5 student policies. It is a
  by-product of the §9.5 run, not a measurement designed to answer this.
- **The tool used to print a different number here, and that is now fixed.**
  `leak_monitor`'s per-build table always partitioned correctly, but its HEADLINE
  pooled every *real* arm — on this log, 25 arms and 3,334 checks spanning builds
  that predate both fixes, plus `ac2fc28 <eval:adversarial:*>`, the day-13
  accidental live run that `docs/schedule.md` records as **not real-model
  evidence**. Quoting it would have inflated *n* by 98× in the flattering
  direction. Found and repaired on day 18: the headline now reports **one build**,
  defaulting to the current one, and pooling is opt-in behind `--pool-builds`.
  The figure above is what the tool prints today. See
  [instrument-failures.md](instrument-failures.md).
- **The measure is weakest where the phenomenon is strongest.** Stemmed token
  cosine plus trigram containment misses synonym paraphrase, and paraphrase is
  exactly what reconstruction looks like. Treat 0/34 as a floor on detection, not
  a ceiling on leakage.

What it supports, modestly: across 34 screened real Call 2 turns on a build where
the monitor can finally see edge answers and the model can finally see the
dialogue, nothing detectable came back. The structural argument does not rest on
it — Call 2's argument list is the guarantee, and this number is a check on the
guarantee rather than a substitute for it.

It also refuses to pool builds *in the table*. The turn log contains 17,433
`backtrack` hits from before the Call 2 fidelity ceiling landed; pooling the file
reports 3.94% parametric reconstruction from a bug that is fixed.

### 5.6 §9.5 — the diagnosis tracks the student, and the prompt is why

Full write-up: **[diagnosis-readthrough.md](diagnosis-readthrough.md)**.

> **Scope.** Every claim in this section is about **`openai/gpt-oss-120b` running
> the prompt this demo ships**, on build `18d220d`. It is not a claim about LLM
> tutors, about Groq, or about any other model. The model variable is not
> isolated and will not be — see *What is not established* at the end.

Thirty answered turns, three student policies whose true knowledge state is known
by construction, Call 1 on `openai/gpt-oss-120b`, run 2026-09-21 (day 18) on
build `18d220d`. Ten distinct items, coverage 1.0.

| true knowledge | n | `guessing` | `confused_prereq` | `correct` | `on_track` | `stuck` |
|---|---|---|---|---|---|---|
| **zero** — knows nothing | **n=12** | **12** | 0 | 0 | 0 | 0 |
| **partial** — knows the region | **n=9** | 3 | 0 | 4 | 2 | 0 |
| **adversarial** — plays the narrowing | **n=9** | 2 | **4** | 2 | 1 | 0 |

`correct`, the one boolean the model is allowed to emit, agreed with the
deterministic grade on **30 of 30**.

**Read the `zero` row as directional, not as a rate.** Twelve turns of one
scripted policy on one model is a clear signal and a small sample; "12/12" is
not evidence that the true rate is near 1.

**One line on day 12.** An earlier version of this section, built on the day-12
run, reported the opposite. That run is withdrawn for cause — unreproducible
dirty build, model never logged — so it is not a contrast this section argues
from, and its figures live in
[diagnosis-readthrough.md](diagnosis-readthrough.md) as history.

**What produces this behaviour is a separate question from measuring it, and our
first answer was wrong.** Day 13 found that Call 1 had received every past turn
as the literal line `role: text` (`1cfc74a`), and this report credited the
improvement to that fix. The controls do not support it. Three runs, all
`gpt-oss-120b`, so the model is fixed by construction:

| | n | prompt | history | reaches a specific state |
|---|---|---|---|---|
| run 1 (`7ba8078`) | n=4 turns | current | **broken** | **yes** — `guessing` 2/4 |
| arm B (day 18) | n=10 cases | **pre-falsifiability** | fixed | **no** — `stuck` on 4/4 contrasting |
| arm A (day 18) | n=10 cases | current | fixed | **yes** — 8/10 specific |

The prompt tracks the outcome on a broken harness and on a fixed one; the
history fix does not. What the history fix demonstrably moves is **grounding** —
run 1 reasons well about nothing (*"their recent inputs were text"*), run 2 four
minutes later names the nodes actually clicked. **Directional, not a rate:** n=2
per cell, n=4 on an aborted run.

**The counter-test, which comes first because the row above flatters the current
prompt.** The shipped prompt tells the model `stuck` is the cheap answer. On the
one constructed case where `stuck` is the *only* defensible answer — three wrong
free-text replies, no clicks, so nothing for `guessing` or `confused_prereq` to
read — it scores **0/2** and says `guessing`; the old prompt scores **2/2**. A
prompt that simply never says `stuck` would win every other row and be worse for
it. Derivation, all five cases and the day-12 calibration withdrawal:
[diagnosis-readthrough.md](diagnosis-readthrough.md).


**The architecture half does not depend on any of this, and stands unchanged.**

1. **The judgement fields are inert.** `student_state`, `correct` and
   `focus_nodes` are logged and read by nothing; mastery comes from a string
   comparison and the lit set from the ladder. Over this run's **40 turns**, the
   curriculum moved on **13**: 6 `advance` the model also asked for, 6
   `backtrack` the server performed while the model asked for a hint, and **1
   `backtrack` the model requested and got**. That fraction is not a quality
   score; the guarantee is that the override is available on all 13, whatever
   the model asks for, which is why it cannot be *that the model is right*.

   **That single model-requested backtrack is also the one the log could not
   account for**, and chasing it found a real hole. `action` begins life as
   `decision.requested_action`, so a Call 1 asking to step back got the word and
   the prerequisite chunk while **nothing moved** — no new item, the student
   still on the node they were failing. Only the two-failure rule ever moved the
   curriculum. A model-requested backtrack is now honoured **only if the target
   prerequisite is below `MASTERY_THRESHOLD`** — §7 backtracks to close a gap,
   and a mastered prerequisite is not one — and is otherwise refused and
   degraded to help. Both paths are tested and the gate is mutation-tested;
   turns now log `backtrack_origin` (`server` / `model` / `refused`), which is
   the field whose absence made that 1 of 13 unattributable.
2. **That inertness is enforced rather than incidental.** It was true by
   accident first — nothing stopped a later change from branching on the field.
   `tests/test_student_state_is_inert.py` walks the AST of the decision modules
   and fails on any read of the three fields. It is **mutation-tested**: planting
   `if decision.student_state == 'guessing': action = 'backtrack'` fails it, as
   does `lit = decision.focus_nodes`. A guard never shown to fail is not a guard.

**This is not a claim that the model does not matter.** `requested_action` still
selects `ask` vs `hint_visual` vs `hint_verbal` wherever the curriculum does not
move, which is most turns. Arm B is the measured case: a prompt that answers
`stuck` to every contrasting student still drives `requested_action`, so the
student gets a flavour of help chosen on a reading that does not track them.
Arm A tracks them. The architecture is unchanged between the two, which is the
point — it contains the damage in the arm that has damage, and does nothing
different in the arm that does not. Both facts are worth keeping: the
containment is load-bearing exactly when the diagnosis is poor, and
nothing about it had to change when the diagnosis improved.

**What the mislabel costs the student, checked rather than assumed.** The
counter-test says the shipped prompt calls a genuinely stuck student
`guessing`. Re-reading `requested_action` on those turns — from the existing A/B
logs, no new calls — **both arms requested `hint_visual` on 4 of 4**. The student
gets the same hint rung whichever label the model picks, so on this case the
mislabel is inert in exactly the way §5.6 claims the labels are. Across all five
cases `ask` appears only on the opening turn, where no response exists yet.

**A server-side hint floor was considered and is not built.** The candidate rule
— two consecutive non-correct turns on an item grant the next rung regardless of
Call 1 — was motivated by the fear that a mislabelled student would be
under-helped. The evidence says they are not: a floor would fire on turns that
are already being hinted. It earns its place the day a run shows `ask` requested
on a failing item, and not before.

**Two caveats this section does not resolve.** `stuck` is used **0 of 30** times
in the policy run — partly the prompt, per the counter-test, and partly
`--max-turns 3` giving no student time to be stuck. And `partial` → `guessing`
on **3 of 9** is the one cell that still looks like miscalibration. Both are for
the human read (§9.5 asks for a person), not for this file.

### What is not established, and is not going to be

**The model is not isolated, and that is closed as a known gap rather than left
open.** Isolating it would mean running the fixed harness and shipped prompt
against `qwen3.8-27b` — one command, ~30,000 tokens. We are not running it:
every day-12 number is withdrawn for cause, so the comparison it would serve is
one this report no longer makes, and the three live runs are all `gpt-oss-120b`
already, so the model is held fixed across them by construction.

The cost, plainly: **nothing here distinguishes "this prompt change helps
`gpt-oss-120b`" from "this prompt change helps models of this kind".** Only the
first is claimed.

### 5.7 One number nothing asked for

`python -m build.validate` · deterministic, no key · reported as the
`[retrieval]` warning (9 of 52 disagree, so 43 agree)

Populating the answer-span mask required knowing which chunk each node
retrieves, which made a number available that nothing had computed: retrieval
serves the node's own declared `source_sections` **43 of 52 times (83%)**.

The misses are largely a length effect — cosine over a long chunk is diluted by
its own vocabulary, so "Slow Start" is served §6.4 (1,301 characters) rather
than the §6.3.2 section named after it (10,699). BM25 was measured over the same
52 nodes and scored 45. Two nodes at **n=52 nodes** (not items) is inside the
interval and adopting it
would force recalibrating a measured retrieval floor, so the scorer stays as it
is and the 83% is reported rather than repaired.

## 6. What we got wrong, and why that is in the report

Six failures in the system, in four weeks, found by the people who wrote the
code. We include them because in every case the *intuitive* fix would have hidden
the problem rather than surfaced it, and because all of them survived a test suite
a reviewer would have called adequate.

- **[representation-blindness.md](representation-blindness.md)** — four
  instances of one mechanism: two fields that are different things in the schema
  and the same thing in the domain. Includes the one we would flag hardest: a
  leak the dedicated leak suite *measured*, *saw*, and filed under "legitimate".
- **[numbers-that-looked-fine.md](numbers-that-looked-fine.md)** — evaluation
  code that ran, passed, and produced well-formed numbers over nothing. A
  leakage rate computed over one item out of 101 for four days. A drift test
  blind to exactly the kind of drift it existed to catch.
- **[diagnosis-readthrough.md](diagnosis-readthrough.md)** — the tutor's model
  of the student, measured against a ground truth it could not see. Found not to
  track it on day 12, found to track it on day 18. Both readings are in the file,
  because the first is the reason the second is believable — and because the
  *explanation* we gave for the difference on the morning of day 18 was wrong,
  which is the sixth failure below.
- **[limitations.md](limitations.md)** — everything above plus the rest,
  including two figures in this report's own source that were stale prose until
  day 8 because they had been typed rather than derived.

- **The sixth is an attribution, not a bug, and it is ours from day 18.** The
  §9.5 re-run reversed the day-12 finding, and we wrote up the reversal as the
  history fix (`1cfc74a`) doing the work. It was a single-cause story for a
  change that moved three variables — prompt, history handling and model — and
  it was written *the same morning*, into a report whose entire argument is that
  you must ask what a number was computed over. Checking commit timestamps is
  what broke it: the Call 1 prompt rewrite landed an hour and three quarters
  after the day-12 run, so day 12 had been using a different prompt all along.
  An A/B that afternoon showed the old prompt reproducing the day-12 degeneracy
  on a fully fixed harness. §5.6 now carries the controls and the corrected
  attribution, beside the containment argument they bear on. **The lesson is not "check your commits" — it is
  that a fix you have just shipped is the most attractive available explanation
  for any improvement that follows it.**

If that pattern generalises even weakly, published leakage and learning-gain
figures from systems of this shape deserve a question rarely asked of them:
**not "what is the number" but "what was it computed over, and how would you
know."**

## 7. The harness was wrong four times, and said so confidently

**[instrument-failures.md](instrument-failures.md)** — kept separate from §6
because it is a different failure and, we think, the more transferable one.

The six above are faults in the tutor, or in how we read it. These are faults in the code doing
the *measuring*, and each produced a confident, specific, plausible verdict **about
the tutor** while the fault was in the harness. Two of them were plausible
enough that we acted on them before noticing, and the fourth was caught only
because its own per-build table contradicted its summary line.

- A diagnosis said *"the student keeps offering text instead of clicking."* We
  filed it as a hallucination. It was an accurate report of a bug in our driver,
  which really was sending text.
- A constructed case told the model *"three turns on this item"* and showed it
  **one** click. It answered `stuck`, explaining *"three turns in with no clear
  right answer"* — a correct reading of a context we had broken. We scored it as
  a failure to recognise a correct answer, and it was directionally consistent
  with a finding we already believed, which is why it went down easily.
- A probe printed *"the diagnosis is not reading the history"* from a run in
  which **every call had failed** on an exhausted token budget, because two empty
  distributions compare equal.
- The leak monitor, whose whole argument is that pooling builds reports a fixed
  bug as a result, printed a **pooled headline** over 25 arms and 3,334 checks
  while its own table partitioned correctly. Found on day 18, quoting it for
  §6.1 would have inflated n by 98× in the flattering direction.

This is not the same as [numbers-that-looked-fine.md](numbers-that-looked-fine.md).
There, the number was *empty* — a rate over one item — and an empty result invites
the question "over what?". Here the number is *wrong in a specific direction and
points at the system under test*, which invites agreement instead.

The fix generalises and is cheap: **internal consistency assertions on every
constructed case** (a probe that tells the model one thing and shows it another is
not measuring the model) and **three-valued verdicts** (`True` / `False` /
`NOT MEASURED`, so a blocked comparison cannot render as a negative result). Both
are in the repo as tests, and one of them caught a third fault before it ever ran:
the two contrasting histories originally shared a node, which would have reported
"cannot discriminate" from two students who were not different.

The uncomfortable part is that we had already built the three-valued refusal once,
for §6.1, and written up why it mattered — then wrote a two-valued verdict into the
next probe anyway. The lesson transferred when it became a test, not when it
became a document.

## 8. Limits

The four we would ask about first, in full at
**[limitations.md](limitations.md)**:

- **One chapter.** Every number here comes from a single ~50-node graph.
- **Curated graph, no extraction run in the shipped artefact.**
- **Simulated students, not people.** All leakage figures come from three
  scripted policies.
- **No human study.** No learning outcome is measured or claimed.

And three that shape how to read §5.

**The model is not Claude.** The tutor runs `openai/gpt-oss-120b` on Call 1 and
`gpt-oss-20b` on Call 2, served by Groq. The key available to this project is a
Groq key; `server/llm.py` speaks both wire formats behind `LLM_PROVIDER` and the
schema does not move between them, but the model identity is a fact about the
results, not an implementation detail. Call 1's model was chosen on measured
diagnosis quality over real items rather than on size, because §9.5 hand-reads
that field.

**§9.1's utterances are still templates.** The free tier is 8,000 tokens per
minute and one Call 1 costs ~2,750 — about two full turns a minute — so a
real-model re-run of twelve arms over 138 dialogues each is days of wall clock.
§9.1 therefore reports the mock-utterance run. This is defensible rather than
merely convenient: the visual arm's narrowing is *deterministic*, computed by
`mastery.py` and the ladder, and does not depend on what Call 2 writes. The
verbal arm is the one this limits, and it is the arm that lost.

**§5's latency figure is an Anthropic number and is not re-derived here.** "Call
1 is ~120 output tokens (~1s)" was written against a model that emits the tool
call directly. gpt-oss emits reasoning first: measured 534–580 completion tokens
and **p50 2.3s** to a validated decision. The architectural claim is untouched —
the graph still moves on Call 1's return, before any utterance exists — but the
*perceived-latency* argument in §5 was built on ~1s and has not been re-argued at
2.3s. Treat that paragraph as stale rather than as verified.

## 9. What we cut, and said so

- **The matched-elimination comparison (§9.2)** — cut deliberately. It asks "is
  visual narrowing better than saying the same thing", is only tractable at fine
  granularity, and its most likely outcome was a null. Claim 2 is guaranteed by
  the contract and needs no comparison to support it.
- **The five-agent design** — collapsed into one tutor pipeline plus retrieval
  plus two deterministic functions, because the agents added latency and cost
  without measurable pedagogical gain. A stronger sentence than "we have five
  agents".
- **3D, simulation, visualization agents, arbitrary PDF upload, misconception
  taxonomies, auth and deployment** — never built, not deferred.

---

*Reproduce the keyless half: `pip install -r requirements.txt && python -m
build.validate && python -m pytest && python -m eval.adversarial && python -m
eval.graph_quality && python -m eval.distractor_screen`. No API key, no network.*

*`python -m eval.leak_monitor` runs keyless too, but on a clean clone it has only
the mock turns the line above just wrote, so it will report `NOT MEASURABLE` for
§6.1 — which is the correct answer, not a failure. §5.5's `0/34` and §5.6's
tables need a key and the day-18 turn log; their raw outputs are committed under
`eval/results/`.*
