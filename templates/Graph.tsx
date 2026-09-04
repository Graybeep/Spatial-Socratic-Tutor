import { useMemo } from "react";
import type { FrozenGraph, GraphState } from "./types";

const NODE_W = 132;
const NODE_H = 44;
const R = 4;

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

interface Props {
  graph: FrozenGraph;
  state: GraphState | null;
  expects: string;
  onNodeClick: (id: string) => void;
  onEdgeClick: (key: string) => void;
}

export function Graph({ graph, state, expects, onNodeClick, onEdgeClick }: Props) {
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

  const nodeClickable = expects === "node_click";
  const edgeClickable = expects === "edge_click";

  return (
    <svg
      viewBox={`${bounds.x} ${bounds.y} ${bounds.w} ${bounds.h}`}
      style={{ width: "100%", height: "100%", display: "block" }}
      role="img"
      aria-label="Concept graph"
    >
      {graph.edges.map((e) => {
        const a = pos.get(e.from);
        const b = pos.get(e.to);
        if (!a || !b) return null;
        const key = `${e.from}->${e.to}`;
        const isDim = dimmed.has(e.from) || dimmed.has(e.to);
        return (
          <line
            key={key}
            x1={a.x + NODE_W / 2}
            y1={a.y + NODE_H}
            x2={b.x + NODE_W / 2}
            y2={b.y}
            stroke="var(--rule)"
            strokeWidth={e.type === "prereq" ? 1.5 : 1}
            strokeDasharray={e.type === "related" ? "4 4" : undefined}
            opacity={isDim ? "var(--dim-opacity)" : 1}
            style={{
              transition: `opacity var(--dim-ms) ease`,
              cursor: edgeClickable && !isDim ? "pointer" : "default",
            }}
            onClick={edgeClickable && !isDim ? () => onEdgeClick(key) : undefined}
          />
        );
      })}

      {graph.nodes.map((n) => {
        const isDim = dimmed.has(n.id);
        const m = state?.mastery?.[n.id] ?? 0;
        const isCurrent = state?.current_node === n.id;
        const clickable = nodeClickable && !isDim;
        return (
          <g
            key={n.id}
            transform={`translate(${n.x} ${n.y})`}
            // Three simultaneous cues. Opacity alone dies on a projector.
            style={{
              opacity: isDim ? "var(--dim-opacity)" : 1,
              filter: isDim ? "saturate(var(--dim-saturate))" : "none",
              transition: `opacity var(--dim-ms) ease, filter var(--dim-ms) ease`,
              cursor: clickable ? "pointer" : "default",
            }}
            onClick={clickable ? () => onNodeClick(n.id) : undefined}
            tabIndex={clickable ? 0 : -1}
            onKeyDown={
              clickable
                ? (ev) => {
                    if (ev.key === "Enter" || ev.key === " ") onNodeClick(n.id);
                  }
                : undefined
            }
          >
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={R}
              fill={masteryFill(m)}
              stroke="var(--ink)"
              strokeWidth={isDim ? "var(--dim-stroke)" : "var(--lit-stroke)"}
              style={{ transition: `stroke-width var(--dim-ms) ease` }}
            />
            {isCurrent && (
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
            >
              {n.label.length > 18 ? n.label.slice(0, 17) + "…" : n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
