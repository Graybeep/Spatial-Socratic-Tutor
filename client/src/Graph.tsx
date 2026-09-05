import { useMemo } from "react";
import type { EdgeRef, FrozenGraph, GraphState } from "./types";

/**
 * Raw SVG, not React Flow. At 50 nodes with frozen coordinates a graph library
 * earns nothing and its default styling fights the dimming channels.
 *
 * TWO INDEPENDENT VISUAL CHANNELS - see tokens.css. mastery -> fill only.
 * narrowing -> stroke weight + opacity + saturation. If they ever mix, a
 * half-mastered lit node and a fully-mastered dim node become the same pixel and
 * the narrowing moment stops reading from the back of the room.
 */

const NODE_W = 132;
const NODE_H = 44;
const R = 4;
const LABEL_MAX = 17;

/** Mastery -> fill. FILL ONLY. Never opacity. */
function masteryFill(m: number): string {
  const stops = [
    [0.0, [201, 207, 205]],
    [0.5, [127, 168, 163]],
    [1.0, [15, 107, 99]],
  ] as const;
  const t = Math.max(0, Math.min(1, m));
  const hi = stops.find((s) => t <= s[0]) ?? stops[2];
  const lo = [...stops].reverse().find((s) => t >= s[0]) ?? stops[0];
  if (hi === lo) return `rgb(${hi[1].join(",")})`;
  const k = (t - lo[0]) / (hi[0] - lo[0]);
  const c = lo[1].map((v, i) => Math.round(v + k * (hi[1][i] - v)));
  return `rgb(${c.join(",")})`;
}

export const edgeKey = (e: EdgeRef) => `${e.from}->${e.to}`;

interface Props {
  graph: FrozenGraph;
  state: GraphState | null;
  expects: string;
  /** Clicked but not yet confirmed. Never scored until the student says so. */
  pendingNode: string | null;
  pendingEdge: EdgeRef | null;
  /** Opened in the rail's node panel. Reading, not answering. */
  inspectedNode: string | null;
  /** Server-owned. No node opens the panel while this is set - see types.ts. */
  panelLocked: boolean;
  busy: boolean;
  onNodeClick: (id: string) => void;
  onNodeInspect: (id: string) => void;
  onEdgeClick: (edge: EdgeRef) => void;
}

