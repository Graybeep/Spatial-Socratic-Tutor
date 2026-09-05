"""build/freeze_layout.py - the one place allowed to decide where a node sits.

Worth testing properly because its output is frozen data that everything
downstream trusts and nothing downstream re-derives. A layout bug does not
surface as an exception; it surfaces as a graph that reads badly on a projector
in week 3, by which point the coordinates are in screenshots and in the
student's muscle memory.
"""
from __future__ import annotations

import json

import pytest

from build import freeze_layout
from build.config import BUILD


def _graph(nodes, edges):
    return {
        "version": "1.0",
        "domain": "test",
        "nodes": [
            {"id": n, "label": n, "definition": "d", "source_sections": ["1"],
             "difficulty": 0.5}
            for n in nodes
        ],
        "edges": [{"from": a, "to": b, "type": t} for a, b, t in edges],
    }


def _write(tmp_path, graph):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# layering
# ---------------------------------------------------------------------------

def test_layering_is_longest_path_not_shortest():
    """d depends on both b and c; c is deeper, so d sits below c, not below b.

    Shortest-path layering would put d at row 1 next to c and draw the a->d edge
    horizontally across the layer, which is the one thing a layered drawing is
    supposed to prevent.
    """
    rank = freeze_layout.layer_nodes(
        ["a", "b", "c", "d"],
        [("a", "b"), ("a", "c"), ("c", "d"), ("b", "d")],
    )
    assert rank == {"a": 0, "b": 1, "c": 1, "d": 2}


def test_a_cycle_stops_the_build():
    """validate.py rejects cycles too, but this runs before it in a fresh
    pipeline and a partial layering would be worse than a stop."""
    with pytest.raises(SystemExit) as e:
        freeze_layout.layer_nodes(["a", "b"], [("a", "b"), ("b", "a")])
    assert "cycle" in str(e.value)


def test_isolated_nodes_still_get_a_layer():
    rank = freeze_layout.layer_nodes(["a", "b", "lonely"], [("a", "b")])
    assert rank["lonely"] == 0


# ---------------------------------------------------------------------------
# placement
# ---------------------------------------------------------------------------

def test_every_prereq_edge_points_downwards(tmp_path):
    graph = _graph(
        ["a", "b", "c", "d", "e"],
        [("a", "b", "prereq"), ("b", "c", "prereq"),
         ("a", "d", "prereq"), ("d", "e", "prereq"), ("c", "e", "related")],
    )
    path = _write(tmp_path, graph)
    assert freeze_layout.main(["--graph", str(path), "--force"]) == 0

    out = json.loads(path.read_text(encoding="utf-8"))
    y = {n["id"]: n["y"] for n in out["nodes"]}
    for e in out["edges"]:
        if e["type"] == "prereq":
            assert y[e["to"]] > y[e["from"]], f"{e['from']}->{e['to']} does not descend"


def test_no_two_nodes_share_a_position(tmp_path):
    graph = _graph(
        [f"n{i}" for i in range(12)],
        [(f"n{i}", f"n{i+1}", "prereq") for i in range(0, 10, 2)],
    )
    path = _write(tmp_path, graph)
    freeze_layout.main(["--graph", str(path), "--force"])

    out = json.loads(path.read_text(encoding="utf-8"))
    positions = [(n["x"], n["y"]) for n in out["nodes"]]
    assert len(set(positions)) == len(positions)


def test_layout_is_deterministic(tmp_path):
    """Same graph in, same coordinates out.

    A layout that drifted between runs would make every graph.json diff
    unreadable and silently invalidate screenshots.
    """
    graph = _graph(
        [f"n{i}" for i in range(9)],
        [("n0", "n3", "prereq"), ("n1", "n3", "prereq"), ("n2", "n4", "prereq"),
         ("n3", "n5", "prereq"), ("n4", "n5", "prereq"), ("n6", "n7", "related")],
    )
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for path in (a, b):
        path.write_text(json.dumps(graph), encoding="utf-8")
        freeze_layout.main(["--graph", str(path), "--force"])

    coords = [
        {n["id"]: (n["x"], n["y"]) for n in json.loads(p.read_text(encoding="utf-8"))["nodes"]}
        for p in (a, b)
    ]
    assert coords[0] == coords[1]


def test_spacing_comes_from_config_not_literals(tmp_path):
    """§13.1: layout geometry is a build knob. Changing it must move the nodes.

    BUILD is a frozen dataclass, same as server CONFIG, so the override goes
    through object.__setattr__ and restores - exactly what conftest's
    config_override does. Nothing outside a test may do this.
    """
    graph = _graph(["a", "b"], [])
    path = _write(tmp_path, graph)

    saved = BUILD.layout_origin_x
    object.__setattr__(BUILD, "layout_origin_x", 500)
    try:
        freeze_layout.main(["--graph", str(path), "--force"])
    finally:
        object.__setattr__(BUILD, "layout_origin_x", saved)

    out = json.loads(path.read_text(encoding="utf-8"))
    assert min(n["x"] for n in out["nodes"]) == 500


# ---------------------------------------------------------------------------
# the freeze itself
# ---------------------------------------------------------------------------

def test_refuses_to_move_an_already_frozen_layout(tmp_path, capsys):
    """§1.2 and §8. The guarded failure is a re-run that quietly shifts a layout
    the demo was built against - not a crash."""
    graph = _graph(["a", "b"], [("a", "b", "prereq")])
    for n in graph["nodes"]:
        n["x"], n["y"] = 11, 22
    path = _write(tmp_path, graph)

    assert freeze_layout.main(["--graph", str(path)]) == 2

    out = json.loads(path.read_text(encoding="utf-8"))
    assert all((n["x"], n["y"]) == (11, 22) for n in out["nodes"]), "coordinates moved anyway"


def test_check_mode_writes_nothing(tmp_path):
    graph = _graph(["a", "b"], [("a", "b", "prereq")])
    path = _write(tmp_path, graph)
    before = path.read_text(encoding="utf-8")

    assert freeze_layout.main(["--graph", str(path), "--check"]) == 0
    assert path.read_text(encoding="utf-8") == before


def test_force_overwrites(tmp_path):
    graph = _graph(["a", "b"], [("a", "b", "prereq")])
    for n in graph["nodes"]:
        n["x"], n["y"] = 11, 22
    path = _write(tmp_path, graph)

    assert freeze_layout.main(["--graph", str(path), "--force"]) == 0
    out = json.loads(path.read_text(encoding="utf-8"))
    assert any((n["x"], n["y"]) != (11, 22) for n in out["nodes"])


def test_the_committed_graph_still_validates_after_a_layout(tmp_path):
    """The real fixture through the real path, so this is not only tested on
    five-node toys."""
    import shutil

    src = BUILD.graph_path
    path = tmp_path / "graph.json"
    shutil.copy(src, path)

    assert freeze_layout.main(["--graph", str(path), "--force"]) == 0
    out = json.loads(path.read_text(encoding="utf-8"))
    assert len(out["nodes"]) == len(json.loads(src.read_text(encoding="utf-8"))["nodes"])
    assert all(isinstance(n["x"], int) and isinstance(n["y"], int) for n in out["nodes"])
