# Spatial Socratic Tutor

An LLM tutor that helps by **showing less** instead of saying more: it narrows a
frozen concept graph visually rather than explaining the answer.

4 weeks, one person working both layers, one chapter, a local demo and three
eval numbers.

**Read `CLAUDE.md` before writing any code.** It is the settled spec — hard rules,
frozen schemas, the two-call architecture, guardrails, mastery maths, evals and the
schedule. Do not re-litigate decisions in it mid-implementation.

## Status

Schemas frozen, mock server running, client rendering the graph against it.

The chapter graph has landed: 52 hand-authored nodes over Peterson & Davie
ch. 6 (Congestion Control), CC BY 4.0 — see `data/SOURCE.md` for attribution and
for why it is hand-authored and why `gold_graph.json` was frozen *before* any
extractor exists. The two-call tutor loop still runs against the mock; `MOCK_MODE`
is still the default.

**The chapter itself has now landed too.** `python -m build.fetch_chapter &&
python -m build.chunk --html` produces `data/chunks.json` — 15 section-aligned
chunks, sections 6.1–6.4 — and retrieval runs over it with no key and no model
call, so `advance` and `explain` cite the chapter even in `MOCK_MODE`.

**And §5's answer masking is no longer inert.** `answer_spans` was `[]` for all
260 items while there was no chunk to offset into; once there was one, that
absence became a live leak on `advance` and `explain` and nothing failed.
`python -m build.annotate_spans` populates the offsets against the chunk
retrieval actually serves, `build/validate.py` re-derives every one of them, and
layer-1 hits on `advance` went from 6 in a 258-turn session to 0. The same pass
produced a number nothing had computed: retrieval serves the node's declared
section **43 of 52 times (83%)**. BM25 scored 45 and was not adopted — see
`docs/writeup/limitations.md` for why two nodes at n=52 does not buy a
recalibration of the gate.

**Next dated commitment: projector contrast test, Monday 2026-09-14** — see
`docs/schedule.md`. **Deadline on the key: 2026-09-22 (day 19).** If there is no API key by then,
`MOCK_MODE` ships and §9.3 and §9.5 are cut. See
`docs/writeup/no-key-plan.md`, which is the version of the report that needs no
key — written early on purpose, so a key arriving late adds two sections rather
than forcing a rewrite.

## Run the mock

```bash
pip install -r requirements.txt
python -m build.validate         # strict; must be clean
python -m pytest                 # 322 tests
python -m server.main            # http://127.0.0.1:8000
```

Then the client, in a second terminal:

```bash
cd client && npm install
npm run dev                      # http://localhost:5173
```

No API key and no network needed — `MOCK_MODE=true` is the default.

To use the real model, put a key in `.env` and set `MOCK_MODE=false`. Without a
key it still runs: Call 1 falls back to the mock's deterministic decision and
Call 2 to the canned per-action line, and both fallbacks are logged. `main`
always runs (§13.2).

```bash
cp .env.example .env   # only needed once real LLM calls go in (week 2)
```

Measure leakage (§9.1) — three student conditions, arms labelled:

```bash
python -m eval.adversarial       # n defaults to 2 per item
```

Score extraction against the hand annotation (§9.3) - no key needed for the
**ceiling**, which is the half that bounds the other:

```bash
python -m eval.graph_quality
```

Screen the item bank (§9.4) - no key, no chapter, no network:

```bash
python -m eval.distractor_screen
```

Aggregate guard layer 1 (§6.1) from the turn log - no key, and it will tell you
what it refuses to report:

```bash
python -m eval.leak_monitor
```

§6 calls the layer-1 rate free. It was logged from day 1 and never aggregated,
so it was free the way an unopened box is packed. The aggregator will not pool
builds (17,433 `backtrack` hits in the log come from a bug fixed by the fidelity
ceiling), will not pool actions, and **will not report a mock rate as §6.1's
number** - a template lookup has no weights to reconstruct an answer from, so it
prints `NOT MEASURABLE` instead of `0.00%`. See `docs/writeup/no-key-plan.md`.

Every eval output carries a `provenance` block saying what it sampled
(`population`, `distinct`, `coverage`). Check it before quoting a number: §9.1
was measured over ONE item for four days and every test passed, because a rate
over one item has the same shape as a rate over a hundred. See
`docs/writeup/numbers-that-looked-fine.md`.

Never report `1/N` as leakage. It is a lower bound that assumes uniform choice;
the measured partial-knowledge rate runs well above it.

`MAX_GUESS_PROBABILITY` is a **policy bound on how far the interface will
narrow**, not a result and not a derivation from one. Its earlier justification
ended "would lose to the verbal baseline the project is trying to beat", which
scoped it to a comparison we have since withdrawn — see below. It was set
conservatively before the corrected eval existed and it still holds, but note
what that means in practice: **the shipped ladder never reaches the floor.**
`interleaved` alternates narrowing and verbal rungs, so with
`NARROW_SCHEDULE=0,12,9,7,5` and an 8-turn budget a real dialogue bottoms out at
9 lit. Only the `visual_only` eval arm ever lights 5. Moving the floor is an
interface decision, not an inference — the rungs where it binds carry n=6.

