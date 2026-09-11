# Limitations

*Draft section, written early on purpose. Volunteering all of this costs nothing
and pre-empts the entire hostile question set; discovering that a reviewer had to
drag it out of us costs the credibility of everything above it.*

---

## The four we would ask about first

**One chapter.** Every number in this report comes from a single graph of ~50
concepts in one subject area. We do not know which results are properties of the
method and which are properties of that graph. Its branching factor, depth and
prerequisite density all plausibly affect how much a narrowing hint gives away,
and we varied none of them. A second chapter is the single highest-value thing we
did not have time for.

**Curated graph, and no extraction run.** The concept graph is hand-authored:
52 nodes over one chapter, written from the chapter's structure. §4 permits
this, and the comparable published systems also use curated graphs, but it means
we have not shown the pipeline works end-to-end on an arbitrary chapter — we
have not run it on one at all.

The ordering is worth stating because it inverts the usual concern. We froze
`gold_graph.json` as a byte-identical copy of the hand-authored graph *before*
any extractor existed. Had we extracted first and hand-corrected the output, the
gold annotation would have been a derivative of the thing it scores — the
annotator anchored by the extractor — which is a standard way to inflate a
precision/recall figure. Annotating blind is the clean version, and we got it by
accident of not having the chapter file, not by foresight.

If an extraction run happens, it scores against a gold that could not have been
contaminated by it. If it does not happen, §9.3 is simply not reported, and the
demo is unaffected because it never depended on extraction working.

**Simulated students, not people.** All leakage figures come from three scripted
policies — zero-knowledge, partial-knowledge, adversarial — guessing over the
candidate set the interface leaves lit. They model *what the interface hands
over*, which is what the leakage question is about, but they do not model
motivation, misconception, fatigue, or the ways a real student reads a screen. A
policy that guesses uniformly over a plausible region is a hypothesis about human
behaviour, and we did not test it.

**No human study.** No learning outcomes are measured or claimed. Nothing here
shows that a student taught this way learns more, learns faster, or retains
longer than one taught by a text tutor. The claim is narrower: about how much the
interface gives away, and how that compares to giving nothing away at all.

## Narrower ones worth stating

**The partial-knowledge student is our construct.** It is operationalised as
"restricts to lit nodes in the answer's graph neighbourhood, then guesses". That
is one reasonable formalisation of partial knowledge and the headline gap between
zero- and partial-knowledge leakage depends on it. A different formalisation
would move the number. The *direction* — that partial knowledge extracts more
from a narrowing than zero knowledge does — follows from the structure of the
hint and is more robust than the magnitude.

**Marginal leakage depends on the baseline arm.** We subtract a no-hints-at-all
condition. An earlier draft subtracted a verbal-hints-only condition, which was
wrong: a verbal hint still eliminates candidates by name, so subtracting it
credits the verbal channel with everything it gave away. On our data that choice
moves the figure by about two points, so the conclusion is not sensitive to it —
but the reasoning would have been, and on a leakier verbal channel it would be.

**Leakage is measured on the answerable-on-the-graph subset.** Items whose answer
is a proposition rather than a node cannot be leaked by dimming, so including
them would dilute the figure toward zero for uninteresting reasons. The number
therefore describes the subset most exposed to the mechanism, which is the
conservative direction, but it is not a whole-bank figure.

**Distractor quality is screened, not solved.** We flag items whose distractors
are never chosen (silently a 3-choice item scored as 4-choice) and items whose
distractor is chosen as often as the key by a strong student (likely ambiguous).
Flagged items go to a human pass. We do not claim the surviving bank is clean,
only that the obviously broken items were removed.

**Node definitions are readable between items, and that is a decision.** The
interface has a node panel: click a node, read its one-sentence definition from
the chapter. It is locked for the whole time an item whose answer is a node is
open — every turn of that item, not merely the turns where the tutor is waiting
for a click — and open otherwise.

The boundary is worth stating because a reviewer will ask what stops a student
reading ahead, and the answer is: nothing does. `graph.json` definitions are
extracts from the source, so for a node whose item asks what that node does, the
definition is close to the answer verbatim. A student can browse the whole graph
before any item on it opens, and our leakage figures assume they have not.

