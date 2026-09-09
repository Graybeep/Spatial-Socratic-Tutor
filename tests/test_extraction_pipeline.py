"""The offline extraction pipeline: chunk -> concepts -> edge candidates.

No chapter file is committed, but this HAS now met real input: the chapter was
fetched, chunked and run through the filter locally, and four of the tests below
exist because of what that produced. Anything a mock could have told us is not
worth a test here; these pin the logic that does not depend on the model.

The pairwise filter is the one worth real tests. §4 leans on it to turn 2,652
ordered pairs into roughly 150 LLM calls, and a filter that is subtly wrong
either costs a fortune in calls or silently discards most of the true edges —
neither of which announces itself, because the human pass downstream sees only
what survived. Measured on the real chapter it kept 381 candidates, 14% of the
pair space, with a 59% recall ceiling against the hand-authored graph.
"""
from __future__ import annotations

import json

import pytest

from build import chunk as chunk_mod
from build import extract_concepts, extract_edges
from build.config import BUILD

CHAPTER = """\
6.1 Issues in Resource Allocation
Resource allocation is the process by which network elements meet the competing
demands that applications have for network resources, primarily link bandwidth
and buffer space. A flow is a sequence of packets sent between one source and
one destination pair, following the same route through the network. Routers may
keep some state per flow in order to make allocation decisions.

6.2 Queuing Disciplines
FIFO means the first packet to arrive at the router is the first one to be
transmitted onward. Tail drop discards arriving packets once the queue is
already full, and it is the drop policy that pairs naturally with FIFO. Because
FIFO makes no distinction between flows, one aggressive sender can occupy most
of the buffer and push everyone else out of it.
F_i = max(F_{i-1}, A_i) + P_i

6.3 TCP Congestion Control
The congestion window limits how much unacknowledged data a sender may have in
flight at one time, and it is kept separately from the window the receiver
advertises. AIMD grows that congestion window by roughly one packet per
round-trip time while nothing is going wrong, and halves it on loss.

6.4 Advanced Congestion Control
RED drops a packet probabilistically before the queue is completely full, so
that senders are told to slow down early rather than all at once. It uses a
weighted running average of the queue length, reacting to sustained load
rather than to a momentary burst of arrivals.
"""


@pytest.fixture()
def chunks(tmp_path):
    src = tmp_path / "chapter.txt"
    src.write_text(CHAPTER, encoding="utf-8")
    return chunk_mod.TextChunker(src).chunks()


# ---------------------------------------------------------------------------
# chunking
# ---------------------------------------------------------------------------

def test_sections_split_on_numbered_headings(chunks):
    assert [c.section for c in chunks] == ["6.1", "6.2", "6.3", "6.4"]
    assert chunks[0].heading_path == "Issues in Resource Allocation"


def test_body_text_is_joined_and_headings_are_not_in_it(chunks):
    body = chunks[1].text
    assert "FIFO" in body and "Tail drop" in body
    assert "Queuing Disciplines" not in body


def test_equations_are_dropped_rather_than_mangled(chunks):
    """§4: equation and table extraction eats two days and buys nothing. A
    half-parsed formula in a chunk poisons retrieval for that section."""
    assert "F_i" not in chunks[1].text


def test_chunks_round_trip_through_the_file(tmp_path, chunks):
    out = tmp_path / "chunks.json"
    chunk_mod.write(chunks, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))["chunks"]
    assert len(loaded) == len(chunks)
    assert loaded[0]["section"] == "6.1"


# ---------------------------------------------------------------------------
# the pairwise filter - §4's cost argument
# ---------------------------------------------------------------------------

CONCEPTS = [
    {"id": "flow", "label": "flow"},
    {"id": "fifo", "label": "FIFO"},
    {"id": "cwnd", "label": "congestion window"},
    {"id": "red", "label": "RED"},
]


def _dicts(chunks):
    return [{"section": c.section, "heading_path": c.heading_path, "text": c.text}
            for c in chunks]


def test_only_forward_pairs_survive(chunks):
    """A prerequisite relation is directional and textbooks are written in
    dependency order: if B is explained first, B is not a prerequisite of A."""
    pairs = extract_edges.candidates(CONCEPTS, _dicts(chunks), window=4)
    assert pairs
    for p in pairs:
        assert (p.from_id, p.to_id) != (p.to_id, p.from_id)
    # flow (6.1) may precede fifo (6.2); never the reverse.
    assert any(p.from_id == "flow" and p.to_id == "fifo" for p in pairs)
    assert not any(p.from_id == "fifo" and p.to_id == "flow" for p in pairs)


