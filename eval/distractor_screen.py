"""CLAUDE.md §9.4 - distractor screen.

Runs entirely on assets already in the repo: no API key, no chapter file, no
network. That is the whole point of the section - it is a fourth number at
near-zero cost, harvested from machinery §9.1 already needed.

WHY THIS IS TWO SCREENS AND NOT ONE
-----------------------------------
§9.4 as written assumes one behavioural test: run the simulated students, count
how often each distractor is selected, flag the never-chosen (dead weight) and
the chosen-as-often-as-the-key (ambiguous). That test is correct for half the
bank and degenerate for the other half, because the bank has two kinds of option
set:

  node_click / edge_click (101 items)
      Options are NODE IDS drawn from the lit set. The students in
      eval/adversarial.py filter candidates by graph region - prereqs,
      dependents, siblings - so a node id is either accepted or rejected and
      selection frequency carries real signal. Screened BEHAVIOURALLY, as §9.4
      specifies.

  mcq (159 items)
      Options are PROSE STRINGS. The region filter is a membership test against
      a set of node ids; a prose option is never in it, the filter matches
      nothing, `candidates()` falls back to the full pool and the student picks
      uniformly. Measured over 4000 draws on a 4-option item:

          partial      [0.245, 0.253, 0.253, 0.249]   <- key first
          adversarial  [0.245, 0.253, 0.253, 0.249]

      Under that policy every distractor is selected exactly as often as the key,
      so the behavioural screen would flag 159/159 items ambiguous and 0/159 dead
      weight. That is not a lenient number or a noisy one; it is an artefact of
      the measuring instrument and reporting it as a finding would be wrong.
      Screened STRUCTURALLY instead - see structural_screen().

The tempting fix is to give the simulated student prose comprehension. That
requires a model in the loop, which needs the key we do not have, and it would
put an LLM inside a number that feeds item quality. §9.4's value is that it is
free. A screen that needs a key is a different, more expensive screen.

Both halves emit the same Finding shape, so the flagged list is one list and the
human pass does not need to care which screen produced a row.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from server.config import CONFIG
from server.graph_store import GraphStore
from server.guards import similarity
from server.mock_tutor import lit_nodes
from eval import provenance

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.adversarial import Student  # noqa: E402


#: The condition §9.4 means by "a strong simulated student". `partial` is the
#: policy that restricts to the answer's graph neighbourhood and then guesses:
#: it is the one that can tell a plausible distractor from an implausible one,
#: which is exactly the discrimination the screen is asking about. `zero` would
#: flag nothing (it never rejects a candidate) and `adversarial` shares
#: partial's region filter, so it adds no independent signal.
STRONG_CONDITION = "partial"

DUPLICATE_ITEM = "duplicate_item"
KEY_NOT_SPECIFIC = "key_not_node_specific"
COIN_FLIP = "coin_flip"
LENGTH_TELL = "length_tell"
DEAD_WEIGHT = "dead_weight"

#: Ordered worst-first. A row can trip more than one rule; this decides which
#: one leads in the report.
SEVERITY = [DUPLICATE_ITEM, KEY_NOT_SPECIFIC, COIN_FLIP, LENGTH_TELL, DEAD_WEIGHT]

#: A per-item flag is only worth a human's attention if a human can act on it.
#: Rules that fire on nearly every item are reported ONCE, as a bank-level
#: finding with a rate, and suppressed from the per-item list. Two of the rules
#: below are like that by nature: a systematic length tell is one defect in the
#: generator, not 159 defects in 159 items.
BANK_LEVEL = {DUPLICATE_ITEM, KEY_NOT_SPECIFIC, LENGTH_TELL}


@dataclass
class Finding:
    item_id: str
    node_id: str
    item_type: str
    rule: str
    detail: str
    #: Selection rates keyed by option, behavioural screen only.
    rates: dict = field(default_factory=dict)

    @property
    def rank(self) -> int:
        return SEVERITY.index(self.rule)


# ---------------------------------------------------------------------------
# behavioural screen - click items
# ---------------------------------------------------------------------------

def behavioural_screen(store: GraphStore, trials: int, seed: int) -> tuple[list, dict]:
    """Selection frequencies over the TERMINAL lit set, per click item.

    Terminal rung, not every rung: the screen asks whether the option set the
    student is finally left with is honest. At earlier rungs the lit set is
    mostly graph, not distractors, and a "never selected" verdict there would be
    about the narrowing schedule rather than about the item.

    WHAT THIS SCREEN CAN AND CANNOT SEE. The `partial` student is uniform WITHIN
    the region it accepts: it has a two-level preference (in-region / out), not
    an ordering. So every surviving candidate ties the key by construction, and
    9.4's "selected as often as the key" test would fire on every item with more
    than one survivor - the same degeneracy as the mcq half, one level down.
    The only signal available is therefore BINARY, and it is the survivor count.
    We report that instead, and it turns out to be the more interesting number.
    """
    findings: list = []
    items = [i for i in store.bank.items if i.type in ("node_click", "edge_click")]
    terminal_level = max(1, len(CONFIG.narrow_schedule) - 1)
    live_counts: list = []
    lit_counts: list = []
    screened_ids: list = []

    for item in items:
        lit = lit_nodes(store, item, terminal_level)
        if len(lit) < 2:
            continue

        student = Student(condition=STRONG_CONDITION,
                          rng=random.Random(f"{seed}:{item.id}"))
        picks = Counter(student.choose(store, item, lit, []) for _ in range(trials))
        rates = {n: picks[n] / trials for n in lit}

        live = [n for n, r in rates.items() if r > CONFIG.distractor_dead_rate]
        dead = [n for n, r in rates.items() if r <= CONFIG.distractor_dead_rate]
        live_counts.append(len(live))
        lit_counts.append(len(lit))
        screened_ids.append(item.id)

        # Per-item flag ONLY where narrowing has gone past the policy floor into
        # a coin flip or worse. Everything milder is aggregated below: a flag on
        # 92 of 101 items is not a worklist, it is a distribution.
        if len(live) <= 2:
            findings.append(Finding(
                item_id=item.id, node_id=item.node_id, item_type=item.type,
                rule=COIN_FLIP,
                detail=(f"{len(lit)} candidates lit but only {len(live)} survive a "
                        f"partial-knowledge region filter ({', '.join(sorted(live))}) "
                        f"- effective guess probability {1 / len(live):.2f} against a "
                        f"{CONFIG.max_guess_probability:.2f} policy ceiling; "
                        f"dead: {', '.join(sorted(dead))}"),
                rates=rates,
            ))

    n = len(live_counts) or 1
    mean_live = sum(live_counts) / n
    mean_lit = sum(lit_counts) / n
    return findings, {
        "items": len(items),
        "screened": len(live_counts),
        "provenance": provenance.over(
            population=[i.id for i in items], sampled=screened_ids,
            observations=len(live_counts) * trials, unit="click items").as_dict(),
        "terminal_level": terminal_level,
        "trials": trials,
        "mean_lit": round(mean_lit, 2),
        "mean_live": round(mean_live, 2),
        "live_distribution": dict(sorted(Counter(live_counts).items())),
        "nominal_guess_probability": round(1 / mean_lit, 3) if mean_lit else None,
        "effective_guess_probability": round(
            sum(1 / c for c in live_counts if c) / n, 3),
        "policy_ceiling": CONFIG.max_guess_probability,
    }


# ---------------------------------------------------------------------------
# structural screen - mcq items
# ---------------------------------------------------------------------------

def structural_screen(store: GraphStore) -> tuple[list, dict]:
    """Offline tells, none of which need a student.

    These are properties of the text rather than of behaviour, so each row is a
    candidate for the human pass, not a verdict - the same contract 9.4 sets for
    the behavioural half.
    """
    findings: list = []
    items = [i for i in store.bank.items if i.type == "mcq"]

    option_sets = Counter((i.answer, tuple(sorted(i.distractors))) for i in items)
    key_nodes: dict = {}
    for i in items:
        key_nodes.setdefault(i.answer, set()).add(i.node_id)

    longest_key = 0
    ratios: list = []

    for item in items:
        options = [item.answer] + list(item.distractors)
        if len(options) < 2:
            continue

        key_len = len(item.answer.split())
        d_lens = [len(d.split()) for d in item.distractors] or [key_len]
        mean_d = sum(d_lens) / len(d_lens)
        if mean_d:
            ratios.append(key_len / mean_d)
        if key_len > max(d_lens):
            longest_key += 1

        reuse = option_sets[(item.answer, tuple(sorted(item.distractors)))]
        if reuse > 1:
            findings.append(Finding(
                item_id=item.id, node_id=item.node_id, item_type=item.type,
                rule=DUPLICATE_ITEM,
                detail=(f"option set shared with {reuse - 1} other item(s) - "
                        f"key {item.answer[:56]!r}"),
            ))

        nodes = key_nodes.get(item.answer, set())
        if len(nodes) > 1:
            findings.append(Finding(
                item_id=item.id, node_id=item.node_id, item_type=item.type,
                rule=KEY_NOT_SPECIFIC,
                detail=(f"this key is the correct answer for {len(nodes)} different "
                        f"nodes - it cannot be node-specific, so at most one of "
                        f"those items is scoreable"),
            ))

        if mean_d and key_len >= mean_d * CONFIG.distractor_length_tell_ratio:
            findings.append(Finding(
                item_id=item.id, node_id=item.node_id, item_type=item.type,
                rule=LENGTH_TELL,
                detail=(f"key is {key_len} words against a {mean_d:.1f}-word mean "
                        f"distractor (ratio {key_len / mean_d:.2f})"),
            ))

    n = len(items) or 1
    return findings, {
        "items": len(items),
        "provenance": provenance.over(
            population=[i.id for i in items], sampled=[i.id for i in items],
            observations=len(items), unit="mcq items").as_dict(),
        "distinct_option_sets": len(option_sets),
        "distinct_prompts": len({i.prompt for i in items}),
        "key_is_longest": longest_key,
        "key_is_longest_rate": round(longest_key / n, 3),
        "chance_rate": 0.25,
        "mean_length_ratio": round(sum(ratios) / len(ratios), 3) if ratios else None,
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def render(findings: list, behav: dict, struct: dict) -> str:
    by_rule = Counter(f.rule for f in findings)
    per_item = [f for f in findings if f.rule not in BANK_LEVEL]
    total = behav["items"] + struct["items"]

    L = []
    L.append("CLAUDE.md 9.4 - DISTRACTOR SCREEN")
    L.append("=" * 76)
    L.append(f"bank: {total} items ({behav['items']} click, {struct['items']} mcq)")
    L.append("")
    L.append("BANK-LEVEL FINDINGS")
    L.append("-" * 76)

    if struct["distinct_option_sets"] < struct["items"]:
        L.append(f"  [{DUPLICATE_ITEM}] {struct['items']} mcq items carry only "
                 f"{struct['distinct_option_sets']} distinct option sets")
        L.append(f"      {by_rule.get(DUPLICATE_ITEM, 0)} items affected; "
                 f"{struct['distinct_prompts']} distinct prompts. The mcq half of")
        L.append("      the bank is generator fixture, not content:")
        L.append("      build/generate_items.py cycles MOCK_MECHANISMS with k % 3")
        L.append("      under BUILD_LLM=mock, the default because build.RealLLM")
        L.append("      is unimplemented.")

    if by_rule.get(KEY_NOT_SPECIFIC):
        L.append(f"  [{KEY_NOT_SPECIFIC}] {by_rule[KEY_NOT_SPECIFIC]} items whose key "
                 f"also answers other nodes")
        L.append("      A key that answers many concepts is not a key. These items")
        L.append("      are scored (1.4 scores mcq) and feed mastery and the")
        L.append("      adaptive path.")

    rate = struct["key_is_longest_rate"]
    if rate > struct["chance_rate"]:
        L.append(f"  [{LENGTH_TELL}] key is the longest option in "
                 f"{struct['key_is_longest']}/{struct['items']} items "
                 f"({rate:.0%}, chance {struct['chance_rate']:.0%})")
        L.append(f"      mean key/distractor word ratio "
                 f"{struct['mean_length_ratio']}. Pick-the-longest answers every")
        L.append("      mcq in the bank with no domain knowledge.")

    L.append("")
    L.append(f"  narrowing: {behav['mean_lit']} candidates lit at terminal rung "
             f"{behav['terminal_level']}, but only")
    L.append(f"  {behav['mean_live']} survive a partial-knowledge region filter. "
             f"Effective guess")
    L.append(f"  probability {behav['effective_guess_probability']} against a "
             f"{behav['policy_ceiling']} policy ceiling "
             f"(nominal {behav['nominal_guess_probability']}).")
    L.append(f"  survivors per item: {behav['live_distribution']}")
    L.append("")
    bp, sp = behav["provenance"], struct["provenance"]
    L.append(f"  sampling: behavioural {bp['distinct']}/{bp['population']} "
             f"{bp['unit']} ({bp['coverage']:.0%}), structural "
             f"{sp['distinct']}/{sp['population']} {sp['unit']} ({sp['coverage']:.0%})")
    L.append("")
    L.append("PER-ITEM FLAGS -> human pass")
    L.append("-" * 76)
    if per_item:
        for f in sorted(per_item, key=lambda f: (f.rank, f.item_id)):
            L.append(f"  [{f.rule}] {f.item_id} ({f.item_type}, node={f.node_id})")
            L.append(f"      {f.detail}")
    else:
        L.append("  none")
    L.append("")
    L.append("A flag is a candidate for review, not a verdict. 9.4's claim is that")
    L.append("the obviously broken items were removed, not that survivors are clean.")
    return "\n".join(L)


def run(trials: Optional[int] = None, seed: Optional[int] = None) -> dict:
    store = GraphStore.load()
    trials = trials or CONFIG.distractor_screen_trials
    seed = seed if seed is not None else CONFIG.mock_seed

    b_findings, behav = behavioural_screen(store, trials, seed)
    s_findings, struct = structural_screen(store)
    findings = b_findings + s_findings

    return {
        "findings": [asdict(f) for f in findings],
        "_objects": findings,
        "behavioural": behav,
        "structural": struct,
        "flagged_item_ids": sorted({f.item_id for f in findings}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--json", type=str, default=None)
    args = parser.parse_args()

    result = run(trials=args.trials, seed=args.seed)
    print(render(result["_objects"], result["behavioural"], result["structural"]))

    if args.json:
        payload = {k: v for k, v in result.items() if k != "_objects"}
        Path(args.json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
