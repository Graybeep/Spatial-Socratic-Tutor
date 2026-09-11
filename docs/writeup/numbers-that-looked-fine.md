# Numbers that looked fine

*Evaluation code that ran, passed its tests, and produced well-formed numbers
over nothing. Three instances, one shared property: **the output had valid shape,
and no test asserted on the sampling underneath it or on the distribution of
scores it was aggregating.***

*This is a different failure class from [representation
blindness](representation-blindness.md), and worth keeping apart from it. That
one is about contracts between components — a guard naming one representation of
a value while the information travels in another. This one is about
instruments: a measurement that cannot register a result, and says nothing
about that in its output.*

---

## Why this class is hard to see at all

Conventional software fails loudly. A broken evaluation fails by producing a
number.

**The outputs are plausible by construction.** A leakage rate of 0.21 looks
exactly like a leakage rate of 0.21. There is no crash, no type error, no
obviously wrong value.

**The population is implicit.** "We ran 200 dialogues" names the observation
count, not the sampled population. Dialogues are the thing you loop over, so
they become the thing you report, even when items are the thing you generalise
to. The mismatch never appears in the output.

## Instance 1 — the sample was one item

§9.1 measures effective leakage across four arms and three student conditions,
reported at n=200 dialogues.

Every dialogue was built from a fresh student state with an identical initial
theta map. `next_node()` is deterministic on that map. `_pick_item()` returns
the first unused item on the chosen node. A guard confined each dialogue to its
opening item so the hint ladder would not reset mid-measurement. The three
compose: every dialogue opened on the same node, drew the same item, and stopped
there.

**Sixty dialogues produced 360 probes over one item out of 101.** The reported
n was 200 draws of the student's random number generator against a single fixed
narrowing. The number had no sampling relationship to the bank it was
generalised to.

All 179 tests passed. Every one asserted on the shape of the eval output. **A
rate computed over one item has exactly the same shape as a rate computed over a
hundred**: a float in [0, 1], under the right key, in a dict with the right arms,
with a plausible-looking `n` beside it.

It was found only because we went to compute a confidence interval, resampling
items, and the cluster bootstrap returned `items=1`. Had we bootstrapped
*dialogues* — the intuitive unit, and the one most published work would use —
the interval would have come back tight, symmetric, entirely plausible, and
completely fictitious. **The naive version of the fix would have concealed the
bug more thoroughly than having no interval at all.**

## Instance 2 — half the population could not register a result

§9.1's simulated student chooses among the lit nodes, and we compare its choice
to the item's answer. For a `node_click` item the answer is a node id. For an
`edge_click` item the answer is a **pair**, serialised `"from->to"`.

A node id can never equal `"from->to"`. Every edge item scored zero — on every
arm, at every rung, for every student condition. **49 of the 101-item
population, structurally incapable of being solved.**

Correcting it moved terminal zero-knowledge leakage on the product arm from
**8.9% to 16.8%**.

Every provenance check passed, because coverage counted items **probed**, not
items **answerable**. All 101 were sampled. Forty-nine of them were being asked
a question in a language they had no way to answer in.

> Coverage asks whether you looked at the whole population. It does not ask
> whether the instrument can register a result on every member of it.

### The demonstration

This is the part a reader can verify without trusting our account of the code.
Once edge items were answerable, we split §9.1's rate by item type and ran it
across all four arms, at the attempt-1 rung (the rung with full *n* in every
arm). Partial-knowledge student:

| arm | lit nodes | `edge_click` | `node_click` |
|---|---|---|---|
| product configuration | 12.0 | **84%** | 30% |
| isolated visual channel | 12.0 | **82%** | 25% |
| verbal channel only | 52.0 | **82%** | 25% |
| no hints at all | 52.0 | **80%** | 21% |

The `edge_click` column does not move. In the last two arms **nothing is
narrowed** — the lit set is all 52 nodes — and edge items still solve at 82%
and 80%. In the last arm there are no hints at all.

**A rate that does not move when the narrowing is removed was never measuring
the narrowing.** It was measuring the `to` endpoint each item's own prompt gives
away, which is a property of the item bank and identical in every arm.

The `node_click` column does move. **The figures to carry away are the scored
ones** — 69 items, the population every §9.1 claim generalises to:

| arm | `node_click`, zero knowledge, scored bank |
|---|---|
| product configuration | **12.5%** |
| isolated visual channel | 3.8% |
| verbal channel only | 1.0% |
| no hints at all | 3.8% |

The isolated visual channel lands **exactly on the no-hint baseline**. Only the
interleaved product arm separates from it, at +8.6 points [+1.9, +16.4], and
that is the single marginal in the whole grid distinguishable from zero. Full
intervals in [limitations.md](limitations.md).

On the demonstration run above — all 101 items, including the 32 determined ones
— the same column reads 17% / 6% / 4% / 2%. **That is a tidier ordering than the
truth, and we are stating it second on purpose.** It is not §9.1's result and
must not be quoted as one; it exists only to complete the contrast this section
is making. Reproduce it with `python -m eval.adversarial --population
answerable`.

The contrast is what both versions agree on, and it is all this section needs:
one column is flat because it is reading the item bank, the other varies with
the arm because it is reading the interface.

The pooling did real damage in the meantime. With the edge items mixed in, the
partial-knowledge figure sat at 52–56% **in every arm**, making the four arms
look indistinguishable — the comparison the whole evaluation exists to make,
washed out by items answering a different question.

