# Walkthrough script — Saturday 2026-09-26

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
python -m server.preflight --expect-mock false     # must print "ready."
```

It checks clean `main`, absent `state.db`, `MOCK_MODE` as declared, and daily
token headroom. **If it says NOT READY, fix it — do not record.**

Provider decided at Thursday's rehearsal. The difference on camera is large:

| | Call 1 | Call 2 | one turn |
|---|---|---|---|
| Groq `gpt-oss-120b` / `20b` | **2.3s** p50 | not measured | — |
| local `qwen3.5-9b` / `gemma-4-e4b` | **56.8s** | **24.3s** | **~81s** |

Only the local pair has been timed end to end (n=1, day 19). Groq's Call 1 p50
is from day 12 and **its Call 2 has never been measured**, so the cloud row has
no turn total — do not assume one, time it at Thursday's rehearsal.

What is certain is the order of magnitude: **a 20-turn take is ~27 minutes
locally.** If recording locally, plan to cut between turns.

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

- **The opening question is vague.** `ItemPublic` carries `id`, `difficulty` and
  `scorable` — **no prompt.** §1.6 renders exactly one text field, so the
  question reaches the student only through the utterance, and Call 2 is
  deliberately denied the item. The first line is therefore something like
  *"Have a look at the map. Which node fits?"* **Narrate the actual question
  yourself** — that is a scripting job, not a bug to fix on Friday.
- **No backtracking early.** The session opens on a **root node**, which has no
  prerequisites, so there is nowhere to step back to. Backtracks appear only
  after the student has advanced and then failed twice.
- **Eight turns on one item forces a reveal.** The tutor gives the answer, marks
  it `resolved_with_support` and awards **zero** mastery. If it fires on camera,
  name it as a designed frustration cap, not a failure.

---

## If it breaks mid-take

- **Call 2 times out** → a canned per-action line appears. The graph has
  *already* moved, which is the point; carry on and mention the fallback.
- **Rate limited on Groq** → stop. Do not narrate a stall. `--report` will show
  what was left.
- **Anything else** → stop, `python -m server.preflight`, start a fresh take
  from a fresh `state.db`. Re-recording 3 minutes is cheaper than explaining an
  artefact.

---

## After the take

```bash
python -m server.preflight --report     # per-turn mean and max
```

Replace `TAKE_BUDGET` with the measured figure — it is provisional at 90,000 and
nothing has counted a real take. Then tag:

```bash
git tag -a demo -m "demo walkthrough recorded"
git push origin demo
```

**After the recording, not before.** The tag is supposed to mean "this commit is
the one on the video."
