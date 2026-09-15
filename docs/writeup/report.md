# A tutor that helps by showing less

*Spatial Socratic Tutor — four weeks, one person, one chapter. This is the spine
of the report: the claim, what was built, what was measured, and what the
measurements do and do not support. Each section links to the detailed writeup
that carries its evidence; nothing important is asserted here that is not argued
there.*

*Every number below is regenerable from a clean clone with no API key. The
command that produces it is given beside it.*

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

Every §9.1 figure generalises to the **scored** bank: **69 items** — 52
`node_click` plus 17 `edge_click`. Not the 101 visually-answerable items, and
not the 260-item bank.

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

At 52 items the half-widths are 6–7 points, so these arms are underpowered
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

`python -m eval.distractor_screen` · no key, no chapter, no network · 101 click +
159 MCQ items, coverage 1.0

A bad distractor corrupts mastery *more quietly* than a wrong key, because
nothing downstream flags it. Two screens, because the bank has two kinds of
option set and one behavioural test is degenerate on the other half:

- **Behavioural**, over the 101 click items: at the terminal rung the mean lit
  set is 3.11 nodes but the mean *live* set — candidates a region-filtering
  student would actually consider — is 2.37. Nominal guess probability .322,
  **effective .613**. The interface narrows further than its own policy floor
  believes.
- **Structural**, over the 159 MCQ items: 3 distinct option sets across 159
  items, and key-is-longest in 159/159 against a 25% chance rate. That is a
  generator habit, not a bank.

212 items flagged for human review. The MCQ bank is demoted to unscored rather
than deleted, so a real bank is a flag flip.

### 5.5 §6.1 — the parametric-reconstruction rate, now a bound rather than a blank

`python -m eval.leak_monitor`

Because Call 2 never saw the answer on a hinting turn, a layer-1 hit there means
the model reconstructed the answer from its own weights. §6 calls this a free
and genuinely interesting number.

**It was blank until day 12, and the instrument said why.** `MOCK_MODE`'s Call 2
is a template lookup with no weights to reconstruct from, so a 0% over mock turns
is not weak evidence of no leakage — it is no evidence, and on a slide it reads
identically to the real thing. The aggregator returned `rate: null` and printed
`NOT MEASURABLE` for six days rather than a zero.

**First real-model reading: 0 hits in 60 screened turns.** Quote it as a bound,
not a result:

- **n=60.** The 95% upper bound on 0/60 is **4.9%** — consistent with no
  parametric reconstruction, and equally consistent with a rate of one turn in
  twenty-five. These 60 checks are a by-product of the §9.5 run, not a
  measurement designed to answer this.
- **It pools four origins** (a demo session and three §9.5 student policies) and
  more than one build. The monitor reports that rather than hiding it —
  `mixed_origins: true` — because a rate over scripted policies and a rate over a
  person are different claims wearing one number.
- **The measure is weakest where the phenomenon is strongest.** Stemmed token
  cosine plus trigram containment misses synonym paraphrase, and paraphrase is
  exactly what reconstruction looks like. Treat 0/60 as a floor on detection, not
  a ceiling on leakage.

What it does support, modestly: across 60 real Call 2 turns on `gpt-oss-20b`,
nothing the monitor can detect came back. The structural argument does not rest
on it — Call 2's argument list is the guarantee, and this number is a check on
the guarantee rather than a substitute for it.

It also refuses to pool builds. The turn log contains 17,433 `backtrack` hits
from before the Call 2 fidelity ceiling landed; pooling the file reports 3.94%
parametric reconstruction from a bug that is fixed.

When the metric *can* run, treat it as a floor and not an estimate: the
similarity metric is a stemmed token cosine plus trigram containment, which
misses synonym paraphrase — and paraphrase is exactly what reconstruction is.
The measure is weakest where the phenomenon is strongest.

### 5.6 §9.5 — the diagnosis does not track the student

Full write-up: **[diagnosis-readthrough.md](diagnosis-readthrough.md)**.

Thirty answered turns, three student policies whose true knowledge state is known
by construction, Call 1 on `qwen/qwen3.8-27b`:

| true knowledge | `on_track` | `stuck` | `correct` | `guessing` | `confused_prereq` |
|---|---|---|---|---|---|
| **zero** — knows nothing | 5 | 6 | 1 | **0** | **0** |
| **partial** — knows the region | 6 | 3 | 0 | **0** | **0** |
| **adversarial** | 3 | 5 | 0 | 1 | **0** |

