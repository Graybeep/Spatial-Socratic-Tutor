# When the measuring apparatus is the thing that is broken

*Four cases from days 12–18. Each one produced a **confident, specific,
plausible verdict about the tutor** while the fault was in the code doing the
measuring. Two of the first three were plausible enough that we acted on them before
noticing.*

This is a different failure from the ones in
[numbers-that-looked-fine.md](numbers-that-looked-fine.md), and the distinction
is worth keeping. There, evaluation code ran correctly over a population that was
not what we thought it was — a rate over one item, reported as a rate over a
hundred. The number was *empty*. Here the number is *wrong in a specific
direction*, and it points at the system under test rather than at the harness.
An empty result invites the question "over what?". A wrong-but-specific result
invites agreement.

It is also, we suspect, the most transferable thing in this report. Anyone
building an evaluation harness for a model will hit it, because the harness is
written in a hurry, by the person who most wants the result, and is the one part
of the pipeline nothing else checks.

---

## Case 1 — the tutor reported our bug and we filed it as a hallucination

**The verdict we drew:** the model hallucinates about the interaction. Reading
§9.5's thirty diagnoses, one said:

> *"the student keeps offering text instead of clicking… reading the definition
> aloud is not a valid move"*

The simulated student clicks. It is a `random.choice` over node ids. So this was
a confabulated interaction — the model inventing a student behaviour that had
never occurred, in the field a human is asked to trust.

**What was actually true:** `Student.choose` returns a node id, and the driver's
`_response` fell through to `StudentResponse(type="text", text=pick)` on any turn
where the server expected prose. On those turns the student really did send text
instead of clicking. The tutor's report was **accurate**, and more grounded in
the interaction than our reading of it was.

It reached only 2 of 40 turns, which is exactly why it survived: a fault that hit
every turn would have been obvious, and a fault that hit none would have been
harmless. Two turns is enough to generate one quotable diagnosis and not enough
to look like a pattern.

**What it would have cost.** "The tutor hallucinates about the interaction" was
on its way into this report as a finding about the model.

## Case 2 — a case that said three turns and showed one click

**The verdict we drew:** the model cannot recognise a correct answer. The
constructed-case probe includes `answered_correctly`, whose history is a single
click on the right node. On `qwen/qwen3.8-27b` it came back `stuck` twice — 0/2
admissible on the least ambiguous case in the set. We reported that.

**What was actually true:** the `Case` dataclass defaults `turns_on_item=3`, and
`answered_correctly` inherited it. So Call 1 was told *"three turns on this
item"* and shown *one* click. Its own diagnosis said so:

> *"Three turns in with no clear right answer…"*

That is a correct reading of the context we built. The model was answering a
question about an incoherent history, and we scored the answer as a failure to
recognise a correct click.

**Why this one is the most dangerous of the first three.** The result was *directionally
consistent with a finding we already believed*. §9.5 had just shown the diagnosis
was uncorrelated with the student; "it cannot even recognise a correct answer"
fits that story so neatly that it reads as confirmation rather than as an
anomaly. A result that contradicts your prior gets audited. A result that extends
it gets written down.

## Case 3 — a verdict over zero observations

**The verdict we drew:** printed verbatim by the probe —

> `DOES NOT SEPARATE a scattered guesser from a prerequisite confusion:`
> `two unambiguously different students, one distribution. The diagnosis is not`
> `reading the history.`

**What was actually true:** every call in that run had failed with
`HTTP 429 DAILY quota exhausted`. There were no observations at all. The verdict
was computed as `scattered != prereqs`, and two empty distributions compare
equal, so "no data" and "identical distributions" were the same value.

This one we caught immediately, because `n=0` was printed on the line above. It
is in this list anyway, because catching it depended on a human happening to read
a column — and the sentence underneath it was already written in the voice of a
finding, ready to be pasted into a slide where the `n` column would not travel
with it.

---

## What the first three have in common

None of them is a bug in the tutor. All three produced output in the register of
a result: specific, causal, and about the system under test. And in all three the
harness was more confident than the evidence, in a direction that happened to be
interesting.

The common mechanism is that **a probe has two jobs and only one of them is
tested**. It must exercise the system, and it must be a faithful description of
what it exercised. The first job fails loudly — a broken probe usually crashes.
The second fails silently and produces prose.

## The fix, and why it generalises

Two rules, both cheap, both now in the codebase as tests rather than as
intentions.

### 1. Internal consistency assertions on every constructed case

A probe that tells the model one thing and shows it another is not measuring the
model. So the invariants of the *construction* are asserted before any call is
made:

