# Dim values — what ships, and what the projector said

*The record of the §8 dimming tokens: the values as shipped, and any change the
projector test forced. Fill in the outcome section on the day, pass or fail.*

---

## THE TRAP, read this first

**The tokens exist in two files and nothing keeps them in sync.**

| file | what it drives |
|---|---|
| `client/src/tokens.css` | **the actual demo** |
| `client/contrast-check.html` | the standalone test page you will tune against |

The contrast check is deliberately standalone — it needs no server, which is why
it can be run anywhere. The cost is that **tuning a value in the test page
changes nothing about the demo.** If the projector test moves a number, it has
to be moved in `tokens.css` too, or the finding is lost and the demo ships the
old value.

Verify they agree before you trust any of this:

```bash
grep -E 'lit-stroke|dim-(stroke|shape|label|edge|saturate)' client/src/tokens.css
grep -E 'lit-stroke|dim-(stroke|shape|label|edge|saturate)' client/contrast-check.html
```

---

## As shipped (verified identical in both files, 2026-09-22)

| token | value | what it does |
|---|---|---|
| `--lit-stroke` | `3px` | **carries the signal.** If the projector crushes anything, watch this, not the colour |
| `--dim-stroke` | `1px` | |
| `--dim-shape-opacity` | `0.20` | the rectangle — the spatial anchor. `tokens.css` says it MUST NOT go lower: below this a dimmed node stops being a *place* and the layout memory goes with it |
| `--dim-label-opacity` | `0.06` | the text. Near zero on purpose — readable text is the leak |
| `--dim-edge-opacity` | `0.15` | |
| `--dim-saturate` | `0.12` | |

Measured contrast against paper, already known and **not** what the test is for:

| | lit | dimmed |
|---|---|---|
| node outline | 17.19:1 (3px) | 1.53:1 (1px) |
| label | 17.19:1 | 1.13:1 |
| edge | 1.81:1 | 1.08:1 |
| fill @ mastery 0.5 | 2.52:1 | 1.18:1 |

Three channels, deliberately: opacity **plus** desaturation **plus** stroke
width. CLAUDE.md §8 requires all three because opacity alone dies on a bad
projector. They are count-independent — nothing about the number of lit nodes
changes per-node contrast.

---

## Outcome of the projector test

**Date run:** ____________  **Hardware / projector:** ____________________

**Run by:** ____________  **Seat used:** back row / ____________

| question | answer |
|---|---|
| lit set locatable without hunting? | |
| reads as one place to look, or scatter? | |
| at 9 lit, legible *as a narrowing*? | |
| is 5 lit obviously better than 9? | |

**Verdict:** pass / fail  ☐

### If any value changed

| token | was | now | why |
|---|---|---|---|
| | | | |

- [ ] changed in `client/src/tokens.css`
- [ ] changed in `client/contrast-check.html`
- [ ] both greps above re-run and agree

**If the change was to `NARROW_SCHEDULE` or the turn budget rather than to a
token, §9.1 must be re-run** — the sweep is over exactly that curve, and the
published leakage figures are points on it. Note it here and in
`docs/schedule.md`:

**§9.1 re-run needed?** yes / no ☐   **done:** ____________

---

## If it was not run

Say so, here and in `docs/schedule.md`, on the day week 3 ends. An untested §8
and a tested-and-passed §8 look identical in a repo three weeks later, and that
is the entire reason this file exists.
