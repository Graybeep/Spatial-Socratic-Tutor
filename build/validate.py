"""Validate the frozen data files. CLAUDE.md §3: must pass before commit.

    python -m build.validate            # strict, for the real chapter graph
    python -m build.validate --fixture  # relaxes the 40-60 node count only

Exit code 0 = clean, 1 = errors. Warnings never fail the run; they are things a
human should look at, not things that break the system.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from server.config import CONFIG
from server.schemas import SCORABLE_EXPECTS, Graph, ItemBank, ItemPublic

MIN_NODES = 40
MAX_NODES = 60


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
            scorable=item.type in SCORABLE_EXPECTS,
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

    node_ids = [n.id for n in graph.nodes]
    node_set = set(node_ids)

    # --- graph structure ----------------------------------------------------
    if len(node_ids) != len(node_set):
        dupes = {n for n in node_ids if node_ids.count(n) > 1}
        rep.error(f"duplicate node ids: {sorted(dupes)}")

    if not fixture and not (MIN_NODES <= len(node_ids) <= MAX_NODES):
        rep.error(f"node count {len(node_ids)} outside required {MIN_NODES}-{MAX_NODES}")
    elif fixture and not (MIN_NODES <= len(node_ids) <= MAX_NODES):
        rep.warn(f"node count {len(node_ids)} outside {MIN_NODES}-{MAX_NODES} (allowed: --fixture)")

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
        if not item.answer_aliases and len(item.answer.split()) <= CONFIG.short_answer_token_cutoff:
            rep.warn(f"{where}: short answer with no aliases; guard layer 1 fuzzy match will not fire")

    for node_id in sorted(node_set - covered):
        rep.error(f"node has no items: {node_id}")

    check_answer_identity(graph, bank, rep)

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