```python
def test_every_case_declares_as_many_turns_as_it_shows_clicks(store, probe_items):
    for case in DC.CASES:
        clicks = len(_clicks(store, item, kinds[case.name]))
        assert case.turns_on_item == clicks
```

and, for the two cases whose whole purpose is to contrast:

```python
def test_the_two_contrasting_cases_share_no_nodes(store, probe_items):
    assert not (scattered & prereq)
```

That second one caught a real fault before it ever ran: the first draft let
`Packet Flow` appear in both the "scattered guesser" and the "prerequisite
confusion" histories. Had it run, it would have reported *"cannot discriminate"*
from two histories that were not different — Case 3's failure mode, but with data
in it, and therefore unfalsifiable by looking at an `n` column.

These tests need no API key, run in milliseconds, and are the only part of the
harness that checks the harness.

### 2. Three-valued verdicts

Any comparison that can be blocked must be able to say so. `True` / `False` /
`None`, where `None` renders as `NOT MEASURED` and explicitly disclaims being a
finding:

```
  NOT MEASURED - one or both contrasting cases returned nothing.
  This is not a finding about the model. A verdict needs both
  distributions; with either empty there is nothing to compare.
```

This is the same refusal `eval/leak_monitor.py` already made for §6.1, where it
prints `NOT MEASURABLE` rather than `0.00%` over mock turns. We had built the
pattern once, understood why it mattered, written it up — and then wrote a
two-valued verdict into the next probe anyway. The lesson did not transfer on its
own; it transferred when it was made a test.

## What this does not fix

Consistency assertions catch a probe that contradicts *itself*. They do not catch
a probe that is coherent and still measures the wrong thing — a constructed
history that is internally consistent but unlike anything a real student would
produce. Nothing here defends against that except reading the cases, and the
scripted-student limitation in
[diagnosis-readthrough.md](diagnosis-readthrough.md) is exactly that
vulnerability left open.

Two further harness faults from the same days are deliberately **not** in this
list, because they are operational rather than epistemic: printing the sheet to a
Windows cp1252 stdout killed a completed thirty-field run at its last step, and
the turn log could not name which model wrote a diagnosis. Both cost time and
neither produced a false claim. The distinction is the point of this document.

---

## Case 4 — a partitioned table with a pooled headline (found day 18)

`eval/leak_monitor.py` exists because pooling `logs/turns.jsonl` across builds
reports 3.94% parametric reconstruction from a bug that is fixed. Its docstring
says so, its per-build table partitions on the `code` fingerprint, and the whole
first third of the module is an argument for why that matters.

**Its HEADLINE pools anyway.** Asked for §6.1 on day 18, it printed
`0 / 3,334` over 25 arms — every *real* arm in the file, spanning builds that
predate both of the fixes that made the monitor able to see, plus
`ac2fc28 <eval:adversarial:*>`, the day-13 accidental live run that
`docs/schedule.md` records in as many words as **not real-model evidence**. The
clean population for that question was 34 checks on one build.

What makes this worth a case rather than a bug report:

- **The number was not wrong.** `0 / 3,334` is a true count of hits over turns.
  It is a well-formed rate over a population assembled by no one, which is the
  failure mode [numbers-that-looked-fine.md](numbers-that-looked-fine.md) is
  about, occurring *inside the instrument written to prevent it*.
- **The guard and the summary disagreed and neither noticed.** The partitioning
  is real and correct; it simply does not reach the line a reader quotes. A
  defence that holds in the table and lapses in the headline is worse than no
  defence, because the table is what persuades you the headline is safe.
- **It would have inflated n by 98×** and tightened a reported bound from 8.4%
  to something near 0.1%, in the direction that flatters the system.

**The fix, and a note on how it was first made.** The initial response was a
documentation fix — quote the per-build partition in §5.5, state that the
headline is not quotable — chosen because day 18 is inside week 3 and
`CLAUDE.md` §11 says a week that overruns cuts from the bottom rather than
borrowing. That was the wrong call for this defect, and it lasted a few hours.
A summary line that a reader will quote is not made safe by a caveat elsewhere
telling them not to; the whole failure here is that the safe-looking table is
what licenses trust in the unsafe line.

`leak_monitor.headline` now reports **one build**, defaulting to the current one,
and names it in the output. Pooling still exists behind `--pool-builds`, because
the pooled figure is occasionally what you want and hiding it would just move the
problem. Three tests pin it, including a regression for a bug found while making
the change: `measure()` reuses the name `build` for each record's own stamp, so
the parameter was clobbered and the headline silently scoped itself to whatever
the last line of the file happened to be.