## Instance 3 — the drift test had a blind spot shaped like the drift

The two above are evaluations. This one is a **test**, and that makes it the
worst of the three: it is the instrument written specifically to catch a class
of problem, failing to register an instance of exactly that class.

`tests/test_client_types_match.py` exists to catch the server and the client
disagreeing about the wire. It compares the TypeScript interface's field names
against `model.model_fields`, and it has caught real drift.

`TurnResponse.session_complete` was then changed from a stored field to a
pydantic `@computed_field`, derived from the new `session_state` so the two could
not contradict each other. Computed fields are **absent from `model_fields` and
present in every payload**. So the test's view of "what the server sends" silently
lost a field that the server still sends, on every response.

What it would have reported is the part worth dwelling on. Not "a field is
missing" — it would have said the *client* declared `session_complete` while the
server never sends it, and the obvious remedy for that message is to delete it
from the client. **Following the test's advice would have removed the one field
most of the client uses to ask whether the session is over**, and the suite would
have gone green on the way.

It was caught because the field set changed in the same commit and the failure
was read rather than satisfied. Nothing structural caught it.

The narrow fix is two lines: `wire_fields()` now returns
`model_fields | model_computed_fields`. The general one is the same lesson as the
fallback enumeration in [limitations.md](limitations.md) — **a test that derives
its expectation from a subset of the thing it is checking will pass on exactly
the cases that subset omits.** `model_fields` was not wrong; it was one of two
places a field can live, and the test knew about one.

We record this separately from the schema change that exposed it. The schema
change was routine. A drift detector that cannot see one of the two kinds of
field it is meant to detect drift in is a fact about our test coverage, and it
would still be true if `session_state` had never been added.

## Adjacent, and the same shape: a constant calibrated against nothing

Not an evaluation, but the same shape, and it cost the demo a whole capability.

Guard layer 4 refuses to answer when retrieval finds nothing above
`RETRIEVAL_SCORE_FLOOR`. That floor was `0.35`, chosen while
`data/chunks.json` did not exist. With no corpus, `search()` returned `None` for
every query and the tutor refused everything — correct behaviour for an empty
corpus, documented at length as such, and **indistinguishable from the failure
waiting underneath it**.

When the real chapter landed, in-domain queries scored 0.12–0.37 against
section-level chunks of 2,000–17,000 characters. The gate refused 100% of them.
The *ranking* had been correct throughout: "slow start congestion window cold
start" ranks section 6.3.2, Slow Start, first. The threshold discarded the right
answer and the tutor said the chapter did not cover it.

Recalibrated against the corpus that now exists:

| population | n | best score |
|---|---|---|
| in-chapter, node label + definition | 52 | min **0.1185**, median 0.2094 |
| adjacent networking (DNS, BGP, Ethernet, TLS) | 8 | max **0.0786** |
| far out-of-domain | 4 | max 0.0625 |

At `0.10`: 52 of 52 in-chapter queries retrieve, 0 of 12 negatives do.

The mechanism was correct and the constant was a guess. **A threshold is a claim
about a distribution, and one set before the distribution exists is a guess
wearing a decimal point** — with no test capable of catching it until the real
data arrives.

## The fix, generalised

Patching each instance is not enough, because the next one will be somewhere
else. The generalisation we adopted:

> **Every eval output carries the size and identity of what it sampled, and
> coverage is asserted, not assumed.**

Not `rate: 0.21` but:

```json
"rate": 0.150,
"provenance": {
  "population": 101, "distinct": 101, "observations": 606,
  "unit": "items", "coverage": 1.0, "complete": true
}
```

`eval/provenance.py` builds these and `provenance.check()` refuses three
conditions: an empty population, a *degenerate* sample (one distinct member,
many observations — the exact signature of instance 1), and silently
incomplete coverage on a run that claims completeness. Deliberate subsampling
stays legal via `expect_full=False`, because the goal is not to forbid partial
coverage but to forbid partial coverage that nobody declared.

The assertion is one line per eval and would have caught instance 1 on day one.
It also caught a live third case immediately: the documented `--n 60` covers
60 of 101 items — 59% — while looking like a complete run. The default is now
two dialogues per item over the **scored** bank of 69.

It does not catch instance 2, and that is the honest limit of it. Provenance
records what was *sampled*; instance 2 was a failure of what could be *scored*.

So there is a second line, and `measure()` now runs it before reporting
anything (`check_strata_answerable`): **for every stratum of the population, the
student's own choice space must contain the answer for at least one item.**
Checked against the un-narrowed pool, so a legitimate 0% under heavy narrowing
never trips it. If a stratum cannot be answered at all, the run raises instead
of returning a rate.

A rate of exactly 0.000 over 49 items is not a finding. It is an instrument
reading zero because it is unplugged, and it looks identical to a real zero in
every output we produce.

## What we are not claiming

Two defects, one blind test and one adjacent constant, in one four-week project,
found by the people who wrote the code. There is an obvious selection effect in
which bugs get noticed and written up.

What we can say is narrower and we think still worth stating: all of them
survived a test suite a reviewer would have called adequate; and in every case
the intuitive fix would have hidden the problem rather than surfaced it —
bootstrap the loop variable, widen the student's answer set, nudge the threshold
down until something passes, delete the field the drift test says is unused.

If that generalises even weakly, published leakage and learning-gain figures
from systems of this shape deserve a question that is rarely asked of them:
**not "what is the number" but "what was it computed over, and how would you
know."**
