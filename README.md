# Spatial Socratic Tutor

An LLM tutor that helps by **showing less** instead of saying more: it narrows a
frozen concept graph visually rather than explaining the answer.

4 weeks, 2 people, one chapter, a local demo and three eval numbers.

**Read `CLAUDE.md` before writing any code.** It is the settled spec — hard rules,
frozen schemas, the two-call architecture, guardrails, mastery maths, evals and the
schedule. Do not re-litigate decisions in it mid-implementation.

## Status

Day 1–2 done: schemas frozen, mock server running. Person B can build the client
against `docs/API.md` without waiting for Person A's chapter graph.

## Run the mock

```bash
pip install -r requirements.txt
python -m build.make_mock_data      # placeholder data/ fixtures
python -m build.validate --fixture  # must be clean
python -m pytest                    # 49 tests
python -m server.main               # http://127.0.0.1:8000
```

No API key and no network needed — `MOCK_MODE=true` is the default.

```bash
cp .env.example .env   # only needed once real LLM calls go in (week 2)
```

## Where things are

| | |
|---|---|
| `docs/API.md` | the wire contract — **start here if you are building the client** |
| `server/schemas.py` | the frozen schemas; authoritative |
| `/schemas` | JSON Schema snapshots; CI fails if `schemas.py` drifts |
| `server/turn.py` | the §5 pipeline |
| `server/mastery.py` | deterministic scoring, no LLM |
| `server/mock_tutor.py` | scripted stand-in for Call 1 and Call 2 |
| `build/validate.py` | DAG / orphan / item checks; must pass before commit |
| `build/make_mock_data.py` | throwaway fixtures; Person A deletes this in week 1 |

Full layout in `CLAUDE.md` §2.

## Contributing

Person A owns content/graph/scoring; Person B owns interface/tutor loop. Neither
edits the other's layer — schemas are the contract (§1.9). `main` must always run;
push at least daily (§13.2). No configuration values hard-coded in source
(§1.10, §13.1).
