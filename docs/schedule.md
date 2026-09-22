# Schedule — dated commitments

*The plan lives in `CLAUDE.md` §11 and is not restated here. This is the list of
things that have a **date** and a **pass/fail**, so a slip is visible on the day
it happens rather than in week 4.*

Project start 2026-09-04. Week 1 is 09-04…09-10, week 2 09-11…09-17,
week 3 09-18…09-24, week 4 09-25…10-01.

---

## Booked

### Monday 2026-09-14 (day 11) — projector contrast test — **SLIPPED, not run**

> **Outcome, recorded 2026-09-15 (day 12): it did not happen.** The day passed
> and nobody ran it. Recorded as a slip rather than quietly rebooked, because
> this file's whole claim is that a slip is visible on the day it happens.
>
> **Rebooked into week 3 (2026-09-18…24)**, which is where §8 asked for it in
> the first place. So the *test* is not late. What is lost is the reason it was
> pulled forward: the half-day contingency below — change `NARROW_SCHEDULE`,
> re-run §9.1 — now falls **inside** week 3 instead of ahead of it, and week 3
> is integration week. Pulling it forward bought exactly that half-day and the
> slip spent it.
>
> Per `CLAUDE.md` §11, a week that overruns cuts from the bottom of the list; it
> does not borrow from the next week. If the contingency fires and week 3 will
> not hold it, the thing to cut is retrieval (§11 names it first), not the test.

**§8, pulled forward.** §8 asks for week 3; this was booked in week 2. Earlier is
the allowed direction, and it is cheap now that the instrument exists.

Run it:

```bash
open client/contrast-check.html        # standalone, no server needed
```

Full-screen on **the actual demo hardware and the actual projector**, then stand
where the back row will sit. Not a laptop screen — the whole point of §8 is that
opacity survives a good display and dies on a bad one.

**What is already known and does not need re-testing.** The three dimming
channels are implemented and are count-independent, so nothing about the number
of lit nodes changes per-node contrast. Composited against paper:

| | lit | dimmed |
|---|---|---|
| node outline | 17.19:1 (3px) | 1.53:1 (1px) |
| label | 17.19:1 | 1.13:1 |
| edge | 1.81:1 | 1.08:1 |
| fill @ mastery 0.5 | 2.52:1 | 1.18:1 |

The **3px ink outline carries the signal**; the fill barely contributes
(2.52:1 lit against 1.18:1 dim). If the projector crushes anything, watch the
stroke, not the colour.

**What is actually being tested, and it is not contrast.** The shipped
`interleaved` ladder bottoms out at **9 lit, not the 5 the floor implies** —
alternating narrowing and verbal rungs plus an 8-turn budget stop it there. Nine
lit nodes span **52% of the canvas** (five span 23%), with 25 dimmed nodes
interleaved among them.

So the question is coverage, not legibility:

- [ ] Can you locate the lit set **without hunting**, from the back of the room?
- [ ] Does it read as **one place to look**, or as scatter across half the map?
- [ ] At 9 lit, is the narrowing legible **as a narrowing** — does it feel like
      the map got smaller, or just like some nodes went grey?
- [ ] Compare against the 5-lit panel. If 5 is obviously better, that is a
      finding about `NARROW_SCHEDULE` or the turn budget, **not** about the
      dimming tokens.

**Fail condition and what it costs.** If 9 lit does not read as a focus, the fix
is the ladder, not the palette: either narrow faster (`NARROW_SCHEDULE`) or let
`interleaved` reach the floor. Both are config, both are §9.1 research variables,
and both need 9.1 re-run afterwards because the sweep is over exactly that curve.
Budget half a day. Doing this in week 2 is what buys that half-day.

**Record the outcome here**, pass or fail, on the day. An untested §8 and a
tested-and-passed §8 look identical in a repo three weeks later.

---

### Monday 2026-09-14 (day 11) — confirm-or-undo, watched by someone else — **still not booked**

> **Outcome, recorded 2026-09-15 (day 12): still not booked, and now overdue.**
> It was unbooked on 09-11 and it is unbooked on 09-15. Four days of being
> written down changed nothing, which is worth noticing: writing an item down
> is not the same as finding a person, and this one needs a person.
>
> It rides along with the projector test into week 3 — it is ten minutes at the
> same projector, after the contrast check. But it has now failed to be booked
> twice, so treat the week-3 slot as the last one. **If nobody is watching by
> the end of week 3, it goes into `limitations.md` as untested** and stops being
> a scheduled item. An assumption honestly labelled is worth more than a booking
> that keeps sliding.

**Open since week 2. Not booked as of 2026-09-11, and still not booked as of
2026-09-15.** Recorded here because an unbooked item that lives in someone's head
and a booked one look identical in a repo, which is the whole reason this file
exists.

The projector test above and this are two tests wearing one name, and only one
of them can be run by the people who built the thing:

| | question | who can answer it |
|---|---|---|
| render + dimming | does the 0.20/0.06 split survive the actual projector from the back row | **us** — it is a hardware question |
| confirm-or-undo | does someone who did not design the gesture understand what a click commits to *before* they commit to it | **not us** |

The second is unanswerable from the inside. We already know what a click means,
and that knowledge is exactly the variable under test. §8 calls confirm-or-undo
the only gate between a stray click and a permanent mastery penalty — a gate
nobody has watched a stranger use is an assumption with a UI on it.

**What it needs:** one person who has not seen the interface, ten minutes, at
the projector, after the contrast check. No script beyond "answer the tutor's
question" and no prompting. Watch for one thing:

- [ ] Does the click → **Confirm / Undo** step read as *"nothing has happened
      yet"*, or as *"this has been submitted"*? If they treat the click itself
      as the answer and the confirm as an acknowledgement, the gate is decorative
      and the fix is in the wording, not the logic.

**Nobody was booked by Monday morning** — that deadline passed on 2026-09-14 and
the item is still open. So the fallback this paragraph describes is now the live
plan, not a contingency: **if week 3 ends with nobody having watched it, say so
in the writeup** rather than letting it read as tested.
`docs/writeup/limitations.md` already lists a human pilot under *what would
change our minds*; an unwatched confirm-or-undo belongs in the same list, at a
much smaller scale.

---

## Standing dates

