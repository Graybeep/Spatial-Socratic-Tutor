"""CLAUDE.md §6 layer 1 — the answer-monitor hit rate, from the turn log.

    python -m eval.leak_monitor
    python -m eval.leak_monitor --json eval/results/leak_monitor.json

No key, no network, no model call. It reads `logs/turns.jsonl` and counts.

WHY THIS EXISTS
---------------
§6.1 asks for one number and calls it free:

    "Because Call 2 never saw the answer, a trigger here means the model
     reconstructed the answer parametrically. Log the rate; it is a free and
     genuinely interesting number for the writeup."

The logging half was built. `guards.stats_snapshot()` even computes the split.
But nothing ever called it — not `/health`, not any eval, not the log reader —
so the rate lived in 457,000 unaggregated jsonl lines and the "free" number was
free the way an unopened box is packed. This is the opener.

WHY IT IS NOT A `wc -l` OVER THE FILE
-------------------------------------
Three ways a naive pass gets it wrong, all of which this file was written in
response to rather than in anticipation of.

**1. The file is not one experiment.** `logs/turns.jsonl` is never truncated and
spans the whole project. Layer 1 fired on 17,433 `backtrack` turns before the
Call 2 fidelity ceiling landed — 100% of backtrack turns in two 50,000-turn
blocks — because backtrack was handed the target node's label and the tutor said
it. `backtrack` is in `RECONSTRUCTION_ACTIONS`, so pooling the file reports 24%
parametric reconstruction from a bug that is fixed. Records now carry `code`
(see `server/turn._code_fingerprint`); this partitions on it and refuses to pool
builds unless asked. Records written before that stamp existed are reported as
`pre-stamp` and excluded from the headline.

**2. A hit is not evidence of the same thing on every action.** §6.1's inference
holds only where Call 2 saw no answer representation: `ask`, `hint_*`,
`backtrack`. On `advance` and `explain` the tutor is *meant* to name the answer,
and pooling those inflates the figure. That split already exists in
`guards.RECONSTRUCTION_ACTIONS` and is reused here rather than re-derived, so
the eval and the server cannot disagree about which actions mean what.

**3. A rate over one item is not a rate.** §9.1 shipped a leakage number
measured over one item out of 101 for four days and every test passed. Every
number here carries `provenance` and the same `distinct == population` check.

**4. A mock cannot reconstruct anything.** `MOCK_MODE` Call 2 is a template
lookup. It has no weights to reconstruct an answer from, so its hit rate is a
property of `prompts/mock_utterances.json` and says nothing whatever about a
model. Reporting it as §6.1's number would be the purest form of the failure in
`docs/writeup/numbers-that-looked-fine.md`: a well-formed rate over a population
that cannot exhibit the phenomenon. Mock and real turns are therefore never
pooled, and the headline refuses to report at all until real turns exist.

WHAT A HIT MEANS AFTER ALL THAT
-------------------------------
On a reconstruction action: Call 2 was handed an action, a hint level, a count
and at most a non-answer label, and the utterance still matched the answer. That
is the model's own weights, and it is the number §6 wants.

On an authorised action: the tutor named an answer it was licensed to name. Not
a leak. Worth counting anyway, because a *rise* there is how an inert mask shows
itself — `answer_spans` was empty for 260 items and the only visible symptom was
6 hits on `advance` in a 258-turn session.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from server.config import CONFIG
from server.guards import RECONSTRUCTION_ACTIONS
from eval import provenance

#: Records written before `server/turn.py` stamped the build. They are real
#: turns and are counted, but they cannot be attributed, so they never enter the
#: headline - see the module docstring, reason 1.
UNSTAMPED = "pre-stamp"


@dataclass
class Arm:
    """One (build, bucket) cell."""

    checks: int = 0
    hits: int = 0
    fell_back: int = 0
    regenerated_clean: int = 0
    items: set = field(default_factory=set)
    hit_items: Counter = field(default_factory=Counter)
    by_action: Counter = field(default_factory=Counter)
    hits_by_action: Counter = field(default_factory=Counter)
    aliases: Counter = field(default_factory=Counter)

    @property
    def rate(self) -> float:
        return self.hits / self.checks if self.checks else 0.0


def bucket_for(action: Optional[str]) -> str:
    """§6.1's inference applies to one of these and not the other.

    Imported from the server rather than restated: an action that moves between
    the two buckets must move in one place, or the eval reports a number the
    running system does not agree with.
    """
    return "parametric_reconstruction" if action in RECONSTRUCTION_ACTIONS else "authorised_naming"


def _alias_of(note: str) -> Optional[str]:
    """The surface layer 1 matched, out of `leak_monitor_hit: alias 'x' at 1.00`.

    Kept because it is the most useful column in the whole report: a hit
    concentrated on one alias is a vocabulary problem, and a hit spread evenly
    across the bank is a model problem. Those need opposite responses.
    """
    marker = "alias '"
    if marker not in note:
        return None
    rest = note.split(marker, 1)[1]
    return rest.split("'", 1)[0] if "'" in rest else None


def read(path: Path) -> Iterable[dict]:
    """Stream. The file is ~450MB and growing; nothing here needs it resident."""
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # A torn last line from a killed run. Counted, not fatal:
                # §10 forbids silent anything, and `malformed` is reported.
                yield {"_malformed": True}


def _relative(path: Path) -> str:
    from server.config import ROOT
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def measure(path: Optional[Path] = None) -> dict:
    path = path or (CONFIG.log_dir / "turns.jsonl")

    arms: dict = defaultdict(Arm)
    real_turns = 0
    builds = Counter()
    malformed = 0
    events = 0
    turns = 0
    screened_items: set = set()

    for record in read(path):
        if record.get("_malformed"):
            malformed += 1
            continue
        if "event" in record:
            events += 1
            continue

        turns += 1
        build = record.get("code") or UNSTAMPED
        builds[build] += 1

        mode = "mock" if record.get("mock") else "real"
        if mode == "real":
            real_turns += 1

        action = record.get("server_action")
        item_id = record.get("item_id")
        note = record.get("leak_note")

        # A turn with no item was never screened - `screen_utterance` is only
        # called when there is an answer to screen against - so counting it as a
        # clean check would dilute every rate below.
        if item_id is None:
            continue

        arm = arms[(build, mode, bucket_for(action))]
        arm.checks += 1
        arm.items.add(item_id)
        arm.by_action[action] += 1
        screened_items.add(item_id)

        if note:
            arm.hits += 1
            arm.hit_items[item_id] += 1
            arm.hits_by_action[action] += 1
            alias = _alias_of(note)
            if alias:
                arm.aliases[alias] += 1
            if "fell_back" in note:
                arm.fell_back += 1
            elif "regenerated_clean" in note:
                arm.regenerated_clean += 1

    from server.graph_store import GraphStore

    store = GraphStore.load()
    population = [
        i.id for nid in store.node_ids for i in store.items_for(nid)
    ]

    out_arms: dict = {}
    for (build, mode, bucket), arm in sorted(arms.items()):
        prov = provenance.over(
            population, arm.items, observations=arm.checks,
            unit="items", expect_full=False,
        )
        out_arms.setdefault(f"{build} [{mode}]", {})[bucket] = {
            "checks": arm.checks,
            "hits": arm.hits,
            "rate": round(arm.rate, 4),
            "fell_back": arm.fell_back,
            "regenerated_clean": arm.regenerated_clean,
            "distinct_items_hit": len(arm.hit_items),
            "top_items": arm.hit_items.most_common(5),
            "top_aliases": arm.aliases.most_common(5),
            "by_action": {
                a: {"checks": c, "hits": arm.hits_by_action.get(a, 0)}
                for a, c in sorted(arm.by_action.items())
            },
            "provenance": prov.as_dict(),
        }

    stamped = [b for b in builds if b != UNSTAMPED]
    return {
        # Relative to the repo, not absolute: this file is committed, and an
        # absolute path makes a result look like it came from one machine.
        "log": _relative(path),
        "turns": turns,
        "events": events,
        "malformed": malformed,
        "builds": dict(builds.most_common()),
        "stamped_builds": sorted(stamped),
        "unstamped_turns": builds.get(UNSTAMPED, 0),
        "real_turns": real_turns,
        "mock_turns": turns - real_turns,
        "arms": out_arms,
        "headline": headline(out_arms),
        "provenance": provenance.over(
            population, screened_items, observations=turns,
            unit="items", expect_full=False,
        ).as_dict(),
    }


def headline(arms: dict) -> dict:
    """§6's number: parametric reconstruction, stamped builds, REAL turns only.

    Two exclusions, and neither is fussiness.

    Unstamped turns cannot name the code that produced them, and this file's
    whole reason for existing is that a fixed bug in that corpus reports as a
    24% result.

    Mock turns cannot exhibit the phenomenon at all. §6.1's claim is about a
    model reconstructing an answer from its weights; a template lookup has no
    weights. A 0% over 10,000 mock turns is not weak evidence of no leakage, it
    is no evidence, and it would read on a slide exactly like the real thing.

    So when there are no real turns this returns `rate: None` and says why,
    rather than returning a number that would be quoted.
    """
    checks = hits = 0
    used = []
    for arm_id, buckets in arms.items():
        if arm_id.startswith(UNSTAMPED) or not arm_id.endswith("[real]"):
            continue
        cell = buckets.get("parametric_reconstruction")
        if not cell:
            continue
        used.append(arm_id)
        checks += cell["checks"]
        hits += cell["hits"]

    if not checks:
        return {
            "arms": [],
            "checks": 0,
            "hits": 0,
            "rate": None,
            "blocked_by": "no stamped real-model turns in the log",
            "why": (
                "MOCK_MODE Call 2 is a template lookup with no weights to "
                "reconstruct an answer from. Its hit rate measures "
                "prompts/mock_utterances.json. §6.1's number needs a key."
            ),
        }
    return {
        "arms": sorted(used),
        "checks": checks,
        "hits": hits,
        "rate": round(hits / checks, 4),
        "blocked_by": None,
    }


def render(result: dict) -> str:
    L = ["CLAUDE.md §6 layer 1 - answer monitor", ""]
    L.append(f"log      {result['log']}")
    L.append(f"turns    {result['turns']:,}  events {result['events']:,}"
             + (f"  malformed {result['malformed']}" if result["malformed"] else ""))

    if result["unstamped_turns"]:
        L.append(f"")
        L.append(f"  {result['unstamped_turns']:,} turns predate the build stamp. They are")
        L.append(f"  counted below under '{UNSTAMPED}' and excluded from the headline:")
        L.append(f"  a rate that cannot name the code that produced it is not a result.")

    for build, buckets in result["arms"].items():
        L.append("")
        L.append(f"build {build}")
        for bucket, cell in sorted(buckets.items()):
            prov = cell["provenance"]
            L.append(f"  {bucket:26s} {cell['hits']:6,} / {cell['checks']:7,} "
                     f"= {cell['rate']:.2%}   over {prov['distinct']} distinct items")
            if cell["fell_back"]:
                L.append(f"      {cell['fell_back']:,} shipped the canned fallback "
                         f"(regeneration hit too)")
            if cell["top_aliases"]:
                shown = ", ".join(f"{a} x{n}" for a, n in cell["top_aliases"])
                L.append(f"      surfaces: {shown}")

    head = result["headline"]
    L.append("")
    L.append("HEADLINE (§6.1)")
    if head["rate"] is None:
        L.append(f"  NOT MEASURABLE - {head['blocked_by']}")
        for line in head["why"].split(". "):
            if line.strip():
                L.append(f"  {line.strip().rstrip('.')}.")
        L.append(f"  ({result['mock_turns']:,} mock turns, "
                 f"{result['real_turns']:,} real. Deadline on the key: "
                 f"see docs/schedule.md.)")
    else:
        L.append(f"  parametric reconstruction: {head['hits']:,} / {head['checks']:,} "
                 f"= {head['rate']:.2%}")
        L.append(f"  arms pooled: {', '.join(head['arms'])}")
    L.append("")
    L.append("A hit on a reconstruction action means Call 2 produced the answer")
    L.append("without ever being shown it. A hit on an authorised action means the")
    L.append("tutor named an answer it was licensed to name - not a leak, but a")
    L.append("rise there is how an inert mask shows itself.")
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--json", type=str, default=None)
    args = parser.parse_args()

    result = measure(args.log)
    print(render(result))

    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
