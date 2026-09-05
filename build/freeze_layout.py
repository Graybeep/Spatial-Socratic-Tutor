"""Compute node x/y ONCE and write them into graph.json (CLAUDE.md §1.2, §4).

    python -m build.freeze_layout            # lay out and write
    python -m build.freeze_layout --check    # report, write nothing
    python -m build.freeze_layout --force    # overwrite coordinates that exist

This is the only thing in the project allowed to decide where a node sits, and
it runs manually, offline, exactly once per graph. Nothing at runtime may lay
out, re-lay-out, or nudge a node: §8 - if nodes move on a mastery update the
student loses the spatial memory and the whole spatial claim evaporates. The
coordinates live in the data file precisely so that no code has the option.

Because of that, it refuses to overwrite existing coordinates without --force.
The failure it is guarding against is not a crash; it is a re-run that quietly
shifts a frozen layout the demo, the screenshots and the muscle memory were all
built against.

WHY NOT DAGRE. §4 says "run dagre ONCE". dagre is JavaScript, and reaching for
it here means either a Node subprocess in a Python build step or a port. For a
50-node prereq DAG the useful part of dagre is three passes - layer, order,
place - and they are about a hundred lines. That is cheaper than the dependency
and it is §1.8-proof. If the layout ever needs to be better than this, the
answer is to hand-edit the coordinates in graph.json, which is a supported
workflow: they are data, and §4's fallback already expects hand-authoring.

THE THREE PASSES

1. Layer. Longest-path ranking over `prereq` edges: a node sits one row below
   its deepest prerequisite. Longest-path, not shortest, so that every edge
   points strictly downward and no edge is horizontal.

2. Order. Barycentre sweeps, down then up, repeated. A node drifts towards the
   average position of its neighbours in the adjacent layer, which is the
   standard cheap crossing-reduction heuristic. `related` edges pull too, at
   half weight: they express "these belong near each other", which is exactly
   what a spatial map wants, but they must not outvote the prerequisite
   structure that the layering is actually about.

3. Place. Evenly spaced within a layer, each layer centred on the widest one.

Deterministic: every tie breaks on node id, so the same graph.json in gives the
same coordinates out. A layout that shifted between runs would make every diff
unreadable and every screenshot stale.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from build.config import BUILD

RELATED_WEIGHT = 0.5


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def layer_nodes(node_ids: list[str], prereq: list[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layering. Returns node id -> row index.

    Kahn's algorithm, taking the max over incoming edges, so a node lands below
    its deepest prerequisite rather than its nearest one. Raises on a cycle -
    build/validate.py already rejects those (a cycle makes next-node selection
    loop forever), but this runs before validate in a fresh pipeline and a
    silent partial layering would be worse than a stop.
    """
    indegree = {n: 0 for n in node_ids}
    out = defaultdict(list)
    for a, b in prereq:
        out[a].append(b)
        indegree[b] += 1

    rank = {n: 0 for n in node_ids}
    # Sorted queue rather than a set: determinism costs nothing at 50 nodes.
    queue = sorted(n for n, d in indegree.items() if d == 0)
    seen = 0
    while queue:
        node = queue.pop(0)
        seen += 1
        for nxt in sorted(out[node]):
            rank[nxt] = max(rank[nxt], rank[node] + 1)
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
                queue.sort()

    if seen != len(node_ids):
        stuck = sorted(n for n, d in indegree.items() if d > 0)
        raise SystemExit(
            f"prereq edges contain a cycle; cannot layer. Involved: {stuck[:8]}"
            + ("..." if len(stuck) > 8 else "")
        )
    return rank


def order_layers(
    layers: dict[int, list[str]],
    neighbours: dict[str, list[tuple[str, float]]],
    sweeps: int,
) -> None:
    """Barycentre sweeps, in place. Down then up, `sweeps` times."""
    def sweep(rows: list[int]) -> None:
        for row in rows:
            position = {n: i for r in layers for i, n in enumerate(layers[r])}
            def barycentre(node: str) -> tuple:
                weighted = [(position[m], w) for m, w in neighbours[node] if m in position]
                if not weighted:
                    # No neighbours: hold station rather than drift to the left
                    # edge and drag unrelated nodes with it.
                    return (position[node], node)
                total = sum(w for _, w in weighted)
                return (sum(p * w for p, w in weighted) / total, node)
            layers[row] = sorted(layers[row], key=barycentre)

    rows_down = sorted(layers)
    for _ in range(sweeps):
        sweep(rows_down)
        sweep(list(reversed(rows_down)))