| date | day | what | state |
|---|---|---|---|
| ~~2026-09-14~~ | 11 | projector contrast test (§8) | **SLIPPED — not run.** Rebooked into week 3, above |
| ~~2026-09-14~~ | 11 | confirm-or-undo watched by a non-author | **SLIPPED — never booked.** Last slot is week 3, then it becomes a limitation, above |
| ~~2026-09-18…24~~ | ~~week 3~~ | ~~projector contrast test + confirm-or-undo~~ | **CLOSED UNRUN on day 19.** Both are now stated limitations, not open items. Reopen only if a live presentation is scheduled |
| ~~2026-09-22~~ | 19 | **API key cut** — resolved early, on day 12. See below | **MET, with a caveat** |
| ~~2026-09-18…24~~ | 12 | diagnosis read-through, 30 `diagnosis` fields (§9.5) | ~~**RUN, and it found something**~~ **INVALIDATED on day 13**: Call 1 was sent `role: text` for every past turn, so the model never saw a click. See [diagnosis-readthrough.md](writeup/diagnosis-readthrough.md) |
| ~~2026-09-16~~ 2026-09-21 | 13 → 18 | **repeat §9.5 on `gpt-oss-120b`**, the model the demo ships — now also the first §9.5 run in which the model can see the dialogue | **RUN AND COMPLETE**, 30/30 fields, five days late. See below |
| — | 12 → 18 | §6.1 parametric-reconstruction rate | ~~**0/60, reported as a bound.**~~ Withdrawn day 13, run later ruled inadmissible; **re-measured day 18 as 0/34**, one-sided 95% bound 8.4%. See below |
| ~~2026-09-17~~ | 14 | **dependency freeze** (§1.8), end of week 2 | **MET a day early**, on day 13 — enforced by a test, see below |
| ~~2026-09-25 → 09-26~~ **from day 19** | 19→ | ~~eval freeze: 24h before Sat 26~~ **SUPERSEDED: no eval runs at all from day 19. The numbers are final.** | in force |
| ~~2026-09-25~~ **2026-09-22** | ~~22~~ **19** | **feature freeze.** Tag `feature-freeze` | **DONE, three days early**, at `e71c6c5`. Demo-path fixes only from here |
| ~~2026-09-29~~ ~~2026-09-26~~ **2026-09-23 (Wed)** | ~~26~~ ~~23~~ **20** | **video walkthrough recorded.** Tag `demo` **after** the recording, not before | **TOMORROW** — script: [walkthrough-script.md](walkthrough-script.md) |
| ~~2026-09-24 (Thu)~~ | ~~21~~ | ~~rehearsal, then replace `TAKE_BUDGET`~~ | **OVERTAKEN**: the recording moved to 09-23, so there is no rehearsal day before it. Pick the provider and measure `TAKE_BUDGET` from the take itself |

Tags cut so far: `schemas-frozen`, `graph-frozen`, `loop-working`, `feature-freeze`.
Left: `demo`, after Saturday's recording and not before.

### 2026-09-15 (day 12) — a key arrived, and it is not an Anthropic key

The day-19 cut was written as *"no key → `MOCK_MODE` ships, §9.3 and §9.5 are
cut"*. A key landed on day 12, seven days early. It is a **Groq** key: it 401s
against `https://api.anthropic.com/v1/messages`, which is the API
`server/llm.py` was written to speak.

**What was done.** `server/llm.py` now speaks two wire formats behind
`LLM_PROVIDER` (§13.1 already put base URLs and model ids in config; the API
they are spoken to is the same kind of value). The *schema* does not move: both
providers are handed the same pydantic model under a forced tool call, and a
response that fails validation fails identically on either. No new dependency —
httpx was already there, which matters because §1.8 freezes dependencies at the
end of week 2 and this is day 12.

**What it changes in the writeup, and this must be said out loud.** The tutor
runs **`openai/gpt-oss-120b`** on Call 1 and `gpt-oss-20b` on Call 2, not Claude.
Call 1's model was chosen on measured diagnosis quality over real items, because
§9.5 hand-reads that field: 120b named the actual confusion where 20b said
"uncertain about the terminology" and omitted the answer node from its focus set.

**Three things the provider swap cost, all of them now fixed and none of them
config:**

- **`max_tokens=300` truncates the response before the tool call exists.**
  gpt-oss emits reasoning *first* — measured 534–580 completion tokens on Call 1
  where CLAUDE.md §5 budgets ~120. Groq reports this as "model did not call a
  tool", which reads like a capability problem and is not one.
- **A 429 was being retried instantly**, burning the whole retry budget inside
  the window the server had just asked us to wait out. It now has its own budget
  and honours `retry-after`.
- **`.env` broke the test suite.** With `MOCK_MODE=false` the suite began making
  paid network calls and hung on the rate limiter. Tests are now hermetic by
  force, not by convention.

**What is still constrained.** The free tier is 8,000 tokens/minute and one
Call 1 costs ~2,750 — about **two full turns per minute**. §9.5 (30 fields) and
§6.1 fit comfortably. A full §9.1 re-run against the real model does not: 12 arms
× 138 dialogues is days of wall clock, so **§9.1 stays a mock-utterance result**
and the report says so. That is defensible — the visual arm's narrowing is
deterministic and does not depend on what Call 2 writes — but it is a limitation,
not a footnote.

**And §5's latency figure is now stale.** "Call 1 is ~120 output tokens (~1s)"
was an Anthropic number. Measured on Groq: **p50 2.3s** to a validated decision.
The architecture claim is untouched — the graph still moves before any utterance
exists — but the number in the report needs re-deriving rather than re-typing.

[no-key-plan.md](writeup/no-key-plan.md) is no longer the expected path. It stays
as written: it is still the report if the key is revoked, and it cost nothing to
have had it ready.

### 2026-09-16 (day 13) — what a perfect run actually looks like

Measured, no key needed: drive the demo answering **every item correctly** and
count nodes crossing `MASTERY_THRESHOLD` (0.6).

| turns | nodes mastered |
|---|---|
| 5 | 0 / 52 |
| 15 | **0 / 52** |
| 20 | 1 / 52 |
| 40 | 3 / 52 |
| 60 | 9 / 52 |
| 150 | 23 / 52 |

**A three-minute video is roughly 15–25 turns.** In that window a flawless
student masters zero or one node, so §8's "mastery recolours nodes" is a change
the viewer never sees. 150 perfect turns reach 23 of 52 and the session still
does not complete.

**This is not a bug and the constants are not being changed.** Two correct
answers cross the threshold from a standing start, which is the intended shape —
§7 fixes `K_START`, `K_MIN` and `THRESHOLD`, and CLAUDE.md §0 says decisions
there are not re-litigated mid-implementation. The learning rate decays with
`n_obs` on purpose, and a demo that recoloured the graph in five turns would be
a demo of a scoring rule tuned for a demo.

**The consequence is for the script, and it points the right way.** §12 says the
contribution is *the visual as a shared referent — pointing as an answer, and
dimming as a non-verbal hint channel*. Narrowing is visible on **turn two**: the
map goes 52 lit to 12 lit before any text arrives. Mastery colour is secondary in
§8 and slow by construction. So:

- [ ] Script the walkthrough around **narrowing and pointing**, which show
      immediately and are what the project claims
- [ ] Do **not** promise "watch the graph light up as they learn" — at demo
      length it will not
- [ ] If mastery colour must appear on camera, open from a **returning student**
      with prior state rather than a fresh session. That is honest (it is what
      sqlite state is for) and it is not the same as retuning the scorer

One check worth doing before recording: an earlier arithmetic pass concluded that
the 35 nodes with a single scorable item could *never* be mastered, because one
correct answer reaches 0.56 against a 0.60 threshold. **That was wrong** — items
are re-served and re-scored, and 23 nodes reach mastery in the run above. The
arithmetic assumed one scorable item meant one scoring observation. Recorded
because the wrong version is the more plausible-sounding one.

### 2026-09-16 (day 13) — the dependency freeze, and what it closed

§1.8 closes dependencies at the end of week 2 (2026-09-17). It was never in the
table above, which is how a hard rule turns into a thing someone remembers on
day 15. Done a day early:

