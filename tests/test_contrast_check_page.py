"""client/contrast-check.html — the week-3 projector instrument (CLAUDE.md §8).

§8 requires the dimming to be tested on the demo hardware in week 3. The page
exists so that test is a 30-second job, and these tests exist so the page cannot
quietly stop standing in for the real component: a contrast check drawn with
stale token values would pass on the projector and prove nothing.

They do NOT test that the dimming looks right. Nothing here can. That is the
part that needs eyes on the actual hardware.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from server.config import CONFIG

PAGE = Path(__file__).resolve().parents[1] / "client" / "contrast-check.html"
TOKENS = Path(__file__).resolve().parents[1] / "client" / "src" / "tokens.css"

#: Every token the page redraws with. If Graph.tsx gains a channel, add it here
#: and to the page, or the instrument stops matching the interface.
DIMMING_TOKENS = [
    "--lit-stroke", "--dim-stroke", "--dim-shape-opacity",
    "--dim-label-opacity", "--dim-edge-opacity", "--dim-saturate",
    "--ink", "--paper", "--rule",
]


def _decls(text: str) -> dict:
    return {k: v.strip() for k, v in re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", text)}


@pytest.fixture(scope="module")
def page() -> str:
    assert PAGE.exists(), f"{PAGE} is missing; regenerate it before the week-3 test"
    return PAGE.read_text(encoding="utf-8")


def _embedded(page: str, name: str):
    return json.loads(re.search(rf"const {name} = (\[.*?\]);\n", page, re.S).group(1))


@pytest.mark.parametrize("token", DIMMING_TOKENS)
def test_page_uses_the_real_token_values(page, token):
    """A stale copy of --dim-shape-opacity would make the projector test a
    measurement of a value the interface no longer uses."""
    real = _decls(TOKENS.read_text(encoding="utf-8"))
    assert token in real, f"{token} vanished from tokens.css"
    assert _decls(page).get(token) == real[token], (
        f"{token} in contrast-check.html is {_decls(page).get(token)!r} but "
        f"tokens.css says {real[token]!r}. Regenerate the page."
    )


def test_the_page_shows_the_rung_the_demo_actually_reaches(page):
    """The whole point. It was built against an assumed floor of 5; the shipped
    interleaved ladder stops at 9."""
    panels = _embedded(page, "PANELS")
    nine = [p for p in panels if p["n"] == 9]
    assert nine, "the 9-lit rung is missing - that is the one being tested"
    assert nine[0]["mode"] == "interleaved"
    assert "what the demo actually reaches" in page


def test_every_panel_lights_the_count_it_claims(page):
    nodes = {n["id"] for n in _embedded(page, "NODES")}
    for panel in _embedded(page, "PANELS"):
        assert len(panel["lit"]) == panel["n"]
        assert set(panel["lit"]) <= nodes, f"{panel['n']}-lit panel names unknown nodes"


def test_the_page_carries_the_whole_frozen_graph(page):
    """Dimming legibility is a property of the FULL map. A page drawn over a
    subset would understate how far the lit set is spread."""
    graph = json.loads((Path(CONFIG.graph_path)).read_text(encoding="utf-8"))
    nodes = _embedded(page, "NODES")
    assert len(nodes) == len(graph["nodes"])
    assert len(_embedded(page, "EDGES")) == len(graph["edges"])
    by_id = {n["id"]: n for n in nodes}
    for n in graph["nodes"]:
        assert by_id[n["id"]]["x"] == n["x"] and by_id[n["id"]]["y"] == n["y"], (
            "layout drifted from graph.json; §1.2 freezes it, so regenerate the page"
        )


def test_the_floor_and_the_shipped_terminal_still_disagree(page):
    """If a future schedule change makes interleaved actually reach
    candidate_floor, this page's premise is gone and it should be regenerated."""
    panels = {p["n"] for p in _embedded(page, "PANELS")}
    assert CONFIG.candidate_floor in panels, "the policy floor is not shown at all"
    assert 9 in panels
