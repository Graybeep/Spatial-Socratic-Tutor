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

`curriculum_moves.json` is generated separately, because it is the one result
here that is **not** a mock-utterance run and does not regenerate with the
others:

```bash
python -m eval.curriculum_moves --build 18d220d --json $T/curriculum_moves.json
```

It counts a specific historical run — the day-18 real-model policy run, 40 turns
over 10 sessions — so the build is named rather than defaulted. Re-running it
without `--build` counts the current build and will report nothing until the
current build has logged turns of its own.

The temp path is not fussiness. These files are committed, so writing one
directly dirties the tree, and the *next* eval in the sequence then stamps itself
`<sha>-dirty` over code that has not changed — the first attempt at this produced
four files claiming an uncommitted build and one that did not. Generate against a
clean tree, copy in, commit once.

## `real_turns.jsonl.gz` — the raw evidence, archived

CLAUDE.md §13.2: *"Logs are gitignored but they are evidence for §9.1, §9.4 and
§9.5 — do not delete them, and archive the 60 eval dialogues somewhere durable
before the week-4 writeup."* This is that archive.

**Every real-model turn this project ever made: 3,411 of them, 0.17 MB gzipped.**
`logs/turns.jsonl` is 655 MB and gitignored; the evidence behind the published
numbers is **0.7%** of it, and the rest is mock and test traffic. Extracted on
`mock: false`, scanned for credentials before committing (zero hits — the log
never contained a key).

| build | turns | what it backs |
|---|---|---|
| `ac2fc28` | 3,226 | §9.1 adversarial arms |
| `6f184ea-dirty` | 63 | early §9.5 runs |
| `18d220d` | 40 | **§5.5's `0/34` and every §5.6 figure** |
| `77b7e5d-dirty` | 40 | day 12, withdrawn for cause, kept because the report cites it |
| `614d066`, `d594341`, `7ba8078`, `7783a34-dirty` | 42 | intermediate runs |

### Reproducing the key-only numbers without a key

The report says §5.5 and §5.6 *"need an API key... and the raw outputs are
committed so the figures can be checked without one."* This is what makes that
true:

```bash
gunzip -c eval/results/real_turns.jsonl.gz > /tmp/turns.jsonl

python -m eval.leak_monitor     --log /tmp/turns.jsonl --build 18d220d
# -> parametric reconstruction: 0 / 34 = 0.00%      (§5.5)

python -m eval.curriculum_moves --log /tmp/turns.jsonl --build 18d220d
# -> 13 emitted, 12 moved; override 6 of 12          (§5.6)
```

Both verified against this archive before it was committed. **Do not regenerate
this file from a later log** — it is a record of runs that happened, and no eval
has run since the day-19 freeze.

Do not pass `--n 60`. §9.1 asks for 60 dialogues, but that was written when a
dialogue was the unit; the unit is the item, and the default (two dialogues per
item, 138 over the scored bank) is what covers it. `--n 60` silently samples 60
of 69.

Results move when the ladder moves. That is expected — `NARROW_SCHEDULE` is a
research variable and §9.1 sweeps it. Re-run and re-commit alongside the change
that moved them.