- **The declared set is the imported set.** Python: `fastapi`, `uvicorn[standard]`,
  `pydantic`, `httpx`, plus `pytest` for dev. Client: `react`, `react-dom`, and the
  Vite/TypeScript toolchain. Every third-party import in `server/`, `build/`,
  `eval/`, `tests/` and `client/src/` is one of these; nothing is declared and
  unused.
- **Versions are pinned exactly** to what the suite passed against on the day,
  in both `requirements.txt` and `client/package.json`. The lockfile's resolved
  tree did not move. The demo machine on day 26 installs what was tested, not
  whatever is newest — use `npm ci`, not `npm install`.
- **`tests/test_dependency_freeze.py` enforces it.** A new name in either
  manifest, or an import of anything undeclared, fails the suite. Version bumps
  are not blocked; new names are. The fix for a red test is not to edit the
  frozen set.

**What it closed, deliberately: PyMuPDF.** `build/chunk.py` has a `PdfChunker`
that imports it lazily. The chapter arrived as HTML, so there was never a PDF to
run it on, and it was not added before the door shut. `--pdf` is now a path that
exits with an explanation; `--html` is the one the frozen graph came from.

**Also closed, and worth saying in the writeup: React Flow.** CLAUDE.md §2 names
`src/Graph.tsx` as React Flow. The client draws raw SVG instead, and
`Graph.tsx`'s header says why: with frozen coordinates a graph library earns
nothing, and its default styling fights the dimming channels. That was a choice
made weeks ago; after today it is also not reversible.

### 2026-09-16 (day 13, evening) — the §9.5 re-run, and where the budget went

The re-run on `gpt-oss-120b` was started and did not finish. It is now
**tomorrow's first task**, on a fresh daily budget. In order:

- **Field 1 exposed a bug under every diagnosis ever measured.** Call 1 and Call 2
  received every past turn as the literal line `role: text` (fixed `1cfc74a`).
  §9.5's day-12 findings and §6.1's 0/60 bound are withdrawn in the writeup.
- **Run 2 stopped itself at field 12** on a Call 1 that called a tool named
  `commentary`; the new fallback refusal did its job. That 400 is now retried
  as a parse failure (`614d066`).
- **Run 3 reached field 15** and was killed by the OS for memory. Partial, not
  committed: `zero` → `guessing` ×6, `correct` agreed with the click 15/15.
- **The rest of the day's budget went to a mistake.** Checking whether §9.1 was
  affected by the reveal fix, a regeneration inherited `MOCK_MODE=false` from
  `.env` and sent 3,226 turns to Groq: 19 succeeded and exhausted the cap, the
  rest fell back to the mock. Those turns are in `logs/turns.jsonl` as
  `origin eval:adversarial:*`, build `ac2fc28`, `mock: false`, and are **not**
  real-model evidence. `eval.adversarial` now refuses a live model unless passed
  `--real-model`.

Tomorrow, with the browser closed:

```bash
LLM_DAILY_LIMIT_WAIT_S=600 python -m eval.diagnosis_readthrough --json $T/diagnosis_readthrough.json --sheet $T/sheet.md
```

### 2026-09-21 (day 18, later) — the prompt A/B, and a correction to this morning

`python -m eval.diagnostic_calibration --prompts current,pre-falsifiability`.
20 Call 1s, ~58k tokens, ~9 minutes. Raw:
[`eval/results/diagnostic_calibration.json`](../eval/results/diagnostic_calibration.json).

**Why it was run.** The §9.5 re-run earlier today was written up as the history
fix (`1cfc74a`) repairing the diagnosis. Checking the provenance killed that:
`516795d`, the Call 1 prompt rewrite, landed **2026-09-15 22:39** — an hour and
three quarters after the day-12 run finished. So day 12 used the old prompt, and
the day-12/day-18 pair moves prompt, history AND model at once.

**Result, same model and same fixed harness, prompt the only variable:**

| | current | pre-falsifiability |
|---|---|---|
| scattered clicks → `guessing` | 2/2 | **0/2** (`stuck`) |
| all clicks upstream → `confused_prereq` | 2/2 | **0/2** (`stuck`) |
| separates the two students | yes | **no** |
| `stuck` when `stuck` IS right | **0/2** | 2/2 |
| specific, all cases | 8/10 | 6/10 |
| `correct` boolean | 6/6 | 6/6 |

**The old prompt reproduces the day-12 degeneracy on a fully fixed harness.**
The history fix is therefore neither necessary nor sufficient for the reversal,
and the model change is not isolated at all. The prompt is the only variable
demonstrated to move this result. `report.md` §5.5 now carries the controls
table and §5.6 the corrected attribution.

**And the current prompt has a cost that a new case was built to find.** Where
`stuck` is the only defensible answer — three wrong free-text replies, no clicks,
so nothing for `guessing` or `confused_prereq` to read — the current prompt says
`guessing` 0/2 of the time correctly and the old one is right 2/2. Telling the
model `stuck` is the cheap answer made it unable to say `stuck` when `stuck` is
honest. Without that case the A/B was a clean 8/10-vs-6/10 win.

`n=2` per cell. Actionable before the demo, not quotable as a measurement.

**A second control turned up in the logs, and it points the same way.** Day 13's
run 1 (`7ba8078`, 4 turns) predates the history fix by four minutes and already
carries the new prompt — the one cell that separates prompt from history on the
day-12 side. With the history still broken it produced `guessing` on 2 of 4
turns with falsifiable reasoning, where day 12's old prompt managed 1 in 30. So
the two controls agree from opposite directions:

| | prompt | history | reaches for a specific state? |
|---|---|---|---|
| day 12 | old | broken | **no** — `stuck`/`on_track` |
| run 1 | **new** | broken | **yes** — `guessing` 2/4 |
| A/B arm B (day 18) | old | **fixed** | **no** — `stuck` to both |
| A/B arm A (day 18) | new | fixed | **yes** |

The prompt tracks the outcome in all four rows; the history fix does not. What
the history fix demonstrably changes is **grounding**: run 1's diagnoses are
well-reasoned about nothing (*"their recent inputs were text"* — an accurate
report of our own bug), run 2's name the nodes actually clicked.

**Day 12 is now withdrawn for cause, not merely superseded.** Its build is
`77b7e5d-dirty` — an uncommitted tree with no commit that restores it — and its
model was never logged. A number whose code and model cannot both be named was
never admissible, independently of any later run disagreeing with it.

**The model control is CLOSED, not scheduled.** `qwen3.8-27b` vs
`gpt-oss-120b` stays confounded and will not be resolved. The reason is that day
12 is withdrawn for cause, so the only comparison the control would serve is one
the report no longer makes; the live claims (run 1, arm A, arm B) are all
`gpt-oss-120b` already, so the model is held fixed across them by construction.
The cost is stated in report.md §5.6: nothing distinguishes "this prompt helps
`gpt-oss-120b`" from "this prompt helps models of this kind", and only the first
is claimed. **This frees the last model-dependent item before the eval freeze**,
so no live run is now required before Thursday 2026-09-24.

