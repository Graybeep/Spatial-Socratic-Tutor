# Identity leakage: a failure mode the evaluation literature cannot see

*Draft section. Numbers regenerate from `python -m eval.adversarial`; the
before/after counts come from `python -m build.validate`.*

---

## The claim

Giving a tutor a non-verbal channel gives it a matching non-verbal **leak**
channel, and every published leakage metric we are aware of is blind to it.

This is not a claim about our hint mechanism. It holds whether or not visual
narrowing turns out to help anyone learn.

## What happened

Our tutor is built against a written rule that only one text field may reach the
client, with a whitelist at the serializer and a test suite asserting no answer
string, alias, prompt or span appears in any response. Those tests were green
throughout.

They were green while the server shipped the answer, in the clear, on **204 of
250 items**.

The item schema carries a `node_id` — which concept the item is about — and an
`answer`. For a click-the-node or multiple-choice item **these are the same
value**. The project's own specification says so in its worked example:

```json
{
  "node_id": "tcp_slow_start",
  "answer":  "tcp_slow_start"
}
```

The public item payload included `node_id`, and the graph state named the same
node again as `current_node` so the interface could show which concept was under
study. A client wanting the answer did not need to guess from the dimming; it
could read the field.

Every leak test compared **strings**. `"tcp_slow_start"` is not the answer
*string* in any sense the tests recognised — the answer was a node identity, and
the payload named that identity in a different field. No amount of substring
matching sees this.

## Why it survived three weeks of people thinking about nothing else

The failure is structural, not careless.

Leakage in a text tutor means *the answer text appears in the utterance*. That
definition is complete for text tutors, because in a text tutor the answer only
exists as a string. Every metric in the surrounding literature inherits that
definition, and so does everyone's intuition, including ours.

The moment the tutor gains a non-verbal channel, the answer acquires a second
existence — as an **identity**: a node id, a coordinate, a highlighted region, a
selection. The verbal leak channel is guarded. The identity channel is not, and
nothing prompts you to look for it, because the concept has no name in the
literature you are working against.

We did not find this by auditing. We found it by building an adversarial
simulated student and asking what a maximally-informed client could already read
from the wire. That question is not one a string-comparison metric ever poses.

## What we changed

- `node_id` removed from the public item payload.
- `current_node` suppressed while an item whose answer is on the graph is open.
  It is still sent for items whose answer is a proposition rather than a node —
  the majority of a well-built bank — so the "where we are" affordance survives
  where it is safe.
- The invariant moved into the **build pipeline**, not the test suite: no item
  may be marked answerable-on-the-graph while anything in the turn payload
  identifies its node. A test only checks the mix of items the current fixture
  happens to have; the pipeline check runs against whatever data is in front of
  it, including a chapter nobody has written yet.
- Two tests that compare identities rather than substrings.

## Why this generalises

Any tutor that can point has this failure mode:

| system | the identity channel |
|---|---|
| concept graph | node id, dimmed set, "current concept" marker |
| diagram or canvas | highlighted region, selection bounds, layer visibility |
| code editor | cursor position, folded ranges, gutter marks, scroll target |
| map or timeline | viewport extent, zoom target, pin set |
| document reader | scroll offset, highlighted span, page number |

In each case there is a field that means "where we are" and is indistinguishable,
to the student, from "here is the answer". In each case a text-based leakage
metric reports zero.

The general form of the check is: **for every field the client receives, ask
whether it identifies the answer under any encoding, not just as text.** That is
a different question from the one the literature asks, and it needs asking once
per output channel.

## Honest limits of this section

- Found in our own system, in mock data, by us. We have not audited anyone
  else's system and make no claim about the frequency of this bug in the wild.
- The generalisation table above is reasoning by analogy, not evidence.
- The fix is verified by construction and by test, not by a human trying to
  exploit the interface.
