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

**`answer_spans` is empty for every item, so span masking is untested.** §3
specifies character offsets of the answer inside the source chunk, and §5 masks
those spans before a chunk is handed to Call 2 on `advance` and `explain`. The
graph was hand-authored from the chapter rather than extracted from a stored
copy of it, so there is no chunk file to offset into and no offsets to record.

The masking code path therefore has never run against a real span. We are not
claiming it works; we are claiming the retrieval gate above it works, which is
the coarser and more important of the two — Call 2 receives no chunk at all on
`ask` and `hint_*`, which is where leakage would matter. Masking only ever
mattered for the two actions that are *meant* to explain. If a chapter file
lands, populating spans and testing the mask is a contained piece of work.

**§9.3's recall has a ceiling of 59% that has nothing to do with the model.**
Edge extraction only asks the model about pairs that survive a filter: A must
precede B in the text, and the two must appear within N sections. Measured
against our hand-annotated graph on the real chapter, that filter passes 39 of
66 true prerequisite edges at the shipped window. No extraction run can score
above that, however good the model is, so the ceiling belongs beside the recall
figure rather than being discovered when the number comes back low.

It was 21% before we ran the pipeline on real text. Comparing sections alone
discarded every pair whose two concepts appear in the *same* section, and 34 of
our 66 edges are exactly that — a textbook introduces several related concepts
in one section, in order, and section-level position cannot see that order. We
now resolve position within the section. We would not have found this from a
test fixture, because a fixture has one concept per section by construction.

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

**Corrected §9.1, over the visually-answerable bank (101 items, n=200
dialogues, 95% percentile cluster bootstrap over items, 2000 resamples):**

| arm | zero | partial | adversarial |
|---|---|---|---|
| product configuration | .090 [.055, .131] | .150 [.100, .207] | .130 [.085, .179] |
| isolated visual channel | .030 [.010, .055] | .130 [.084, .183] | .165 [.105, .228] |
| verbal channel only | .020 [.005, .040] | .125 [.079, .176] | .080 [.040, .126] |
| no hints at all | .010 [.000, .025] | .110 [.065, .160] | .095 [.055, .144] |

Marginal over the no-hints baseline, paired on item:

| arm | condition | marginal | 95% CI |
|---|---|---|---|
| product configuration | zero | **+.080** | [+.040, +.124] |
| product configuration | partial | +.040 | [−.010, +.090] |
| product configuration | adversarial | +.035 | [−.020, +.090] |
| isolated visual channel | adversarial | **+.070** | [+.010, +.130] |
| isolated visual channel | zero | +.020 | [−.005, +.050] |
| isolated visual channel | partial | +.020 | [−.040, +.080] |
| verbal channel only | zero | +.010 | [−.015, +.035] |
| verbal channel only | partial | +.015 | [−.040, +.065] |
| verbal channel only | adversarial | −.015 | [−.070, +.041] |

The interval is a **cluster** bootstrap: it resamples items, not dialogues, and
pools all of a drawn item's probes. Resampling dialogues would treat repeated
draws on one item as independent evidence about the bank and report an interval
far narrower than the data supports. The marginal is paired — one item index is
drawn and both arms take that item's probes — so item difficulty cancels within
each resample as it does in the point estimate.

**What survives, and it is less than we claimed.** Exactly one marginal in the
shipped configuration is distinguishable from zero: the narrowing hands a
**zero-knowledge** student +8.0 points over no hints at all, CI [+4.0, +12.4].
The partial-knowledge marginal is +4.0 points with an interval crossing zero,
and so is the adversarial one.

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
101 items the half-widths run around 5 points, and a real effect of 3 points
would not be detected here. **"Crosses zero at n=101 items" is the claim; "no
leakage to partially-knowledgeable students" is not** - the partial and
adversarial arms are underpowered, not null, and we report all three rows with
their intervals rather than the one that reached significance.

The pattern across the three - narrowing helping most where the student has
least, and mattering less once they have narrowed the field themselves - is the
sentence we would lead with, because it is a hint behaving the way a hint
should. But it rests on a corrected eval one day old, and only the
zero-knowledge interval is tight enough to carry a claim on its own. We would
want it reproduced on a second chapter before leaning on it.

**The effective candidate set is smaller than the policy floor.** `candidate_floor`
is derived from `max_guess_probability = 0.2`, so the ladder lights five nodes at
the terminal rung and the interface presents a nominal 1-in-5 guess. Measured
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
were *different from each other*. See `eval-harness-failures.md`; it is the same
failure class as the two recorded there.

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
