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
| 2026-09-18…24 | week 3 | diagnosis read-through, 30 logged `diagnosis` fields (§9.5) | **unblocked.** `python -m eval.diagnosis_readthrough` |
| — | — | §6.1 parametric-reconstruction rate | **unblocked, not yet run.** Needs real turns in the log; `eval/leak_monitor.py` already partitions them by build and origin |
| 2026-09-25 | 22 | **feature freeze.** Tag `feature-freeze` | pending |
| 2026-09-29 | 26 | **video walkthrough recorded.** Tag `demo` | pending |

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

### A note for whoever runs the projector test

Run it against a server started **from current `main`**. Three things landed
after 2026-09-10 that change what the demo does on screen — §5's answer masking
went from inert to working, and `advance`/`explain` stopped being handed the open
item's answer label. A long-running dev server from an earlier day is serving
the old behaviour.

## Not on this list

Anything without a date. The cut order in `CLAUDE.md` §11 governs what goes when
a week overruns — cut from the bottom, do not borrow from next week.