export function Graph({
  graph,
  state,
  expects,
  pendingNode,
  pendingEdge,
  inspectedNode,
  panelLocked,
  busy,
  onNodeClick,
  onNodeInspect,
  onEdgeClick,
}: Props) {
  // dimmed_nodes is authoritative. Empty set == no narrowing.
  const dimmed = useMemo(
    () => new Set(state?.dimmed_nodes ?? []),
    [state?.dimmed_nodes],
  );
  const pos = useMemo(
    () => new Map(graph.nodes.map((n) => [n.id, n])),
    [graph.nodes],
  );

  const bounds = useMemo(() => {
    const xs = graph.nodes.map((n) => n.x);
    const ys = graph.nodes.map((n) => n.y);
    const pad = 80;
    return {
      x: Math.min(...xs) - pad,
      y: Math.min(...ys) - pad,
      w: Math.max(...xs) - Math.min(...xs) + NODE_W + pad * 2,
      h: Math.max(...ys) - Math.min(...ys) + NODE_H + pad * 2,
    };
  }, [graph.nodes]);

  const nodeClickable = expects === "node_click" && !busy;
  const edgeClickable = expects === "edge_click" && !busy;
  const pendingEdgeKey = pendingEdge ? edgeKey(pendingEdge) : null;

  // One gesture, two meanings: while the tutor is waiting for a point a click
  // is an ANSWER, otherwise it opens the node panel to read. They cannot both
  // be live, because reading a definition during an item is reading your way to
  // the answer inside the one interaction §9.1 exists to measure.
  //
  // `pointing` decides which gesture the click IS. It does NOT decide whether
  // reading is allowed - `panelLocked` does, it comes from the server, and it
  // holds for the whole item. Gating reading on `expects` alone leaves the hole
  // this closes: answer wrong on purpose, and on the tutor's follow-up turn
  // `expects` is "text" while the narrowing is still on screen.
  const pointing = expects === "node_click" || expects === "edge_click";
  const canInspect = !panelLocked && !busy;

  return (
    <svg
      viewBox={`${bounds.x} ${bounds.y} ${bounds.w} ${bounds.h}`}
      style={{ width: "100%", height: "100%", display: "block" }}
      role="img"
      aria-label={`Concept graph, ${graph.nodes.length - dimmed.size} of ${graph.nodes.length} concepts still in play`}
    >
      {graph.edges.map((e) => {
        const a = pos.get(e.from);
        const b = pos.get(e.to);
        if (!a || !b) return null;
        const key = `${e.from}->${e.to}`;
        const isDim = dimmed.has(e.from) || dimmed.has(e.to);
        const isPending = pendingEdgeKey === key;
        return (
          <line
            key={key}
            x1={a.x + NODE_W / 2}
            y1={a.y + NODE_H}
            x2={b.x + NODE_W / 2}
            y2={b.y}
            stroke={isPending ? "var(--pending)" : "var(--rule)"}
            strokeWidth={isPending ? 4 : e.type === "prereq" ? 1.5 : 1}
            strokeDasharray={e.type === "related" ? "4 4" : undefined}
            opacity={isDim ? "var(--dim-edge-opacity)" : 1}
            style={{
              transition: "opacity var(--dim-ms) ease",
              cursor: edgeClickable && !isDim ? "pointer" : "default",
            }}
            onClick={
              edgeClickable && !isDim
                ? () => onEdgeClick({ from: e.from, to: e.to })
                : undefined
            }
          />
        );
      })}

      {graph.nodes.map((n) => {
        const isDim = dimmed.has(n.id);
        const m = state?.mastery?.[n.id] ?? 0;
        const isCurrent = state?.current_node === n.id;
        const isPending = pendingNode === n.id;
        const isInspected = inspectedNode === n.id && !isPending;
        // Dimmed nodes are ruled out, so they can never be answered. They can
        // still be read between questions - what was excluded is part of what
        // the map is for.
        const answerable = nodeClickable && !isDim;
        const clickable = pointing ? answerable : canInspect;
        return (
          <g
            key={n.id}
            transform={`translate(${n.x} ${n.y})`}
            // Opacity lives on the rect and the text SEPARATELY, not here on
            // the group - dimming the group would force one value on both, and
            // the shape and the label need opposite treatment (see tokens.css).
            style={{
              filter: isDim ? "saturate(var(--dim-saturate))" : "none",
              transition: "filter var(--dim-ms) ease",
              cursor: clickable ? "pointer" : "default",
            }}
            onClick={
              clickable
                ? () => (pointing ? onNodeClick(n.id) : onNodeInspect(n.id))
                : undefined
            }
            tabIndex={clickable ? 0 : -1}
            role={clickable ? "button" : undefined}
            aria-label={clickable ? n.label : undefined}
            onKeyDown={
              clickable
                ? (ev) => {
                    if (ev.key === "Enter" || ev.key === " ") {
                      ev.preventDefault();
                      if (pointing) onNodeClick(n.id);
                      else onNodeInspect(n.id);
                    }
                  }
                : undefined
            }
          >
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={R}
              fill={masteryFill(m)}
              stroke={isPending ? "var(--pending)" : "var(--ink)"}
              strokeWidth={isPending ? 4 : isDim ? "var(--dim-stroke)" : "var(--lit-stroke)"}
              // Holds at ~0.20. This rectangle is the spatial anchor.
              opacity={isDim ? "var(--dim-shape-opacity)" : 1}
              style={{
                transition:
                  "stroke-width var(--dim-ms) ease, opacity var(--dim-ms) ease",
              }}
            />
            {isInspected && (
              <rect
                width={NODE_W + 10}
                height={NODE_H + 10}
                x={-5}
                y={-5}
                rx={R + 2}
                fill="none"
                stroke="var(--ink)"
                strokeWidth={2}
              />
            )}
            {isCurrent && !isPending && !isInspected && (
              <rect
                width={NODE_W + 10}
                height={NODE_H + 10}
                x={-5}
                y={-5}
                rx={R + 2}
                fill="none"
                stroke="var(--ink)"
                strokeWidth={1}
                strokeDasharray="3 3"
              />
            )}
            <text
              x={NODE_W / 2}
              y={NODE_H / 2 + 4}
              textAnchor="middle"
              fontSize={12}
              fontWeight={600}
              fill={m > 0.55 ? "var(--paper)" : "var(--ink)"}
              // Driven near zero independently. The readable text is what leaks.
              opacity={isDim ? "var(--dim-label-opacity)" : 1}
              style={{ transition: "opacity var(--dim-ms) ease" }}
              pointerEvents="none"
            >
              {n.label.length > LABEL_MAX + 1
                ? n.label.slice(0, LABEL_MAX) + "…"
                : n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
