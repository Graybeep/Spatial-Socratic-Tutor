# What our guards could not see

*This section is not about tutoring. It is about the guards - the tests and the
contracts - and it is here because we hit the same class of failure five times
in six days on a system we were actively looking at. Five independent instances
in one small project is not bad luck; it is a property of how systems with a
non-verbal channel get checked.*

*Instances 4 and 5 were found after this section was first drafted, by someone
reading the argument in it and asking what else it implied. That is the strongest
evidence we have that the pattern is real rather than three stories told
together.*

---

## The pattern

All five defects were invisible to a full, passing test suite. None was subtle
in retrospect. All five had the same structure:

> **The test asserted on the shape of a value. The defect was in a property the
> shape does not carry.**

A shape assertion — the key is present, the type is right, the float is in
[0, 1], the arms are labelled, no forbidden string appears — is the assertion
style that comes naturally, that reviewers ask for, and that linters and schema
validators encourage. It is also, for a class of defect that matters
particularly in LLM and evaluation code, structurally incapable of failing.

## Instance 1 — identity, not equality

`ItemPublic` is the whitelist of item fields the client may see. It deliberately
excludes `answer`, `answer_aliases`, `answer_spans` and `distractors`. It
carried `node_id`.

For a `node_click` item, **the answer *is* the item's node**. CLAUDE.md §3's own
worked example has `node_id: "tcp_slow_start"` and `answer: "tcp_slow_start"`.
Shipping `node_id` handed the answer to the client in the clear, for 204 of 250
items in the bank at the time.

Every leak test passed. They compared the serialised payload against a list of
forbidden strings, and `node_id` is not a forbidden string — it is a *different
field that happens to hold the same value*. The tests knew about equality of
text. The defect was one of **identity**: two fields that are the same thing in
this domain and different things in the schema.

A schema cannot express "this field and that field are the same referent". Only
a test that asks *what is this value, in the domain?* rather than *what does
this value look like?* can catch it.

## Instance 2 — coverage, not shape

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

## Instance 3 — representation, not field name

`ItemPublic` was fixed. The eval was fixed. Then Layer 1 — the answer monitor —
started firing on nearly every turn during an eval run, and the reason was that
**Call 2 was being handed the answer**, by a third route.

Two rules of the spec collide:

> **§1.5** Call 2 never receives the answer. Not the answer string, not the
> answer aliases, not the source chunk during `ask` or `hint_*`.
>
> **§5** Call 2 receives `action`, `hint_level`, focus node **labels**, last 2
> turns.

For a `node_click` item the answer *is* a node, so the node's label is an answer
alias — literally, appearing verbatim in `answer_aliases` in 52 of 52 such items.
Narrowing exists to leave the answer lit, so the answer's node is normally *in*
`focus_nodes`. §5 therefore instructs the implementation to pass a string that
§1.5 forbids. **The two rules cannot both be satisfied as written.**

Measured exposure, over 25 items driven to the turn budget:

| action | turns | carrying the answer label |
|---|---|---|
| `ask` | 125 | 80% |
| `hint_visual` | 65 | 78% |
| `hint_verbal` | 15 | 100% |
| `backtrack` | 64 | 100% |
| `advance` | 10 | 100% (legitimate, §5) |
| forced reveal | 3 | 0% (legitimate, §6 layer 3) |

The monitor caught 15.5% of turns. That number was the trap: **the guard screens
the output, but the breach was in the input.** 15.5% measured how often the
mock's canned lines happened to use a label they were handed. A live model told
to hint about a concept, and given that concept's name, would say it far more
often. The reassuring number and the dangerous quantity were different things.

## Instance 4 — a population half of which could not register a result

§9.1's simulated student chooses among the lit nodes and we compare its choice to
the item's answer. For a `node_click` item the answer is a node id. For an
`edge_click` item the answer is a **pair**, serialised `"from->to"`.

A node id can never equal `"from->to"`. So every edge item scored zero, on every
arm, at every rung, for every student condition — **49 of the 101-item
population, structurally incapable of being solved**, silently halving the
measured rate.

Correcting it moved terminal zero-knowledge leakage on the product arm from
**8.9% to 16.8%**.

This is instance 1's failure — one referent, several representations — reappearing
on the *measuring* side rather than the leaking side. The student could reason
about the graph perfectly well; it simply had no way to *express* an edge. Every
provenance check passed, because coverage counted items **probed**, not items
**answerable**: all 101 were sampled, and 49 of them were being asked a question
in a language they could not answer in.

> Coverage asks whether you looked at the whole population. It does not ask
> whether the instrument can register a result on every member of it.

## Instance 5 — a threshold calibrated against nothing

Guard layer 4 refuses to answer when retrieval finds no chunk above
`RETRIEVAL_SCORE_FLOOR`. That floor was `0.35`.

