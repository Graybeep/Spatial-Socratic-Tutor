"""Which rule moved the curriculum, and whether it actually moved - from the log.

    python -m eval.curriculum_moves --build 18d220d
    python -m eval.curriculum_moves --json eval/results/curriculum_moves.json

No key, no network, no model call. It reads `logs/turns.jsonl` and counts, so
the eval freeze (`docs/schedule.md`) does not apply to it.

WHY THIS EXISTS
---------------
`report.md` §5.6 rests an architecture claim on a count: over the day-18 run's
40 turns, the curriculum moved on 13 - 6 `advance` the model also asked for, 6
`backtrack` the server performed while the model asked for a hint, and 1
`backtrack` the model requested and got. The guarantee being argued is that the
server's override is available on every one of them, whatever Call 1 asks for.

That count was produced by hand, once, and no committed code could reproduce it.
This project has withdrawn a number for exactly that (day 12, `77b7e5d-dirty`:
"a number whose code and model cannot both be named was never admissible"), and
`eval/provenance.py` exists because a result that carries its value but not its
sampling cannot be trusted. The 6/6/1 split was the last load-bearing figure in
the report still in that category. This is the opener.

WHAT THE HAND COUNT GOT WRONG
-----------------------------
It counted turns that *emitted* a curriculum action and reported them as turns
on which the curriculum *moved*. Those are not the same set, and the gap between
them is the entire day-19 finding: `action` began life as
`decision.requested_action`, so a Call 1 asking to step back got the word and the
prerequisite chunk while no item changed.

Re-derived here, build `18d220d`: **13 turns emitted a curriculum action and 12
moved the curriculum.** The odd one out is the single model-requested backtrack,
`itm_0021 -> itm_0021`. The hand count named that turn as the unattributable one
and still counted it as a move in the same paragraph.

So this module reports the two numbers separately and never collapses them. The
`moved` column is computed from `item_id` changing within a session, which is
evidence independent of any action label - it is what would have caught the
day-19 hole on day 18, from the same log, with no new calls.

WHY IT PARTITIONS ON BUILD
--------------------------
`logs/turns.jsonl` is never truncated and spans the whole project, and the rule
under measurement *changed*: before day 19 a model-requested backtrack moved
nothing, after it the request is honoured only against an unmastered prerequisite
and otherwise refused. Pooling the file counts two different servers as one. It
partitions on `code` and refuses to pool unless asked, the same way
`eval/leak_monitor.py` does and for the same reason.

WHY MOCK AND REAL ARE NEVER POOLED
----------------------------------
Whether the server *overrode* the model is a statement about what the model
asked for. In `MOCK_MODE` Call 1 is a template, so `requested_action` is a
property of `prompts/` and not of any model, and an agreement rate over it means
nothing. The split is reported; the two are never summed.

WHY `backtrack_origin` IS NOT SIMPLY TRUSTED
--------------------------------------------
The field landed on day 19. Every record before it predates the field, so the
origin has to be inferred from `server_action` against `call1.requested_action`
for the historical corpus - which is what the hand count did. Where the field IS
present it is used, and the two are cross-checked: a disagreement is reported
rather than silently resolved, because a field that has drifted from the
behaviour it names is worth more as a visible complaint than as a quiet default.

WHAT THE INFERENCE CANNOT DO, AND WHY THE FIELD HAD TO EXIST
------------------------------------------------------------
`infer_origin` reads a backtrack as the model's whenever Call 1 asked for one.
When the two-failure rule (§7) fires on the *same* turn that Call 1 happens to
request `backtrack`, the server moved the curriculum and the model merely agreed
- and the inference calls it `model` anyway. That case is in the corpus: build
`77b7e5d-dirty`, `sess_2acfcff9b419` turn 2, where the preceding two turns both
scored false and the item moved `itm_0026 -> itm_0021`.

So on pre-day-19 records **`backtrack:model` is an upper bound on
model-initiated backtracks, not a count of them.** This is not a defect in the
inference; it is the ambiguity that made `backtrack_origin` worth adding, stated
where a reader of the number will meet it. On day-19-and-later records the field
is authoritative and the bound is exact.

Note that the day-18 reading survives this caveat rather than depending on it:
its one `backtrack:model` turn was *stationary*, and a two-failure backtrack
always moves the item. So that turn cannot have been a coincident server
backtrack, which is what makes it evidence of the hole rather than of the
ambiguity.

THE OVERRIDE COUNT
------------------
`overrode_*` counts curriculum actions where `server_action` differs from
`call1.requested_action` - the server doing something other than what the model
asked. `diagnosis-readthrough.md` quotes this as "server overrode Call 1 where
the curriculum moved", and it was hand-derived too, with the day-12 and day-18
columns silently using different denominators (12 moved against 13 emitted). It
is reported here against both so the two can never drift apart again.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Iterable, Optional

from eval import provenance
from server.build_info import CODE
from server.config import CONFIG

#: Actions that move the student to a different item. `explain`, `ask` and the
#: hint rungs keep the student where they are.
MOVING_ACTIONS = ("advance", "backtrack")

#: The vocabulary `server/turn.py` writes. Pinned here so a fourth spelling
#: appearing later is a visible complaint rather than a silent new bucket.
ORIGINS = ("server", "model", "refused")


def read(path: Path) -> Iterable[dict]:
    """Stream the log. It is hundreds of megabytes; nothing loads it whole."""
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "turn_id" in record:
                yield record


def infer_origin(record: dict) -> Optional[str]:
    """Which rule moved the curriculum backwards, for records of any age.

    Returns None when the turn did not backtrack. A pre-day-19 record cannot
    express `refused` at all - the gate did not exist, so the request was simply
    honoured - and this returns `server`/`model` for it exactly as the hand count
    did.
    """
    if record.get("server_action") != "backtrack":
        return None
    requested = (record.get("call1") or {}).get("requested_action")
    return "model" if requested == "backtrack" else "server"


def measure(path: Optional[Path] = None, build: Optional[str] = None,
            pool_builds: bool = False) -> dict:
    """Count curriculum actions, and separately count the ones that moved."""
    path = path or (CONFIG.log_dir / "turns.jsonl")

    partitions: dict = collections.defaultdict(lambda: {
        "turns": 0,
        "sessions": set(),
        "emitted": collections.Counter(),
        "moved": collections.Counter(),
        "stationary": [],
        "origin_disagreements": [],
        "first_turn_moves": 0,
        "overrode_emitted": 0,
        "overrode_moved": 0,
    })
    #: Last item seen per (partition, session). A session cannot span builds -
    #: the server does not change mid-run - so this is keyed by both anyway.
    last_item: dict = {}

    for record in read(path):
        code = record.get("code") or "pre-stamp"
        mock = bool(record.get("mock"))
        if not pool_builds and build is not None and code != build:
            continue
        key = ("pooled" if pool_builds else code, "mock" if mock else "real")
        part = partitions[key]
        part["turns"] += 1
        session = record.get("session_id")
        part["sessions"].add(session)

        item = record.get("item_id")
        previous = last_item.get((key, session))
        last_item[(key, session)] = item

        action = record.get("server_action")
        if action not in MOVING_ACTIONS:
            continue

        inferred = infer_origin(record)
        logged = record.get("backtrack_origin")
        if logged is not None and inferred is not None and logged != inferred:
            part["origin_disagreements"].append({
                "session_id": session, "turn_id": record.get("turn_id"),
                "logged": logged, "inferred": inferred,
            })
        label = "advance" if action == "advance" else f"backtrack:{logged or inferred}"
        part["emitted"][label] += 1

        #: The server doing something other than what Call 1 asked for. This is
        #: the figure diagnosis-readthrough.md quotes; see the module docstring.
        overrode = action != (record.get("call1") or {}).get("requested_action")
        if overrode:
            part["overrode_emitted"] += 1

        if previous is None:
            #: The first turn of a session has nothing to compare against, so
            #: whether it moved is undefined rather than false.
            part["first_turn_moves"] += 1
            continue
        if item != previous:
            part["moved"][label] += 1
            if overrode:
                part["overrode_moved"] += 1
        else:
            part["stationary"].append({
                "session_id": session, "turn_id": record.get("turn_id"),
                "action": action, "label": label, "item_id": item,
            })

    out = {}
    for (code, mode), part in partitions.items():
        emitted = sum(part["emitted"].values())
        moved = sum(part["moved"].values())
        prov = provenance.over(
            population=part["sessions"],
            sampled=part["sessions"],
            observations=part["turns"],
            unit="sessions",
        )
        out[f"{code}:{mode}"] = {
            "build": code,
            "mode": mode,
            "turns": part["turns"],
            "sessions": len(part["sessions"]),
            "emitted_total": emitted,
            "moved_total": moved,
            "overrode_emitted": part["overrode_emitted"],
            "overrode_moved": part["overrode_moved"],
            "emitted": dict(sorted(part["emitted"].items())),
            "moved": dict(sorted(part["moved"].items())),
            "stationary": part["stationary"],
            "first_turn_moves": part["first_turn_moves"],
            "origin_disagreements": part["origin_disagreements"],
            "provenance": prov.as_dict(),
            "provenance_problem": prov.problem(),
        }
    return out


def render(result: dict) -> str:
    if not result:
        return ("no turns matched. `logs/turns.jsonl` is partitioned on `code`; "
                "pass --build with one that is present, or --pool-builds.")
    lines = []
    for key in sorted(result):
        arm = result[key]
        lines.append(f"=== build {arm['build']} [{arm['mode']}] ===")
        lines.append(f"  {arm['turns']} turns over {arm['sessions']} sessions")
        lines.append(f"  {arm['emitted_total']} turns emitted a curriculum action; "
                     f"{arm['moved_total']} moved the curriculum")
        for label in sorted(set(arm["emitted"]) | set(arm["moved"])):
            lines.append(f"    {label:<22} emitted {arm['emitted'].get(label, 0):>3}"
                         f"   moved {arm['moved'].get(label, 0):>3}")
        lines.append(f"  server overrode Call 1 on {arm['overrode_moved']} of "
                     f"{arm['moved_total']} moved "
                     f"({arm['overrode_emitted']} of {arm['emitted_total']} emitted)")
        for row in arm["stationary"]:
            lines.append(f"  STATIONARY  {row['label']} on {row['session_id']} "
                         f"turn {row['turn_id']}: item stayed {row['item_id']}")
        for row in arm["origin_disagreements"]:
            lines.append(f"  ORIGIN DISAGREES  {row['session_id']} turn {row['turn_id']}: "
                         f"logged {row['logged']!r}, inferred {row['inferred']!r}")
        if arm["first_turn_moves"]:
            lines.append(f"  {arm['first_turn_moves']} curriculum action(s) on a "
                         f"session's first turn; movement undefined, excluded from moved")
        if arm["provenance_problem"]:
            lines.append(f"  SAMPLING: {arm['provenance_problem']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--json", type=str, default=None)
    parser.add_argument("--build", default=None,
                        help="which build to count. Defaults to the current one.")
    parser.add_argument("--pool-builds", action="store_true",
                        help="count every build as one. The rule under "
                             "measurement changed on day 19; pooling counts two "
                             "different servers as one.")
    args = parser.parse_args()

    build = args.build if args.build is not None else (None if args.pool_builds else CODE)
    result = measure(path=args.log, build=build, pool_builds=args.pool_builds)
    print(render(result))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
