"""Generate the MOCK graph.json and items.json fixtures.

NOT part of the real pipeline. CLAUDE.md §4 describes the real build (PDF ->
concepts -> edges -> human correction -> freeze_layout). This script exists only
so the mock server and Person B's client have something schema-valid to render on
day 2, before Person A's chapter graph lands in week 1.

Person A overwrites data/graph.json and data/items.json with the real thing and
deletes this file. Nothing imports it at runtime.

    python -m build.make_mock_data
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (id, label, definition, difficulty, section) grouped into dagre-ish layers.
LAYERS = [
    [
        ("tcp_segment", "TCP Segment", "The unit TCP hands to IP, carrying a sequence number and payload.", 0.1, "3.5.1"),
        ("tcp_reliable_delivery", "Reliable Delivery", "TCP's guarantee that bytes arrive once, in order, despite loss.", 0.15, "3.5.2"),
    ],
    [
        ("tcp_rtt_estimation", "RTT Estimation", "The smoothed round-trip-time sample TCP keeps to set its timeout.", 0.3, "3.5.3"),
        ("tcp_flow_control", "Flow Control", "Rate limiting imposed by the receiver's buffer, not the network.", 0.25, "3.5.5"),
        ("tcp_congestion_window", "Congestion Window", "The sender-side limit cwnd on unacknowledged bytes in flight.", 0.3, "3.7.1"),
    ],
    [
        ("tcp_receive_window", "Receive Window", "The advertised free buffer space the receiver returns in every ACK.", 0.25, "3.5.5"),
        ("tcp_slow_start", "Slow Start", "The phase where cwnd doubles each RTT as the sender probes for capacity.", 0.4, "3.7.1"),
        ("tcp_loss_event", "Loss Event", "A timeout or triple duplicate ACK, which TCP reads as congestion.", 0.35, "3.7.1"),
    ],
    [
        ("tcp_congestion_avoidance", "Congestion Avoidance", "Linear growth of cwnd by one MSS per RTT once past the threshold.", 0.45, "3.7.1"),
        ("tcp_ssthresh", "Slow Start Threshold", "The cwnd value at which the sender switches from doubling to linear growth.", 0.5, "3.7.1"),
        ("tcp_triple_dup_ack", "Triple Duplicate ACK", "Three repeated ACKs for the same byte, signalling an isolated loss.", 0.45, "3.7.1"),
        ("tcp_timeout", "Timeout", "Expiry of the retransmission timer, read as severe congestion.", 0.4, "3.5.3"),
    ],
    [
        ("tcp_aimd", "AIMD", "Additive increase, multiplicative decrease - the shape of TCP's sawtooth.", 0.6, "3.7.2"),
        ("tcp_fast_retransmit", "Fast Retransmit", "Resending the missing segment on the third duplicate ACK, before the timer fires.", 0.55, "3.7.1"),
    ],
    [
        ("tcp_fast_recovery", "Fast Recovery", "Halving cwnd instead of dropping to one after a triple duplicate ACK.", 0.7, "3.7.1"),
        ("tcp_fairness", "TCP Fairness", "The tendency of competing AIMD flows to converge on an equal share.", 0.75, "3.7.3"),
    ],
]

PREREQ_EDGES = [
    ("tcp_segment", "tcp_reliable_delivery"),
    ("tcp_segment", "tcp_congestion_window"),
    ("tcp_reliable_delivery", "tcp_rtt_estimation"),
    ("tcp_reliable_delivery", "tcp_flow_control"),
    ("tcp_flow_control", "tcp_receive_window"),
    ("tcp_congestion_window", "tcp_slow_start"),
    ("tcp_congestion_window", "tcp_loss_event"),
    ("tcp_rtt_estimation", "tcp_timeout"),
    ("tcp_slow_start", "tcp_congestion_avoidance"),
    ("tcp_slow_start", "tcp_ssthresh"),
    ("tcp_loss_event", "tcp_triple_dup_ack"),
    ("tcp_loss_event", "tcp_timeout"),
    ("tcp_congestion_avoidance", "tcp_aimd"),
    ("tcp_ssthresh", "tcp_aimd"),
    ("tcp_triple_dup_ack", "tcp_fast_retransmit"),
    ("tcp_aimd", "tcp_fast_recovery"),
    ("tcp_fast_retransmit", "tcp_fast_recovery"),
    ("tcp_aimd", "tcp_fairness"),
]

RELATED_EDGES = [
    ("tcp_flow_control", "tcp_congestion_window"),
    ("tcp_receive_window", "tcp_congestion_window"),
]

X_SPACING = 260
Y_SPACING = 150
X_MARGIN = 120
Y_MARGIN = 80


def build_graph() -> dict:
    nodes = []
    widest = max(len(layer) for layer in LAYERS)
    for row, layer in enumerate(LAYERS):
        # Centre each layer against the widest one, the way dagre would.
        offset = (widest - len(layer)) * X_SPACING / 2
        for col, (nid, label, definition, difficulty, section) in enumerate(layer):
            nodes.append({
                "id": nid,
                "label": label,
                "definition": definition,
                "source_sections": [section],
                "difficulty": difficulty,
                "x": round(X_MARGIN + offset + col * X_SPACING, 1),
                "y": round(Y_MARGIN + row * Y_SPACING, 1),
            })
    edges = [{"from": a, "to": b, "type": "prereq"} for a, b in PREREQ_EDGES]
    edges += [{"from": a, "to": b, "type": "related"} for a, b in RELATED_EDGES]
    return {
        "version": "1.0",
        "domain": "MOCK_computer_networks_ch3",
        "nodes": nodes,
        "edges": edges,
    }


def build_items(graph: dict) -> dict:
    by_layer = {}
    for row, layer in enumerate(LAYERS):
        for nid, *_ in layer:
            by_layer[nid] = row

    items = []
    n = 0
    for node in graph["nodes"]:
        nid = node["id"]
        # Distractors: siblings in the same layer, then the layer above. Weak by
        # design - eval §9.4 is meant to catch exactly this kind of lazy
        # distractor, and it should flag them on the mock data too.
        siblings = [m["id"] for m in graph["nodes"]
                    if m["id"] != nid and by_layer[m["id"]] == by_layer[nid]]
        nearby = [m["id"] for m in graph["nodes"]
                  if m["id"] != nid and abs(by_layer[m["id"]] - by_layer[nid]) == 1]
        distractors = (siblings + nearby)[:3]

        n += 1
        items.append({
            "id": f"itm_{n:04d}",
            "node_id": nid,
            "type": "node_click",
            "prompt": f"Click the node that matches: {node['definition']}",
            "answer": nid,
            "answer_aliases": [node["label"].lower(), node["label"].lower().replace(" ", "-")],
            "distractors": distractors,
            "difficulty": node["difficulty"],
            "visually_answerable": True,
            "answer_spans": [],
        })

        n += 1
        items.append({
            "id": f"itm_{n:04d}",
            "node_id": nid,
            "type": "mcq",
            "prompt": f"Which concept is described as: {node['definition']}",
            "answer": nid,
            "answer_aliases": [node["label"].lower()],
            "distractors": distractors,
            "difficulty": round(min(1.0, node["difficulty"] + 0.05), 2),
            "visually_answerable": True,
            "answer_spans": [],
        })

    # One edge_click item so the client has to implement that path too.
    # Convention: the answer for an edge_click item is "src->dst".
    n += 1
    items.append({
        "id": f"itm_{n:04d}",
        "node_id": "tcp_fast_recovery",
        "type": "edge_click",
        "prompt": "Click the edge from the phase that halves cwnd to the one it depends on.",
        "answer": "tcp_aimd->tcp_fast_recovery",
        "answer_aliases": ["aimd to fast recovery"],
        "distractors": ["tcp_slow_start", "tcp_timeout", "tcp_fairness"],
        "difficulty": 0.65,
        "visually_answerable": True,
        "answer_spans": [],
    })

    return {"version": "1.0", "domain": graph["domain"], "items": items}


def main() -> None:
    graph = build_graph()
    items = build_items(graph)
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    (data / "graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    (data / "items.json").write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, {len(items['items'])} items")


if __name__ == "__main__":
    main()
