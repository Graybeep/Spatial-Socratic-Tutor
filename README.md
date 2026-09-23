# Spatial Socratic Tutor

An LLM tutor that helps by **showing less** instead of saying more: it narrows a
frozen concept graph visually rather than explaining the answer.

4 weeks, one person working both layers, one chapter, a local demo and three
eval numbers.

**Read `CLAUDE.md` before writing any code.** It is the settled spec — hard rules,
frozen schemas, the two-call architecture, guardrails, mastery maths, evals and the
schedule. Do not re-litigate decisions in it mid-implementation.

## Status

**Feature freeze cut on 2026-09-22 (day 19), three days early, at `e71c6c5`.**
Demo-path fixes only from here; no eval runs — the numbers are final. The
walkthrough is recorded 2026-09-23 and tagged `demo` after, not before.

Tags so far: `schemas-frozen`, `graph-frozen`, `loop-working`, `feature-freeze`.

| | |
|---|---|
| Tests | **537** green |
| Graph | **52** hand-authored nodes, 66 prereq edges, one chapter |
| Item bank | **260** items, **69** scorable |
| Providers | **3** — Anthropic, Groq, any OpenAI-compatible local server |
| Fresh clone to a served page | **~90s**, no key, no network |

### What it does

One endpoint, `POST /turn`, and two hand-written model calls per turn. Call 1
sees the answer and decides; Call 2 writes the sentence and is **never given the
answer**, so it cannot name what it was never told. The graph reacts on Call 1's
return, before any utterance exists. Seven guard layers sit over that, mastery is
Rasch-form arithmetic in Python, and only clicks are ever scored.

Measured against the running server: narrowing lands on **turn two** (52 lit to
12), the shipped `interleaved` ladder bottoms out at **9 lit, not the 5 the floor
implies**, hints cap at 4, and an 8-turn budget forces a reveal worth zero
mastery.

### What the numbers say

The headline is **+8.6 points** of post-hint solve rate for the shipped
configuration against a zero-knowledge simulated student, 95% CI
**[+1.9, +16.4]** — and it is **one cell in a grid of nine**; every other arm
crosses zero. **We do not claim visual narrowing beat the verbal channel.** It
did not, on this bank, at this *n*.

Two supporting figures are bounds rather than estimates: graph-extraction recall
has a **45%** ceiling at the shipped window, and parametric reconstruction is
**0 of 34**, one-sided 95% upper bound 8.4%.

Start with [`docs/writeup/report.md`](docs/writeup/report.md) — its first page
carries the claims, the number with its interval, and the seven things that
should make a reader distrust all of it.

### What it is not

One chapter. A hand-authored graph, with no extraction run on an arbitrary
document. Simulated students, **no human study, and no learning outcome measured
or claimed**. Only Call 1 has been timed on a live model (p50 2.3s); Call 2 has
not, and the demo's pacing is a mock's. Confirm-or-undo has never been
watched by anyone who did not design it. All of it is argued in
[`docs/writeup/limitations.md`](docs/writeup/limitations.md).

## Run the mock

**No API key, no network, no `.env`.** `MOCK_MODE=true` is the default, so a
fresh clone runs as-is. Verified from an empty directory on 2026-09-22
(Python 3.11.9, Node 20): **~90 seconds from `git clone` to a served page**, or
about 2.5 minutes including the test suite.

Terminal 1 — the server:

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows; use .venv/bin/activate elsewhere
pip install -r requirements.txt    # ~40s

python -m build.validate           # expect: 0 error(s), 8 warning(s)
python -m pytest                   # expect: 537 passed
python -m server.main              # http://127.0.0.1:8000
```

Terminal 2 — the client:

```bash
cd client
npm ci                             # the lockfile, exactly (§1.8 freeze)
npm run dev                        # http://localhost:5173
```

Open **http://localhost:5173**. The client finds the API at
`http://127.0.0.1:8000` by default, so no client `.env` is needed either.

Two things worth knowing before you read the output:

- **`build.validate` prints warnings and that is the expected result.** It exits
  **0** with **8 warnings**, each naming a known property of the item bank —
  MCQ option sets that repeat, edge items determined by their anchor, nine nodes
  whose served chunk disagrees with their declared section. They are findings
  the writeup discusses, not a broken install. **Only `0 error(s)` matters.**
- **The venv is not optional advice.** §1.8 pins every dependency to the exact
  version the suite passed against, and `pip install` into a populated
  environment will not downgrade what is already there.

To use a real model, put a key in `.env` and set `MOCK_MODE=false`. Without a
key it still runs: Call 1 falls back to the mock's deterministic decision and
Call 2 to the canned per-action line, and both fallbacks are logged. `main`
always runs (§13.2).

```bash
cp .env.example .env
```

## Choose a provider

`LLM_PROVIDER` picks one of three. The **schema does not move between them**:
all three are handed the same pydantic model under a forced tool call, and a
response that fails validation fails identically on each. Only the wire format
differs — URL, auth header, body shape, and where the tool call lands.