**No server hint floor, on evidence.** The stuck-only case was re-read from the
existing A/B logs (no new calls): on all 4 turns, both arms requested
`hint_visual`. Arm A mislabels the student (`guessing`, 0/2) but asks for the
same rung arm B does, so the mislabel costs the student no help. `ask` appears
only on the opening turn, where no response exists yet. A two-strikes server
floor would fire on turns that are already being hinted. If a future run shows
`ask` requested on a failing item, that is when it earns its place.

---

### 2026-09-22 (day 19) — a backtrack that never backtracked

Found while counting curriculum moves for §5.6's containment argument, from the
day-18 log, no new calls. Of 40 turns, **13 emitted a curriculum action and 12
moved the curriculum**: 6 `advance` the model also asked for, 6 `backtrack` the
server performed while the model asked for a hint, and **1 `backtrack` the model
requested, which moved nothing**.

*(This sentence said "13 moves" until later on day 19, which was the same
conflation the rest of the entry is about. See the day-19 recount entry below.)*

That last one could not be attributed, and chasing it found a hole.
`action = decision.requested_action`, so a Call 1 asking to step back got the
word and the prerequisite chunk while **nothing moved** — no `start_item`, no new
item, the student still on the node they were failing. Only the two-failure rule
(§7) ever moved the curriculum.

**Now:** a model-requested backtrack is honoured only if the target prerequisite
is below `MASTERY_THRESHOLD` — §7 backtracks to close a gap, and a mastered
prerequisite is not one. Otherwise it is refused and degraded to
`BACKTRACK_REFUSED_ACTION` (default `hint_visual`; the student is still on the
item and the rung has already been spent). The two-failure path is untouched.
Both paths tested, gate mutation-tested, and turns now log `backtrack_origin`
(`server` / `model` / `refused`) so the next count is attributable.

**The log end is held too, later the same day.** The gate tests assert on
`Phase1`, which is the deciding end of the wire; the count will read
`logs/turns.jsonl`. `_log` could have stopped writing the field, or written it
for the wrong turns, with every gate test still green — the day-18 problem
repeating silently in the place it was found. `tests/test_backtrack_origin_reaches_the_log.py`
drives complete turns and asserts on the written record: one case per origin,
`None` on a turn that moved nothing backwards, and the vocabulary pinned to those
four values so a fourth spelling is not a silent new bucket. Mutation-checked
both ways — field always `None`, and a refusal mislabelled as the model's.

**No eval re-run is needed for this** and none was done: the day-18 §9.5 and §6.1
figures are diagnosis and utterance measurements, and neither depends on which
rule moved the curriculum. The change is in the demo path, so it wants a manual
pass before the walkthrough — added to the projector-test session, which is still
unbooked.

---

### 2026-09-22 (day 19, later) — the recount, and a number that argued with itself

The day-19 entry above was written from a hand pass over the day-18 log. Writing
the tool that should have produced it found that the pass had made, in its own
reporting, the same conflation the bug was about: it counted turns that **emitted**
a curriculum action and called them turns on which the curriculum **moved**, then
said two sentences later that one of them moved nothing.

`eval/curriculum_moves.py` derives the split from `logs/turns.jsonl` — no key, no
network, no model call, so the eval freeze does not apply. It decides movement by
testing whether `item_id` changed within a session, rather than trusting the
action label, which is what makes the two numbers different at all.

| build | turns | emitted | moved | server overrode Call 1 |
|---|---|---|---|---|
| `18d220d` (day 18) | 40 | **13** | **12** | 6 of 12 moved |
| `77b7e5d-dirty` (day 12, withdrawn) | 40 | 12 | 12 | 11 of 12 moved |

The stationary turn is named rather than merely subtracted: `sess_88764468ce90`
turn 4, item stayed `itm_0021`. Results are committed under `eval/results/`.

**Three documents carried the old figure and now do not:** `report.md` §5.6 (the
containment argument), this file's day-19 entry, and
[diagnosis-readthrough.md](writeup/diagnosis-readthrough.md), whose override row
was the worst of the three — its two columns used *different denominators*, 12
moved against 13 emitted, in one side-by-side comparison. They coincide for day
12 and diverge for day 18, which is how it survived being read.

**It is recorded in `report.md` §6 as the seventh failure**, because the lesson
is that section's own closing question turned inward: the report asks what every
number was computed over, and did not ask it of a number computed by hand, once,
with nothing able to disagree.

**One limitation is stated rather than fixed, and it is narrower than first
written.** On records predating day 19, a §7 two-failure backtrack landing on a
turn where Call 1 also asked to step back is indistinguishable from a
model-initiated one, so `backtrack:model` is an upper bound **as a count of
requests**. That case is in the corpus (day 12, `sess_2acfcff9b419` turn 2).

It does **not** bound the move count. On pre-day-19 builds the only `start_item`
on a backtrack sits inside the two-failure branch behind a `consecutive_failures`
guard, so a model request moved nothing at all: **model-initiated moves are zero
by construction there, not bounded.** Any pre-day-19 move labelled `model` was
the server's two-failure rule with the model agreeing by coincidence. The first
version of this entry applied the bound to both counts, which was too weak in
the direction that matters.

The day-18 reading does not rest on either: its one `backtrack:model` turn was
stationary, and a two-failure backtrack always moves the item.

---

### 2026-09-22 (day 19, later still) — the demo path gets a flag, a ledger and a pre-flight

Three things, all on the demo path, all before Friday's feature freeze.

**`MODEL_BACKTRACK`, and it did not exist.** It was assumed to be on `main`
already; `git log --all -S MODEL_BACKTRACK` returns nothing, so the day-19 gate
had been shipping unconditional. It now exists and **defaults to false**: with
it off, every `backtrack` Call 1 requests degrades to `BACKTRACK_REFUSED_ACTION`
and only §7's two-failure rule moves the student backwards. The finer mastery
gate is still underneath and only runs when the lever is on.

Off is also the honest default for the report: **before day 19 a model request
moved nothing in any case**, so `false` is the behaviour every measurement was
taken under. Both settings are tested, and the gate is mutation-tested in both
directions (default flipped on; flag not consulted).

**A token ledger, because `STATS` counts calls and a quota counts tokens.**
`server/llm.py` now appends one line per provider response to
`logs/tokens.jsonl` — model, timestamp, prompt and completion tokens —
normalised across both wire formats. It is written **before** extraction, so a
refusal or an unparseable tool call is recorded at full cost; a ledger that only
recorded successes would under-report exactly the days that went badly. The
write can never raise.

**A pre-flight that fails loudly.** `python -m server.preflight` checks clean
`main` (not `-dirty`), absent `state.db`, `MOCK_MODE` against a *declared*
expectation, trailing-24h spend on the Call 1 model against `TPD_LIMIT` leaving
at least `TAKE_BUDGET`, and no model call in the last 24 hours. Each check
prints whether it passed or failed, because a pre-flight that only speaks up on
failure teaches nobody what it verified.

**The provider probe was considered and is not the budget check.** Groq's
`x-ratelimit-remaining-tokens` is the *per-minute* window and there is no daily
equivalent in the headers, so a probe would report a number that refills in
sixty seconds and say nothing about the limit that ends the day. `--probe`
exists, sends one token, and claims only that credentials and connectivity work.