### What the numbers show, and what they do not

Quote these from the **scored** bank: 69 items (52 `node_click` + 17
`edge_click`), not the 101 visually-answerable ones and not the 260-item bank.

**They do not show that the visual channel beat the verbal one.** On the
`node_click` stratum, exactly one marginal over the no-hint baseline is
distinguishable from zero — the shipped interleaved configuration, at zero
knowledge, **+8.6 points [+1.9, +16.4]**. The isolated visual channel lands on
the baseline (.038 against .038). Every other cell crosses zero, in both
directions. At 52 items the half-widths are 6–7 points, so these arms are
underpowered rather than null — but that cuts both ways and here it cuts against
us.

The demo's claim does not depend on winning that comparison, and should not be
pitched as though it does. What holds regardless:

- **the tutor cannot name the answer while hinting** — a property of Call 2's
  argument list, not an observed behaviour (`docs/writeup/representation-blindness.md`)
- **narrowing performs reductions that cannot be expressed in one utterance** —
  a property of what fits in a turn; you cannot name 38 excluded nodes and the
  graph does it in one frame
- **the evaluation-blindness findings**, which are about system design and hold
  whatever generates the text (`docs/writeup/numbers-that-looked-fine.md`)

Useful knobs while building (see `docs/API.md`):

```bash
LADDER_MODE=verbal_only python -m server.main    # hints arrive, nothing dims
NARROW_SCHEDULE=0,25,18,12,8 python -m server.main
```

## Where things are

| | |
|---|---|
| `docs/API.md` | the wire contract — **start here if you are building the client** |
| `server/schemas.py` | the frozen schemas; authoritative |
| `/schemas` | JSON Schema snapshots; CI fails if `schemas.py` drifts |
| `server/turn.py` | the §5 pipeline |
| `server/llm.py` | the two hand-written calls; Call 2's signature is the leak guarantee |
| `server/guards.py` | layers 1, 4 and 6 (0/2/3/5 live where they can be enforced) |
| `prompts/` | tutor contract + both call instructions; never Python literals |
| `server/mastery.py` | deterministic scoring, no LLM |
| `server/mock_tutor.py` | scripted stand-in for Call 1 and Call 2 |
| `build/config.py` | build-pipeline knobs (§13.1); the server never imports it |
| `build/chunk.py` | chapter → chunks; the seam to swap when real PDF text arrives |
| `build/extract_concepts.py` | pass 1, candidates for the human review |
| `build/extract_edges.py` | pass 2; the precedence + co-occurrence filter |
| `server/retrieval.py` | TF-IDF chunk search, gated by layer 4; 83% section accuracy |
| `build/annotate_spans.py` | fills `answer_spans` so §5's mask masks; re-derived by `validate` |
| `build/validate.py` | DAG / orphan / item checks; must pass before commit |
| `build/freeze_layout.py` | runs once, writes x/y into `graph.json`, then never again |
| `build/generate_items.py` | items from the graph; LLM behind a mocked seam |
| `build/llm.py` | the build-side LLM seam — mock by default, `BUILD_LLM=real` |
| `data/SOURCE.md` | attribution, and why the gold graph was frozen first |
| `eval/adversarial.py` | §9.1 effective leakage — `python -m eval.adversarial` |
| `eval/graph_quality.py` | §9.3 extraction recall ceiling; deterministic, no key |
| `eval/leak_monitor.py` | §6.1 layer-1 rate from the log; refuses to pool builds or report a mock |
| **`docs/writeup/report.md`** | **the assembled report — start here** |
| `docs/writeup/representation-blindness.md` | the design contribution: fidelity ceiling, not field whitelist (4 instances) |
| `docs/writeup/numbers-that-looked-fine.md` | evals, and one drift test, that produced well-formed results over nothing |
| `docs/writeup/` | other draft report sections — identity leakage, limitations |
| `docs/writeup/no-key-plan.md` | **the report that stands without a key**, and the day-19 decision |
| `build/fetch_chapter.py` | downloads the chapter into a gitignored dir; URLs in `build/config.py` |
| `client/src/types.ts` | reconciled against `/schemas`; supersedes `templates/` |
| `client/src/Graph.tsx` | the frozen-layout SVG and the two dimming channels |
| `client/contrast-check.html` | §8 projector test, at the 9-lit rung the demo really reaches |
| `docs/schedule.md` | dated commitments and their pass/fail — next: projector test Mon 2026-09-14 |
| `client/src/Chat.tsx` | the rail — transcript, composer, turn budget, node panel |

Full layout in `CLAUDE.md` §2.

## Contributing

One person, both roles. "Person A" (content/graph/scoring) and "Person B"
(interface/tutor loop) name the two layers, not two people — see `CLAUDE.md` §0.
Neither layer edits the other; schemas are the contract (§1.9). `main` must always
run; push at least daily (§13.2). No configuration values hard-coded in source
(§1.10, §13.1).
