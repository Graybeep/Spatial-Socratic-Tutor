# CLAUDE.md — Spatial Socratic Tutor

Read this file fully before writing code. It encodes decisions that were argued
through and settled. Do not re-litigate them mid-implementation. If a decision
here blocks you, stop and ask the human; do not route around it.

---

## 0. Project constraints

- **Duration:** 4 weeks, hard stop.
- **Team:** one person, working both roles. "Person A" (content/graph/scoring) and
  "Person B" (interface/tutor loop) are a **split of the work, not two people** — they
  name the two layers and the boundary between them. Every rule below that mentions
  Person A or Person B still applies; read it as a rule about which layer you are in
  right now, not about who is at the keyboard. The layer separation is the point, and
  it is worth *more* solo than it would be in a pair: it is the only thing stopping a
  quick fix on one side from silently reaching across into the other.
  Practical consequences of being solo are noted in §1.9, §11 and §13.2.
- **Deliverable:** a working local demo over ONE chapter + three eval numbers.
- **Not a deliverable:** a product, a deployment, a human study, arbitrary PDF ingestion.

**Thesis the demo must support:**
LLM tutors leak answers because their only way to help is to say more. This tutor
helps by showing less: it narrows a concept graph visually instead of explaining.

Every feature must serve that sentence. Anything that doesn't is out of scope.

---

## 1. Hard rules

Violating any of these invalidates the project. They are not preferences.

1. **No agent framework.** No LangGraph, CrewAI, AutoGen, LlamaIndex agents.
   Plain Python orchestration with `httpx` and the model API. Two LLM calls total
   per turn, both hand-written.
2. **The knowledge graph is frozen data.** Built offline, hand-corrected, committed
   as `data/graph.json`. Nothing about the graph is computed, mutated, or re-laid-out
   at runtime. Node x/y coordinates are stored in the file.
3. **Mastery is computed in Python, never by an LLM.** The model may emit a boolean
   `correct`. It may not emit a score, a percentage, or a mastery estimate.
4. **Mastery is scored only on deterministic items:** node click, edge click, MCQ.
   Free-text answers are for teaching and dialogue only. Never score them.
   Free-text grading is unreliable and silently corrupts the entire adaptive path.
5. **Call 2 never receives the answer.** Not the answer string, not the answer
   aliases, not the source chunk during `ask` or `hint_*` actions. See §5.
6. **The client renders exactly one text field: `utterance`.** Whitelist, not filter.
   Any other field reaching the client is a bug at severity 1.
7. **Server owns all counters.** `hint_level`, `turn_count`, `n_obs` are server state.
   The model *requests*; the server *decides*. Fields from the model are prefixed
   `requested_`.
8. **No new dependencies after end of week 2.** No exceptions.
9. **Neither layer edits the other.** Schemas are the contract. Solo, this becomes a
   self-discipline rather than a fact about access: when a change wants to touch both
   layers in one sitting, that is a signal the schema is wrong — fix the schema
   deliberately, or do the two edits as two separate commits. Never "just reach across".
10. **No hard-coded values in code.** Model names, API keys and base URLs, file paths,
    thresholds, hint caps, turn budgets, prompt text and port numbers live in
    `server/config.py`, `.env` or `prompts/` — never as literals inside logic. See §13.
11. **Push to GitHub regularly.** Remote is
    `https://github.com/Graybeep/Spatial-Socratic-Tutor.git`. Commit at every working
    checkpoint, push at least daily. See §13.

---

## 2. Repo layout

