# Spatial Socratic Tutor

An LLM tutor that helps by **showing less** instead of saying more.

> LLM tutors leak answers because their only way to help is to say more. This
> tutor helps by showing less: it narrows a concept graph visually instead of
> explaining.

The student works through one textbook chapter laid out as a map of concepts.
When they get stuck, the tutor does not explain the answer. It dims the parts of
the map that cannot be the answer, so the search space shrinks without the tutor
saying anything new. Answers are given by **pointing**: clicking a node or an
edge on the map.

Built in four weeks by one person, over one chapter, as a local demo with a set
of evaluation numbers. It is a research prototype, not a product.

---

## Contents

1. [What it does today](#what-it-does-today)
2. [Setup](#setup)
3. [Using a real model](#using-a-real-model)
4. [Architecture](#architecture)
5. [Results](#results)
6. [Limitations](#limitations)
7. [Running the evaluations](#running-the-evaluations)
8. [Configuration](#configuration)
9. [Future scope](#future-scope)
10. [Project status](#project-status)
11. [Where things are](#where-things-are)
12. [Source and licence](#source-and-licence)

---

## What it does today

**The chapter.** Chapter 6, *Congestion Control*, of Peterson and Davie,
*Computer Networks: A Systems Approach* (CC BY 4.0). It is turned into:

| | |
|---|---|
| Concept graph | **52** hand-authored nodes, **66** prerequisite edges and 7 "related" edges, with a frozen layout |
| Item bank | **260** items: 52 node-click, 49 edge-click, 159 multiple choice |
| Scored items | **69** (52 node-click and 17 edge-click). Only clicks affect mastery |

**A session, from the student's side:**

1. A landing screen explains the map, how to answer, and why parts of it will dim.
2. The full map appears with all 52 nodes lit. **Nodes never move.** Their positions
   are stored in the data file, so the student's spatial memory stays valid.
3. The tutor asks a question, which stays pinned in a **question card** while
   hints arrive. The student answers by clicking a node or an edge (or choosing
   an option, for multiple choice), then confirms or undoes the click, so a
   misclick is never scored. The selected node is outlined in violet, and a note
   under the map names it and says how to confirm or switch.
4. **If the answer is wrong, the map narrows.** On the next turn 52 lit nodes
   become 12, then 9. The graph changes as soon as the tutor has decided, before
   its sentence has been written, and the note says what happened: *"Not this
   one. 40 concepts faded — the answer is one of the 12 still lit."*
5. Hints escalate one level per turn, up to level 4. After **8 turns** on one item
   the tutor reveals the answer, marks the item "resolved with support", and
   awards no mastery. This caps frustration.
6. Mastery is recomputed in Python after every scored click. Nodes are recoloured
   by mastery, never resized or moved. A failed item lowers the student's
   estimate on its prerequisites, and two failures in a row send the student back
   to the weakest prerequisite.
7. When a node is mastered, the next node is chosen from the ones whose
   prerequisites are all mastered, lowest mastery first.

The map can be zoomed from "Fit map" up to 4×, labels are shown in full, and a
badge in the header says whether the tutor is the offline script or a real
model.

**It runs with no API key.** Mock mode is the default: a scripted tutor stands in
for both model calls, and the narrowing, scoring and guards are the real code.

---

## Setup

### Prerequisites

- **Python 3.11** (verified on 3.11.9)
- **Node.js 20** and npm
- git

That is all. No database server, no Docker, no API key.

### 1. Clone

```bash
git clone https://github.com/Graybeep/Spatial-Socratic-Tutor.git
cd Spatial-Socratic-Tutor
```

### 2. Start the server (terminal 1)

```bash
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows (Git Bash)
source .venv/Scripts/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Install, check, and run:

```bash
pip install -r requirements.txt    # about 40 seconds
python -m build.validate           # expect: 0 error(s), 8 warning(s)
python -m pytest                   # expect: 556 passed
python -m server.main              # serves http://127.0.0.1:8000
```

### 3. Start the client (terminal 2)

```bash
cd client
npm ci                             # installs exactly what the lockfile pins
npm run dev                        # serves http://localhost:5173
```

### 4. Open it

Go to **http://localhost:5173**. The client looks for the API at
`http://127.0.0.1:8000` by default, so no configuration is needed.

A fresh clone reaches a working page in about **90 seconds**, or about 2.5
minutes including the test suite.

### If something looks wrong

- **`build.validate` prints 8 warnings.** That is expected. Each one names a
  known property of the item bank that the writeup discusses. Only
  `0 error(s)` matters.
- **Use a virtual environment.** Every dependency is pinned to the exact version
  the tests passed against. Installing into an existing environment will not
  downgrade packages that are already there, and the pins will not hold.
- **The client cannot reach the server.** Check the server is running on port
  8000. If you changed the port, set `VITE_API_BASE_URL` in `client/.env`.
- **Start from a clean state.** Student progress lives in `state.db` in the repo
  root. Delete it to start a new student.

---

## Using a real model

Copy the example config, then edit it:

```bash
cp .env.example .env
```

Set `MOCK_MODE=false`, pick a provider with `LLM_PROVIDER`, and fill in the key
it needs. `.env` is gitignored and never committed.

| `LLM_PROVIDER` | needs | Call 1 model | Call 2 model |
|---|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-5` | `claude-haiku-4-5` |
| `groq` | `GROQ_API_KEY` | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` |
| `local` | nothing | set `CALL1_MODEL` yourself | set `CALL2_MODEL` yourself |

Every real-model number in the report was measured on **`groq`**.

All three providers receive the same schema under a forced tool call, so a
response that fails validation fails the same way on each. Only the wire format
differs. If `MOCK_MODE=false` and no key is present, the server still runs: Call
1 falls back to the mock decision and Call 2 to a canned sentence, and both
fallbacks are logged.

### A local model

Point `LOCAL_BASE_URL` at any server that speaks `/v1/chat/completions` (LM
Studio, Ollama, llama.cpp's server, vLLM):

```bash
LLM_PROVIDER=local MOCK_MODE=false \
LOCAL_BASE_URL=http://127.0.0.1:1234 \
CALL1_MODEL=your/model CALL2_MODEL=your/other-model \
python -m server.main
```

- **Set both model names.** The defaults are the models this was developed on and
  will not exist on your machine. An unknown model comes back as a 400 error.
- **The model must support tool calls.** The architecture depends on a forced
  tool call with a validated schema.
- **Expect it to be slow.** One measured turn with local models (a 9B model for
  Call 1, a small Gemma for Call 2) took about 81 seconds, which is why local
  timeouts default to 180 seconds.

To see which models a local server offers: `curl http://127.0.0.1:1234/v1/models`

### Before recording or presenting

```bash
python -m server.preflight --expect-mock true    # must print "ready."
```

It checks that `main` is clean, `state.db` is absent, `MOCK_MODE` is what you
declared, and that the provider's daily token allowance has room for a take.

---

## Architecture

### The idea in one picture

```
 student clicks or types
          |
          v
 +------------------+   sees the answer, the item, the student's history
 | Call 1: DECIDE   |   returns: diagnosis, correct?, requested action,
 +------------------+            requested hint level, nodes to focus on
          |
          v
 +------------------+   owns every counter; applies the guards;
 | Server (Python)  |   decides the real action and hint level
 +------------------+
          |
          +-------------------------> graph_state sent to the client NOW
          |                           (the map dims before any text exists)
          v
 +------------------+   sees ONLY: action, hint level, focus node labels,
 | Call 2: SPEAK    |              the last 2 turns
 +------------------+   never the answer, never the source text while hinting
          |
          v
   one sentence, checked by guard layer 1, then the item's own question
   appended by the server, streamed into a map that has already changed
          |
          v
 mastery update in Python (clicks only), next-node choice in Python, log
```

**The split is the mechanism.** Call 1 needs the answer to judge the student.
Call 2 writes the words and is never given the answer, so it cannot say what it
was never told. This is guaranteed by the argument list of the function that
makes Call 2, not by an instruction asking the model to behave.

**How the question reaches the screen.** Call 2 is not given the item either.
After it has written its sentence and guard layer 1 has checked it, the server
appends the item's authored question as the last paragraph of `utterance`, and
the client splits that paragraph off into the question card. The question is
kept out of the history Call 2 sees on later turns, no other field carries it,
and no item's question contains its own answer or any of its aliases.

### One endpoint

Everything goes through `POST /turn`. With `?stream=true` it returns
server-sent events in this order: `graph_state`, then `utterance`, then `done`.
The client is built against the streaming form, because the order is the point:
the map reacts first. The full wire contract is in [`docs/API.md`](docs/API.md).

### What each part is responsible for

| Part | Responsibility | Never does |
|---|---|---|
| Call 1 (`server/llm.py`) | diagnose the student, request an action | emit a score or a mastery number |
| Server (`server/turn.py`) | own hint level, turn count and mastery; apply guards | let the model set a counter directly |
| Call 2 (`server/llm.py`) | write one sentence | see the answer, the aliases, or the source chunk while hinting |
| Mastery (`server/mastery.py`) | Rasch-style update, prerequisite decay, next node | call an LLM |
| Client (`client/src`) | render the frozen map and exactly one text field, split into the tutor's sentence and the question card | render any field except `utterance` |

Fields the model sends that the server may override are prefixed `requested_`.
The model requests; the server decides.

### Guard layers

| # | Layer | How it works |
|---|---|---|
| 0 | Structural | Only `utterance` is ever rendered. A whitelist at the serializer, not a filter |
| 1 | Answer monitor | Checks each sentence for the answer. Since Call 2 never saw it, a hit means the model reconstructed it from its own knowledge. Retry once, then use a canned line |
| 2 | Hint monotonicity | Hint level rises by at most 1 per turn and never falls within an item, capped at 4 |
| 3 | Turn budget | 8 turns on one item forces a reveal with zero mastery |
| 4 | Retrieval gate | If no source text scores above the floor, the tutor must say the chapter does not cover it |
| 5 | Mastery isolation | The model may only say correct or not. Python computes the number |
| 6 | Chunk delimiting | Retrieved source text is wrapped and marked as untrusted data |

### Mastery

Deterministic Python, unit-tested, no LLM:

- Each node has an ability estimate `theta`. A correct answer with hints counts as
  a correct answer on an **easier** item, so it earns less. A wrong answer with
  hints counts as a wrong answer on an easier item, so it costs **more**.
- The learning rate shrinks as a node gets more observations.
- A failed item lowers each prerequisite's estimate by 0.05. This is what makes
  the graph do work rather than decorate the screen.
- Only deterministic answers (clicks and multiple choice) can ever be scored.
  In this bank that means the 69 click items. Free text is for dialogue only,
  because grading it is unreliable.

### Frozen data, built offline

The graph and items are data files, built once and committed. Nothing about the
graph is computed at runtime.

```
chapter text -> chunks -> candidate concepts -> candidate edges
            -> human correction -> validate (DAG, orphans, granularity)
            -> freeze layout (x/y written into graph.json, once)
            -> generate items -> human review
```

The build scripts live in `build/` and are run by hand. In the end the graph was
hand-authored, which the plan allowed, and the extraction pipeline was measured
against it rather than used to build it. See [Results](#results).

### Deliberate simplifications

- **No agent framework.** Plain Python and `httpx`, two hand-written calls per
  turn. An earlier five-agent design was collapsed because the extra agents added
  latency and cost with no measurable teaching benefit.
- **Four runtime dependencies**: FastAPI, uvicorn, pydantic, httpx. Frozen since
  the end of week 2 and enforced by a test.
- **No hard-coded values.** Models, paths, thresholds and ports are in
  `server/config.py` and `.env`. Prompt text is in `prompts/`.

---

## Results

The full argument, with every number's command, is in
[`docs/writeup/report.md`](docs/writeup/report.md). Start there.

**What is claimed:**

| # | Claim | Status |
|---|---|---|
| 1 | The tutor cannot name the answer while hinting | holds by construction |
| 2 | Narrowing performs reductions that cannot be said in one sentence | holds by construction |
| 3 | A visual channel creates a visual leak channel that text checks cannot see | shown on this system |
| 4 | Visual narrowing beats a verbal hint | **not supported** |

**The headline number.** The shipped configuration gives a simulated student
with no knowledge **+8.6 points** of post-hint solve rate over no hints at all,
95% CI **[+1.9, +16.4]**. That is one cell in a grid of nine. Every other cell's
interval crosses zero, and at 52 items the comparisons are underpowered.

**Two bounds:**

- Graph extraction can recover at most **45%** of the true prerequisite edges at
  the shipped settings.
- The rate at which Call 2 reconstructed the answer on its own was **0 of 34**
  turns, a one-sided 95% upper bound of 8.4%.

**The numbers still hold after the September 25 interface update.** That update
shows the student the item's question. No simulated student reads the tutor's
text, so the evaluation's inputs did not change. Re-run on the updated build,
`python -m eval.adversarial` reproduces all twelve node-click cells of the
report's leakage table exactly.

**What this is not.** One chapter, a hand-authored graph, simulated students,
**no human study, no learning outcome measured**. See
[Limitations](#limitations).

---

## Limitations

The short version. Each is argued, with its numbers, in
[`docs/writeup/limitations.md`](docs/writeup/limitations.md).

**Scope**

- **One chapter.** Every number comes from one graph of 52 concepts. Nothing
  shows the method transfers to another chapter or subject, or which results
  depend on this graph's shape.
- **The graph was written by hand, not extracted.** The extraction pipeline was
  only measured against it, and can recover at most 45% of the prerequisite
  edges at the shipped settings.

**Evidence**

- **Simulated students only.** The leakage figures come from three scripted
  policies (zero-knowledge, partial-knowledge, adversarial). They model what the
  interface hands over, not how a real person reads a screen.
- **No human study, no learning outcome.** Nothing here shows that anyone learns
  more, faster, or for longer this way.
- **Thin statistics.** One of the nine leakage comparisons separates from zero.
  With 52 scored node-click items, the confidence intervals are 6 to 7 points
  wide.
- **Half the latency is unmeasured.** Call 1 is timed on a real model (median
  2.3s). Call 2 and the full turn are not, and the demo is paced by the mock.

**Scoring and the item bank**

- **Mastery is shallow evidence.** It rests on 1 or 2 recognition-level click
  items per concept, asked again on later visits, so it measures familiarity
  with the map more than understanding. A flawless student masters 1 node in 20
  turns.
- **All 159 multiple-choice items are placeholders and are not scored.** The
  correct option is the longest one in every item. They are still shown, and
  now that the question card exists, their templated wording (*"What does Packet
  Flow actually do?"*) is on screen.
- **Edge questions name one end of the connection.** For 32 edge items that
  leaves a single possible answer, so they are not scored. The 17 scored ones
  leave two, a coin flip before any hint.

**Guards and interface**

- **The answer monitor misses paraphrase.** Guard layer 1 matches tokens, so an
  answer restated in other words gets through.
- **The two human checks were never run.** Nobody has tested the dimming on a
  projector or watched a stranger use confirm-or-undo. The colours and label
  size changed on September 25, so the contrast figures in
  [`docs/dim-values.md`](docs/dim-values.md) are computed, not observed. Labels
  are larger now, and at full-screen size a ruled-out label is faintly readable.
- **With a real model, a wrong answer can be moved past.** Call 1's requested
  action becomes the server's action, and nothing checks that `advance` follows
  a correct answer. Mock mode, and so the demo, is unaffected.

---

## Running the evaluations

| Command | Measures | Needs a key |
|---|---|---|
| `python -m eval.adversarial` | effective leakage: can a student who does no reasoning solve the item after a hint? | no |
| `python -m eval.graph_quality` | extraction recall against the hand-annotated gold graph | no |
| `python -m eval.distractor_screen` | multiple-choice distractors that are never picked, or picked as often as the key | no |
| `python -m eval.leak_monitor` | how often guard layer 1 fired, per build and per action | no (reports `NOT MEASURABLE` on mock turns) |
| `python -m eval.diagnosis_readthrough --n 30` | 30 diagnoses printed beside the student's true state, for reading by hand | **yes**, refuses to run on the mock |

Every real-model turn this project made is archived in
`eval/results/real_turns.jsonl.gz`, so the key-dependent numbers can be
recomputed without a key:

```bash
gunzip -c eval/results/real_turns.jsonl.gz > turns.jsonl
python -m eval.leak_monitor     --log turns.jsonl --build 18d220d
python -m eval.curriculum_moves --log turns.jsonl --build 18d220d
```

Every eval output includes a `provenance` block (population, distinct items,
coverage). Check it before quoting a number: a rate over one item has the same
shape as a rate over a hundred.

---

## Configuration

Everything is in `.env` (see `.env.example`, which documents each value) and read
once at startup by `server/config.py`. The ones worth knowing:

| Variable | Default | What it does |
|---|---|---|
| `MOCK_MODE` | `true` | scripted tutor, no key, no network |
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `groq` or `local` |
| `LADDER_MODE` | `interleaved` | `interleaved`, `visual_only`, `verbal_only` or `none` |
| `NARROW_SCHEDULE` | `0,12,9,7,5` | how many nodes stay lit at each hint level |
| `MAX_GUESS_PROBABILITY` | `0.2` | the narrowing floor (never fewer than 5 lit) |
| `TURN_BUDGET` | `8` | turns on one item before a forced reveal |
| `HINT_MAX` | `4` | highest hint level |
| `MASTERY_THRESHOLD` | `0.6` | mastery needed to count a node as learned |
| `MODEL_BACKTRACK` | `false` | whether Call 1 may send the student back a node |
| `PORT` | `8000` | server port |

Try the hint channels side by side:

```bash
LADDER_MODE=verbal_only python -m server.main         # hints, but nothing dims
NARROW_SCHEDULE=0,25,18,12,8 python -m server.main    # a gentler narrowing
```

---

## Future scope

What would come next, ordered roughly by how much each would strengthen the
central claim.

**Evidence**

- **A human study.** Every number comes from simulated students. The first real
  question is whether people learn more, or leak less, with the map than without
  it.
- **A larger scored item bank.** With 52 node-click items the confidence
  intervals are 6 to 7 points wide, too wide to settle whether visual beats
  verbal. More items per node would power that comparison.
- **Re-run the leakage eval on a real model.** It currently uses template
  sentences, because the free API tier makes a full real-model run take days.
  The visual arm does not depend on the text, but the verbal arm does.
- **Time Call 2 on a real provider.** The full turn latency on a cloud model has
  never been measured, so whether the two-call split costs total time is open.
- **Run the two human checks.** The projector contrast test and a stranger
  trying confirm-or-undo were planned and never run. `docs/human-tests.md` is a
  ready-to-follow kit for both.
- **The matched-elimination comparison.** Compare a visual hint with a verbal
  hint that names the exact same excluded nodes. Cut for time; still the cleanest
  test of whether modality matters.

**Content**

- **Make the multiple-choice items scorable.** In all 159 of them the correct
  option is also the longest, so all 159 are excluded from scoring. Rewriting the
  distractors could grow the scored bank from 69 items to as many as 228.
- **Edge questions that do not give away an endpoint.** Today each one names the
  concept the connection leads into, which leaves one or two candidates before
  any hint. Asking about the relationship instead would let edge items measure
  the narrowing.
- **A second chapter.** Nothing here shows the approach transfers.
- **Any topic of choice.** Today the tutor teaches one fixed chapter. The goal is
  to let a learner pick any topic and get a map and questions built for it. The
  current pipeline cannot do that yet: it finds 30 of 66 true prerequisite edges
  (at most 49 of 66, or 74%, however it is tuned), because it only proposes an
  edge when the prerequisite is named first. Its generated multiple-choice items
  put the correct answer as the longest option in 159 of 159. Getting there
  needs four things: edge proposal that does not depend on text order, a required
  human correction step, automatic item-quality screens, and `build/validate.py`
  as the gate every generated topic must pass. The plan is in the report's
  "Future work: any topic" section.
- **Stronger mastery evidence.** Give each concept at least 3 distinct scored
  items, and stop crediting a correct answer on a question the student has
  already solved. Today mastery rests on 1 or 2 recognition clicks per concept,
  which measures familiarity with the map more than understanding.

**Tutor behaviour**

- **Learner choice, done as a mastery prior.** A "start here" picker does not
  work, because every session begins at the graph's three root nodes and the
  first advance would send the student back. Instead, choosing a section could
  mark its prerequisites as provisionally known, and the existing backtrack rules
  would correct the student if that was wrong. Designed in the report, not built.
- **Explain-first mode for beginners.** When a concept's prerequisites are all
  unmastered, explain a prerequisite first, then ask about the target concept, so
  the explanation scaffolds the question without answering it. Not built:
  explaining a node and then asking for that node is 100% leakage by
  construction for click items, and would invalidate the effective-leakage
  measurements (report §5.2).
- **Let the ladder reach its floor.** The shipped ladder alternates visual and
  verbal hints and stops at 9 lit nodes, not the 5 the floor allows. Whether 5
  reads better is untested.
- **A semantic answer monitor.** Guard layer 1 uses token overlap, which misses a
  paraphrase of the answer. An embedding check would catch it, at the cost of a
  new dependency.
- **Only advance after a correct answer.** One check in `server/turn.py` would
  stop a live Call 1 from moving a student past an item they got wrong. It only
  matters with a real model. It was found after the feature freeze and left as
  it is.
- **Faster visible mastery.** A flawless student masters 1 node in 20 turns. The
  scoring constants are deliberately conservative. Tuning them is a research
  question, not a fix.

---

## Project status

Four-week project, 2026-09-04 to 2026-10-01. Feature freeze was cut on
2026-09-22, three days early, and the evaluation numbers are final.

After the freeze, only demo-path fixes and writeup edits went in, with one larger
exception. On 2026-09-25 the interface was redesigned for the demo: the landing
page, the question card, the guide note under the map, map zoom, full labels,
and the mode badge. It changes what the student sees, not what the tutor
decides, and the evaluation reproduces unchanged on it (see [Results](#results)).

**Done:** the graph, the item bank, the two-call tutor, the guards, mastery,
the evaluations, the report, and the interface.

**Left:** record the walkthrough video, then tag that commit `demo`. The
projector test and the stranger test (see [Limitations](#limitations)) are
still open.

| Milestone tag | Meaning |
|---|---|
| `schemas-frozen` | wire and data schemas fixed, mock server running |
| `graph-frozen` | the chapter graph and gold annotation committed |
| `loop-working` | the two real calls, prompts and guards working end to end |
| `feature-freeze` | demo-path fixes only from here |
| `demo` | the commit shown in the recorded walkthrough (added after recording) |

Day-by-day decisions and slips are recorded in [`docs/schedule.md`](docs/schedule.md).
The settled design is in [`CLAUDE.md`](CLAUDE.md); read it before changing code.

---

## Where things are

| Path | What it is |
|---|---|
| [`docs/writeup/report.md`](docs/writeup/report.md) | **the report: start here** |
| [`docs/writeup/limitations.md`](docs/writeup/limitations.md) | every known limitation, argued |
| [`docs/API.md`](docs/API.md) | the wire contract between server and client |
| [`docs/walkthrough-script.md`](docs/walkthrough-script.md) | the three-minute demo script |
| [`docs/human-tests.md`](docs/human-tests.md) | the projector and stranger tests, ready to run |
| [`docs/dim-values.md`](docs/dim-values.md) | the dimming and colour values, their contrast, and where to record the projector result |
| [`CLAUDE.md`](CLAUDE.md) | the settled design and hard rules |
| `server/turn.py` | the per-turn pipeline |
| `server/llm.py` | the two model calls and the three providers |
| `server/guards.py` | guard layers 1, 4 and 6 |
| `server/mastery.py` | scoring and next-node selection |
| `server/schemas.py` | the frozen schemas; snapshots in `schemas/` |
| `server/mock_tutor.py` | the scripted tutor used in mock mode |
| `server/preflight.py` | the pre-recording checks |
| `server/config.py` | every setting and its default |
| `prompts/` | the tutor contract, both call prompts, canned fallback lines |
| `client/src/App.tsx` | the session, the question card, the guide note and map zoom |
| `client/src/Graph.tsx` | the frozen-layout map and dimming |
| `client/src/Chat.tsx` | transcript, answer box, turn budget, node panel |
| `client/src/Landing.tsx` | the screen before the map |
| `client/src/tokens.css` | colours and the dimming values |
| `client/contrast-check.html` | the projector test page; open it without a server |
| `data/graph.json` | nodes, edges and layout |
| `data/items.json` | the item bank |
| `data/gold_graph.json` | hand-annotated edges, used only for evaluation |
| `build/` | the offline pipeline; `build/validate.py` must pass before commit |
| `eval/` | the evaluations; raw outputs in `eval/results/` |
| `tests/` | 556 tests |

---

## Source and licence

The concept graph and items are derived from Chapter 6, *Congestion Control*, of
Larry Peterson and Bruce Davie, *Computer Networks: A Systems Approach*
(<https://book.systemsapproach.org/congestion.html>), released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0). Attribution and details
of what is committed are in [`data/SOURCE.md`](data/SOURCE.md).