**`TAKE_BUDGET=40000` is provisional and nothing has measured a take.** After
Thursday's rehearsal, `python -m server.preflight --report` gives per-turn mean
and max from the ledger, takes-per-day at `TPD_LIMIT`, and the minimum seconds
per turn at 8,000 TPM. Replace the default with the measured figure — a
pre-flight trusted against a guess is worse than no pre-flight.

**Kit for the human tests** is [human-tests.md](human-tests.md) (one page, both
tests, the reset commands, and the day-19 backtrack path to watch) and
[dim-values.md](dim-values.md) (the shipped tokens, and where to record what the
projector said). The dim tokens live in **two** files — `client/src/tokens.css`
drives the demo, `client/contrast-check.html` is what you tune against — and
nothing syncs them. They agree as of today; if the test moves a value and only
the test page changes, the finding is lost and the demo ships the old number.

---

### 2026-09-22 (day 19, evening) — a third provider, local, and the number that decides Thursday

Two offline models are on the demo machine, served by LM Studio on port 1234:
`qwen/qwen3.5-9b` and `google/gemma-4-e4b`. They remove the token constraint
entirely for offline work. **No default changed** — `LLM_PROVIDER` is still
`groq`, and the decision is Thursday's on measured numbers, not tonight's.

**It works, and the architecture did not have to bend.** Both models return a
valid `Call1Decision` under a forced tool call. One real turn, end to end,
against the live server:

| | model | latency | tokens |
|---|---|---|---|
| Call 1 | `qwen/qwen3.5-9b` | **56.8s** | 3,406 |
| Call 2 | `google/gemma-4-e4b` | **24.3s** | 1,947 |
| | | **~81s/turn** | 5,353 |

Against Groq's **2.3s** p50 on Call 1. No parse failures, no retries. Call 2
wrote *"Twelve are left; what do they have in common?"* — the count, not the
answer, which is what §5's split is for.

**§1.8 holds: no new dependency.** `httpx` already covers it. Three differences,
all small and all config:

- LM Studio **rejects the object form of `tool_choice`** (*"Supported string
  values: none, auto, required"*). `required` is equivalent here because each
  call defines exactly one tool — pinned by a test, because it stops being true
  the day a second tool is added.
- Path is `/v1/chat/completions`, not Groq's `/openai/v1/...`.
- No key, so `_invoke`'s credential guard is skipped for `LOCAL_PROVIDERS` and
  the pre-flight's daily-token check reports **"not applicable"** rather than
  passing — a local server has no quota to be short of, and "does not apply" and
  "passed" are different things.

The body, schema and extraction are Groq's, shared deliberately: a response that
validates on one validates on the other, so the two cannot drift into being
different contracts.

**Both providers ship, and the choice is the user's.** The repo goes to GitHub
with three providers behind `LLM_PROVIDER` — `anthropic`, `groq`, `local` — and
README's *Choose a provider* section is the entry point. The provider is named
`local`, not `lmstudio`: the same body works against any server exposing an
OpenAI-compatible `/v1/chat/completions` (Ollama, llama.cpp, vLLM), and
`LOCAL_BASE_URL` points at whichever is running. Renamed the same day it was
added, while no one outside this repo had used the old name.

**One trap found while documenting it.** `.env.example` pinned
`CALL1_MODEL=claude-opus-5` and five siblings. `_load_dotenv` uses
`os.environ.setdefault`, so anything set there beats the provider default
permanently — a user copying the example and switching to `local` would have
sent a Claude model id to their own server and got a 400, which is exactly the
opposite of being able to choose a provider. Those six are now commented, the
defaults resolve from `LLM_PROVIDER`, and a test fails if any is re-pinned.

**What this does NOT settle, and Thursday must.** ~81s/turn is the blocker, not
tokens. A 15–25 turn take is 20+ minutes of wall clock, most of it the viewer
watching nothing. §5's architecture claim survives — the graph still moves on
Call 1's return, before any utterance exists — but it moves 57 seconds in. And
every figure in §5.5, §5.6 and §9.5 is `gpt-oss-120b`/`gpt-oss-20b`: shipping
the demo on a model the report never measured is a documentation problem at
minimum. Rehearse both back to back and decide on that.

**Two caveats on tonight's numbers.** They are **n=1 per model**, on one
machine, with nothing else loaded — directional, not a benchmark. And an earlier
synthetic probe without graph context had qwen emitting focus ids that are not
real nodes; with the digest supplied it returned `tcp_slow_start` correctly, so
read nothing into the first result.

**One consequence for the freeze.** Its recorded purpose is that the recording
must not open on a machine whose daily budget went to an eval the night before.
A local provider has no daily budget, so if Saturday runs local that rationale
does not apply. The window is left as booked — it is a standing instruction and
not mine to void — but it should be revisited once the provider is chosen.

---

### 2026-09-22 (day 19, night) — the demo path, driven end to end

Run before Friday's freeze, because §11 asks that `main` be left in a state that
does not need a verification run afterwards. Mock mode, real `/session` and
`/turn`, no model call.

- **Client builds clean.** `npm run typecheck` and `npm run build` both exit 0;
  34 modules, 154 kB (50 kB gzipped).
- **Perfect student:** advances item to item, no narrowing — `advance` applies
  none by design.
- **Failing student**, which is what the walkthrough shows:

| turn | action | lit | dimmed |
|---|---|---|---|
| t0 | `ask` | 52 | 0 |
| t1 | `hint_visual` | **12** | 40 |
| t2 | `hint_verbal` | 12 | 40 |
| t3 | `hint_visual` | **9** | 43 |
| t4–t6 | `hint_verbal` | 9 | 43 |
| t7 | forced reveal → `advance` | — | — |

Four documented behaviours confirmed live rather than from tests: **narrowing
lands on turn two** (52 → 12, before any utterance), the `interleaved` ladder
**bottoms out at 9 lit, not 5** — the number the projector test is actually
about — the hint counter **caps at `HINT_MAX` 4** and never decreases, and the
**8-turn budget forces a reveal** and moves on.

**No `backtrack` appeared, and that is correct.** The session opens on a root
node, so `backtrack_target` has no prerequisite to return and §7's two-failure
rule has nowhere to send the student; the turn budget fires first. Checked
rather than assumed, because an absent backtrack and a broken backtrack look
identical in a trace.

---

### 2026-09-22 (day 19) — FEATURE FREEZE, tagged. Demo-path fixes only from here.

Brought forward from day 22. Tag `feature-freeze` at `e71c6c5`. **No eval runs
from here on: the numbers are final.**

**Fresh-clone test, because a grader will try that path first.** Cloned to an
empty directory, no `.env`, no key, README followed verbatim in a clean venv:

| step | time |
|---|---|
| `git clone` | 2s |
| `python -m venv` + `pip install -r requirements.txt` | 55s |
| `python -m build.validate` | 5s (0 errors, 8 warnings) |
| `python -m pytest` | 59s (537 passed) |
| `python -m server.main` → serving | 8s |
| `npm ci` + `npm run dev` | 18s |

**~90 seconds from clone to a served page**, 2.5 minutes including the suite.
It ran first try: `/health` 200, `/session` and `/turn` 200, the client shell
served on 5173, and **CORS preflight from `http://localhost:5173` accepted** —
the two-server dev setup's classic failure, checked rather than assumed. The
client falls back to `http://127.0.0.1:8000` with no client `.env`.

**Three README fixes it forced**, all because the text was accurate for someone
who already had the repo working:

- **No venv step.** §1.8 pins exact versions, and `pip install` into a populated
  environment will not downgrade what is there. Now the first instruction.
- **`build.validate` was described as "strict; must be clean".** It exits 0 and
  prints 8 warnings. A grader reads "must be clean", sees eight warnings, and
  concludes the install is broken. The README now states the expected output
  verbatim and says only `0 error(s)` matters.
- **No expected outputs at all.** Each command now says what success looks like.

**Pre-flight: the 24h eval-freeze veto is removed.** It conflated a calendar rule
with the only question a pre-flight can answer — *is there budget for this take*.
A run the night before is harmless if it left headroom and fatal if it did not,
and the headroom check already decides that. `TAKE_BUDGET` is now the single
gate, raised **40,000 → 90,000**: one measured turn cost 5,353 tokens, so a
20-turn take is ~107,000 and the old figure would have passed a pre-flight for a
take the budget could not hold. Still provisional — replace it with the first
take's measured figure.

---

### 2026-09-22 (day 19) — writeup: first page, and §6 regrouped by mechanism

**§6 no longer counts.** It ran "six failures... the sixth is... the seventh
is...", and a running tally invites the wrong question — *how many?* — instead
of the one that transfers: *what kind, and would it have happened to you?* It is
now four mechanisms, each with the instances under it and a **transferable
form** line:

1. **Two fields that differ in the schema and are identical in the domain** —
   101 of 260 items shipped the answer in the clear with the suite green.
2. **A well-formed number over the wrong population** — the one-item leakage
   rate, the 13-emitted/12-moved conflation, the mismatched denominators, the
   pooled builds. `eval/provenance.py` is the structural fix.
3. **The fix you just shipped is the most attractive explanation** — the day-18
   attribution error.
4. **The instrument was broken and reported confidently about the tutor** —
   cross-referenced to §7, which keeps its own count because "the harness was
   wrong four times" is a fact about the harness, not a way of grouping.

**A first page, before any argument.** Claims table with per-claim links; the
headline number **+8.6 points, 95% CI [+1.9, +16.4]**, stated immediately as
*one cell in a grid of nine* with the rest crossing zero; and the seven things
that would make a reader distrust the whole report — one chapter, curated graph
with no extraction run, simulated students, a baseline that is not silent, a
similarity metric biased downward exactly where the phenomenon is strongest,
**confirm-or-undo untested by any stranger**, and mock latency figures.

Limitations go on page one deliberately. A limitations section a reader reaches
on page nine has already done its damage.

Housekeeping the rewrite forced: §2 had repeated the first page's claims table
verbatim eighty lines later, so it now carries only the ordering argument; §7's
"the seven above" became a reference to §6's mechanisms; six in-page anchors
were wrong because `§` and em-dashes do not slugify the way I assumed. All
links, in-page and file, now resolve.

---

### 2026-09-22 (day 19) — the walkthrough script

Day 13 said *"script it around narrowing, not mastery"* and left it as a
checkbox. [walkthrough-script.md](walkthrough-script.md) is the script: three
beats over three minutes, every number in it measured rather than estimated.

**Three beats.** The frozen map (52 lit, and why the layout never moves); the
narrowing, which lands on **turn two** at 52 → 12 and again at 12 → 9, held in
silence so the camera sees the graph move *before* the sentence exists; and
pointing as the answer, which is §12's actual contribution.

**Three things it forbids on camera**, each because the measurement says so:

- **Not** *"watch the graph light up as they learn"* — a flawless student
  masters 0 nodes in 15 turns and 1 in 20. Mastery colour is invisible at demo
  length. Open from a returning student if it must appear.
- **Not** any claim the visual arm won. One cell in nine: +8.6, CI [+1.9, +16.4].
- **Not** any implication the graph was extracted. It is hand-authored.

**One thing found while writing it, and it is a scripting problem rather than a
bug.** `ItemPublic` carries `id`, `difficulty` and `scorable` and **no prompt**:
§1.6 renders exactly one text field, and Call 2 is deliberately denied the item,
so the item's actual question never reaches the screen. The opening line is
therefore generic — *"Have a look at the map. Which node fits?"* The presenter
narrates the real question. Worth knowing before Saturday rather than during it.

**A latency row was left deliberately empty.** Groq's Call 1 p50 is 2.3s from
day 12 and **its Call 2 has never been timed**, so the script gives no cloud
turn total and says to measure it Thursday. The local pair is timed end to end
(56.8s + 24.3s = ~81s/turn, n=1), so only the local figure carries a
20-turn estimate: ~27 minutes.

---

### 2026-09-22 (day 19) — the recording moved to tomorrow, and learner choice is future work

**Recording is 2026-09-23, not 09-26.** Third date this item has had
(09-29 → 09-26 → 09-23) and the first one that is inside 24 hours. Consequences,
because a date change that is not costed is a date change that surprises someone:

- **There is no rehearsal day.** Thursday's rehearsal was going to pick the
  provider on measured turns and replace `TAKE_BUDGET` from a real take. Both now
  have to happen *during* the take, or not at all. `TAKE_BUDGET` stays at its
  provisional 90,000.
- **Groq's Call 2 is still untimed**, so the cloud turn total is still unknown.
  The local pair is the only end-to-end measurement there is (~81s/turn).
- The eval freeze window was written as *the 24 hours before Saturday*. It is
  moot: no eval has run since day 19 and none will.

**Learner choice: the picker is rejected on a mechanism, not on taste.**
`next_node` returns the lowest-mastery node whose prerequisites are *all*
mastered. On a fresh session nothing is mastered, so the ready set is the graph's
**3 root nodes, and all three are in §6.1** (verified: `6.1.1`, `6.1.3`). A
student who picks §6.3 is returned to §6.1 by the first `advance`. It would be an
illusion of choice discarded on turn one.

**The version that works is a prior, not a position**, and is written up in
`report.md` §9: initialise the chosen section's prerequisite ancestors at
`MASTERY_THRESHOLD`, which makes its nodes ready without special-casing
selection, and let §7's prereq back-decay and two-failure backtrack correct the
claim when the student turns out not to know the skipped material. Existing
machinery, no new rule. **Not built before submission.**

**Upload stays cut, on measurements**: 30/66 prereq recall (45% ceiling), 17
edges missed because the chapter names a concept before its prerequisite, and an
MCQ key that is the longest option in 159/159 items. Prereq edges drive selection,
backtracking and decay, so a graph missing half of them disables the adaptive
path rather than degrading it.

---

### 2026-09-22 (day 19) — the take is recorded in MOCK_MODE

`.env` set to `MOCK_MODE=true` (gitignored, so this is a local change; the
committed default was already `true`). The move to 09-23 removed the rehearsal
day, and recording in mock removes every risk that day was meant to absorb:

| open question | resolved by |
|---|---|
| Which provider ships on camera? | none is called |
| Groq's Call 2 was never timed | nothing to time |
| ~81s/turn on the local pair | mock paces at 0.9s + 1.4s = **2.3s/turn** |
| Rate limit mid-take | impossible |

A 20-turn take is **~46 seconds** of waiting and plays in real time.

**The cost, stated rather than hidden: the tutor's sentences are templates.** The
script now requires saying so on camera. It is defensible for exactly the reason
§9.1 is already reported as a mock-utterance result — **narrowing is computed
from the graph and the ladder, and is identical whether a model writes the words
or not** — but it is only defensible when said. Unsaid and later noticed, it
reads as a demo that faked its tutor.

**`TAKE_BUDGET` will not be measured.** A mock take writes no ledger lines, so
`--report` finds an empty ledger and the figure stays provisional at 90,000. No
take has ever been costed; the first real-model session is what would close it.

Three script sections went stale with the decision and were fixed: the pre-flight
invocation now declares `--expect-mock true`, the break-glass list drops the
provider failures that cannot occur in mock, and the after-the-take step no
longer promises a measurement it cannot produce.

---

### 2026-09-22 (day 19) — two documents caught up to the project

**`limitations.md` did not carry confirm-or-undo.** This file committed to it on
day 12 — *"if nobody is watching by the end of week 3, it goes into
`limitations.md` as untested"* — and week 3 ends 09-24 with the recording on
09-23, so it will not happen. The entry now exists, under *Narrower ones worth
stating* rather than the headline four, because this file said it belongs beside
the human pilot **at a much smaller scale** and the four-item heading carries a
count that must stay true. It states what is built (the client sends only
confirmed clicks, so an unconfirmed misclick never reaches `/turn`) and what is
untested (whether a first-time user reads the step as a gate at all).

**The README's Status block was stale by a week.** It opened *"Schemas frozen,
mock server running, client rendering the graph against it"* — true in week 2 —
and said nothing about feature freeze, the three providers, the writeup or any
result. It still named the projector test as the next dated commitment. This is
the page a grader reads first, and the fresh-clone test established they will
reach it before anything else.

Rewritten to carry the freeze and its tag, a five-row fact table, what the system
does, the headline number **with its interval and the grid-of-nine caveat**, the
two bounded figures, and what it is not — one chapter, hand-authored graph, no
human study, mock latency, confirm-or-undo unwatched. It links into the report's
first page rather than restating it. One duplicated *Read CLAUDE.md* paragraph
introduced by the rewrite was removed; all links verified.

---

### 2026-09-22 (day 19) — cold consistency pass over the writeup

The report gained a first page, a regrouped §6 and a future-work section today,
all by edit rather than rewrite, so it was read cold and checked mechanically
rather than by eye. Four classes, three clean:

- **Links:** every cross-file link and every in-page anchor across `docs/` and
  `README.md` resolves. Clean.
- **Section references:** every `§N.N` pointing at a report section resolves to a
  section that exists. Clean.
- **Figures:** the headline (+8.6, CI [+1.9, +16.4]), the extraction ceiling
  (30 of 66, 45%), the reconstruction bound (0 of 34, 8.4%) and the bank counts
  (260 / 101 / 69) agree in every file that states them. Test counts agree too;
  the 364, 249 and 179 in the writeup are deliberate historical statements about
  specific past moments, not stale figures.
- **Headings: two defects, both mine, both fixed.** `At a glance` was an `H1`, so
  the report had two top-level titles; and its three subsections were `H2`, which
  put *What we claim* at the same level as *1. The claim* and made the numbered
  spine look like it began at item four. The whole block is demoted one level.
  Anchors re-verified afterwards — nothing pointed at the moved headings.

Also made exact: the limitations line said *"a single ~50-node graph"* in two
places while the precise figure, 52, is given elsewhere. On a page that otherwise
quotes exact counts an approximation reads as a different number rather than the
same one rounded.

`readthrough-sheet.md` has no `H1` and that is correct — it is the generated
worksheet for the §9.5 human read, not prose.

---

### 2026-09-22 (day 19) — the evidence is archived, and §13.2 is finally met

CLAUDE.md §13.2 has said since day 1: *"archive the 60 eval dialogues somewhere
durable before the week-4 writeup."* It had never been done, and the writeup goes
out tomorrow. `logs/turns.jsonl` is **655 MB and gitignored** — one laptop, one
copy, holding the only raw evidence behind §5.5 and §5.6.

**The evidence is 0.7% of that file.** 3,411 real-model turns out of 668,087
lines; the rest is mock and test traffic. Extracted on `mock: false`, scanned for
credentials first (**zero hits** — no key ever reached the log), and committed at
`eval/results/real_turns.jsonl.gz`: **0.17 MB gzipped.**

| build | turns | backs |
|---|---|---|
| `ac2fc28` | 3,226 | §9.1 adversarial arms |
| `18d220d` | 40 | **§5.5's `0/34` and every §5.6 figure** |
| `77b7e5d-dirty` | 40 | day 12, withdrawn for cause, kept because the report cites it |
| five others | 105 | intermediate runs |

**Both published numbers were reproduced from the archive alone before it was
committed**, with no key and no network: `leak_monitor --log ... --build 18d220d`
returns `0 / 34`, and `curriculum_moves` returns 13 emitted / 12 moved with the
override at 6 of 12. Exact matches.

That upgrades a claim the report was making loosely. Its opening note said the
raw outputs were committed so the figures could be **checked**; they can now be
**recomputed**, and the note gives the two keyless commands. The distinction
matters for a reader deciding whether to believe a number they cannot rerun.

One rule recorded with it: **do not regenerate this file from a later log.** It
is a record of runs that happened, and no eval has run since the day-19 freeze.

---

### 2026-09-22 (day 19) — the projector test is closed unrun, and says so

Dropped from the open list rather than carried into the recording as a pending
item. It was booked for day 11, slipped, rebooked into week 3, and never run;
week 3 ends 09-24 and the recording is 09-23. It needed a projector and a room,
and neither was ever available.

**It is recorded in `limitations.md`**, and the entry is careful about which
half is untested. Per-node contrast is **measured** and is not the worry — a lit
outline is 17.19:1 at 3px against a dimmed 1.53:1 at 1px, the 3px ink carries
the signal, and those ratios are count-independent. What was never tested is
whether the lit **set** reads as one place to look from the back of a room: the
shipped ladder bottoms out at **9 lit, not 5**, and nine nodes span **52% of the
canvas** with 25 dimmed nodes interleaved.

The consequence is bounded and stated: if it read as scatter, the fix would be
`NARROW_SCHEDULE` or the turn budget — configuration, not palette — and both are
§9.1 research variables, so either change would require re-running the leakage
sweep. That is precisely why it is not a change to make untested on the day.

**Reopen only if a live presentation is scheduled.** For a recorded walkthrough
the display is the camera's, not a projector's, so the question does not arise.

Both human-dependent items are now closed the same way: written down as
assumptions with the evidence that bounds them, rather than left as bookings
that kept sliding. An assumption honestly labelled is worth more than a booking
nobody kept.

---

### 2026-09-22 (day 19) — a landing screen, and a deliberate freeze exception

**This is a feature added after `feature-freeze` was tagged**, on an explicit
call, and it is recorded here so the tag does not quietly stop meaning anything.
The freeze stands for everything else.

**The gap it closes.** The app opened straight onto 52 lit nodes. A student who
has not read the report cannot place the question: they do not know the map is a
chapter, that a click is an answer, or that being wrong is what makes the map
work. The first thing the interface did was ask a question its user could not
situate.

`client/src/Landing.tsx` comes first now. Three steps in plain language — you get
a map / you answer by pointing / stuck, and it shrinks — and no jargon the tutor
does not itself use: no "nodes", no "hint ladder", no "narrowing schedule".

**What it deliberately does not do: preview the narrowing.** `App.tsx` already
carried the rule — *"The only motion in this app is the dim transition. No
entrance animations … that is what makes the narrowing the memorable moment."* An
animated 52 → 12 teaser here would spend that moment before the student reaches
the real one, on their own wrong answer. So the narrowing is described in one
line and shown for the first time when it happens.

**Visual language is the app's, not the mock-up's.** The design brief was a dark
glassmorphic page; the client is light paper, teal off the mastery ramp, IBM Plex
Sans. Dropping a dark page in front of a light app would read as two products, so
the structure was kept and the palette taken from `tokens.css`.

**The session no longer opens on mount.** It opens when the student presses
Start. Verified: loading the page writes **0 session rows**, and the Start path
(`/graph` + `/session` + first `/turn`) works. A failed start returns to Landing
with the reason on it rather than a dead screen, so there is somewhere to press
again.

Typecheck and build clean; 537 tests still pass. No server change — this is
entirely layer B.

---

### Eval freeze: no eval runs in the 24 hours before Saturday 2026-09-26

**The window is Friday 2026-09-25 00:00 to Saturday 2026-09-26 00:00.** Nothing
in `eval/` that touches the model runs inside it.

**The reason for the Saturday date is now known: the recording is Saturday
2026-09-26.** This was recorded on day 18 as a bare instruction with its purpose
missing, and this file said so rather than guessing. The window is the 24 hours
before the take, and it exists so the recording does not open on a machine whose
daily token budget was spent on an eval the night before. `TAKE_BUDGET` and the
pre-flight's trailing-24h check are the same constraint made checkable.

That also moves the walkthrough **earlier**, from 2026-09-29 to 2026-09-26.
CLAUDE.md §11 asks for the video *by* day 26, which is a deadline and not a
date; Saturday is day 23 and comfortably inside it.

What matters operationally is the deadline it creates:

- **Anything needing the live model must finish by end of Thursday
  2026-09-24.** That is inside week 3, which ends the same day.
- **Nothing model-dependent is open against this deadline.** When this was
  written, the §9.5 model control on `qwen3.8-27b` was the last item under it;
  it was closed the same day, not run — see the day-18 prompt A/B entry above.
  What remains possible rather than planned is a re-run of §6.1 or §9.5 on a
  later build. If one becomes necessary it has to happen by Thursday; as of
  day 19 none is.
- It collides with the **feature freeze on 2026-09-25** (day 22), which is the
  first day of the window. A feature freeze normally invites one last
  verification run; here it cannot have one. So the last full verification has
  to be Thursday, a day *before* the freeze, and `main` must be left in a state
  that does not need one.

Offline evals that read `logs/turns.jsonl` and make no model call —
`eval.leak_monitor`, `eval.graph_quality`, `eval.distractor_screen` — are not
model runs and are unaffected. `eval.adversarial` already refuses a live model
unless passed `--real-model`, so it is only in scope when that flag is used.

---

### A note for whoever runs the projector test

Run it against a server started **from current `main`**. Three things landed
after 2026-09-10 that change what the demo does on screen — §5's answer masking
went from inert to working, and `advance`/`explain` stopped being handed the open
item's answer label. A long-running dev server from an earlier day is serving
the old behaviour.

### 2026-09-21 (day 18) — the §9.5 re-run finally ran, five days late

It was written down on day 13 as *"tomorrow's first task, on a fresh daily
budget"*. Days 14–17 produced one commit, a README cleanup. The item did not
fail on its merits; it simply was not picked up, which is the same failure mode
as the two unbooked projector items above and is recorded the same way.

**It ran clean:** 30/30 fields, exit 0, no Call 1 fallback, provenance complete,
build `18d220d`. Roughly 18 minutes at `--pace-s 32`.

**What it found is a reversal, not a confirmation.** `zero` → `guessing` 12/12
where day 12 had 0/12; `confused_prereq` used 4 times where day 12 never used it;
`correct` agreeing with the deterministic grade 30/30. The day-12 conclusion —
*"the diagnosis does not track the student"* — was a finding about the
`role: text` formatting bug. `report.md` §5.6 and
[diagnosis-readthrough.md](writeup/diagnosis-readthrough.md) now carry both
readings, dated.

It also **reproduced day 13's abandoned run-3 partial exactly** (`zero` →
`guessing` ×6, `correct` 15/15 at field 15) before continuing to 30.

