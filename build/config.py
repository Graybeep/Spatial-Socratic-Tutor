"""Build-pipeline configuration. CLAUDE.md §1.10 / §13.1.

The offline pipeline's knobs, in one place: cosine merge threshold, the
co-occurrence window, items per node, the node-count bounds and the layout
geometry. §13.1 names most of these explicitly.

Separate from `server/config.py` on purpose. This is read by `/build` scripts
that run manually and never at runtime (§1.2, §4); the server must never import
it, and nothing here may be read while serving a turn. Sharing one object would
make that boundary invisible and let a build knob drift into request handling.

The env loading is deliberately the server's, imported rather than copied, so a
single `.env` configures both and there is one parser to be wrong.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# _load_dotenv has already run at server.config import time; reuse its helpers
# rather than re-implementing five lines of parsing that could disagree.
from server.config import ROOT, _float, _int, _path, _str  # noqa: F401


@dataclass(frozen=True)
class BuildConfig:
    # --- source ---------------------------------------------------------------
    #: The chapter PDF. Not committed if its licensing is unclear (§13.2).
    source_pdf: object = field(default_factory=lambda: _path("SOURCE_PDF", "data/chapter.pdf"))
    #: Extracted text + heading path, so extraction is re-runnable without PyMuPDF.
    chunks_path: object = field(default_factory=lambda: _path("CHUNKS_PATH", "data/chunks.json"))

    # --- outputs (frozen data, §1.2) -----------------------------------------
    graph_path: object = field(default_factory=lambda: _path("GRAPH_PATH", "data/graph.json"))
    items_path: object = field(default_factory=lambda: _path("ITEMS_PATH", "data/items.json"))
    gold_graph_path: object = field(
        default_factory=lambda: _path("GOLD_GRAPH_PATH", "data/gold_graph.json")
    )

    # --- concept extraction (§4) ---------------------------------------------
    #: Merge two candidate concepts when their embeddings exceed this. A human
    #: confirms every merge; this only decides what gets shown to them.
    merge_cosine: float = field(default_factory=lambda: _float("MERGE_COSINE", 0.88))
    #: Edge CANDIDATES only where A precedes B in the text and the two co-occur
    #: within this many sections. 50 nodes is 2,450 unordered pairs; the
    #: ordering + co-occurrence prior cuts that to roughly 150 LLM calls.
    cooccurrence_window_sections: int = field(
        default_factory=lambda: _int("COOCCURRENCE_WINDOW_SECTIONS", 2)
    )

    # --- item generation (§4) -------------------------------------------------
    items_per_node: int = field(default_factory=lambda: _int("ITEMS_PER_NODE", 5))

    # --- validation bounds (§3) ----------------------------------------------
    #: 40-60 nodes. Below 40 the graph is too thin for narrowing to mean
    #: anything; above 60 no chapter teaches them in one sitting.
    min_nodes: int = field(default_factory=lambda: _int("MIN_NODES", 40))
    max_nodes: int = field(default_factory=lambda: _int("MAX_NODES", 60))

    # --- layout (§1.2, §8) ----------------------------------------------------
    #: Run once, offline, into graph.json. Nodes never move afterwards - a node
    #: that moves on a mastery update costs the student the spatial memory the
    #: whole claim rests on.
    layout_node_w: int = field(default_factory=lambda: _int("LAYOUT_NODE_W", 132))
    layout_node_h: int = field(default_factory=lambda: _int("LAYOUT_NODE_H", 44))
    layout_x_gap: int = field(default_factory=lambda: _int("LAYOUT_X_GAP", 48))
    layout_y_gap: int = field(default_factory=lambda: _int("LAYOUT_Y_GAP", 96))
    layout_origin_x: int = field(default_factory=lambda: _int("LAYOUT_ORIGIN_X", 80))
    layout_origin_y: int = field(default_factory=lambda: _int("LAYOUT_ORIGIN_Y", 80))
    #: Crossing-reduction sweeps. More than a handful buys nothing measurable.
    layout_sweeps: int = field(default_factory=lambda: _int("LAYOUT_SWEEPS", 8))


BUILD = BuildConfig()