We think that is the right boundary for a study tool rather than a test. A
student reading their own textbook is not leakage; it is the activity. What
would be leakage is the *tutor* handing over the sentence at the moment of
being asked, which is what the lock prevents. The distinction we are drawing is
between material the student went and got, and material the interface pushed at
them mid-question, and only the second is what §9.1 measures.

Two honest consequences. Our numbers describe a student who has not pre-read,
which is the leakier direction to assume for the mechanism but the less
conservative one for the headline figure. And the boundary is enforced per item,
not per session, so nothing stops a determined student reading all 50 definitions
first — against which the only real defence would be removing the panel, which
would make the graph a diagram rather than a map.

**`answer_spans` was empty for every item, and the mask was therefore inert.**
This is closed, and the way it was found is worth more than the fix.

§3 specifies character offsets of the answer inside the source chunk, and §5
masks those spans before a chunk is handed to Call 2 on `advance` and `explain`.
While the graph was hand-authored and no chapter file existed, there was nothing
to offset into, every item carried `answer_spans: []`, and this section said so.
Then `data/chunks.json` landed and retrieval started serving real prose — and
the empty spans stopped being a documented absence and became a live leak. The
positive half of §5's gate was wired, the masking half was a no-op, and Call 2
received the chapter's own explanation of the concept, unmasked, on every
`advance` and `explain`.

**Nothing failed.** 249 tests passed, `build/validate.py` was clean, and the
section you are reading described the gap accurately in the present tense while
its reason had expired. What surfaced it was reading the turn log: guard layer 1
was firing on `advance` — 6 hits in a 258-turn session, each one regenerating,
hitting again, and shipping a canned fallback in place of the tutor's line.

The reason nobody looked is the interesting part. `guards.stats_snapshot()`
splits layer-1 hits into `parametric_reconstruction` (`ask`, `hint_*` — Call 2
saw no answer, so a hit can only have come from the weights) and
`authorised_naming` (`advance`, `explain` — these actions are *meant* to name
the answer, and pooling them would inflate the figure that matters). That split
is right, and it is why the reported §6 number was never contaminated.

But it is a statement about the ACTION, not about the mechanism, and it quietly
absorbed the defect. `advance` is licensed to confirm an answer the student has
already given. It is not licensed to forward the chapter's unmasked explanation
of the concept — that is precisely what §5's `answer_spans` masking exists to
prevent. The bucket labelled the symptom "intended" and the inert mask underneath
it stayed invisible. Same shape as the two failures in
[numbers-that-looked-fine.md](numbers-that-looked-fine.md): a correctly computed
signal read as evidence about something it cannot distinguish.

`build/annotate_spans.py` now populates the offsets against the chunk retrieval
actually serves, and `build/validate.py` re-derives every one of them on every
run, so a span that stops landing on the answer fails the build. Layer-1 hits on
`advance` went from 6 in a 258-turn session to 0.

**70 of 260 items have spans; the other 190 have no label-fidelity occurrence of
their answer in the chunk they retrieve.** Literal offsets cannot mask a chunk
that teaches slow start without writing the words, and no offset scheme could.
The claim is therefore unchanged in shape and only narrower than it looks:
masking is now real for the items where the chapter names the answer, and §5's
retrieval gate — no chunk at all on `ask` and `hint_*`, which is where leakage
would matter — remains the coarser and more important half.

**Retrieval serves the section the chapter disagrees with for 9 of 52 nodes.**
Measuring the spans required knowing which chunk each node retrieves, which made
a number available that nothing had computed: the served chunk matches the
node's own declared `source_sections` **43 of 52 times (83%)**.

The misses are mostly a length effect. Cosine over a long chunk is diluted by
that chunk's own vocabulary, so a short section wins over the long one that
actually teaches the concept — "Slow Start" is served 6.4 (1,301 characters)
rather than the 6.3.2 section named after it (10,699). BM25, the standard fix
for exactly that, was measured over the same 52 nodes and scored 45. **Two nodes
at n=52 is inside the interval**, and adopting it would force a recalibration of
`RETRIEVAL_SCORE_FLOOR`, which was itself measured (52 in / 12 out). So the
scorer stays as it is, the 83% is reported rather than repaired, and §11's "cut
retrieval before you cut the tutor loop" is the reason that is the right trade
rather than a shrug.

