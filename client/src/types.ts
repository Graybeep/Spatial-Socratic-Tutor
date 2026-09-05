/**
 * RECONCILED against /schemas/*.schema.json and server/main.py.
 * Supersedes templates/types.ts, which was a stub written from CLAUDE.md §5.
 *
 * Six things the stub guessed differently from the server. Listed because the
 * whole point of freezing the schemas was to make these findable:
 *
 *   1. Request field is `response`, not `answer`, and it is a discriminated
 *      object ({type, node_id | edge | choice_id | text}), not {kind, value}.
 *      Unknown fields are rejected with 422 - every model is extra="forbid".
 *   2. Edges are {from, to} objects. There is no "a->b" key on the wire; that
 *      form exists only inside items.json.
 *   3. `turn_count` does not exist. There is `turn_id` (monotonic per session)
 *      and `turn_budget: {used, max}` (per item).
 *   4. The stream ends with a `done` event carrying the full TurnResponse.
 *      There is no `error` event - transport failure surfaces as a dead socket,
 *      which api.ts turns into a client-side fallback.
 *   5. GraphState has `focus_edges`, which the stub omitted.
 *   6. `session_id` comes from POST /session. The server owns session state, so
 *      a client-invented UUID is not a session.
 */

export type Action =
  | "ask"
  | "hint_visual"
  | "hint_verbal"
  | "advance"
  | "backtrack"
  | "explain";

export type Expects = "text" | "node_click" | "edge_click" | "mcq";

/** Server-side eval knob. The client never sets it; it only has to survive
 *  verbal_only, where nothing ever dims. */
export type LadderMode = "interleaved" | "visual_only" | "verbal_only";

export interface GraphNode {
  id: string;
  label: string;
  definition: string;
  source_sections: string[];
  difficulty: number;
  x: number;
  y: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  type: "prereq" | "related";
}

/** GET /graph. Fetched once. Never mutated, never re-laid-out (CLAUDE.md §1.2). */
export interface FrozenGraph {
  version: string;
  domain: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** ItemPublic - stripped server-side. No prompt, answer, alias, span or distractor.
 *
 *  NO `node_id`, and it must not come back. For a node_click or mcq item the
 *  answer IS the item's node, so shipping node_id hands over the answer in the
 *  clear (it held for 204 of the 250 fixture items). This type carried it until
 *  the server dropped it; the field was never populated after that, so any
 *  client code reading it was reading `undefined`.
 *  `graph_state.current_node` is null for the same reason while such an item is
 *  open - see docs/API.md, "What the client must never infer". */
export interface ItemPublic {
  id: string;
  difficulty: number;
  scorable: boolean;
}

export interface McqOption {
  id: string;
  /** The one carve-out to §1.6: server-owned node label, never model output. */
  label: string;
}

export interface EdgeRef {
  from: string;
  to: string;
}

export interface TurnBudget {
  used: number;
  max: number;
}

/**
 * dimmed_nodes is AUTHORITATIVE. An empty dimmed set means no narrowing, full
 * stop - it does not distinguish "hint level 0" from "this item is not on the
 * graph", and the client does not need it to. focus_nodes is derived and exists
 * for logging and eval §9.2; render from dimmed_nodes.
 */
export interface GraphState {
  current_node: string | null;
  focus_nodes: string[];
  focus_edges: EdgeRef[];
  dimmed_nodes: string[];
  /** node_id -> 0..1. Drives FILL ONLY. Never opacity, never position. */
  mastery: Record<string, number>;
}

/** Everything decided before Call 2 runs. Arrives ~0.8s ahead of the utterance.
 *  Carries enough to make the graph INTERACTIVE, not just repainted. */
export interface GraphStatePhase {
  session_id: string;
  turn_id: number;
  action: Action;
  hint_level: number;
  expects: Expects;
  item: ItemPublic | null;
  mcq_options: McqOption[];
  turn_budget: TurnBudget;
  resolved_with_support: boolean;
  session_complete: boolean;
  /** See TurnResponse. Arrives in phase 1 because the gate has to be live the
   *  moment the graph becomes interactive. */
  panel_locked: boolean;
  graph_state: GraphState;
}

/** POST /turn (non-streaming), and the `done` event of the stream. */
export interface TurnResponse {
  session_id: string;
  turn_id: number;
  schema_version: string;
  utterance: string;
  action: Action;
  hint_level: number;
  expects: Expects;
  mcq_options: McqOption[];
  graph_state: GraphState;
  item: ItemPublic | null;
  turn_budget: TurnBudget;
  resolved_with_support: boolean;
  session_complete: boolean;
  /**
   * True while an item whose answer is a node is open. The node panel must not
   * open on ANY node while it is set.
   *
   * DO NOT derive this from `expects`. A per-turn gate re-opens the panel the
   * moment the tutor stops waiting for a click - answer wrong on purpose, take
   * the follow-up, and the panel is live again with the narrowing still on
   * screen. It is a property of the item, so the server sends it and it holds
   * for every turn the item is open.
   */
  panel_locked: boolean;
}

/** What the student did. `type` must match the `expects` last received. */
export type StudentResponse =
  | { type: "text"; text: string }
  | { type: "node_click"; node_id: string }
  | { type: "edge_click"; edge: EdgeRef }
  | { type: "mcq"; choice_id: string };

export interface TurnRequest {
  session_id: string;
  response: StudentResponse | null;
}

/** SSE envelope. Event names verified against server/main.py::_sse. */
export type StreamEvent =
  | { event: "graph_state"; data: GraphStatePhase }
  | { event: "utterance"; data: { utterance: string } }
  | { event: "done"; data: TurnResponse };