```
/data
  graph.json          # frozen: nodes, edges, layout coords
  items.json          # frozen: item bank
  gold_graph.json     # hand-annotated prereq edges, for eval only
/build                # offline pipeline, run manually, not at runtime
  extract_concepts.py
  extract_edges.py
  generate_items.py
  freeze_layout.py
  validate.py         # DAG check, schema check, orphan check
/server
  main.py             # FastAPI, one meaningful endpoint: POST /turn
  turn.py             # orchestrator
  llm.py              # two call wrappers, structured output, retry
  guards.py           # layers 1-6
  mastery.py          # deterministic scoring + selection
  retrieval.py        # chunk search, gated
  state.py            # sqlite student state
/client
  src/Graph.tsx       # React Flow, static layout
  src/Chat.tsx
  src/api.ts
/eval
  adversarial.py      # simulated student, published attack taxonomy
  matched_hints.py    # visual vs verbal at matched elimination
  graph_quality.py    # precision/recall vs gold_graph.json
  distractor_screen.py
/logs                 # every turn, full Call 1 output, jsonl
```

---

## 3. Frozen schemas

**Freeze these on day 2. Mock the server against them so Person B is never blocked.**
A schema change in week 2 costs both people a day.

### graph.json

```json
{
  "version": "1.0",
  "domain": "computer_networks_ch3",
  "nodes": [
    {
      "id": "tcp_slow_start",
      "label": "Slow Start",
      "definition": "one-sentence, from source",
      "source_sections": ["3.7.1"],
      "difficulty": 0.4,
      "x": 340, "y": 180
    }
  ],
  "edges": [
    { "from": "tcp_aimd", "to": "tcp_fast_recovery", "type": "prereq" }
  ]
}
```

Constraints enforced by `build/validate.py`, which must pass before commit:
- prereq edges form a **DAG** (a cycle makes next-node selection loop forever)
- every node teachable in one ~5-minute exchange — reject "TCP" sitting beside
  "the 0.5 multiplicative decrease factor"
- no orphan nodes, no dangling edge endpoints
- 40–60 nodes total

### items.json

```json
{
  "id": "itm_0031",
  "node_id": "tcp_slow_start",
  "type": "node_click | edge_click | mcq",
  "prompt": "Click the node where the sender first probes for capacity.",
  "answer": "tcp_slow_start",
  "answer_aliases": ["slow start", "slow-start", "ss phase"],
  "distractors": ["tcp_aimd", "tcp_fast_recovery", "tcp_flow_control"],
  "difficulty": 0.4,
  "visually_answerable": true,
  "answer_spans": [[1204, 1310]]
}
```

- `visually_answerable`: **true only if the answer is a node or edge on the graph.**
  "Why does TCP halve cwnd on loss?" is a mechanism, not a node → `false`.
  Expect more than half the bank to be `false`. The matched-hint eval runs on the
  `true` subset only; mixing them makes the comparison invalid.
- `answer_aliases`: short-answer strings for Layer 1 exact/fuzzy matching.
- `answer_spans`: character offsets of the answer inside the source chunk, for
  masking. Populate at build time.

---

## 4. Offline pipeline (`/build`, Person A, week 1)

Run manually. Never at runtime.

```
chapter.pdf
 → PyMuPDF text + section headings
 → chunk at section level, retain heading path
 → LLM pass 1: candidate concepts {id, label, definition, source_span}
 → canonicalize: merge candidates with embedding cosine > 0.88, human confirms
 → edge CANDIDATES only where A precedes B in text AND co-occur within 2 sections
 → LLM pass 2: classify each candidate edge as prereq | related | none
 → HUMAN CORRECTION PASS   ← this is the actual work, do not defer it
 → validate.py: DAG, granularity, orphans
 → freeze_layout.py: run dagre ONCE, write x/y into graph.json
 → generate_items.py: 5 items per node
 → HUMAN REVIEW (see §9 on distractors)
```

The pairwise-precedence filter matters: 50 nodes is 2,450 unordered pairs. The
ordering + co-occurrence prior cuts that to roughly 150 LLM calls.

**Pick a prose-heavy chapter.** Equation and table extraction will eat two days
and buys nothing.

**Fallback that is fully acceptable:** if extraction quality is poor by day 3,
hand-write `graph.json` in a text editor. A hand-authored 40-node graph is a valid
input to everything downstream. Curated graphs are what the comparable published
systems use. Say so in the writeup rather than hiding it.

---

## 5. Runtime architecture

One meaningful endpoint: `POST /turn`.

