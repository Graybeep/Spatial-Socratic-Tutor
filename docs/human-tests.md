# The two tests that need a room, a projector and a person

*One page. Print it or keep it open on a phone. Both tests happen in one
sitting, contrast check first, and the whole thing is about twenty-five minutes.*

`docs/schedule.md` carries the history: both were booked for day 11, both
slipped, and week 3 (ends **2026-09-24**) is the last slot. If the second one
does not happen it becomes a written limitation, not another booking.

---

## Before you leave for the room

Run this. It fails loudly and tells you which thing is wrong:

```bash
python -m server.preflight --expect-mock true
```

`--expect-mock true` because **these two tests need no API key and no model.**
The dimming is deterministic and the click gesture is client-side; running them
against the real model spends tokens on something that cannot be affected by
what the tutor says.

### Reset to a clean demo

The pre-flight checks these; this is how you get them true.

```bash
git checkout main
git status --porcelain          # must print nothing
rm -f state.db                  # DESTRUCTIVE: wipes the student's progress
python -m server.preflight --expect-mock true

# terminal 1
MOCK_MODE=true python -m uvicorn server.main:app --port 8000
# terminal 2
cd client && npm ci && npm run dev
```

**Start the server from current `main`, not from a terminal you left open.**
Three things landed after 2026-09-10 that change what the demo does on screen
(§5's answer masking went from inert to working; `advance`/`explain` stopped
being handed the open item's answer label), and a long-running dev server is
serving the old behaviour. The `build` check exists because of exactly this.

---

## Test 1 — projector contrast (§8). ~15 minutes. You can run this yourself.

```bash
open client/contrast-check.html     # standalone, no server needed
```

Full screen, **actual demo hardware, actual projector**. Then go and sit where
the back row will sit. A laptop screen answers a different question.

**This is not really a contrast test and that is the point.** The contrast
ratios are already measured and are in `docs/schedule.md`; the 3px ink outline
carries the signal and the fill barely contributes. What is untested is
*coverage*: the shipped `interleaved` ladder bottoms out at **9 lit, not 5**,
and nine lit nodes span **52% of the canvas**.

- [ ] Can you locate the lit set **without hunting**, from the back?
- [ ] Does it read as **one place to look**, or as scatter across half the map?
- [ ] At 9 lit, is the narrowing legible **as a narrowing** — does the map feel
      smaller, or do some nodes just look grey?
- [ ] Compare against the 5-lit panel. If 5 is obviously better, that is a
      finding about `NARROW_SCHEDULE` or the turn budget, **not** about the
      dimming tokens.

**If it fails, the fix is the ladder, not the palette** — narrow faster, or let
`interleaved` reach the floor. Both are config, both are §9.1 research
variables, and both need §9.1 re-run afterwards. Budget half a day.

**Record the outcome in [dim-values.md](dim-values.md) on the day, pass or
fail.** An untested §8 and a tested-and-passed §8 look identical in a repo three
weeks later.

---

## Test 2 — confirm-or-undo, watched. ~10 minutes. You cannot run this one.

**It needs one person who has not seen the interface.** That is the whole
design: you already know what a click commits to, and that knowledge is the
variable under test. §8 calls confirm-or-undo the only gate between a stray
click and a permanent mastery penalty, and a gate nobody has watched a stranger
use is an assumption with a UI on it.

**Give them nothing but this:** *"Answer the tutor's questions."* No tour, no
explanation of the graph, no prompting when they hesitate. Hesitation is data.

Watch for **one** thing:

- [ ] Does the click → **Confirm / Undo** step read as *"nothing has happened
      yet"*, or as *"this has been submitted"*?

If they treat the click itself as the answer and the confirm as an
acknowledgement, **the gate is decorative** and the fix is in the wording, not
the logic.

### What to write down, in their words not yours

| | record |
|---|---|
| did they hesitate before the first click? | |
| what did they say, verbatim, at the confirm step? | |
| did they ever use Undo? on purpose, or by accident? | |
| did they ask what a click would do *before* clicking? | |

The verbatim line matters more than your reading of it. If you find yourself
writing "they seemed to understand", write what they actually did instead.

---

## Also, in the same sitting: the day-19 backtrack path

Two minutes, and it is the one recent change nobody has watched run.

The demo ships `MODEL_BACKTRACK=false`, so **every backtrack you can see on the
demo path is §7's two-failure rule** — the model's own requests are refused and
degrade to a hint. Get a node wrong twice in a row and watch what happens.

- [ ] Does the graph move to the prerequisite node, and does the utterance
      match the move rather than describing the node you just left?
- [ ] Does the hint rung reset, so the prerequisite is asked fresh rather than
      opening at the rung you had climbed to?

---

## After, before you close the laptop

- Write the outcomes into [dim-values.md](dim-values.md) and the table above
  into `docs/schedule.md`, dated, pass or fail.
- If nobody watched test 2, say so there. `docs/writeup/limitations.md` already
  lists a human pilot under *what would change our minds*; an unwatched
  confirm-or-undo belongs in that list at a much smaller scale, and an
  assumption honestly labelled is worth more than a booking that keeps sliding.
