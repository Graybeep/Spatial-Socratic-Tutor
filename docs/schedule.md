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
| 2026-09-18…24 | week 3 | both of the above, at the projector, contrast check first | rebooked |
| ~~2026-09-22~~ | 19 | **API key cut** — resolved early, on day 12. See below | **MET, with a caveat** |
| ~~2026-09-18…24~~ | 12 | diagnosis read-through, 30 `diagnosis` fields (§9.5) | ~~**RUN, and it found something**~~ **INVALIDATED on day 13**: Call 1 was sent `role: text` for every past turn, so the model never saw a click. See [diagnosis-readthrough.md](writeup/diagnosis-readthrough.md) |
| ~~2026-09-16~~ 2026-09-21 | 13 → 18 | **repeat §9.5 on `gpt-oss-120b`**, the model the demo ships — now also the first §9.5 run in which the model can see the dialogue | **RUN AND COMPLETE**, 30/30 fields, five days late. See below |
| — | 12 → 18 | §6.1 parametric-reconstruction rate | ~~**0/60, reported as a bound.**~~ Withdrawn day 13, run later ruled inadmissible; **re-measured day 18 as 0/34**, one-sided 95% bound 8.4%. See below |
| ~~2026-09-17~~ | 14 | **dependency freeze** (§1.8), end of week 2 | **MET a day early**, on day 13 — enforced by a test, see below |
| **2026-09-25 00:00 → 2026-09-26 00:00** | 21–22 | **eval freeze: no eval runs in the 24h before Sat 26** | booked, see below |
| 2026-09-25 | 22 | **feature freeze.** Tag `feature-freeze` | pending |
| 2026-09-29 | 26 | **video walkthrough recorded.** Tag `demo` | pending — **script it around narrowing, not mastery.** See below |

Tags cut so far: `schemas-frozen`, `graph-frozen`, `loop-working`.

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
day-18 log, no new calls. Of **13 moves in 40 turns**: 6 `advance` the model also
asked for, 6 `backtrack` the server performed while the model asked for a hint,
and **1 `backtrack` the model requested and got**.

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

**No eval re-run is needed for this** and none was done: the day-18 §9.5 and §6.1
figures are diagnosis and utterance measurements, and neither depends on which
rule moved the curriculum. The change is in the demo path, so it wants a manual
pass before the walkthrough — added to the projector-test session, which is still
unbooked.

---

### Eval freeze: no eval runs in the 24 hours before Saturday 2026-09-26

**The window is Friday 2026-09-25 00:00 to Saturday 2026-09-26 00:00.** Nothing
in `eval/` that touches the model runs inside it.

This is a standing instruction recorded on day 18; the reason for the Saturday
date is not written down here, and whoever reads this later should not infer one.
What matters operationally is the deadline it creates:

- **Anything needing the live model must finish by end of Thursday
  2026-09-24.** That is inside week 3, which ends the same day.
- The still-open model-dependent work is listed under day 18 below: the §9.5
  model control on `qwen3.8-27b`, and any re-run of §6.1 or §9.5 on a later
  build. If they do not happen by Thursday they do not happen before Saturday.
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