What this bounds: on `advance` and `explain` the tutor cites the wrong section
about one time in six, and a span computed against that chunk is correct and
useless. It does not touch `ask` or `hint_*`, which receive no chunk at all.

**§9.3's recall has a ceiling of 45% that has nothing to do with the model.**
Edge extraction only asks the model about pairs that survive a filter: A must
precede B in the text, and the two must appear within N sections. Measured
against our hand-annotated graph on the real chapter, that filter passes **30 of
66** true prerequisite edges at the shipped window of 2. No extraction run can
score above that, however good the model is, so the ceiling belongs beside the
recall figure rather than being discovered when the number comes back low.

Widening the window does not rescue it. 1/2/3/4 sections give 23/30/32/35 edges,
and at an **infinite** window it stops at 49 of 66 — **74.2%**. That residual is
not a knob: 17 edges are missed because the chapter names the dependent concept
*before* its prerequisite, usually where a section heading announces a topic and
the body introduces the parts afterwards. The window is a tunable; the ordering
assumption is a wall.

It was 21% before we ran the pipeline on real text. Comparing sections alone
discarded every pair whose two concepts appear in the *same* section, and 34 of
our 66 edges are exactly that — a textbook introduces several related concepts
in one section, in order, and section-level position cannot see that order. We
now resolve position within the section. We would not have found this from a
test fixture, because a fixture has one concept per section by construction.

**This paragraph said 59% and 39 of 66 until day 8, and that is its own
finding.** Those figures were written by hand in the commit that first ran the
pipeline on real text — before `eval/graph_quality.py` existed to compute them.
The chunker then changed two commits later, and when the eval was finally built
it measured 45%. Nothing connected the two: the prose was not derived from the
eval, so it could not go stale *visibly*. The reproducible number is whatever
`python -m eval.graph_quality` prints today, and the figure in the eval's own
closing advice is now interpolated from the measurement rather than typed,
because that sentence had hardcoded 0.59 and was still asserting it in the
output of the tool that disagreed.

**The answer monitor's similarity metric misses synonym paraphrase, and that is
the biased direction.** §6 specifies embedding cosine; embeddings are a
dependency we do not have, so the implemented metric is the maximum of a
stemmed, stopword-stripped token cosine and character-trigram containment. That
catches morphological variants and reordered phrasing. It does not catch a
restatement built from different words — "the sender backs off, cutting its
allowance in half once the path shows strain" scores 0.06 against the answer it
paraphrases.

This matters more than a generic "approximate metric" caveat, because
reconstruction *means* restating in the model's own words. The metric is
therefore weakest precisely where the phenomenon is strongest, so the reported
parametric-reconstruction rate is not merely a lower bound: it is biased
downward in the direction of the thing being measured. Treat it as a floor, and
do not report it as an estimate of the true rate.

**Every §9.1 figure before day 5 was measured on one item.** This is the most
serious error we have made and it invalidated an earlier draft of this section,
so it is stated first and in full.

`run_dialogue` built each dialogue from a fresh student state with an identical
initial theta map. `next_node()` is deterministic on that map, `_pick_item()`
returns the first unused item on the chosen node, and a guard confined each
dialogue to its opening item so the ladder would not reset mid-measurement. The
three interact: every dialogue opened on the same node, drew the same item, and
stopped there. Sixty dialogues produced 360 probes over **one** item out of 101.

The reported n=200 was therefore 200 draws of the *student's* random number
generator against a single fixed narrowing — not 200 samples of the item bank.
The number had no sampling relationship to the bank it was generalised to, and
no confidence interval over items existed to be computed.

It was found by trying to compute that interval. The cluster bootstrap reported
`items=1`, which is the signature of the defect rather than an artefact of the
method. Nothing else would have caught it: all 179 tests passed throughout,
because every one of them asserted on the *shape* of the eval output — keys
present, rates within [0,1], arms labelled — and a rate computed over one item
has exactly the same shape as a rate computed over a hundred.

Two consequences we want on the record. The earlier claim that the
partial-knowledge advantage "was +26 points on the day-2 fixture and is +12
points on the chapter graph", which we attributed to the synthetic graph having
a more informative lit region than a real one, was **not a graph-shape effect at
all**: it was two different single items. That explanation is withdrawn. And the
headline inverted once the bank was actually sampled — see below.

