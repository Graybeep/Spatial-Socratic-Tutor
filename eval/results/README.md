# Eval results

Committed on purpose, unlike `/logs`.

`/logs` is gitignored per CLAUDE.md §13.2 — it is raw per-turn evidence, large
and regenerated constantly. These are *results*: small, few, and the thing the
week-4 writeup cites. Keeping them in git means a number on a slide can always be
traced to the run that produced it.

Regenerate with:

```bash
python -m eval.adversarial --n 60 --json eval/results/leakage.json
```

Results move when the ladder moves. That is expected — `NARROW_SCHEDULE` is a
research variable and §9.1 sweeps it. Re-run and re-commit alongside the change
that moved them.
