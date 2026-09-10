# Schedule — dated commitments

*The plan lives in `CLAUDE.md` §11 and is not restated here. This is the list of
things that have a **date** and a **pass/fail**, so a slip is visible on the day
it happens rather than in week 4.*

Project start 2026-09-04. Week 1 is 09-04…09-10, week 2 09-11…09-17,
week 3 09-18…09-24, week 4 09-25…10-01.

---

## Booked

### Monday 2026-09-14 (day 11) — projector contrast test

**§8, pulled forward.** §8 asks for week 3; this is week 2. Earlier is the
allowed direction, and it is cheap now that the instrument exists.

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

## Standing dates

| date | day | what | state |
|---|---|---|---|
| 2026-09-14 | 11 | projector contrast test (§8) | **booked, above** |
| 2026-09-22 | 19 | **API key cut.** No key → `MOCK_MODE` ships, §9.3 and §9.5 are cut | pending — see [no-key-plan.md](writeup/no-key-plan.md) |
| 2026-09-18…24 | week 3 | diagnosis read-through, 30 logged `diagnosis` fields (§9.5) | blocked on a key |
| — | — | §6.1 parametric-reconstruction rate | **instrument built, blocked on a key.** `python -m eval.leak_monitor` prints `NOT MEASURABLE` and says why; a mock has no weights to reconstruct from. Fills itself in on the day a key lands |
| 2026-09-25 | 22 | **feature freeze.** Tag `feature-freeze` | pending |
| 2026-09-29 | 26 | **video walkthrough recorded.** Tag `demo` | pending |

Tags cut so far: `schemas-frozen`, `graph-frozen`, `loop-working`.

### A note for whoever runs the projector test

Run it against a server started **from current `main`**. Three things landed
after 2026-09-10 that change what the demo does on screen — §5's answer masking
went from inert to working, and `advance`/`explain` stopped being handed the open
item's answer label. A long-running dev server from an earlier day is serving
the old behaviour.

## Not on this list

Anything without a date. The cut order in `CLAUDE.md` §11 governs what goes when
a week overruns — cut from the bottom, do not borrow from next week.