**Corrected §9.1**, over the **scored** bank — 69 items, of which the 52
`node_click` items are the stratum reported here (n=138 dialogues, 95%
percentile cluster bootstrap over items, 2000 resamples).

Two things changed since the version of this table that stood a day ago, and
both moved the numbers against us. It pooled `node_click` with `edge_click` at a
time when edge items were unsolvable by construction and scored a guaranteed
zero, so every cell was diluted; and it drew on 101 items including the 32 whose
anchor determines their own answer, which are now excluded from mastery. The
superseded figures are not reproduced — they were measured over a population we
no longer claim.

| arm | zero | partial | adversarial |
|---|---|---|---|
| product configuration | .125 [.067, .192] | .308 [.221, .404] | .288 [.202, .385] |
| isolated visual channel | .038 [.010, .077] | .163 [.096, .240] | .288 [.192, .385] |
| verbal channel only | .010 [.000, .029] | .202 [.115, .288] | .183 [.115, .260] |
| no hints at all | .038 [.010, .077] | .260 [.183, .356] | .240 [.164, .327] |

Marginal over the no-hints baseline, paired on item:

| arm | condition | marginal | 95% CI |
|---|---|---|---|
| product configuration | zero | **+.086** | [+.019, +.164] |
| product configuration | partial | +.048 | [−.067, +.173] |
| product configuration | adversarial | +.048 | [−.058, +.164] |
| isolated visual channel | zero | +.000 | [−.058, +.058] |
| isolated visual channel | partial | −.096 | [−.192, +.000] |
| isolated visual channel | adversarial | +.048 | [−.086, +.183] |
| verbal channel only | zero | −.029 | [−.067, +.010] |
| verbal channel only | partial | −.058 | [−.192, +.077] |
| verbal channel only | adversarial | −.058 | [−.173, +.067] |

**A claim we bolded a day ago does not survive this.** The isolated visual
channel's adversarial marginal was reported as **+.070 [+.010, +.130]** —
significant, and the one cell that let the visual channel look like it beat the
verbal one on its own. On the scored `node_click` stratum it is +.048
[−.086, +.183] and crosses zero. **We are not claiming the visual arm won.**
It did not, on this bank, at this n.

The interval is a **cluster** bootstrap: it resamples items, not dialogues, and
pools all of a drawn item's probes. Resampling dialogues would treat repeated
draws on one item as independent evidence about the bank and report an interval
far narrower than the data supports. The marginal is paired — one item index is
drawn and both arms take that item's probes — so item difficulty cancels within
each resample as it does in the point estimate.

**What survives, and it is less than we claimed.** Exactly one marginal in the
entire grid is distinguishable from zero: the shipped configuration hands a
**zero-knowledge** student +8.6 points over no hints at all, CI [+1.9, +16.4].
The partial-knowledge marginal is +4.8 points with an interval crossing zero, and
so is the adversarial one. Every cell in the isolated-visual and verbal-only arms
crosses zero, in both directions.

The isolated visual channel at zero knowledge is +.000 — .038 against a .038
baseline. **The visual channel alone, with no verbal hint beside it, contributed
nothing measurable here.** Only the interleaved product configuration, which
uses both channels, separates from baseline at all.

This inverts the earlier story, and we hold the new framing more loosely than the old one deserved to be held. We previously reported that partial knowledge
extracts substantially more from a narrowing than zero knowledge does, and
called the direction more robust than the magnitude. On a properly sampled bank
the *reverse* is the only significant effect: the measurable leakage is to the
student who knows nothing, which is the student for whom a five-candidate lit
set is a genuine reduction from fifty. A partially-knowledgeable student had
already narrowed the field themselves, so the interface tells them less — that
is a coherent mechanism, and it is a better result for the thesis than the one
we lost, but we did not predict it and we are not going to present it as though
we had.

We are not treating the crossing-zero marginals as evidence of no effect. Over
52 node items the half-widths run around 6-7 points, and a real effect of 5
points would not be detected here. **"Crosses zero at n=52 items" is the claim;
"the visual channel does nothing" is not** - these arms are underpowered, not
null, and we report every row with its interval rather than the one that reached
significance. That cuts both ways, and this is the direction it cuts against us.

