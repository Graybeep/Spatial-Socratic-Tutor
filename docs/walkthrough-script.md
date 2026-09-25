# Walkthrough script — Wednesday 2026-09-23

*Three minutes. Built around **narrowing and pointing**, which show immediately
and are what §12 says the project contributes. Not around mastery, which at demo
length is invisible.*

Every number below was measured, not estimated. Sources are named so a claim on
camera can be checked afterwards.

---

## The one-sentence thesis, said at the top

> *LLM tutors leak answers because their only way to help is to say more. This
> tutor helps by showing less: it narrows a concept graph visually instead of
> explaining.*

Everything in the take serves that sentence. If a segment does not, cut it.

---

## Before you press record

```bash
python -m server.preflight --expect-mock true      # must print "ready."
```

It checks clean `main`, absent `state.db`, `MOCK_MODE` as declared, and daily
token headroom. **If it says NOT READY, fix it — do not record.**

## The provider question is settled: record in MOCK_MODE

`.env` is set to `MOCK_MODE=true` for the take. That removes every risk the
recording could not absorb, now that the move to 09-23 left no rehearsal day:

| | resolved by recording in mock |
|---|---|
| Which provider? | none — no model is called |
| Groq Call 2 never timed | irrelevant; nothing to time |
| ~81s/turn on local models | gone — the mock paces at **0.9s + 1.4s = 2.3s/turn** |
| `TAKE_BUDGET` still provisional | no tokens spent at all |
| Rate limit mid-take | impossible |

**A 20-turn take is about 46 seconds of waiting.** It plays in real time.

### Say out loud that the tutor's words are canned

This is the one thing mock mode obliges you to disclose, and it costs nothing
because the report already argues it:

> *"The sentences you're hearing are templates — there's no model running. The
> narrowing is the real thing: it's computed from the graph and the hint ladder,
> and it's identical whether a model writes the words or not."*

That is true by construction and is exactly why §9.1 is reported as a
mock-utterance result: **the visual arm's narrowing is deterministic and does not
depend on what Call 2 writes.** Said plainly it is a design point. Left unsaid
and later noticed, it reads as a demo that quietly faked its tutor.

**Do not claim a live model is reasoning on camera.** If asked, the real-model
path is one environment variable and the report's numbers come from it.

---

## The spine: three beats

### Beat 1 — the map, before anything happens (0:00–0:25)

Full graph, 52 nodes, all lit. Say what it is: one chapter, 52 concepts,
prerequisite edges, **frozen layout — the nodes never move.**

> *"The layout is frozen on purpose. If nodes moved when the student improved,
> they'd lose the spatial memory that makes the map worth having."*

### Beat 2 — the narrowing, which is the whole demo (0:25–1:40)

Answer wrong, or say nothing. **On the very next turn the map goes 52 lit to
12.** Measured; it is turn two every time.

> *"I got it wrong. Watch the map — not the text."*

Let it land in silence before reading the utterance. **The graph changes before
the sentence exists**: it reacts on Call 1's return, and Call 2 streams into an
already-changed screen. That ordering is the architecture, so let the camera see
it.

Then get it wrong again: **12 → 9 lit.** Say the count out loud both times.

> *"Forty nodes just stopped being candidates, and the tutor did not say a word
> about any of them. You cannot name forty exclusions in one sentence. That's
> the reduction the verbal channel can't perform at all."*

That is claim 2, and it holds by construction rather than by measurement — the
strongest thing you can say on camera.

### Beat 3 — pointing as the answer (1:40–2:30)

Click the right node. The answer is a **click, not a sentence**: the graph is a
shared referent both sides can point at.

> *"The answer wasn't typed. It was pointed at. That's the contribution — the
> visual as something the dialogue refers to, not decoration beside it."*

Then the honest closing beat, on screen for ~20 seconds.

---

## What NOT to promise

- **Do not say "watch the graph light up as they learn."** Measured: a flawless
  student masters **0 nodes in 15 turns, 1 in 20, 3 in 40.** At demo length,
  mastery colour does not visibly change. It is slow by construction — §7 fixes
  the constants and they are not being retuned for a demo.
  If mastery colour must appear on camera, **open from a returning student with
  prior state.** That is honest — it is what the sqlite state is for — and it is
  not the same as retuning the scorer.
- **Do not claim the visual arm beat the verbal one.** It did not. The measured
  result is one cell in a grid of nine: +8.6 points for the shipped
  configuration against a zero-knowledge student, CI [+1.9, +16.4]. Say that
  number or say nothing about it.
- **Do not imply the graph was extracted.** It is hand-authored. §4 permits it
  and the comparable published systems do the same — say so plainly if asked.

---

## Three things that will happen, so they don't surprise you

- **The current question is now visible.** The September 25 interface update
  composes the authored prompt into `utterance` after Call 2 and pins it in the
  question card. Read that question on camera, then demonstrate a wrong choice,
  narrowing, confirmation, and the next question. The archived leakage numbers
  precede this update; do not describe them as measurements of this interface.
- **No backtracking early.** The session opens on a **root node**, which has no
  prerequisites, so there is nowhere to step back to. Backtracks appear only
  after the student has advanced and then failed twice.
- **Eight turns on one item forces a reveal.** The tutor gives the answer, marks
  it `resolved_with_support` and awards **zero** mastery. If it fires on camera,
  name it as a designed frustration cap, not a failure.

---

## If it breaks mid-take

In mock there is no network, no key and no rate limit, so the whole class of
provider failures cannot occur. What is left:

- **Eight turns on one item** → a forced reveal fires. Designed, not broken;
  name it as the frustration cap and carry on.
- **The session ends** → the circuit breaker cut it after repeated forced
  reveals. Start a fresh take rather than explaining it.
- **Anything else** → stop, `python -m server.preflight --expect-mock true`,
  start a fresh take from a fresh `state.db`. Re-recording 3 minutes is cheaper
  than explaining an artefact.

---

## After the take

**Nothing to measure.** A mock take spends no tokens and writes no ledger lines,
so `python -m server.preflight --report` will correctly report an empty ledger
and **`TAKE_BUDGET` stays provisional at 90,000**. That is a real gap, not an
oversight: no take has ever been costed, and the first real-model session is
what would close it.

Tag it:

```bash
git tag -a demo -m "demo walkthrough recorded"
git push origin demo
```

**After the recording, not before.** The tag is supposed to mean "this commit is
the one on the video."