def test_the_window_excludes_distant_pairs(chunks):
    """Concepts that never appear near each other are not in a prerequisite
    relation in THIS chapter, whatever their relation in the field."""
    near = extract_edges.candidates(CONCEPTS, _dicts(chunks), window=1)
    far = extract_edges.candidates(CONCEPTS, _dicts(chunks), window=4)
    assert len(near) < len(far)
    # flow (6.1) -> red (6.4) is 3 apart: in at window 4, out at window 1.
    assert any(p.from_id == "flow" and p.to_id == "red" for p in far)
    assert not any(p.from_id == "flow" and p.to_id == "red" for p in near)


def test_the_filter_actually_cuts_the_call_count(chunks):
    """The reason the filter exists. Without it every ordered pair is a call."""
    pairs = extract_edges.candidates(CONCEPTS, _dicts(chunks), window=2)
    ordered_pairs = len(CONCEPTS) * (len(CONCEPTS) - 1)
    assert len(pairs) < ordered_pairs / 2


def test_a_concept_never_mentioned_in_the_text_is_skipped(chunks):
    """It must not default to position 0, which would make an unmentioned
    concept look like a prerequisite of everything."""
    concepts = CONCEPTS + [{"id": "ghost", "label": "quantum entanglement"}]
    pairs = extract_edges.candidates(concepts, _dicts(chunks), window=4)
    assert not any("ghost" in (p.from_id, p.to_id) for p in pairs)


def test_nearest_pairs_come_first(chunks):
    """So a truncated budget spends its calls on the likeliest edges."""
    pairs = extract_edges.candidates(CONCEPTS, _dicts(chunks), window=4)
    assert [p.distance for p in pairs] == sorted(p.distance for p in pairs)


# ---------------------------------------------------------------------------
# canonicalisation
# ---------------------------------------------------------------------------

def test_exact_duplicates_merge_after_normalisation():
    kept, _ = extract_concepts.canonicalise([
        {"id": "a", "label": "Slow Start"},
        {"id": "b", "label": "slow start"},
        {"id": "c", "label": "AIMD"},
    ])
    assert len(kept) == 2


def test_near_duplicates_are_flagged_not_merged():
    """No embeddings, so nothing is merged on a guess. The pair goes to the
    human pass instead — the conservative direction, and a visible one."""
    kept, suspicious = extract_concepts.canonicalise([
        {"id": "a", "label": "congestion window"},
        {"id": "b", "label": "effective window"},
    ])
    assert len(kept) == 2
    assert ("congestion window", "effective window") in [tuple(p) for p in suspicious]


def test_slug_is_usable_as_a_node_id():
    assert extract_concepts.slug("Bit-by-Bit Round Robin") == "bit_by_bit_round_robin"


# ---------------------------------------------------------------------------
# the pipeline runs end to end on the mock
# ---------------------------------------------------------------------------

def test_the_whole_pipeline_runs_without_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("BUILD_LLM", raising=False)
    src = tmp_path / "chapter.txt"
    src.write_text(CHAPTER, encoding="utf-8")
    chunks_path = tmp_path / "chunks.json"

    assert chunk_mod.main(["--text", str(src), "--out", str(chunks_path)]) == 0

    concepts_out = tmp_path / "candidate_concepts.json"
    assert extract_concepts.main(
        ["--chunks", str(chunks_path), "--out", str(concepts_out)]) == 0
    concepts = json.loads(concepts_out.read_text(encoding="utf-8"))
    assert concepts["generator"] == "mock"
    assert concepts["concepts"]

    edges_out = tmp_path / "candidate_edges.json"
    assert extract_edges.main([
        "--chunks", str(chunks_path),
        "--concepts", str(_as_graph(concepts, tmp_path)),
        "--out", str(edges_out),
    ]) == 0
    edges = json.loads(edges_out.read_text(encoding="utf-8"))
    assert edges["generator"] == "mock"