It was chosen while `data/chunks.json` did not exist. With no corpus,
`search()` returned `None` for every query and the tutor refused everything —
which is the correct behaviour for an empty corpus, is documented at length in
`server/retrieval.py` as such, and is indistinguishable from the failure that
was waiting underneath it.

When the real chapter landed, in-domain queries scored 0.12–0.37 against
section-level chunks of 2,000–17,000 characters. The gate refused **100% of
them**. The *ranking* had been correct the whole time: "slow start congestion
window cold start" ranked section 6.3.2, Slow Start, first. The threshold threw
the correct answer away and the tutor said the chapter did not cover it.

Recalibrated against the corpus that now exists:

| population | n | score |
|---|---|---|
| in-chapter, node label + definition | 52 | min **0.1185**, median 0.2094 |
| adjacent networking (DNS, BGP, Ethernet, TLS) | 8 | max **0.0786** |
| far out-of-domain | 4 | max 0.0625 |

At `0.10`, 52 of 52 in-chapter queries retrieve and 0 of 12 negatives do.

The general form: **a threshold is a claim about a distribution, and a threshold
set before the distribution exists is a guess wearing a decimal point.** Nothing
in the codebase distinguished the two, and the surrounding comment was unusually
thorough — which made it read as more considered than it was.

## The unifying claim

Five instances, and the pattern is sharper than "test more carefully":

| | the guard compared | the defect lived in |
|---|---|---|
| `ItemPublic.node_id` | strings | **identity** — two fields, one referent |
| §9.1 one-item sample | shapes | **coverage** — what was sampled |
| Call 2 answer label | field names | **representation** — one answer, many forms |
| edge items unsolvable | items probed | **expressibility** — what the instrument can register |
| retrieval floor 0.35 | a number's presence | **calibration** — the distribution it was set against |

> **In a system with a non-verbal channel, the same information has multiple
> representations, and every guard written against one representation is blind
> to the others.**

Here the answer has at least four representations, in decreasing fidelity:

    node id  →  node label  →  position in a lit set  →  size of a lit set

A field whitelist can only ever name the first. `ItemPublic` excluded `answer`
and admitted `node_id`; §5 excluded the answer string and admitted the label.
Both whitelists were correct about the field they named and silent about the
representation that carried the same information.

**The contract has to be a fidelity ceiling per action, not a field whitelist.**
That is what we implemented (`CALL2_FIDELITY` in `server/turn.py`):

| action | ceiling | Call 2 receives |
|---|---|---|
| `ask` | safe label | a label only if it cannot be the answer |
| `hint_visual` | count | cardinality, no identities |
| `hint_verbal` | count | cardinality plus the answer's *category* |
| `backtrack` | count | cardinality only |
| `advance`, `explain` | labels | full identities, legitimately |
| forced reveal | labels | full identities, §6 layer 3 |

Answer-alias exposure on `ask`/`hint_*` went from 78–100% to **zero**, and the
monitor's hit rate on those actions from 15.5% to 0%.

## Why this is worth more than the leak it closed

The fidelity ceiling makes the project's thesis **true by construction rather
than by measurement**.

"The tutor helps by showing less" was, before this, a claim about behaviour that
the architecture did not enforce — Call 2 *could* express the answer in words
during a hint, and we were measuring how often it did. After it, Call 2 has no
representation of the answer available during a hint at all. It is handed an
action, a hint level and a number. The claim is now a property of the wiring,
and every leakage figure reported afterwards describes a system that *cannot*
name the answer while hinting, rather than one that was observed not to.

It also cleans up the monitor. Because Call 2 sees no answer label on
`ask`/`hint_*`, a Layer 1 hit on those actions is now unambiguously **parametric
reconstruction** — the model producing the answer from its own weights, given
only a count. That is a genuinely interesting number and it is now measurable in
isolation. Hits on `advance`/`explain` are reported separately and are not
reconstruction at all; they are the monitor observing an action doing its job.
Pooling the two, as the old statistic did, produced a figure that meant nothing.

We report the reconstruction rate as **not yet measured**: it is 0% against the
mock, but a mock has no weights to reconstruct from, so that figure is a
property of the fixture and not of any model.

## One deviation, recorded

The per-action ceiling above did not initially distinguish the *arity* of the
answer, and applied strictly it made 49 of the 101 scored items unaskable. For a
node answer the label is the whole answer, so withholding it costs only phrasing.
For an edge answer the answer is a *pair*, and the question — "which prerequisite
links into X?" — cannot be posed without naming X. Under the strict rule, 32 of
36 edge `ask` turns received no anchor at all, leaving Call 2 to ask "which one
is it?" about an unspecified edge.

So `ask` on an edge item may name **one** endpoint, never both. In all 49 edge
items `node_id` is the *to* endpoint, so the unknown is which prerequisite links
into it; naming the *to* end is strictly lower fidelity than the answer and is
the anchor the item was authored around — its own prompt names it in 49 of 49
cases. Naming the *from* endpoint remains forbidden, and a dedicated test asserts
that both endpoints never arrive together, which no per-label check would catch
since each one alone looks permissible.

