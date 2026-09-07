"""The offline extraction pipeline: chunk -> concepts -> edge candidates.

There is no chapter file in the repo, so none of this has met real input. What
IS tested is the logic that does not depend on the model: sectioning, the
pairwise precedence + co-occurrence filter, and canonicalisation.

The pairwise filter is the one worth real tests. §4 leans on it to turn 2,450
ordered pairs into roughly 150 LLM calls, and a filter that is subtly wrong
either costs a fortune in calls or silently discards most of the true edges —
neither of which announces itself, because the human pass downstream sees only
what survived.
"""
from __future__ import annotations

import json

import pytest

from build import chunk as chunk_mod
from build import extract_concepts, extract_edges
from build.config import BUILD

CHAPTER = """\
6.1 Issues in Resource Allocation
Resource allocation is the process by which network elements meet demands.
A flow is a sequence of packets between one source and destination.

6.2 Queuing Disciplines
FIFO means the first packet to arrive is the first transmitted.
Tail drop discards arriving packets once the queue is full.
F_i = max(F_{i-1}, A_i) + P_i

6.3 TCP Congestion Control
The congestion window limits unacknowledged data.
AIMD grows the window by one packet per RTT and halves it on loss.

6.4 Advanced Congestion Control
RED drops a packet probabilistically before the queue is full.
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