def _as_graph(concepts: dict, tmp_path):
    """extract_edges reads `nodes`; the concepts file writes `concepts`."""
    path = tmp_path / "as_graph.json"
    path.write_text(json.dumps({"nodes": concepts["concepts"]}), encoding="utf-8")
    return path


def test_missing_chunks_is_a_clear_stop_not_a_traceback():
    with pytest.raises(SystemExit, match="hand-authored"):
        extract_concepts.main(["--chunks", "does/not/exist.json"])
    with pytest.raises(SystemExit, match="hand-authored"):
        extract_edges.main(["--chunks", "does/not/exist.json"])


# ---------------------------------------------------------------------------
# alias collisions (build/validate.py)
# ---------------------------------------------------------------------------

def test_two_nodes_sharing_a_surface_is_an_error():
    """Unambiguously broken data: every name-based matcher becomes ambiguous,
    and not every consumer reports a hit rate the way guard layer 1 does."""
    from build.validate import Report, check_alias_collisions
    from server.schemas import Graph, ItemBank

    graph = Graph.model_validate({
        "version": "1.0", "domain": "t",
        "nodes": [
            {"id": "a", "label": "Slow Start", "definition": "d",
             "source_sections": ["1"], "difficulty": 0.5, "x": 0, "y": 0},
            {"id": "b", "label": "slow-start", "definition": "d",
             "source_sections": ["1"], "difficulty": 0.5, "x": 0, "y": 0},
        ],
        "edges": [{"from": "a", "to": "b", "type": "prereq"}],
    })
    rep = Report()
    check_alias_collisions(graph, ItemBank(version="1.0", domain="t", items=[]), rep)
    assert any("alias collision" in e for e in rep.errors)


def test_nesting_is_a_warning_not_an_error():
    """A hard substring ban is unsatisfiable on real terminology: Weighted Fair
    Queuing contains Fair Queuing because WFQ is FQ plus weights. Renaming one
    to pass a lint would distort the subject."""
    from build.validate import Report, check_alias_collisions
    from server.schemas import Graph, ItemBank

    graph = Graph.model_validate({
        "version": "1.0", "domain": "t",
        "nodes": [
            {"id": "fq", "label": "Fair Queuing", "definition": "d",
             "source_sections": ["1"], "difficulty": 0.5, "x": 0, "y": 0},
            {"id": "wfq", "label": "Weighted Fair Queuing", "definition": "d",
             "source_sections": ["1"], "difficulty": 0.5, "x": 0, "y": 0},
        ],
        "edges": [{"from": "fq", "to": "wfq", "type": "prereq"}],
    })
    rep = Report()
    check_alias_collisions(graph, ItemBank(version="1.0", domain="t", items=[]), rep)
    assert not rep.errors
    assert any("nested concept name" in w for w in rep.warnings)


def test_the_shipped_bank_has_no_equality_collisions():
    """The regression this exists to prevent. The bank had 53 collisions when
    the check was written; 51 were generated edge aliases of the form
    "<parent> to <child>", which contain both endpoint labels by construction."""
    from build.validate import Report, check_alias_collisions
    from server.graph_store import GraphStore

    store = GraphStore.load()
    rep = Report()
    check_alias_collisions(store.graph, store.bank, rep)
    assert rep.errors == [], rep.errors


def test_same_section_concepts_still_get_an_order():
    """The bug real text exposed, and the reason position is (section, offset).

    Comparing sections alone discards every same-section pair. Measured against
    the hand-authored graph that was 34 of 66 true prerequisite edges — more
    than half, thrown away before the model was asked anything — and it capped
    §9.3's achievable recall at 21%. A textbook introduces several related
    concepts in one section, in order, and that order is the evidence.
    """
    chunks = [{
        "section": "6.2",
        "heading_path": "Queuing Disciplines",
        "text": ("FIFO means the first packet to arrive is transmitted first. "
                 "Tail drop discards arriving packets once the queue is full."),
    }]
    concepts = [{"id": "fifo", "label": "FIFO"},
                {"id": "tail_drop", "label": "tail drop"}]

    pairs = extract_edges.candidates(concepts, chunks, window=2)
    assert any(p.from_id == "fifo" and p.to_id == "tail_drop" for p in pairs),         "same-section pair was discarded"
    assert not any(p.from_id == "tail_drop" and p.to_id == "fifo" for p in pairs),         "order within the section was ignored"