```
1. load student_state from sqlite
2. assemble Call 1 context
3. CALL 1  → decision object
4. server applies guards, updates counters, decides final action
5. graph_state returned/streamed IMMEDIATELY (client dims from focus_nodes)
6. CALL 2  → utterance only
7. if the turn scored a deterministic item → mastery.update() in Python
8. if node complete → mastery.next_node() in Python
9. log everything to /logs
```

### Call 1 — diagnosis and decision

Inputs: current item, **the answer**, retrieved chunk, last 6 turns, student state.
Output schema:

```json
{
  "student_state": "on_track|confused_prereq|stuck|correct|guessing",
  "diagnosis": "internal reasoning, never rendered, always logged",
  "correct": true,
  "requested_action": "ask|hint_visual|hint_verbal|advance|backtrack|explain",
  "requested_hint_level": 2,
  "focus_nodes": ["tcp_slow_start", "tcp_aimd"],
  "expects": "text|node_click|edge_click|mcq"
}
```

**There is no `answer_known` field.** Call 1 reads the answer from `items.json`;
restating it only puts the answer into the generation stream for zero gain.
Do not add it back.

### Call 2 — utterance

Fresh context. Receives **only**:
`action`, `hint_level`, focus node **labels**, last 2 turns.

Output: `{ "utterance": "..." }`

**Retrieval gate — this is the point of the split.** The source chunk explains the
concept being questioned, in fluent student-ready prose. Handing it to Call 2 leaks
the answer in higher fidelity than any single field would.

| action | chunk passed to Call 2? |
|---|---|
| `ask`, `hint_visual`, `hint_verbal` | **no** — labels only |
| `advance`, `explain` | yes, with `answer_spans` masked |
| `backtrack` | prereq node chunk only |

Call 2 does not need source text to ask a question about two highlighted nodes.

### Latency

Call 1 is ~120 output tokens (~1s). The graph dims off `focus_nodes` before Call 2
starts. Call 2 streams into an already-changed screen. This is a *better* perceived
latency profile than a single 500-token call, not a tax.

**Required:** six canned fallback utterances, one per action, for Call 2 timeout
after the graph has already reacted.

---

## 6. Guardrails

Ordered by how much they actually save you.

| # | Layer | Mechanism |
|---|---|---|
| 0 | **Structural** | Only `utterance` renders. Whitelist at the serializer. Student text never reaches the renderer, so this is not jailbreakable from the chat surface. |
| 1 | **Answer monitor** | See below. Post-split this is a *monitor*, not a guard. |
| 2 | **Hint monotonicity** | Server counter. `+1` per turn max, never decreases within an item. `hint_level = min(counter, 4)`. |
| 3 | **Turn budget** | 8 turns on one item → forced reveal, mark `resolved_with_support`, award zero mastery. Prevents the frustration loop that kills real users. |
| 4 | **Retrieval gate** | No chunk above threshold → tutor must state the chapter doesn't cover it. Log every occurrence. |
| 5 | **Mastery isolation** | LLM emits a boolean. Python computes the number. |
| 6 | **Chunk delimiting** | Retrieved text wrapped and marked as untrusted data — the source PDF is an injection surface. |

### Layer 1 detail

Because Call 2 never saw the answer, a trigger here means the model **reconstructed
the answer parametrically**. Log the rate; it is a free and genuinely interesting
number for the writeup.

Split the check by answer length — cosine similarity against a two-token string is
close to meaningless:

```python
if len(tokenize(answer)) <= 5:
    hit = fuzzy_match(utterance, item["answer_aliases"], threshold=0.9)
else:
    hit = cosine(embed(utterance), embed(answer)) > 0.85
```

On hit: regenerate Call 2 once, then fall back to the canned utterance. Always log.

---

## 7. Mastery and selection

`server/mastery.py`. Deterministic. No LLM. Unit-tested.

