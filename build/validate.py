"""Validate the frozen data files. CLAUDE.md §3: must pass before commit.

    python -m build.validate            # strict, for the real chapter graph
    python -m build.validate --fixture  # relaxes the 40-60 node count only

Exit code 0 = clean, 1 = errors. Warnings never fail the run; they are things a
human should look at, not things that break the system.
"""
from __future__ import annotations

import re

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from build.config import BUILD
from server.config import CONFIG
from server.schemas import SCORABLE_EXPECTS, Graph, ItemBank, ItemPublic


def _norm(text: str) -> str:
    """Lowercase word tokens joined by single spaces, so "Fast Retransmit",
    "fast-retransmit" and "fast  retransmit" are one surface."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


class Report:
    def __init__(self) -> None:
        self.errors: list = []
        self.warnings: list = []
        self.notes: list = []

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def render(self) -> int:
        for n in self.notes:
            print(f"  note  {n}")
        for w in self.warnings:
            print(f"  WARN  {w}")
        for e in self.errors:
            print(f"  ERROR {e}")
        print(f"\n{len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return 1 if self.errors else 0


def find_cycle(nodes: list, prereq_edges: list):
    """Return one cycle as a list of node ids, or None.

    CLAUDE.md §3: a cycle makes next-node selection loop forever, because no node
    in it ever becomes ready. This is the single most important check here.
    """
    adj = {n: [] for n in nodes}
    for src, dst in prereq_edges:
        if src in adj:
            adj[src].append(dst)

    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in nodes}
    stack: list = []

    def visit(node):
        colour[node] = GREY
        stack.append(node)
        for nxt in adj.get(node, []):
            if colour.get(nxt) == GREY:
                return stack[stack.index(nxt):] + [nxt]
            if colour.get(nxt) == WHITE:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        colour[node] = BLACK
        return None

    for n in nodes:
        if colour[n] == WHITE:
            found = visit(n)
            if found:
                return found
    return None


def check_alias_collisions(graph: Graph, bank: ItemBank, rep: Report) -> None:
    """No two concepts may be confusable by their names (CLAUDE.md §3, §6).

    An alias is a matching surface. If two nodes share one, every consumer that
    matches on names is ambiguous, and the consumers are not all equally
    visible: guard layer 1 reports a hit rate, so noise there is at least
    countable, whereas anything that matched aliases while scoring would corrupt
    mastery with nothing watching.

    Grading does NOT currently use aliases - it compares ids, and free text is
    never scored at all (§1.4) - so mastery is not corrupted today. That is a
    thinner guarantee than it sounds: it holds only while §1.4 holds and while
    nothing else starts consuming aliases. This check is what makes it hold by
    construction rather than by nobody having done it yet.

    TWO SEVERITIES, and the split is a real constraint rather than a softening:

    - EQUALITY is an error. Two nodes with the same surface is unambiguously
      broken data, always, with no domain in which it is correct.

    - CONTAINMENT is a warning, listed in full. A hard substring ban is not
      satisfiable on real terminology: "Weighted Fair Queuing" contains "Fair
      Queuing" because WFQ *is* FQ plus weights, and that is what the field
      calls them. Renaming one to satisfy a lint would distort the subject to
      make a check pass. Every containment is therefore printed on every build,
      and every consumer that matches on names must be containment-aware -
      server/guards.py takes the other node labels as `context_phrases` for
      exactly this reason.

    This check found 53 collisions when it was written. 51 were one bug:
    edge_click aliases were generated as "<parent label> to <child label>",
    which contains both endpoint labels by construction. Those aliases are gone
    - no student types that phrase and the edge is graded by id.
    """
    surfaces: dict[str, set] = {}
    for node in graph.nodes:
        surfaces.setdefault(node.id, set()).add(_norm(node.label))
    for item in bank.items:
        for alias in item.answer_aliases:
            if _norm(alias):
                surfaces.setdefault(item.node_id, set()).add(_norm(alias))

    ids = sorted(surfaces)
    nested: list[str] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            for sa in sorted(surfaces[a]):
                for sb in sorted(surfaces[b]):
                    if sa == sb:
                        rep.error(
                            f"alias collision: {a} and {b} share the surface "
                            f"{sa!r}; every name-based matcher is ambiguous"
                        )
                    elif f" {sa} " in f" {sb} ":
                        nested.append(f"{sa!r} ({a}) inside {sb!r} ({b})")
                    elif f" {sb} " in f" {sa} ":
                        nested.append(f"{sb!r} ({b}) inside {sa!r} ({a})")

    for line in sorted(set(nested)):
        rep.warn(f"nested concept name: {line} — consumers must be containment-aware")


def check_answer_identity(graph: Graph, bank: ItemBank, rep: Report) -> None:
    """No item may be `visually_answerable: true` while the turn payload
    identifies its node.

    THIS IS THE CHECK THAT WOULD HAVE CAUGHT THE REAL ONE. `ItemPublic.node_id`
    shipped the answer for 204 of 250 items - for a node_click or mcq item the
    answer IS the item's node - and every leak test stayed green because they all
    compared answer STRINGS and none compared answer IDENTITY. A tutor with a
    non-verbal channel gets a matching non-verbal leak channel, and no amount of
    substring matching sees it.

    It lives here, in the pipeline, rather than in a test, because the test that
    caught it only catches it for whatever mix of `visually_answerable` the
    current fixture happens to have. When Person A's chapter lands with a
    different mix - CLAUDE.md §3 expects most of a real bank to be `false` - the
    ratio shifts and nobody re-checks. This runs on whatever data is in front of
    it.

    Three ways the identity escapes, all checked:
      1. a field of ItemPublic naming the node (how it happened)
      2. an item id that encodes its node ("itm_0031_tcp_slow_start")
      3. `graph_state.current_node` naming it - enforced in server/turn.py and
         asserted here as a schema invariant
    """
    if "node_id" in ItemPublic.model_fields:
        rep.error(
            "ItemPublic has a node_id field. For a node_click or mcq item the "
            "answer IS item.node_id, so this ships the answer in the clear. "
            "See server/schemas.py."
        )

    labels = {n.id: n.label for n in graph.nodes}
    visually = [i for i in bank.items if i.visually_answerable]

    for item in visually:
        public = ItemPublic(
            id=item.id,
            difficulty=item.difficulty,
            scorable=item.type in SCORABLE_EXPECTS and item.scorable,
        )
        payload = json.dumps(public.model_dump()).lower()

        # The answer's identity, in every form it could take.
        identities = {item.node_id.lower(), item.answer.lower()}
        identities.update(part.lower() for part in item.answer.split("->") if part)
        for node_id in list(identities):
            if node_id in labels:
                identities.add(labels[node_id].lower())

        for identity in identities:
            if len(identity) < 3:
                continue  # too short to be an identifier; would false-positive
            if identity in payload:
                rep.error(
                    f"item {item.id}: visually_answerable=true but the public "
                    f"payload contains {identity!r}. The client can name the "
                    f"answer without answering."
                )

    total = len(bank.items)
    if total:
        share = len(visually) / total
        rep.note(
            f"visually_answerable: {len(visually)}/{total} ({share:.0%}). "
            f"CLAUDE.md §9.2 runs on this subset only."
        )
        if share > 0.5:
            rep.warn(
                f"{share:.0%} of items are visually_answerable. CLAUDE.md §3 "
                f"expects more than half to be false - a mechanism question is "
                f"not a node. Check the flag is being set honestly; getting it "
                f"wrong invalidates §9.2 and widens the identity-leak surface."
            )


def check_edge_item_anchors(graph: Graph, bank: ItemBank, rep: Report) -> None:
    """How much of an edge item is left once its anchor is named.

    # Why this check exists

    Call 2's fidelity ceiling lets an `ask` turn on an edge item name ONE
    endpoint, the `to`. The justification given for that was "the item's own
    prompt already names it in 49/49 cases, so exposing it costs nothing" —
    which is true, and is the argument for why the ITEM is broken rather than
    why the exposure is safe. A student told the `to` endpoint is not searching
    73 edges. They are searching the edges that END there.

    So the real candidate count for an edge item is the IN-DEGREE of its anchor,
    and that follows from what is exposed, not from how the prompt is phrased.
    At in-degree 1 the anchor IS the answer and no reasoning happens at all; at
    2 it is a coin flip. Either way `difficulty` is fiction, and difficulty
    feeds `d_eff` in mastery.update() — so a miscalibrated edge item does not
    merely mis-score itself, it moves theta the wrong distance on every
    observation (§7).

    This matters more since mcq was demoted to unscored: edge items are now 49
    of the 101 items that can move mastery at all.

    Nothing here is an ERROR. A hand-authored graph with one prereq per concept
    is a legitimate graph; it is the item TEMPLATE that cannot ask a question
    about it. Flagging is the fix, re-authoring is the human pass.
    """
    edges = [e for e in graph.edges if e.type == "prereq"]
    in_edges: dict = {}
    for e in edges:
        in_edges.setdefault(e.to, []).append(e.from_)

    edge_items = [i for i in bank.items if i.type == "edge_click"]
    if not edge_items:
        return
    scorable_ids = {i.id: i.scorable for i in edge_items}

    floor = BUILD.min_edge_item_candidates
    thin: list = []
    determined: list = []
    collisions: list = []

    for item in edge_items:
        anchor = item.node_id
        sources = in_edges.get(anchor, [])
        n = len(sources)

        # The exposed endpoint is only the `to` when the answer actually ends at
        # node_id. If a future item anchors the other way the candidate set is
        # the out-edges, and silently reporting the wrong one is worse than
        # saying so.
        if "->" in item.answer and item.answer.split("->")[1] != anchor:
            rep.warn(
                f"{item.id}: answer {item.answer!r} does not end at node_id "
                f"{anchor!r}; the anchor rule assumes the `to` endpoint, so this "
                f"item's exposure is not covered by that analysis"
            )
            continue

        if n <= 1:
            determined.append((item.id, anchor, item.difficulty))
        elif n < floor:
            thin.append((item.id, anchor, n, item.difficulty))

        # A distractor equal to the true `from` endpoint is not a distractor.
        if "->" in item.answer and item.answer.split("->")[0] in (item.distractors or []):
            collisions.append(item.id)

    if determined:
        worst = sorted(determined, key=lambda t: -t[2])[:5]
        listed = ", ".join(f"{i} ({a}, difficulty {d})" for i, a, d in worst)
        # ERROR only if any of them still counts toward mastery. A determined
        # item is harmless as long as it cannot move theta - same mechanism and
        # the same reversibility as the mcq demotion above. Re-authoring 32
        # items buys a slightly larger bank for a day of week 3 and a fresh
        # chance to introduce the item-quality defect this check exists to find.
        still_scored = [i for i, _a, _d in determined if scorable_ids.get(i)]
        say = rep.error if still_scored else rep.warn
        scope = "SCORED" if still_scored else "unscored (scorable=false)"
        say(
            f"[edge anchor] [{scope}] {len(determined)}/{len(edge_items)} edge items "
            f"are DETERMINED by their anchor: the named `to` endpoint has exactly "
            f"one prereq, so naming it names the answer and the stated difficulty "
            f"is unreachable. Worst by claimed difficulty: {listed}"
            + ("" if len(determined) <= 5 else f", +{len(determined) - 5} more")
            + (f". STILL SCORED: {', '.join(still_scored[:6])} - set scorable=false "
               f"or re-author; guess rate 1.0 cannot be expressed as a difficulty."
               if still_scored else "")
        )

    if thin:
        listed = ", ".join(f"{i} ({a}, {n} candidates)" for i, a, n, _ in thin[:5])
        rep.warn(
            f"[edge anchor] {len(thin)}/{len(edge_items)} edge items leave fewer "
            f"than {floor} candidates once the anchor is named (a coin flip at 2). "
            f"{listed}" + ("" if len(thin) <= 5 else f", +{len(thin) - 5} more")
        )

    if thin:
        scored_thin = [i for i, _a, _n, _d in thin if scorable_ids.get(i)]
        rep.warn(
            f"[edge anchor] {len(scored_thin)} SCORED edge items remain at 2 "
            f"candidates: a bounded difficulty-calibration problem, not a "
            f"giveaway. Guess rate 0.5 against a claimed difficulty; §7's d_eff "
            f"is where that discrepancy lands."
        )

    scored_edges = [i for i in edge_items if i.scorable]
    rep.note(
        f"scored edge items: {len(scored_edges)}/{len(edge_items)}. The scored "
        f"click bank is what 9.1 and 9.4 generalise to - quote that n, not the "
        f"whole bank."
    )

    if collisions:
        rep.warn(
            f"[edge anchor] {len(collisions)} edge item(s) list the answer's own "
            f"`from` endpoint among their distractors, so one distractor is the "
            f"key: {', '.join(collisions[:6])}"
            + ("" if len(collisions) <= 6 else f", +{len(collisions) - 6} more")
        )

    # The distribution, always, so a clean bank is visibly clean rather than
    # silently unchecked.
    counts = [len(in_edges.get(i.node_id, [])) for i in edge_items]
    hist = {n: counts.count(n) for n in sorted(set(counts))}
    rep.note(
        f"edge-item candidate counts (in-degree of the named anchor): {hist}. "
        f"Median {sorted(counts)[len(counts) // 2]}."
    )


def check_answer_spans(graph: Graph, bank: ItemBank, rep: Report) -> None:
    """Do the recorded offsets still blank the answer in the chunk that ships?

    §3 defines `answer_spans` as offsets into the source chunk and §5 masks them
    before a chunk reaches Call 2 on `advance` and `explain`. Both halves are
    silent when wrong: an offset that no longer lands on the answer masks some
    unrelated sentence, the chunk still names the answer, and the only thing
    downstream is layer 1 - a monitor whose hit rate is a REPORTED number, so a
    stale span shows up as a leak the model never committed.

    So the offsets are re-derived here rather than trusted. `build.annotate_spans`
    computes them from `retrieval.search`; this asks the same question again and
    fails if the answer survives masking. That makes the pair
    (chunks.json, retrieval scorer) a frozen input in fact and not just in
    intent - change either and this check goes red before a demo does.

    Retrieval accuracy is reported alongside, against each node's own declared
    `source_sections`. A span computed against the wrong section is perfectly
    valid and completely useless, and nothing else in the repo measures that.
    """
    from build.annotate_spans import answer_surface, find_spans
    from server import guards, retrieval

    nodes = {n.id: n for n in graph.nodes}
    labels = {n.id: n.label for n in graph.nodes}

    served_wrong_section, no_chunk = [], []
    stale, survived = [], []
    with_spans = 0

    for item in bank.items:
        node = nodes.get(item.node_id)
        if node is None:
            continue

        hit = retrieval.search(f"{node.label} {node.definition}")
        if hit is None:
            no_chunk.append(item.node_id)
            if item.answer_spans:
                rep.error(
                    f"item {item.id}: has answer_spans but retrieval refuses a "
                    f"chunk for {item.node_id}, so nothing masks them"
                )
            continue

        if node.source_sections and hit.chunk.section not in node.source_sections:
            served_wrong_section.append(
                (item.node_id, tuple(node.source_sections), hit.chunk.section))

        surface = answer_surface(item.model_dump(by_alias=True), labels)
        expected = find_spans(hit.chunk.text, surface)
        recorded = [list(s) for s in item.answer_spans]

        if recorded:
            with_spans += 1
            for start, end in recorded:
                if not (0 <= start < end <= len(hit.chunk.text)):
                    rep.error(
                        f"item {item.id}: span [{start}, {end}] is outside the "
                        f"{len(hit.chunk.text)}-character chunk {hit.chunk.id}"
                    )

        if recorded != expected:
            stale.append(item.id)
            continue

        masked = guards.mask_spans(hit.chunk.text, item.answer_spans).casefold()
        leftover = sorted(s for s in surface if s in masked)
        if leftover:
            survived.append((item.id, leftover[:2]))

    if stale:
        rep.error(
            f"{len(stale)} item(s) carry answer_spans that do not match the "
            f"chunk they would be masked against - re-run "
            f"`python -m build.annotate_spans`: {stale[:6]}"
            + (f", +{len(stale) - 6} more" if len(stale) > 6 else "")
        )
    for item_id, leftover in survived:
        rep.error(
            f"item {item_id}: the answer survives masking - {leftover} still "
            f"appear in the chunk handed to Call 2 (§5)"
        )

    empty = len(bank.items) - with_spans
    rep.note(
        f"answer_spans: {with_spans}/{len(bank.items)} items masked. The other "
        f"{empty} have no label-fidelity occurrence in the chunk they retrieve, "
        f"so there is nothing to mask - §5's retrieval gate, not masking, is "
        f"what keeps `ask`/`hint_*` clean."
    )

    scored = len(bank.items) - len(no_chunk)
    if served_wrong_section:
        rep.warn(
            f"[retrieval] the served chunk disagrees with the node's declared "
            f"source_sections for {len(set(n for n, _, _ in served_wrong_section))} "
            f"of {len(nodes)} nodes. Spans there are correct for a chunk the "
            f"chapter says is the wrong one, and `advance`/`explain` cite that "
            f"section: "
            + ", ".join(f"{n} ({'/'.join(want)} -> {got})"
                        for n, want, got in sorted(set(served_wrong_section))[:5])
        )
    if no_chunk:
        rep.warn(
            f"[retrieval] guard layer 4 refuses a chunk for "
            f"{len(set(no_chunk))} node(s); {scored} items are maskable at all"
        )


def check_item_distinctness(bank: ItemBank, rep: Report, fixture: bool) -> None:
    """Catch a generator fixture reaching data/ as though it were content.

    This check exists because it did happen and nothing caught it. 159 mcq items
    were committed carrying 3 distinct option sets, because build/generate_items.py
    cycles MOCK_MECHANISMS with `k % 3` under BUILD_LLM=mock - which is the
    default, since build.RealLLM is unimplemented. Every other check passed: the
    ids were unique, the schema was satisfied, the counts were right, the DAG was
    clean. Nothing in the pipeline asked whether the items were DIFFERENT.

    Two rules, both about the same failure from different angles:

      option-set reuse   the same (key, distractors) tuple on many items
      key reuse ACROSS NODES   one key that is correct for several concepts,
                               which is the harder error - it means at most one
                               of those items can be scoreable, and 1.4 scores
                               mcq into mastery and the adaptive path

    ERROR in strict mode, WARNING under --fixture, where placeholder content is
    the point.
    """
    mcq = [i for i in bank.items if i.type == "mcq"]
    if not mcq:
        return

    # SEVERITY IS KEYED ON CONSEQUENCE, NOT ON LENIENCY. The rule itself is
    # unchanged and still fires on exactly the same condition; what changes is
    # whether a fixture bank is currently allowed to corrupt anything. A
    # non-distinct bank that feeds theta is an ERROR because mastery and the
    # adaptive path are computed from it. The same bank marked scorable=false
    # still teaches and still appears in dialogue, but moves no number, so it is
    # a WARNING that prints on every build until the items are regenerated.
    #
    # This is what makes "flip a flag" the whole remediation when a real bank
    # lands: set scorable=true and the same check goes straight back to ERROR
    # without anything here being edited.
    scorable_mcq = [i for i in mcq if i.scorable]
    say = rep.error if (scorable_mcq and not fixture) else rep.warn
    scope = ("scored" if scorable_mcq else "unscored (scorable=false)")

    option_sets = {}
    for item in mcq:
        option_sets.setdefault(
            (item.answer, tuple(sorted(item.distractors))), []).append(item.id)

    reused = {k: v for k, v in option_sets.items() if len(v) > 1}
    if reused:
        worst = max(reused.items(), key=lambda kv: len(kv[1]))
        affected = sum(len(v) for v in reused.values())
        say(f"[{scope}] mcq option sets not distinct: {len(mcq)} items carry "
            f"{len(option_sets)} distinct (key, distractors) tuples; "
            f"{affected} items affected, worst reused {len(worst[1])}x "
            f"(key {worst[0][0][:48]!r}). This is what a mock item bank looks "
            f"like - check BUILD_LLM before trusting data/items.json.")

    key_nodes = {}
    for item in mcq:
        key_nodes.setdefault(item.answer, set()).add(item.node_id)
    cross = {k: v for k, v in key_nodes.items() if len(v) > 1}
    if cross:
        worst = max(cross.items(), key=lambda kv: len(kv[1]))
        say(f"[{scope}] {len(cross)} mcq key(s) answer more than one node; worst "
            f"answers {len(worst[1])} different nodes ({worst[0][:48]!r}). A key "
            f"that answers many concepts is not node-specific, so at most one of "
            f"those items is scoreable.")

    # Length tell. Not a distinctness problem, but the same human pass fixes it
    # and it is free to compute here. Warning in both modes: a real bank can
    # legitimately have a few long keys; what is damning is the RATE.
    longest = sum(1 for i in mcq
                  if i.distractors
                  and len(i.answer.split()) > max(len(d.split()) for d in i.distractors))
    rate = longest / len(mcq)
    if rate > BUILD.length_tell_alarm_rate:
        rep.warn(f"key is the longest option in {longest}/{len(mcq)} mcq items "
                 f"({rate:.0%}; chance is 25% at 4 options). Pick-the-longest is a "
                 f"content-free strategy that scores these items.")


def validate(graph_path: Path, items_path: Path, fixture: bool) -> Report:
    rep = Report()

    try:
        graph = Graph.model_validate_json(graph_path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        rep.error(f"graph.json failed schema validation:\n{exc}")
        return rep
    try:
        bank = ItemBank.model_validate_json(items_path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        rep.error(f"items.json failed schema validation:\n{exc}")
        return rep

    check_item_distinctness(bank, rep, fixture)
    check_answer_spans(graph, bank, rep)

    node_ids = [n.id for n in graph.nodes]
    node_set = set(node_ids)

    # --- graph structure ----------------------------------------------------
    if len(node_ids) != len(node_set):
        dupes = {n for n in node_ids if node_ids.count(n) > 1}
        rep.error(f"duplicate node ids: {sorted(dupes)}")

    if not fixture and not (BUILD.min_nodes <= len(node_ids) <= BUILD.max_nodes):
        rep.error(f"node count {len(node_ids)} outside required {BUILD.min_nodes}-{BUILD.max_nodes}")
    elif fixture and not (BUILD.min_nodes <= len(node_ids) <= BUILD.max_nodes):
        rep.warn(f"node count {len(node_ids)} outside {BUILD.min_nodes}-{BUILD.max_nodes} (allowed: --fixture)")

    for e in graph.edges:
        if e.from_ not in node_set:
            rep.error(f"dangling edge source: {e.from_} -> {e.to}")
        if e.to not in node_set:
            rep.error(f"dangling edge target: {e.from_} -> {e.to}")
        if e.from_ == e.to:
            rep.error(f"self-loop on {e.from_}")

    connected = {e.from_ for e in graph.edges} | {e.to for e in graph.edges}
    for orphan in sorted(node_set - connected):
        rep.error(f"orphan node (no edges): {orphan}")

    prereq_edges = [(e.from_, e.to) for e in graph.edges if e.type == "prereq"]
    seen_pairs = set()
    for pair in prereq_edges:
        if pair in seen_pairs:
            rep.error(f"duplicate prereq edge: {pair[0]} -> {pair[1]}")
        seen_pairs.add(pair)

    cycle = find_cycle(node_ids, prereq_edges)
    if cycle:
        rep.error("prereq edges are not a DAG; cycle: " + " -> ".join(cycle))

    # --- items --------------------------------------------------------------
    item_ids = [i.id for i in bank.items]
    if len(item_ids) != len(set(item_ids)):
        dupes = {i for i in item_ids if item_ids.count(i) > 1}
        rep.error(f"duplicate item ids: {sorted(dupes)}")

    covered = set()
    for item in bank.items:
        where = f"item {item.id}"
        if item.node_id not in node_set:
            rep.error(f"{where}: node_id {item.node_id} not in graph")
            continue
        covered.add(item.node_id)

        if item.type == "edge_click":
            # Convention: the answer is "src->dst".
            if "->" not in item.answer:
                rep.error(f"{where}: edge_click answer must be 'src->dst', got {item.answer!r}")
            else:
                src, _, dst = item.answer.partition("->")
                if not any(e.from_ == src and e.to == dst for e in graph.edges):
                    rep.error(f"{where}: answer edge {item.answer} is not in the graph")
        elif item.visually_answerable and item.answer not in node_set:
            rep.error(
                f"{where}: visually_answerable=true but answer {item.answer!r} "
                f"is not a node id"
            )
        elif not item.visually_answerable and item.answer in node_set:
            # A node-valued answer IS on the graph, so the flag is wrong. This
            # matters: 9.2 runs on the true subset, and a mislabelled item both
            # corrupts that split and widens the identity-leak surface.
            rep.error(
                f"{where}: visually_answerable=false but answer {item.answer!r} "
                f"is a node on the graph"
            )

        if item.answer in item.distractors:
            rep.error(f"{where}: answer appears in its own distractors")
        for d in item.distractors:
            # Distractors must be the same KIND as the answer. A node-id
            # distractor beside a proposition answer makes the odd one out
            # visible without reading either.
            if item.visually_answerable and d not in node_set:
                rep.error(f"{where}: distractor {d} is not a node id")
            if not item.visually_answerable and d in node_set:
                rep.error(
                    f"{where}: distractor {d!r} is a node id but the answer is "
                    f"a proposition; the odd option out is guessable by shape"
                )
        if len(set(item.distractors)) != len(item.distractors):
            rep.error(f"{where}: duplicate distractors")

        if item.type == "mcq" and len(item.distractors) < 3:
            # A 3-choice item scored as 4-choice corrupts mastery quietly
            # (CLAUDE.md §9.4).
            rep.warn(f"{where}: mcq has {len(item.distractors)} distractors, expected 3")

        # CLAUDE.md §3: visually_answerable is true ONLY if the answer is a node
        # or edge on the graph. Getting this wrong invalidates eval §9.2, which
        # runs on the true subset.
        answer_on_graph = (
            item.answer in node_set
            or (
                "->" in item.answer
                and any(f"{e.from_}->{e.to}" == item.answer for e in graph.edges)
            )
        )
        if item.visually_answerable and not answer_on_graph:
            rep.error(f"{where}: visually_answerable=true but answer is not a node or edge")

        # Aliases only matter for SHORT answers. CLAUDE.md 6 layer 1 splits on
        # answer length: <=5 tokens uses fuzzy matching against the aliases,
        # longer answers use cosine against the answer itself. Warning about a
        # missing alias on a proposition answer is noise, and 150 lines of noise
        # is how a real warning gets missed.
        # edge_click is excluded, and not as a convenience. Its answer is
        # "src->dst", an id pair no student ever types, and the only alias that
        # could mean anything - "<parent label> to <child label>" - contains
        # both endpoint labels by construction and so collides with both of
        # those nodes. Warning that an edge item has no aliases is asking for
        # the collision back. Layer 1 uses the answer string on these.
        if (
            item.type != "edge_click"
            and not item.answer_aliases
            and len(item.answer.split()) <= CONFIG.short_answer_token_cutoff
        ):
            rep.warn(f"{where}: short answer with no aliases; guard layer 1 fuzzy match will not fire")

    for node_id in sorted(node_set - covered):
        rep.error(f"node has no items: {node_id}")

    check_answer_identity(graph, bank, rep)
    check_alias_collisions(graph, bank, rep)
    check_edge_item_anchors(graph, bank, rep)

    if not fixture:
        for node_id in sorted(covered):
            count = sum(1 for i in bank.items if i.node_id == node_id)
            if count < 5:
                rep.warn(f"node {node_id} has {count} items, CLAUDE.md §4 targets 5")

    return rep


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=CONFIG.graph_path)
    parser.add_argument("--items", type=Path, default=CONFIG.items_path)
    parser.add_argument("--fixture", action="store_true",
                        help="relax the 40-60 node count for mock data")
    args = parser.parse_args()

    print(f"graph: {args.graph}")
    print(f"items: {args.items}")
    print(f"mode:  {'fixture' if args.fixture else 'strict'}\n")
    return validate(args.graph, args.items, args.fixture).render()


if __name__ == "__main__":
    sys.exit(main())
