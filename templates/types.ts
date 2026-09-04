/**
 * STUB — reconcile against /schemas/*.schema.json before writing feature code.
 * Written from CLAUDE.md §5 and the mock report, not from docs/API.md.
 * Anything marked VERIFY is a guess at a field name.
 */

export type Action =
  | "ask"
  | "hint_visual"
  | "hint_verbal"
  | "advance"
  | "backtrack"
  | "explain";

export type Expects = "text" | "node_click" | "edge_click" | "mcq";

export type LadderMode = "interleaved" | "visual_only" | "verbal_only";

export interface GraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
  difficulty: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  type: "prereq" | "related";
}

/** data/graph.json — loaded once, never mutated. */
export interface FrozenGraph {
  version: string;
  domain: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** ItemPublic — stripped server-side. No prompt, answer, alias or span. */
export interface ItemPublic {
  id: string;
  node_id: string;
  difficulty: number;
  scorable: boolean;
}

export interface McqOption {
  id: string;
  label: string; // the one carve-out to §1.6; server-owned, never model output
}

/**
 * Phase 1 of the stream. Arrives ~0.8s. Render immediately.
 * dimmed_nodes is AUTHORITATIVE — empty means no narrowing.
 * focus_nodes is derived and kept for logging/matched-elimination only.
 */
export interface GraphState {
  focus_nodes: string[];
  dimmed_nodes: string[];
  mastery: Record<string, number>; // node_id -> 0..1
  current_node: string | null;
}

/** Phase 2 of the stream. Arrives ~2.2s p50. Build against p95. */
export interface UtteranceState {
  utterance: string;
}

/** Non-streaming shape, and the merged result of both stream phases. */
export interface TurnResponse extends GraphState, UtteranceState {
  action: Action; // server-decided, post-guard
  hint_level: number; // server counter, 0..4
  expects: Expects;
  item: ItemPublic | null;
  mcq_options?: McqOption[];
  turn_count: number;
  resolved_with_support?: boolean; // turn-budget forced reveal
}

export interface TurnRequest {
  session_id: string;
  answer?: {
    kind: "text" | "node_click" | "edge_click" | "mcq";
    value: string; // node id, edge key, option id, or free text
  };
}

/** Two-phase stream envelope. VERIFY event names against docs/API.md. */
export type StreamEvent =
  | { event: "graph_state"; data: GraphState & { action: Action; hint_level: number; expects: Expects; item: ItemPublic | null; mcq_options?: McqOption[]; turn_count: number } }
  | { event: "utterance"; data: UtteranceState }
  | { event: "error"; data: { message: string } };