```python
HINT_MAX = 4
K_START, K_MIN = 0.4, 0.15
THRESHOLD = 0.6

def update(theta, difficulty, correct, hint_level, n_obs):
    h = min(hint_level, HINT_MAX)
    d_eff = difficulty - 0.5 * h          # hinted item is an EASIER item
    p = 1 / (1 + math.exp(-(theta - d_eff)))
    k = max(K_MIN, K_START / (1 + 0.15 * n_obs))
    return theta + k * (float(correct) - p)

def mastery(theta):
    return 1 / (1 + math.exp(-theta))
```

**Do not** implement this as `observed = correct * (1 - 0.25 * hint_level)`.
That form goes negative past hint 4 and clamping it to zero throws away signal by
making a heavily-hinted correct answer identical to a wrong one. Adjusting effective
difficulty is the model-consistent fix: correct-with-hints yields a small positive
update; **wrong-with-hints yields a large negative one**, which is correct — failing
*with* help is stronger evidence of not knowing than failing without it.

**Backward propagation.** On a failed item, decay each prerequisite node's theta by
`0.05`. This is what makes the graph do work instead of being decoration. Without it
you have a mind map with numbers on it.

**Next-node selection.**

```python
def next_node(graph, mastery_map):
    ready = [n for n in graph.nodes
             if all(mastery_map[p] >= THRESHOLD for p in graph.prereqs(n))]
    unmastered = [n for n in ready if mastery_map[n] < THRESHOLD]
    return min(unmastered, key=lambda n: mastery_map[n]) if unmastered else None
```

Two consecutive failures on the current node → backtrack to its lowest-mastery
prerequisite.

---

## 8. Interface rules

- **Layout is frozen.** Nodes never move. If they move on mastery update, the student
  loses spatial memory and the entire spatial claim evaporates.
- **Dimming must survive a projector.** Opacity alone fails on bad contrast. Use
  opacity **plus** desaturation **plus** stroke width. Test on the actual demo
  hardware in **week 3**, not week 4.
- **Click answers need confirm-or-undo.** A misclick scored as wrong corrupts mastery.
- Mastery recolors nodes; it does not resize or reposition them.
- Graph reacts on Call 1 return, before `utterance` arrives. Never block the visual
  on the text.

---

## 9. Evaluation (`/eval`, week 4)

Three numbers. Build these instead of polish.

### 9.1 Leakage, measured as post-hint solve rate

**Do not measure leakage as "does the answer string appear in the utterance."** That
scores visual hints at 0% by construction and a reviewer kills it in ten seconds.

Measure **effective leakage**: after the hint, can a simulated student that performs
no reasoning produce the correct answer? Dimming 50 nodes to 2 is a coin flip and may
transfer *more* information than the verbal hint it is compared against.

Run 60 dialogues, not 30 — below ~15 percentage points, differences at n=30 are noise.
Use a published adversarial attack taxonomy so the numbers are comparable to existing
baselines rather than to an invented one.

### 9.2 Matched-elimination visual vs verbal

**Do not match by hint-level label.** That reproduces the metric problem one layer down.

Match by **the same named excluded node set**: if the visual hint dims to leave 12 of
50 candidates, the verbal hint must eliminate *those same 38 nodes by name*.

This is only tractable at fine granularity — you cannot name 38 nodes in one utterance.
**Treat that constraint as the finding, not a limitation.** Report two claims:

- At fine granularity (~hint level 3+), matched-elimination visual and verbal perform
  comparably, or visual wins.
- At coarse granularity, the visual channel performs reductions that **cannot be
  expressed verbally in one turn**.

The second is a structural argument for the spatial interface and does not depend on
winning a horse race. If the fine-grained comparison comes back null, that shows the
mechanism is information reduction rather than modality — still a real result, and a
more defensible one.

### 9.3 Graph precision/recall

Hand-annotate `gold_graph.json` for the chapter. Report automated extraction against
it **before** human correction. Reporting 0.6 and stating that you corrected it by
hand is more credible than implying it was automatic.

### 9.4 Distractor screen (free, from logs you already have)

Four hours over 250 items is 58 seconds each — enough for the key, not for three
distractors. A bad distractor corrupts mastery *more quietly* than a wrong key,
because nothing downstream flags it.

