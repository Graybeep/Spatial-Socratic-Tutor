# Spatial Socratic Tutor

An LLM tutor that helps by **showing less** instead of saying more: it narrows a
frozen concept graph visually rather than explaining the answer.

4 weeks, 2 people, one chapter, a local demo and three eval numbers.

**Read `CLAUDE.md` before writing any code.** It is the settled spec — hard rules,
frozen schemas, the two-call architecture, guardrails, mastery maths, evals and the
schedule. Do not re-litigate decisions in it mid-implementation.

## Status

Day 1–2 done: schemas frozen, mock server running, client rendering 50 nodes
against it. Person A's real chapter graph drops into `data/` and replaces the
fixture; nothing else changes.

## Run the mock

```bash
pip install -r requirements.txt
python -m build.make_mock_data   # placeholder 50-node fixture
python -m build.validate         # strict; must be clean
python -m pytest                 # 85 tests
python -m server.main            # http://127.0.0.1:8000
```

Then the client, in a second terminal:

```bash
cd client && npm install
npm run dev                      # http://localhost:5173
```

No API key and no network needed — `MOCK_MODE=true` is the default.

```bash
cp .env.example .env   # only needed once real LLM calls go in (week 2)
```

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
| `server/mastery.py` | deterministic scoring, no LLM |
| `server/mock_tutor.py` | scripted stand-in for Call 1 and Call 2 |
| `build/validate.py` | DAG / orphan / item checks; must pass before commit |
| `build/make_mock_data.py` | throwaway 50-node fixture; Person A deletes this in week 1 |
| `client/src/types.ts` | reconciled against `/schemas`; supersedes `templates/` |

Full layout in `CLAUDE.md` §2.

## Contributing

Person A owns content/graph/scoring; Person B owns interface/tutor loop. Neither
edits the other's layer — schemas are the contract (§1.9). `main` must always run;
push at least daily (§13.2). No configuration values hard-coded in source
(§1.10, §13.1).