The pattern across the three - narrowing helping most where the student has
least, and mattering less once they have narrowed the field themselves - is the
sentence we would lead with, because it is a hint behaving the way a hint
should. But it rests on a corrected eval one day old, and only the
zero-knowledge interval is tight enough to carry a claim on its own. We would
want it reproduced on a second chapter before leaning on it.

**The effective candidate set is smaller than the policy floor.** `candidate_floor`
is derived from `max_guess_probability = 0.2`, so the ladder lights five nodes at
its terminal rung and the interface presents a nominal 1-in-5 guess. (That floor
is a policy bound set before the corrected eval, and the shipped `interleaved`
ladder does not reach it — only the `visual_only` arm lights 5. The screen below
measures the arm that does.) Measured
through the partial-knowledge student's region filter, only 3.45 of those five
survive as plausible: the remainder is the hash-ordered filler `candidate_order`
appends after the answer, its distractors and its graph neighbours. Effective
guess probability is **0.309 against a 0.20 ceiling**, and twelve items narrow to
two live candidates — the coin flip the configuration explicitly sets out to
avoid. Survivor distribution over 101 items: {2: 12, 3: 41, 4: 39, 5: 9}.

The measurement is conditional on our region filter being a reasonable model of
plausibility, which is the same construct caveat that applies to the
partial-knowledge student above. It is not conditional on anything about the
model, and it is a property of the narrowing schedule rather than of any item.

**Mastery is measured through a single modality, and that modality is the thing
under test.** Every scored item is now a node click or an edge click. MCQ was the
only scored type that was not a graph interaction, and we demoted it (below), so
θ is estimated entirely from what the student does on the graph.

This is a confound between **concept knowledge and interface fluency**. A student
who reads the layout well looks knowledgeable; a student who understands TCP
congestion control but has not built a mental model of *our particular picture of
it* looks weak, and the adaptive path will route them backwards through
prerequisites they already know. Worse for our purposes, the same channel carries
both the measurement and the intervention: §9.1 asks how much the narrowing gives
away, and mastery is estimated from performance on narrowed items. The two are
not independent, so a narrowing that helps a student answer also raises their
measured mastery, and we cannot fully separate "learned the concept" from "read
the hint".

We accepted it for one reason: the alternative was worse. The MCQ bank is
generator fixture (below), so keeping it scored would mean estimating θ partly
from items whose keys each answer 52 different concepts. **Narrow but honest
beats broad but corrupt**, and a confound we can name and bound is preferable to
a corruption we cannot see. A demo whose mastery numbers are wrong in a
*known* direction is still demonstrable; one whose numbers are wrong in an
unknown direction is not.

The honest scope of the claim, then: our mastery estimates describe *performance
on graph-mediated items*, and we do not claim they are a modality-independent
measure of concept knowledge. Restoring a second modality is a flag flip — the
MCQ items remain in the bank at `scorable: false` — so this is a property of the
current bank rather than of the architecture.

We would want two things before treating θ as a real ability estimate: a scored
item type that does not route through the graph, and a check that the two types
rank students similarly. Neither is in scope in four weeks, and we would rather
state the confound than let a reviewer with an assessment background find it.

**61% of the item bank is generator fixture, and it is now unscored.** 159 of 260
items are mcq, and those 159 carry **three** distinct (key, distractors) tuples:
`generate_items.py` cycles a three-element `MOCK_MECHANISMS` list with `k % 3`
under `BUILD_LLM=mock`, which is the default because `build.RealLLM` is
unimplemented. The same key is therefore the correct answer for 52 different
concepts, which cannot be true of any of them. The key is the longest option in
159/159 items against a chance rate of 25%, so pick-the-longest scores the entire
mcq bank with no domain knowledge.

§9.1 is unaffected: `visually_answerable` is exactly the 101 click items, whose
answers are node ids derived from the graph, and the mcq items are excluded from
the leakage subset by construction. Mastery **was** affected — §1.4 scores mcq —
which is why those items now carry `scorable: false` and contribute nothing to θ,
next-node selection or backtracking. They still appear in dialogue and still
teach; they move no number.

They are flagged, not deleted, so that a real bank is a flag flip rather than a
reconstruction of a third of the item bank under time pressure. `build/validate.py`
keeps the check at full strength and keys only its *severity* on consequence: a
non-distinct bank that feeds θ is an error, the same bank marked unscored is a
warning that prints on every build. Setting `scorable: true` restores the error
without anything in the validator being edited.