def place(layers: dict[int, list[str]]) -> dict[str, tuple[int, int]]:
    """Even spacing inside a layer; layers centred on the widest."""
    step_x = BUILD.layout_node_w + BUILD.layout_x_gap
    step_y = BUILD.layout_node_h + BUILD.layout_y_gap
    widest = max((len(v) for v in layers.values()), default=1)

    coords: dict[str, tuple[int, int]] = {}
    for row in sorted(layers):
        members = layers[row]
        indent = (widest - len(members)) * step_x // 2
        for i, node in enumerate(members):
            coords[node] = (
                BUILD.layout_origin_x + indent + i * step_x,
                BUILD.layout_origin_y + row * step_y,
            )
    return coords


def count_crossings(edges, coords) -> int:
    """Pairs of edges that cross, as a quality number to print.

    Not an optimisation target - it is here so a bad layout is visible in the
    build output instead of on the projector in week 3.
    """
    segments = [
        (coords[a][0], coords[a][1], coords[b][0], coords[b][1])
        for a, b in edges
        if a in coords and b in coords
    ]
    crossings = 0
    for i, (ax1, ay1, ax2, ay2) in enumerate(segments):
        for bx1, by1, bx2, by2 in segments[i + 1:]:
            # Only edges spanning the same rows can cross in a layered drawing.
            if ay1 != by1 or ay2 != by2:
                continue
            if (ax1 - bx1) * (ax2 - bx2) < 0:
                crossings += 1
    return crossings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", default=BUILD.graph_path, type=Path)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    ap.add_argument("--force", action="store_true",
                    help="overwrite coordinates that are already frozen")
    ap.add_argument("--sweeps", type=int, default=BUILD.layout_sweeps)
    args = ap.parse_args(argv)

    graph = _load(args.graph)
    nodes = graph["nodes"]
    node_ids = [n["id"] for n in nodes]
    known = set(node_ids)

    prereq = [
        (e["from"], e["to"]) for e in graph["edges"]
        if e.get("type") == "prereq" and e["from"] in known and e["to"] in known
    ]
    related = [
        (e["from"], e["to"]) for e in graph["edges"]
        if e.get("type") != "prereq" and e["from"] in known and e["to"] in known
    ]

    already = [n["id"] for n in nodes if n.get("x") is not None and n.get("y") is not None]
    if already and not args.force and not args.check:
        print(
            f"{len(already)}/{len(nodes)} nodes already have frozen coordinates.\n"
            "Refusing to move them: §1.2 freezes the layout and §8 says a node "
            "that moves costs the student the spatial memory the claim rests on.\n"
            "Pass --force if you genuinely intend to re-freeze this graph.",
            file=sys.stderr,
        )
        return 2

    rank = layer_nodes(node_ids, prereq)
    layers: dict[int, list[str]] = defaultdict(list)
    for node in sorted(node_ids):
        layers[rank[node]].append(node)

    neighbours: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for a, b in prereq:
        neighbours[a].append((b, 1.0))
        neighbours[b].append((a, 1.0))
    for a, b in related:
        neighbours[a].append((b, RELATED_WEIGHT))
        neighbours[b].append((a, RELATED_WEIGHT))

    order_layers(layers, neighbours, args.sweeps)
    coords = place(layers)

    print(f"{len(nodes)} nodes in {len(layers)} layers "
          f"(widest {max(len(v) for v in layers.values())})")
    print(f"{count_crossings(prereq, coords)} prereq edge crossings")

    if args.check:
        print("--check: nothing written")
        return 0

    for node in nodes:
        node["x"], node["y"] = coords[node["id"]]

    args.graph.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    print(f"wrote coordinates into {args.graph}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