From the 60 eval dialogues:
- distractor never selected → dead weight; the item is silently 3-choice while scored
  as 4-choice
- distractor selected as often as the key by a **strong** simulated student → likely
  also-correct or ambiguous

Flagged items go to the human pass. This is a fourth number at near-zero cost.

### 9.5 Diagnosis read-through (week 3, manual, non-optional)

Hand-read 30 logged `diagnosis` fields. This is the only way to find out whether the
tutor's model of the student bears any relationship to reality, and no metric above
would catch that failure.

---

## 10. Things to avoid

**Do not build these. They are deleted, not deferred. Do not add them to a roadmap
slide — they weaken the pitch.**

- NeRF / Gaussian Splatting / Three.js / any 3D
- A simulation engine
- A "visualization agent" that picks chart types
- Arbitrary PDF upload
- Misconception detection (needs a domain taxonomy that does not exist here)
- A five-level adaptive difficulty ladder (~5 items per node leaves no statistical room)
- Auth, multi-user, user profiles, cloud deployment

**Deferred to one 15-second Phase 2 slide:** automated extraction over arbitrary
uploads, cross-chapter entity resolution, learner-style personalization, human study.

**Collapsed, and say so out loud as a design decision:** the five agents from the
original document became one tutor pipeline plus retrieval plus two deterministic
functions. *"We removed three agents because they added latency and cost without
measurable pedagogical gain"* is a stronger line than *"we have five agents."*

**Also avoid:**
- LLM-scored free text anywhere near mastery
- Dynamic graph re-layout
- Re-injecting the tutor contract only at session start — the model drifts back into
  explaining over ~20 turns. Re-inject every turn.
- Silent retries. Every retry, guard trigger and parse failure gets logged. If
  structured-output parse failure exceeds 2%, the schema is too complex — simplify it.

---

## 11. Schedule and cut order

| | Person A | Person B |
|---|---|---|
| Days 1–2 | **Both:** freeze schemas, mock the server | |
| Week 1 | extract + hand-correct graph; generate + review items | React Flow static graph, node panel, chat shell |
| Week 2 | retrieval, mastery service, next-node rule | two-call tutor loop, hint escalation, node↔chat binding |
| Week 3 | **Integration — budget the whole week** | + projector contrast test, diagnosis read-through |
| Week 4 | evals 9.1–9.4 | demo polish, writeup, rehearse |

**One person means the two columns are not parallel.** The table stays as written —
it is the definition of the two tracks — but a week's row is a week's *total* work,
alternated, not two weeks of capacity. Read the columns as "both of these happen this
week", and expect to switch tracks within a week rather than to run them at once.
Two consequences:

- The mock server (days 1–2) is still worth its cost. Its original job was to unblock
  Person B while Person A built the graph; solo, its job is to let the interface track
  proceed without the real graph existing yet, and to keep the schema boundary honest.
  Do not skip it on the grounds that nobody is waiting on you.
- The cut order in §11 matters more, not less. There is no second person to absorb a
  slip, so when a week overruns, cut from the bottom of the list rather than borrowing
  time from the next week.

- **Feature freeze: day 22.**
- **Record a full video walkthrough by day 26.** Cheapest insurance in the project.
- **If week 3 slips, cut retrieval before you cut the tutor loop.** One chapter fits
  in context. RAG is architecture theater at this scale — keep it because it is in the
  pitch, drop it without guilt if time goes.
- If forced to choose, ship items 1–4 of §1 working end-to-end over six things at 80%.

---

## 12. Prior art — do not accidentally reproduce it

GraphMASAL, TutorLLM, Auto-HKG, ALEKS all already do graph + multi-agent + mastery +
adaptive path, several with published evals. Feature parity with them is worth nothing.

The one contribution that is ours: **the visual as a shared referent in the dialogue —
pointing as an answer, and dimming as a non-verbal hint channel.** Nobody in that list
has a tutor that narrows the student's search space without saying more.

Protect that. Cut anything else first.

---

## 13. Configuration and version control