Nothing flagged this for four days. The ids were unique, the schema validated,
the counts were right and the DAG was clean — no check asked whether the items
were *different from each other*. See `numbers-that-looked-fine.md`; it is the same
failure class as the two recorded there.

**A set enumerated in prose drifted from the set the code produces, and the
gap was a crash on the least recoverable turn.** §5 specifies "six canned
fallback utterances, one per action". Seven things are passed to `_call2` as an
action: the six in the `Action` literal, plus `resolved_with_support`, which is
not an `Action` at all but is handed to Call 2 as one on a §6 layer 3 forced
reveal.

That seventh had no `prompts/` file. So a Call 2 timeout on a forced-reveal turn
raised `FileNotFoundError` out of the fallback handler — the one code path whose
entire purpose is graceful degradation. A fallback for the fallback, missing.

It is the same shape as the key-is-always-longest finding above: **a property
that was true by accident and encoded in a place nothing could check it
against.** "Six" was true when §5 was written and stopped being true the moment
`resolved_with_support` was added, and nothing anywhere held a list of actions
that Python could compare against a list of files. Prose cannot be asserted on.

Two things made it invisible for a fortnight. `mock_call2` never raises, so
`MOCK_MODE` cannot reach the handler; and `llm.call2` is never called without a
key, so neither can a keyless run. Every one of our tests was therefore
structurally incapable of executing the line. It would have run for the first
time on the day the key landed, on a forced reveal — the turn where the student
is already frustrated, the graph has already moved, and the tutor going silent
is worst.

The repair is not the missing file. It is that `tests/test_fallback_coverage.py`
now enumerates from `CALL2_FIDELITY`, the dict `turn.py` actually indexes when
it calls Call 2, so the set under test is the set the code uses rather than the
set a docstring remembers.

**The build-drift guard on `state.db` is correct exactly up to an uncommitted
tree, and that edge is the point.** Sessions carry a `code_fingerprint`, and
`Store.get` refuses one written by a different build — the mastery *values* were
computed by other logic even when the graph fingerprint still matches and every
key still resolves.

The fingerprint is `<short sha>`, or `<short sha>-dirty` when the tree is not
clean. Two different dirty trees therefore stamp identically, so **drift between
an uncommitted fix and its commit is exactly as unguarded as the gap this
closed.** That is a deliberate trade and not an oversight: a stamp that changed
on every keystroke would invalidate the running session on every edit and the
guard would be turned off within a day.

We state it as a boundary rather than a caveat because it is the third guard in
this system with that structure — correct up to a named edge, and dangerous only
if the edge is discovered by someone else. `RETRIEVAL_SCORE_FLOOR` is a claim
about a distribution and was a guess until the corpus existed. The graph
fingerprint catches content drift and is blind to code drift. This one catches
code drift and is blind to uncommitted code. Each is worth having; none is worth
mistaking for the general case.

**Latency figures come from a mock.** The two-call timing profile the interface
is built around was reproduced from configured delays, not measured against a
live model under load.

## One we cut deliberately

We did not run the matched-elimination comparison between visual and verbal hints
at equal excluded-node sets. It was in the original plan and we dropped it.

The reason is that it became a weaker version of a result we already had. That
comparison asks "is visual narrowing better than saying the same thing?" — it is
only tractable at fine granularity, since a verbal hint cannot name 38 excluded
nodes in one turn, and its most likely outcome was a null. The marginal-leakage
measurement answers a strictly better question: does the shipped configuration
give a partially-knowledgeable student anything beyond what they already knew?
That holds at every rung rather than only the deepest ones, and does not depend
on constructing an unnatural verbal hint.

We record it here rather than omitting it, because "we planned this and dropped
it for these reasons" is a stronger position than a reviewer noticing the gap.

## What would change our minds

- A second chapter with a different graph shape moving the marginal-leakage
  figure materially would mean the result is graph-specific, not method-specific.
- A human pilot in which students report using the dimming to *narrow their
  search* rather than to *identify the answer* would support the mechanism story
  the simulated students can only gesture at.
- An identity-leak audit of an existing published tutor finding nothing would
  weaken the generalisation in the leakage section considerably.