def test_source_sections_locate_a_concept_the_prose_never_names():
    """An authored label is a tidy noun phrase; prose is not. The graph says
    "Jain's Fairness Index", the chapter says "fairness index"."""
    chunks = [{"section": "6.1.3", "heading_path": "Evaluation Criteria",
               "text": "The fairness index gives a number between zero and one."}]
    pos = extract_edges.first_appearance(
        [{"id": "fi", "label": "Jain's Fairness Index", "source_sections": ["6.1.3"]}],
        chunks)
    assert "fi" in pos


# ---------------------------------------------------------------------------
# HtmlChunker — the implementation the real chapter actually goes through
# ---------------------------------------------------------------------------

_PAGE = """<!doctype html>
<html><head><title>6.3 TCP Congestion Control &mdash; Computer Networks</title>
<style>.x{{color:red}}</style></head>
<body>
<nav class="bd-links"><p>6.3 TCP Congestion Control</p><p>Previous</p></nav>
<article role="main">
  <h1>{h1}<a class="headerlink" href="#tcp" title="Link to this heading">\uf0c1</a></h1>
  <p>{body1}</p>
  <h2>{h2}<a class="headerlink" href="#ss">\uf0c1</a></h2>
  <p>{body2}</p>
</article>
<footer><p>Copyright</p></footer>
</body></html>
"""


def _page(h1, body1, h2, body2):
    return _PAGE.format(h1=h1, body1=body1, h2=h2, body2=body2)


def _write(tmp_path, name, markup):
    p = tmp_path / name
    p.write_text(markup, encoding="utf-8")
    return p


def test_html_chunker_sections_a_rendered_page(tmp_path):
    prose = "Congestion control is about the sender learning the capacity. " * 6
    more = "Slow start ramps the window up from a cold start exponentially. " * 6
    path = _write(tmp_path, "00_tcpcc.html", _page(
        "6.3 TCP Congestion Control", prose, "6.3.1 Slow Start", more))

    chunks = chunk_mod.HtmlChunker([path]).chunks()

    assert [c.section for c in chunks] == ["6.3", "6.3.1"]
    assert chunks[0].heading_path == "TCP Congestion Control"
    assert "Congestion control is about" in chunks[0].text


def test_html_chunker_drops_nav_and_footer_furniture():
    """The nav repeats the chapter heading. If it survives, `_sections` sees
    section 6.3 twice and extract_edges gets the wrong reading position."""
    prose = "The sender determines how much capacity is available. " * 8
    lines = chunk_mod.html_lines(_page(
        "6.3 TCP Congestion Control", prose, "6.3.1 Slow Start", prose))

    assert "Previous" not in lines
    assert "Copyright" not in lines
    # exactly one copy of the heading — the one inside <article>
    assert sum(l.startswith("6.3 TCP") for l in lines) == 1


def test_html_chunker_strips_the_headerlink_glyph():
    """A private-use glyph riding into the heading makes HEADING fail to match,
    and the whole page collapses into one section."""
    prose = "Queuing disciplines decide which packet leaves next. " * 8
    lines = chunk_mod.html_lines(_page(
        "6.2 Queuing Disciplines", prose, "6.2.1 FIFO", prose))
    heading = next(l for l in lines if l.startswith("6.2 "))
    assert heading == "6.2 Queuing Disciplines"
    assert "\uf0c1" not in heading


def test_html_chunker_preserves_file_order(tmp_path):
    """Reading order is a pipeline input: §4's precedence filter derives
    section -> position from it."""
    a = "Resource allocation meets competing demands for bandwidth. " * 8
    b = "TCP congestion control was introduced in the late 1980s. " * 8
    p1 = _write(tmp_path, "00_issues.html", _page("6.1 Issues", a, "6.1.1 Network Model", a))
    p2 = _write(tmp_path, "01_tcpcc.html", _page("6.3 TCP", b, "6.3.1 Slow Start", b))

    forward = [c.section for c in chunk_mod.HtmlChunker([p1, p2]).chunks()]
    reverse = [c.section for c in chunk_mod.HtmlChunker([p2, p1]).chunks()]

    assert forward == ["6.1", "6.1.1", "6.3", "6.3.1"]
    assert reverse == ["6.3", "6.3.1", "6.1", "6.1.1"]
