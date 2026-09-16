# Eval results

Committed on purpose, unlike `/logs`.

`/logs` is gitignored per CLAUDE.md §13.2 — it is raw per-turn evidence, large
and regenerated constantly. These are *results*: small, few, and the thing the
week-4 writeup cites. Keeping them in git means a number on a slide can always be
traced to the run that produced it.

Every block in these files carries `code` and `generated_at` — the build that
computed the number, stamped at the moment it was written. Check it before
quoting: a result outlives the code that produced it, and `leakage.json` sat for
five days across three behavioural commits with no way to tell from the file
whether it was current. (It was. That took a manual re-run to establish, which is
the cost this stamp removes.)

Regenerate **to a temp path first, then copy in**:

```bash
export MOCK_MODE=true   # .env ships false for the demo; these results are mock-utterance
T=$(mktemp -d)
python -m eval.adversarial                      --json $T/leakage.json
python -m eval.adversarial --population answerable --json $T/leakage_answerable.json
python -m eval.graph_quality                    --json $T/graph_quality.json
python -m eval.distractor_screen                --json $T/distractor_screen.json
python -m eval.leak_monitor                     --json $T/leak_monitor.json
cp $T/*.json eval/results/
```

The temp path is not fussiness. These files are committed, so writing one
directly dirties the tree, and the *next* eval in the sequence then stamps itself
`<sha>-dirty` over code that has not changed — the first attempt at this produced
four files claiming an uncommitted build and one that did not. Generate against a
clean tree, copy in, commit once.

Do not pass `--n 60`. §9.1 asks for 60 dialogues, but that was written when a
dialogue was the unit; the unit is the item, and the default (two dialogues per
item, 138 over the scored bank) is what covers it. `--n 60` silently samples 60
of 69.

Results move when the ladder moves. That is expected — `NARROW_SCHEDULE` is a
research variable and §9.1 sweeps it. Re-run and re-commit alongside the change
that moved them.
