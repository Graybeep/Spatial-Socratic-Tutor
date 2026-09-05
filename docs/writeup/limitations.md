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

**Curated graph.** The concept graph was built by an automated extraction pass
followed by a human correction pass, and we report extraction quality *before*
correction precisely so the automated number is not confused with the graph we
actually used. The comparable published systems also use curated graphs. This is
a limitation of the demonstration, not a hidden one, but it means we have not
shown the pipeline works end-to-end on an arbitrary chapter.

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