We record this as a deviation rather than folding it into the rule, because it is
the kind of exception that widens if it is not written down.

### The justification was backwards, and the correction is a finding

"Its own prompt names the *to* endpoint in 49 of 49 cases" was offered as the
reason the exposure is free. It is that. It is *also* the reason the **item** is
broken, and stating it only in the first sense hid the second.

A student told the *to* endpoint is not choosing among 73 edges. They are
choosing among the prerequisite edges that **end there**. So we measured that,
per item, and put the check in `build/validate.py`:

| candidates once the anchor is named | items |
|---|---|
| 1 — the anchor *is* the answer | **32 / 49** |
| 2 — a coin flip | 17 / 49 |
| 3 or more | 0 / 49 |

Median candidate count: **1**. Claimed difficulties on determined items run as
high as 0.85. Since MCQ was demoted to unscored, these 49 items are half of
everything that can move mastery at all, and `difficulty` feeds `d_eff` directly
in §7's update — so a miscalibrated edge item does not merely mis-score itself,
it moves θ the wrong distance on every observation.

One consequence has no calibration fix. At one candidate the guess rate is 1.0,
and §7's logistic reaches p = 1 only as `d_eff → -∞`; there is no difficulty
value that represents "free". Those 32 items need re-authoring or exclusion.
Only the 17 at two candidates are a difficulty problem.

**The deviation stands.** An unaskable item is worse than an anchored one, and
the `from`/`to` asymmetry with a paired test is a clean way to hold the line.
What changes is that the anchor is no longer offered as *costless*: it is
costless *against a bank whose edge items were already giving it away*, and the
bank is what we now say needs fixing.

This also separated a number that had been pooling two questions. In §9.1, at
the terminal rung:

| condition | `edge_click` | `node_click` |
|---|---|---|
| zero-knowledge | 16% | 17% |
| partial-knowledge | **84%** | **30%** |
| adversarial | 82% | 25% |

The 84% is the *item* leaking, not the interface. The control that settles it:
in the `verbal_only` arm nothing dims — the lit set stays at all 52 nodes — and
edge items still solve at 82%. **A rate that does not move when the narrowing is
removed was never measuring the narrowing.** `node_click` does move across arms
(17% / 6% / 4% at zero knowledge) and is what §9.1 now reports as its headline.

Pooled, the partial-knowledge figure sat at 52–56% in all three arms, making
them look indistinguishable. That was the edge items washing the arm differences
out of a comparison the whole evaluation exists to make.

## Why this class is worse here than elsewhere

Three properties of LLM-tutor evaluation make it unusually exposed:

**The outputs are plausible by construction.** A leakage rate of 0.21 looks
exactly like a leakage rate of 0.21. There is no crash, no type error, no
obviously wrong value to notice. Conventional software fails loudly; a broken
eval fails by producing a number.

**The population is implicit.** "We ran 200 dialogues" names the observation
count, not the sampled population. Dialogues are the thing you loop over, so
they become the thing you report, even when items are the thing you generalise
to. The mismatch is invisible in the output.

**Simulated students collapse silently.** Our students filter candidates by
graph region. On prose MCQ options that filter matches nothing, falls through,
and picks uniformly — measured at .245/.253/.253/.249 across four options. A
screen built on that policy would have flagged 159 of 159 items "ambiguous" and
reported it as a finding about item quality. The measuring instrument had
degenerated to a coin, and nothing in its output said so.

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
many observations — the exact signature of instance 2), and silently
incomplete coverage on a run that claims completeness. Deliberate subsampling
stays legal via `expect_full=False`, because the goal is not to forbid partial
coverage but to forbid partial coverage that nobody declared.

The assertion is one line per eval and would have caught instance 2 on day one.
It also caught a live third case immediately: the documented `--n 60` covers
60 of 101 items — 59% — while looking like a complete run. The default is now
two dialogues per item.

For instance 1 the corresponding rule is narrower but the same in spirit: a
whitelist over a leak surface must be tested against **identity**, not string
equality — for each item, assert that no serialised field *equals the answer's
referent*, whatever that field is named.

## What we are not claiming

We did not run a study of evaluation harnesses. This is five defects in one
four-week project, found by the people who wrote the code, and there is an
obvious selection effect in which bugs get noticed and written up.

What we can say is narrower and we think still worth stating: all five defects
survived a test suite that a reviewer would have called adequate; four of the
five were found by accident while doing something else, and the fifth was found
by taking this section's own argument seriously and asking where else it
applied; and in every case the intuitive fix would have hidden the problem
rather than surfaced it - compare more strings, bootstrap the loop variable,
carve labels out of §1.5, widen the student's answer set, nudge the threshold
down until something passes. If that generalises even weakly, published
leakage and learning-gain figures from systems of this shape deserve a question
that is rarely asked of them: **not "what is the number" but "what was it
computed over, and how would you know."**