**What the delay cost, concretely.** Nothing in tokens — the run fits the daily
budget with room. What it cost is week-3 integration time, in the week §11
already names as the one to budget whole. The projector test and the
confirm-or-undo observation are still unbooked and still need a person and
hardware, and week 3 ends 2026-09-24.

**Three things are still open and are not closed by this run:**

- ~~**`eval/diagnostic_calibration.py` has not been re-run.**~~ **Re-run the
  same day**, as a prompt A/B. See the day-18 A/B entry below.
- **§6.1 is now 0/34, a one-sided 95% upper bound of 8.4%** (two-sided 10.3%)
  — about one turn in twelve,
  so an absence of evidence rather than evidence of absence. It is not compared
  against the withdrawn day-12 figure: that run is inadmissible, and a withdrawn
  number quoted as the benchmark is a withdrawn number still in use. The only
  build carrying both instrument fixes is `18d220d`, verified by
  `git merge-base`: `614d066` has the history fix but not the edge-answer fix.
- ~~**`leak_monitor`'s printed HEADLINE pools builds** and must not be quoted;
  documented rather than repaired, per §11's cut-from-the-bottom rule.~~
  **Repaired the same day.** The documentation-only fix was the wrong call: a
  summary line a reader will quote is not made safe by a caveat elsewhere saying
  do not. The headline now reports one build, defaults to the current one and
  names it; `--pool-builds` is opt-in. Case 4 in
  [instrument-failures.md](writeup/instrument-failures.md) records both the
  defect and the bad first fix.

**Also observed, worth a line in the writeup:** Call 2 on `gpt-oss-20b` invented
a tool name (`json`) on 4 of 40 turns; the retry from `71501ac` recovered all but
2, which shipped the canned fallback. Those 2 are real-mode turns carrying a
template utterance, and the turn record has no `call2_fallback` flag to exclude
them from §6.1's denominator. They did not land in the screened population this
time (`fell_back=0` in the partition), but the gap is real and is the kind of
thing that silently deflates a rate later.

## Not on this list

Anything without a date. The cut order in `CLAUDE.md` §11 governs what goes when
a week overruns — cut from the bottom, do not borrow from next week.
