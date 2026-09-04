# Spatial Socratic Tutor

An LLM tutor that helps by **showing less** instead of saying more: it narrows a
frozen concept graph visually rather than explaining the answer.

4 weeks, 2 people, one chapter, a local demo and three eval numbers.

**Read `CLAUDE.md` before writing any code.** It is the settled spec — hard rules,
frozen schemas, the two-call architecture, guardrails, mastery maths, evals, and the
schedule. Do not re-litigate decisions in it mid-implementation.

## Setup

```bash
cp .env.example .env      # fill in ANTHROPIC_API_KEY
```

Everything else has a default. No configuration values are hard-coded in source
(`CLAUDE.md` §1.10, §13.1).

## Layout

See `CLAUDE.md` §2.

## Contributing

Person A owns content/graph/scoring; Person B owns interface/tutor loop. Neither
edits the other's layer — schemas are the contract (§1.9). `main` must always run;
push at least daily (§13.2).
