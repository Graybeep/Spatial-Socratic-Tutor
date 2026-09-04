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
| `graph_state` | `session_id`, `turn_id`, `action`, `hint_level`, `graph_state` | after Call 1, ~1s |
| `utterance` | `{"utterance": "..."}` | after Call 2, ~1.5s later |
| `done` | the full `TurnResponse` | immediately after |

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

**Dimming.** `focus_nodes` empty means *no narrowing* — the whole graph stays lit.
That is the level-0 state, not "dim everything". When it is non-empty,
`dimmed_nodes` is its exact complement and is sent explicitly so the client
renders dimming rather than deciding policy.

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

Faithful: the narrowing sequence, server-owned counters, hint monotonicity, the
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
