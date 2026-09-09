# Representation blindness

*A guard names a field. The information travels in every representation of that
field's value, and the guard is silent about all of them. We hit this three
times in six days, and the fix — a fidelity ceiling per action rather than a
field whitelist — is the design contribution of this project.*

*This is a claim about contracts between components. It holds whatever generates
the text, and it generalises to any tutor with a non-verbal channel, because
that channel is precisely a representation no field list can name.*

---

## The mechanism

All three defects were invisible to a full, passing test suite. None was subtle
in retrospect. All three had the same structure:

> **The guard named a representation. The information was also present in
> another one.**

Here the answer has at least four representations, in decreasing fidelity:

    node id  →  node label  →  position in a lit set  →  size of a lit set

A field whitelist can only ever name the first. `ItemPublic` excluded `answer`
and admitted `node_id`; §5 excluded the answer string and admitted the label;
the fidelity ceiling permitted an edge item's `to` endpoint as strictly lower
fidelity than the answer, on a graph where it usually *is* the answer. Each
guard was correct about the thing it named and silent about the representation
carrying the same information.

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

## Instance 2 — representation, not field name

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

## Instance 3 — fidelity is a property of the data, not of the field

The ceiling below permits `ask` on an edge item to name **one** endpoint, the
`to`, on the reasoning that for an edge answer the answer is a *pair*: naming
one end is strictly lower fidelity than naming the edge, and the question
"which prerequisite links into X?" cannot be posed without X. All 49 edge items
have `node_id` as the `to` endpoint, and each item's own prompt already names it.

"Its own prompt already names it in 49 of 49 cases" was offered as the reason
the exposure is free. It is that. It is **also** the reason the item is broken,
and stating it only in the first sense hid the second.

A student told the `to` endpoint is not choosing among 73 edges. They are
choosing among the prerequisite edges that **end there**:

| candidates once the anchor is named | items |
|---|---|
| 1 — the anchor *is* the answer | **32 / 49** |
| 2 — a coin flip | 17 / 49 |
| 3 or more | 0 / 49 |

Median candidate count: **1**. The ladder had not been climbed down at all. A
"strictly lower fidelity" representation was, given this graph's structure,
fully determining — and no reasoning about the *field* could have revealed that,
because the collapse lives in the data.

> **Fidelity is not a property of the representation. It is a property of the
> representation *given the data*, and it has to be measured against the data
> rather than argued from the schema.**

`build/validate.py` now measures it: per edge item, the in-degree of the named
anchor, with the two buckets reported separately because they need different
repairs. At one candidate the guess rate is 1.0, and §7's logistic reaches
p = 1 only as `d_eff → -∞` — there is no difficulty value that represents
"free". Those 32 items are excluded from mastery (`scorable: false`, the same
mechanism and the same reversibility as the MCQ demotion). The 17 at two
candidates remain scored and are a bounded calibration problem.

The scored click bank is therefore **52 node + 17 edge = 69 items**, and that
is the population every mastery claim here generalises to.

The deviation itself stands: an unaskable item is worse than an anchored one,
and the `from`/`to` asymmetry with a test asserting both endpoints never arrive
together is a clean way to hold the line. What changed is that the anchor is no
longer described as costless — it is costless *against a bank whose edge items
were already giving it away*, and the bank is what needed fixing.

## The fix — a fidelity ceiling, not a field whitelist

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

## What we are not claiming

Three defects in one four-week project, found by the people who wrote the code.
There is an obvious selection effect in which bugs get noticed and written up,
and we did not run a study of anything.

What we can say is narrower: all three survived a test suite a reviewer would
have called adequate, and in every case the intuitive fix would have hidden the
problem rather than surfaced it — compare more strings, carve labels out of
§1.5, argue from the schema that one endpoint is half an answer.

The companion section, *[Numbers that looked
fine](numbers-that-looked-fine.md)*, covers a different failure class we hit
twice: evaluation code that produced well-formed numbers over nothing. The two
are worth keeping apart. This one is about contracts between components; that
one is about instruments that cannot register a result.