These are hard rules §1.10 and §1.11 spelled out. They are process rules, not
architecture — they do not override anything in §1–§12.

### 13.1 No hard-coding

Nothing that a human might reasonably want to change gets typed as a literal inside
logic. Concretely:

| Kind | Lives in | Never in |
|---|---|---|
| Model IDs, API base URLs, temperature, max tokens, timeouts | `server/config.py` (read from env with defaults) | `llm.py` call sites |
| API keys | `.env`, gitignored; `.env.example` committed with empty values | anywhere in git, ever |
| Data paths (`data/graph.json`, `data/items.json`, sqlite path, `logs/`) | `server/config.py` | scattered `open("data/...")` calls |
| Scoring constants (`HINT_MAX`, `K_START`, `K_MIN`, `THRESHOLD`, prereq decay `0.05`, `d_eff` slope `0.5`) | module-level named constants in `mastery.py`, overridable from config | inline literals inside `update()` |
| Guard constants (turn budget `8`, fuzzy threshold `0.9`, cosine threshold `0.85`, short-answer token cutoff `5`, retrieval score floor) | `server/config.py` | inline in `guards.py` |
| Prompt text — tutor contract, Call 1 schema instructions, Call 2 instructions, the six canned fallback utterances | `prompts/*.txt` or `prompts/*.md`, loaded at startup | Python string literals |
| Frontend API base URL, port | `client/.env` / Vite env | `api.ts` |
| Build pipeline knobs (cosine merge `0.88`, co-occurrence window `2 sections`, items-per-node `5`, node count bounds `40–60`) | `build/config.py` | inline in each build script |

Two clarifications so this does not get misread:

- **Frozen data is not hard-coding.** `data/graph.json`, `data/items.json`,
  `data/gold_graph.json` and the x/y layout coordinates inside them are *data files*.
  §1.2 requires them to be static and committed. Hand-authoring `graph.json` per §4's
  fallback is fine. This rule is about literals in *code*, not values in *data*.
- **Schemas are not config.** The Call 1 / Call 2 output schemas in §5 and the file
  schemas in §3 are the frozen contract between two people (§1.9). They are defined
  once in code, not made configurable, and not changed after day 2.

A config value gets a default that makes the demo run with zero setup beyond an API
key. Config is read once at startup into a frozen object; no module reads `os.environ`
at call time.

### 13.2 Git and GitHub

Remote: `https://github.com/Graybeep/Spatial-Socratic-Tutor.git`

- **Branch `main` is the demo branch and must always run.** If `main` is broken at the
  end of a day, fix it or revert it before logging off.
- Work on `a/<topic>` and `b/<topic>` branches by **layer, not by author**, and merge
  to `main`. §1.9 says neither layer edits the other, so merge conflicts should be
  near-zero; a conflict outside `data/` or a schema file means the branch crossed the
  line. Solo this costs almost nothing and buys the one thing a single worker cannot
  get from a colleague: a diff that shows, per branch, which layer a change actually
  touched. Committing straight to `main` erases exactly that signal.
- **Commit at every working checkpoint. Push at least once per day.** Work that exists
  only on one laptop is the single cheapest way to lose a week of a four-week project —
  and with one person there is no second copy of the repo anywhere by default.
- Tag milestones: `schemas-frozen` (day 2), `graph-frozen`, `loop-working`,
  `feature-freeze` (day 22), `demo` (day 26, matching the recorded walkthrough).
- Commit messages: one line, imperative, naming the layer —
  `mastery: add prereq backward decay`, `client: dim nodes off focus_nodes`.

**Committed:** all source, `data/*.json`, `prompts/`, `.env.example`, `eval/`, tests.
**Gitignored:** `.env`, `logs/*.jsonl`, `*.db`/sqlite state, `__pycache__/`,
`node_modules/`, `client/dist/`, the source PDF if licensing is unclear.

Logs are gitignored but they are *evidence for §9.1, §9.4 and §9.5* — do not delete
them, and archive the 60 eval dialogues somewhere durable before the week-4 writeup.