| `LLM_PROVIDER` | needs | Call 1 default | notes |
|---|---|---|---|
| *(unset)* | nothing | — | `MOCK_MODE=true`, no key, no network. **Start here.** |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-5` | |
| `groq` | `GROQ_API_KEY` | `openai/gpt-oss-120b` | what every number in the report was measured on |
| `local` | nothing | `qwen/qwen3.5-9b` | any OpenAI-compatible local server |

### Running against a local model

No key, no network, no quota. Point `LOCAL_BASE_URL` at whatever is serving
`/v1/chat/completions` — LM Studio, Ollama, `llama.cpp`'s server, vLLM:

```bash
LLM_PROVIDER=local MOCK_MODE=false LOCAL_BASE_URL=http://127.0.0.1:1234 CALL1_MODEL=your/model CALL2_MODEL=your/other-model python -m server.main
```

**Set `CALL1_MODEL` and `CALL2_MODEL` explicitly.** The defaults name the two
models this was developed against and will not exist on your machine. A model
id the server does not serve comes back as a 400, not as a fallback.

Two things to expect, both measured here on 2026-09-22, n=1 per model:

- **It is slow.** One turn end to end took **~81s** — 56.8s for Call 1
  (`qwen/qwen3.5-9b`) and 24.3s for Call 2 (`google/gemma-4-e4b`), against
  Groq's 2.3s p50 on Call 1. Hence the 180s default timeouts on this provider;
  a 10s cloud timeout fails every local call before it finishes thinking.
- **Your model must do tool calls.** The whole architecture rests on a forced
  tool call with a validated schema. `tool_choice` is sent as the string
  `required` here, because LM Studio rejects the object form outright; that is
  equivalent only because each call defines exactly one tool.

Check what a server is offering before pointing at it:

```bash
curl http://127.0.0.1:1234/v1/models
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

Hand-read 30 `diagnosis` fields (§9.5) — **needs a key**, and refuses to run
without one, because reading thirty mock diagnoses measures `mock_tutor.py`:

```bash
LLM_PROVIDER=groq MOCK_MODE=false python -m eval.diagnosis_readthrough --n 30
```

It prints the fields with the student's **true** knowledge state and actual click
on the page beside each one, so a diagnosis can be judged without cross-
referencing a second file. The students are scripted, which is a real limitation
and is stated — but it is also the only way to have ground truth at all: reading
thirty diagnoses of a real student, nobody can say whether "confused about the
prerequisite" was *true*. It also checks the two things that need no human: does
`correct` match what was actually clicked (Call 1 sees the answer, so anything
under 100% is a scoring fault), and does `student_state` move at all across three
different true knowledge states.

Aggregate guard layer 1 (§6.1) from the turn log - no key, and it will tell you
what it refuses to report:

```bash
python -m eval.leak_monitor
```

§6 calls the layer-1 rate free. It was logged from day 1 and never aggregated,
so it was free the way an unopened box is packed. The aggregator will not pool
builds (17,433 `backtrack` hits in the log come from a bug fixed by the fidelity
ceiling), will not pool actions, will not pool **origins** without saying so, and
**will not report a mock rate as §6.1's number** - a template lookup has no
weights to reconstruct an answer from, so it prints `NOT MEASURABLE` instead of
`0.00%`. See `docs/writeup/no-key-plan.md`.

Every turn record also says **who drove it**. `origin` is `server` for a person
over HTTP and `eval:adversarial:<mode>:<condition>` for one of the three scripted
policies. Today `mock` separates those by accident; on the day a key lands an
eval sweep and a real student are both `mock: false` at the same build, and §9.5
- the hand-read of 30 `diagnosis` fields, the one check no metric substitutes for
- would draw its sample from whichever ran last. Turns logged before day 12 read
as `pre-origin`, not as people.

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
| `server/origin.py` | who drove a turn - a person, or one of eval's policies; §9.5's sample gate |
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
| `eval/leak_monitor.py` | §6.1 layer-1 rate from the log; refuses to pool builds, origins or report a mock |
| `eval/diagnosis_readthrough.py` | §9.5 — 30 diagnoses against ground truth; refuses to run on the mock |
| `eval/curriculum_moves.py` | §5.6's containment count from the log; separates actions *emitted* from curriculum *moved* |
| **`docs/writeup/report.md`** | **the assembled report — start here** |
| `docs/writeup/diagnosis-readthrough.md` | §9.5 — the tutor's model of the student, against a truth it could not see |
| `docs/writeup/instrument-failures.md` | the harness producing confident verdicts while itself broken; the fix generalises |
| `eval/diagnostic_calibration.py` | constructed cases where one diagnosis is forced — `python -m eval.diagnostic_calibration` |
| `docs/writeup/representation-blindness.md` | the design contribution: fidelity ceiling, not field whitelist (4 instances) |
| `docs/writeup/numbers-that-looked-fine.md` | evals, and one drift test, that produced well-formed results over nothing |
| `docs/writeup/` | other draft report sections — identity leakage, limitations |
| `docs/writeup/no-key-plan.md` | **the report that stands without a key**, and the day-19 decision |
| `build/fetch_chapter.py` | downloads the chapter into a gitignored dir; URLs in `build/config.py` |
| `client/src/types.ts` | reconciled against `/schemas`; supersedes `templates/` |
| `client/src/Landing.tsx` | the screen before the map: what it is, how to answer, why it dims |
| `client/src/Graph.tsx` | the frozen-layout SVG and the two dimming channels |
| `client/contrast-check.html` | §8 projector test, at the 9-lit rung the demo really reaches |
| `server/preflight.py` | demo pre-flight — clean main, fresh state.db, declared MOCK_MODE, 24h token budget |
| `server/llm.py` | three providers behind one seam: Anthropic, Groq, and a local OpenAI-compatible server |
| `docs/human-tests.md` | one page for the two tests that need a room, a projector and a person |
| `docs/walkthrough-script.md` | the three-minute demo script, and what not to promise on camera |
| `docs/dim-values.md` | the shipped dim tokens, and where the projector test's outcome gets recorded |
| `docs/schedule.md` | dated commitments and their pass/fail — next: projector test, week 3 (slipped from 09-14) |
| `client/src/Chat.tsx` | the rail — transcript, composer, turn budget, node panel |

Full layout in `CLAUDE.md` §2.
