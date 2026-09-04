# API contract — frozen day 2

This is the contract between Person A and Person B (CLAUDE.md §1.9). The
authoritative definition is `server/schemas.py`; the JSON Schema snapshots in
`/schemas` are what fails CI if it drifts. This page is the readable version.

Base URL defaults to `http://127.0.0.1:8000` (`VITE_API_BASE_URL`).

---

## Running the mock

```bash
pip install -r requirements.txt
python -m build.make_mock_data      # writes the placeholder data/ fixtures
python -m build.validate --fixture  # must be clean
python -m server.main               # http://127.0.0.1:8000
```

No API key, no network. `MOCK_MODE=true` is the default.

`GET /health` reports `mock_mode`, node and item counts.

---

## Endpoints

### `GET /graph`

The frozen graph. **Fetch once, at session start.** Nothing in it changes for the
life of the session — CLAUDE.md §1.2 and §8: the layout is frozen and nodes never
move. Per-turn state comes from `graph_state` instead.

```json
{
  "version": "1.0",
  "domain": "MOCK_computer_networks_ch3",
  "nodes": [
    { "id": "tcp_slow_start", "label": "Slow Start", "definition": "...",
      "source_sections": ["3.7.1"], "difficulty": 0.4, "x": 340, "y": 180 }
  ],
  "edges": [ { "from": "tcp_aimd", "to": "tcp_fast_recovery", "type": "prereq" } ]
}
```

Render `x`/`y` verbatim. Do not run a layout algorithm. Do not let nodes move on
mastery update — that is the one change that would invalidate the whole spatial
claim.

### `POST /session`

```json
→ {}                                    ← {"session_id": "sess_ab12cd34", "schema_version": "1.0"}
```

### `POST /turn`

The only meaningful endpoint. `response: null` opens the dialogue or asks for the
next item.

```json
{
  "session_id": "sess_ab12cd34",
  "response": {
    "type": "text | node_click | edge_click | mcq",
    "text":      "...",                        // type=text
    "node_id":   "tcp_slow_start",             // type=node_click
    "edge":      {"from": "a", "to": "b"},     // type=edge_click
    "choice_id": "tcp_slow_start"              // type=mcq
  }
}
```

`type` must match the `expects` the server last sent. Unknown fields are rejected
with 422 — the schema is `extra="forbid"` everywhere on purpose.

**Only send confirmed clicks.** CLAUDE.md §8: a misclick scored as wrong corrupts
mastery permanently. Confirm-or-undo lives in the client; an unconfirmed click must
never reach this endpoint.

Response:

```json
{
  "session_id": "sess_ab12cd34",
  "turn_id": 3,
  "schema_version": "1.0",

  "utterance": "I've dimmed everything that can't be it - 5 left.",

  "action": "ask | hint_visual | hint_verbal | advance | backtrack | explain",
  "hint_level": 2,
  "expects": "node_click",
  "mcq_options": [ {"id": "tcp_slow_start", "label": "Slow Start"} ],

  "graph_state": {
    "current_node": "tcp_slow_start",
    "focus_nodes": ["tcp_slow_start", "tcp_aimd"],
    "focus_edges": [ {"from": "tcp_slow_start", "to": "tcp_aimd"} ],
    "dimmed_nodes": ["tcp_segment", "..."],
    "mastery": { "tcp_segment": 0.61, "tcp_slow_start": 0.43 }
  },

  "item": { "id": "itm_0031", "node_id": "tcp_slow_start",
            "difficulty": 0.4, "scorable": true },

  "turn_budget": { "used": 3, "max": 8 },
  "resolved_with_support": false,
  "session_complete": false
}
```

### `POST /turn?stream=true` — build against this one

Server-sent events, three of them, in order:

| event | payload | when |
|---|---|---|
| `graph_state` | see below | after Call 1, ~1s |
| `utterance` | `{"utterance": "..."}` | after Call 2, ~1.5s later |
| `done` | the full `TurnResponse` | immediately after |

The `graph_state` event carries everything needed to become **interactive**, not
just to repaint:

```
session_id, turn_id, action, hint_level, expects, item, mcq_options,
turn_budget, resolved_with_support, session_complete, graph_state
```

Withholding `expects` / `item` / `mcq_options` until `done` would leave the
student staring at a narrowed graph they cannot click for another ~1.4s, which
throws away most of what the two-call split bought. `tests/test_turn_contract.py`
pins this field set against `client/src/types.ts::GraphStatePhase`.

**Move the graph on the first event.** Do not wait for the utterance. CLAUDE.md §5
and §8: the graph reacts on Call 1 return and never blocks on the text — the
utterance is meant to stream into an already-changed screen. The mock reproduces
the real timings (`MOCK_CALL1_DELAY_S`, `MOCK_CALL2_DELAY_S`) so what you build
against feels like the finished system.

Measured against the running mock:

```
 0.78s  event: graph_state
 2.20s  event: utterance
 2.20s  event: done
```

---

## Rendering rules

**`utterance` is the only text you may render.** Whitelist, not filter
(CLAUDE.md §1.6, guard layer 0). The one exception is `mcq_options[].label`,
which is server-owned data from `items.json`, never model output, and without
which MCQ is unrenderable.

`diagnosis`, `student_state`, `correct` and the raw Call 1 decision are logged
server-side and never cross the wire. If you ever see one in a response, that is
a severity-1 bug — say so immediately, do not filter it client-side.

