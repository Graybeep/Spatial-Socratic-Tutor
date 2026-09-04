"""Read-only access to the frozen graph and item bank.

CLAUDE.md §1.2: the graph is frozen data. Nothing here computes, mutates or
re-lays-out anything. Loaded once at startup; every method is a lookup.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from server.config import CONFIG
from server.schemas import Graph, Item, ItemBank, Node


class GraphStore:
    def __init__(self, graph: Graph, bank: ItemBank) -> None:
        self.graph = graph
        self.bank = bank

        self._nodes: dict = {n.id: n for n in graph.nodes}
        self._prereqs: dict = defaultdict(list)
        self._dependents: dict = defaultdict(list)
        for e in graph.edges:
            if e.type == "prereq":
                self._prereqs[e.to].append(e.from_)
                self._dependents[e.from_].append(e.to)

        self._items_by_node: dict = defaultdict(list)
        self._items_by_id: dict = {}
        for item in bank.items:
            self._items_by_node[item.node_id].append(item)
            self._items_by_id[item.id] = item

    # --- construction --------------------------------------------------------

    @classmethod
    def load(cls, graph_path: Optional[Path] = None, items_path: Optional[Path] = None) -> "GraphStore":
        graph_path = graph_path or CONFIG.graph_path
        items_path = items_path or CONFIG.items_path
        graph = Graph.model_validate_json(Path(graph_path).read_text(encoding="utf-8"))
        bank = ItemBank.model_validate_json(Path(items_path).read_text(encoding="utf-8"))
        return cls(graph, bank)

    # --- lookups -------------------------------------------------------------

    @property
    def node_ids(self) -> list:
        return [n.id for n in self.graph.nodes]

    def node(self, node_id: str) -> Node:
        return self._nodes[node_id]

    def label(self, node_id: str) -> str:
        """Call 2 receives focus node LABELS, never definitions or chunks
        (CLAUDE.md §5)."""
        node = self._nodes.get(node_id)
        return node.label if node else node_id

    def labels(self, node_ids) -> list:
        return [self.label(n) for n in node_ids]

    def prereqs(self, node_id: str) -> list:
        return list(self._prereqs.get(node_id, []))

    def dependents(self, node_id: str) -> list:
        return list(self._dependents.get(node_id, []))

    def items_for(self, node_id: str) -> list:
        return list(self._items_by_node.get(node_id, []))

    def item(self, item_id: str) -> Item:
        return self._items_by_id[item_id]

    def initial_theta_map(self) -> dict:
        """Every node starts unmastered at theta 0 (mastery 0.5)."""
        return {n.id: 0.0 for n in self.graph.nodes}