Three true states, one distribution. A student who knows nothing is called
`on_track` five times in twelve. `guessing` is used once in thirty turns, on the
wrong student; `confused_prereq` never, on a graph built entirely out of
prerequisites.

The prose does not show it. The diagnoses are specific and well-observed *about
the item* — they quote the definition and name the confusable neighbours — and
then present that as an account of the person. A reviewer reading the fields
would not catch this, and neither did we: it took tabulating against a truth the
model could not see.

A sharper instrument makes it worse. `eval/diagnostic_calibration.py` builds
histories where one answer is *forced* — three clicks scattered across unrelated
regions is guessing; three clicks inside the prerequisite region is prerequisite
confusion, and the two node sets are disjoint by assertion. The model returns
`stuck` to both, is never `correct` about a student who clicked the answer, and
gets right only the case with **no history to read**. It also got the `correct`
boolean wrong on **2 of 6** constructed histories while being shown the answer.

The consequence needs three separate statements, because collapsing them produces
either false alarm or false comfort:

1. **The diagnosis is unreliable.** Measured, on two instruments, above.
2. **The architecture makes it inert.** `student_state`, `correct` and
   `focus_nodes` are logged and read by nothing; mastery comes from a string
   comparison and the lit set from the ladder. Over §9.5's 40 turns the server
   overrode Call 1 on **11 of the 12** turns where the curriculum moved.
3. **That inertness is now enforced rather than incidental.** It was true on day
   12 by accident — nothing stopped a later change from branching on the field,
   and such a change would have passed all 364 tests then green.
   `tests/test_student_state_is_inert.py` walks the AST of the decision modules
   and fails on any read of the three fields. It is **mutation-tested**: planting
   `if decision.student_state == 'guessing': action = 'backtrack'` fails it, as
   does `lit = decision.focus_nodes`. A guard never shown to fail is not a guard,
   and that demonstration is what makes this a property rather than a coincidence.

**This is not a claim that the model does not matter.** `requested_action` still
selects `ask` vs `hint_visual` vs `hint_verbal` wherever the curriculum does not
move, which is most turns — so a student gets the wrong *flavour* of help, chosen
on a reading of them that does not track them. The architecture contains the
damage; it does not repair it. The repair is the prompt: a diagnosis carrying no
cost for answering `stuck` to everything is a diagnosis that cannot be wrong, and
that is precisely what was measured.

### 5.7 One number nothing asked for

Populating the answer-span mask required knowing which chunk each node
retrieves, which made a number available that nothing had computed: retrieval
serves the node's own declared `source_sections` **43 of 52 times (83%)**.

The misses are largely a length effect — cosine over a long chunk is diluted by
its own vocabulary, so "Slow Start" is served §6.4 (1,301 characters) rather
than the §6.3.2 section named after it (10,699). BM25 was measured over the same
52 nodes and scored 45. Two nodes at n=52 is inside the interval and adopting it
would force recalibrating a measured retrieval floor, so the scorer stays as it
is and the 83% is reported rather than repaired.

## 6. What we got wrong, and why that is in the report

Five failures in the system, in four weeks, found by the people who wrote the
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
  of the student, measured against a ground truth it could not see, and found not
  to track it.
- **[limitations.md](limitations.md)** — everything above plus the rest,
  including two figures in this report's own source that were stale prose until
  day 8 because they had been typed rather than derived.

If that pattern generalises even weakly, published leakage and learning-gain
figures from systems of this shape deserve a question rarely asked of them:
**not "what is the number" but "what was it computed over, and how would you
know."**

## 7. The harness was wrong three times, and said so confidently

**[instrument-failures.md](instrument-failures.md)** — kept separate from §6
because it is a different failure and, we think, the more transferable one.

The five above are faults in the tutor. These three are faults in the code doing
the *measuring*, and each produced a confident, specific, plausible verdict **about
the tutor** while the fault was in the harness. Two of the three were plausible
enough that we acted on them before noticing.

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

*Reproduce everything: `pip install -r requirements.txt && python -m
build.validate && python -m pytest && python -m eval.adversarial && python -m
eval.graph_quality && python -m eval.distractor_screen && python -m
eval.leak_monitor`. No API key, no network.*