**Dimming. `dimmed_nodes` is AUTHORITATIVE.** An empty dimmed set means no
narrowing, full stop. Render from it and ignore `focus_nodes`, which is derived
and exists for logging and eval §9.2's matched-elimination comparison.

This matters because `focus_nodes: []` is ambiguous between "hint level 0" and
"this item is not answerable on the graph" (`visually_answerable: false`).
`dimmed_nodes: []` is not ambiguous: nothing is dimmed, so dim nothing.

Narrowing only ever happens on a `hint_visual`. It **persists** across
subsequent turns on the same item and is monotone — a hint never re-lights a node
it already excluded. `advance`, `backtrack`, `ask` and `explain` send an empty
dimmed set; `current_node` carries "where we are".

Dimming must survive a projector (CLAUDE.md §8): opacity **plus** desaturation
**plus** stroke width. Opacity alone fails on bad contrast. Test on the actual
demo hardware in week 3.

**Mastery** is a float in `[0,1]` per node. It recolours nodes. It must not resize
or reposition them.

**`turn_budget`** is worth showing — it is the difference between a student who
knows help is coming and one who feels trapped. `resolved_with_support: true`
means the budget forced a reveal and the item scored zero.

---

## What the mock does and does not do

Faithful: the narrowing ladder, server-owned counters, hint monotonicity, the
turn budget, deterministic grading, mastery and next-node selection, the Call 1 →
graph → Call 2 latency profile, the full response shape.

Not mocked, deliberately: retrieval, the answer monitor (guard layer 1), and real
diagnosis. `diagnosis` is a canned string — the week-3 read-through (§9.5) needs
genuine model output and mock text would only pollute the logs.

Swapping in the real thing is a change to `server/turn.py`'s two `mock_tutor`
calls. Nothing in this document changes.

---

## Guarantees the tests enforce

`tests/test_turn_contract.py`, run it before you debug anything:

- no item prompt, answer, alias, distractor or span appears in any response
- `TurnResponse` has exactly the field set above
- hint level rises by at most 1 per turn, never falls within an item, caps at 4
- 8 turns on one item forces a reveal and awards zero mastery
- free text never moves mastery (CLAUDE.md §1.4)
- a wrong answer lowers the node *and* decays its prerequisites
- `focus_nodes` and `dimmed_nodes` always partition the graph
- narrowing is monotone within an item — a hint never re-lights an excluded node
- node coordinates are identical across requests

---

## The narrowing ladder (§9.1, §9.2)

**The schedule is a research variable, not a constant.** It lives in config
because eval §9.1 sweeps it: effective leakage as a function of terminal
candidate-set size is a *curve*, and the curve is the result. Baking one point
on it into the client would throw the rest away.

```
NARROW_SCHEDULE=0,12,9,7,5      # candidates lit per hint level; 0 = no narrowing
MAX_GUESS_PROBABILITY=0.2       # floor = ceil(1/p) = 5 candidates
LADDER_MODE=interleaved         # interleaved | visual_only | verbal_only
```

The floor is set by **guess probability**, not node count. A terminal set of `k`
hands a non-reasoning student a `1/k` chance, which is effective leakage under
§9.1's own definition. Narrowing to 2 is a coin flip and would lose to the verbal
baseline. Schedule entries below the floor are clamped up to it.

The schedule is indexed by the **visual** narrowing level, not the hint level —
so in `interleaved` mode, where only every other rung is visual, a run consumes
only the first few entries.

| mode | behaviour | why |
|---|---|---|
| `interleaved` | alternates visual/verbal, last rung verbal | production |
| `visual_only` | every hint narrows | §9.2 arm |
| `verbal_only` | **nothing ever dims** | §9.2 arm |

`verbal_only` is a real rendering case: hints arrive, `dimmed_nodes` stays empty,
the graph never changes. The client must handle it — discovering it in week 4
would be exactly the surprise the mock exists to prevent.

§9.2 is unrunnable on an interleaved ladder: a verbal hint following a visual one
operates on an already-narrowed graph and only has to eliminate the remainder to
"match", which measures nothing. The eval arms must run pure. Verbal hints
therefore never narrow — confounding the channels makes the comparison
meaningless.

Measured on the 50-node fixture, `visual_only`, default schedule:

```
hint 1  →  12/50 lit   (8% guess)
hint 2  →   9/50 lit  (11% guess)
hint 3  →   7/50 lit  (14% guess)
hint 4  →   5/50 lit  (20% guess, the floor)
```

## MCQ

`mcq_options` is the key plus its distractors, shuffled on a seed derived from
`(session_id, item_id)`. Stable across re-renders and reconnects within a
session, different across sessions and across items. The key is never at a fixed
position — shipping bank order would put it at index 0 every time and make every
MCQ free.

The blanket claim "no distractor ever appears in a response" is **false and
always was**: on an MCQ turn the options *are* the distractors, and their labels
are the answer's aliases. What holds is narrower, and `tests/test_mcq.py` pins
it: the item prompt never appears on any turn; aliases never appear on a non-MCQ
turn; `mcq_options` never ships on a turn that did not ask for one.

## Local state

`state.db` migrates additively on open. Adding a column to `server/state.py`'s
SCHEMA does nothing to an existing database — `CREATE TABLE IF NOT EXISTS` is a
no-op on a table that exists — so every write would fail with `no such column`
until the file was deleted. Tests all run on `:memory:` and never see it;
`tests/test_state_migration.py` is the one that does.
