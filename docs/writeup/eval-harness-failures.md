# What our evaluation harness could not see

*This section is not about tutoring. It is about the tests, and it is here
because we hit the same class of failure twice in five days on a system we were
actively looking at. Two independent instances in one small project is not bad
luck; it is a property of how these systems get tested.*

---

## The pattern

Both defects were invisible to a full, passing test suite. Neither was subtle in
retrospect. Both had the same structure:

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

We did not run a study of evaluation harnesses. This is two defects in one
four-week project, found by the people who wrote the code, and there is an
obvious selection effect in which bugs get noticed and written up.

What we can say is narrower and we think still worth stating: both defects
survived a test suite that a reviewer would have called adequate; both were
found by accident while doing something else; and in both cases the intuitive
fix (compare more strings; bootstrap the loop variable) would have hidden the
problem rather than surfaced it. If that generalises even weakly, published
leakage and learning-gain figures from systems of this shape deserve a question
that is rarely asked of them: **not "what is the number" but "what was it
computed over, and how would you know."**
