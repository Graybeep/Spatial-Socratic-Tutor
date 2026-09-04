import { useEffect, useRef, useState } from "react";
import { Graph } from "./Graph";
import { Chat, NodePanel, type Line } from "./Chat";
import { createSession, loadGraph, streamTurn } from "./api";
import type {
  EdgeRef,
  Expects,
  FrozenGraph,
  GraphState,
  McqOption,
  StudentResponse,
  TurnBudget,
} from "./types";
import "./tokens.css";

/**
 * Dependency direction: App -> Graph -> types, App -> Chat -> types,
 * App -> api -> types. Nothing imports upward, and neither child fetches.
 *
 * App is the only place that knows there is a session, a network, or an order
 * to the two stream phases. Graph and Chat are handed values and call back.
 *
 * The only motion in this app is the dim transition. No entrance animations, no
 * hover transitions - that is what makes the narrowing the memorable moment.
 */

export default function App() {
  const [graph, setGraph] = useState<FrozenGraph | null>(null);
  const [gs, setGs] = useState<GraphState | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [expects, setExpects] = useState<Expects>("text");
  const [mcq, setMcq] = useState<McqOption[]>([]);
  const [hint, setHint] = useState(0);
  const [budget, setBudget] = useState<TurnBudget | null>(null);
  const [resolvedWithSupport, setResolvedWithSupport] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [complete, setComplete] = useState(false);

  // Confirm-or-undo (CLAUDE.md §8). A click is a PROPOSAL. Nothing reaches
  // /turn until the student confirms, because a misclick scored as wrong
  // corrupts mastery permanently and there is no undo on the server.
  const [pendingNode, setPendingNode] = useState<string | null>(null);
  const [pendingEdge, setPendingEdge] = useState<EdgeRef | null>(null);

  // Reading a node, not answering with it. See Graph.tsx on why these two can
  // never be live at the same time.
  const [inspected, setInspected] = useState<string | null>(null);

  const session = useRef<string | null>(null);
  // StrictMode runs mount effects twice in dev. Without this guard that opens
  // two sessions and plays two opening turns, and the transcript shows every
  // tutor line duplicated - which reads as a server bug and is not one.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const [g, sid] = await Promise.all([loadGraph(), createSession()]);
        setGraph(g);
        session.current = sid;
        void send(null);
      } catch {
        setErr("Could not reach the tutor.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function send(response: StudentResponse | null) {
    if (!session.current) return;
    setBusy(true);
    setErr(null);
    setMcq([]);
    setInspected(null);
    clearPending();

    await streamTurn(
      { session_id: session.current, response },
      {
        // Phase 1. The graph moves HERE, ~0.8s ahead of any text, and becomes
        // interactive here too. Do not hold it back to sync with the utterance.
        onGraphState: (p) => {
          setGs(p.graph_state);
          setExpects(p.expects);
          setHint(p.hint_level);
          setMcq(p.mcq_options);
          setBudget(p.turn_budget);
          setResolvedWithSupport(p.resolved_with_support);
          setComplete(p.session_complete);
        },
        onUtterance: (text) => {
          setLines((l) => [...l, { who: "tutor", text }]);
          setBusy(false);
        },
        onError: (m) => {
          setErr(m);
          setBusy(false);
        },
      },
    );
    setBusy(false);
  }

  function clearPending() {
    setPendingNode(null);
    setPendingEdge(null);
  }

  function labelOf(id: string): string {
    return graph?.nodes.find((n) => n.id === id)?.label ?? id;
  }

  function confirmPending() {
    if (pendingNode) {
      setLines((l) => [...l, { who: "you", text: labelOf(pendingNode) }]);
      void send({ type: "node_click", node_id: pendingNode });
    } else if (pendingEdge) {
      setLines((l) => [...l, { who: "you", text: pendingEdgeLabel() }]);
      void send({ type: "edge_click", edge: pendingEdge });
    }
  }

  function pendingEdgeLabel(): string {
    if (!pendingEdge) return "";
    return `${labelOf(pendingEdge.from)} → ${labelOf(pendingEdge.to)}`;
  }

  function answerMcq(option: McqOption) {
    setLines((l) => [...l, { who: "you", text: option.label }]);
    void send({ type: "mcq", choice_id: option.id });
  }

  function answerText(value: string) {
    setLines((l) => [...l, { who: "you", text: value }]);
    void send({ type: "text", text: value });
  }

  if (!graph) {
    return <div style={{ padding: 32 }}>{err ?? "Loading the graph."}</div>;
  }

  const total = graph.nodes.length;
  const lit = total - (gs?.dimmed_nodes.length ?? 0);
  const narrowed = lit < total;

  // A pending node takes over the panel: same surface, but it is now the thing
  // you are about to answer with, so it shows its name and not its definition.
  const panelNodeId = pendingNode ?? inspected;
  const panelNode = panelNodeId
    ? (graph.nodes.find((n) => n.id === panelNodeId) ?? null)
    : null;

  const pendingLabel = pendingNode
    ? labelOf(pendingNode)
    : pendingEdge
      ? pendingEdgeLabel()
      : null;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr var(--rail)",
        height: "100vh",
        overflow: "hidden",
      }}
    >
      {/* minHeight:0 is load-bearing. A grid item's automatic minimum size is
          content-based, and an SVG with width:100% has an intrinsic height from
          its viewBox aspect - so without this the row grows to ~866px at 50
          nodes, the graph runs off the bottom and the readout goes with it.
          Invisible at 16 nodes, obvious at 50. */}
      <main style={{ position: "relative", minWidth: 0, minHeight: 0, overflow: "hidden" }}>
        <Graph
          graph={graph}
          state={gs}
          expects={expects}
          pendingNode={pendingNode}
          pendingEdge={pendingEdge}
          inspectedNode={inspected}
          busy={busy}
          onNodeClick={(id) => {
            setPendingEdge(null);
            setPendingNode(id);
          }}
          onNodeInspect={(id) => setInspected((cur) => (cur === id ? null : id))}
          onEdgeClick={(e) => {
            setPendingNode(null);
            setPendingEdge(e);
          }}
        />

        {/* The research variable, and the demo's punchline. Large, quiet, mono.
            Mono appears exactly here and nowhere else. */}
        <div style={{ position: "absolute", left: 28, bottom: 24 }}>
          <div className="readout" style={{ fontSize: 42, lineHeight: 1 }}>
            {lit}
            <span style={{ opacity: 0.35 }}> / {total}</span>
          </div>
          <div style={{ fontSize: 13, opacity: 0.65, marginTop: 4 }}>
            {narrowed ? `${total - lit} ruled out` : "Nothing ruled out yet"}
            {hint > 0 && ` · hint ${hint} of 4`}
          </div>
        </div>
      </main>

      <aside
        style={{
          background: "var(--paper)",
          borderLeft: "1px solid var(--rule)",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        {panelNode && (
          <NodePanel
            node={panelNode}
            mastery={gs?.mastery?.[panelNode.id] ?? 0}
            answering={pendingNode !== null}
            onClose={() => {
              setInspected(null);
              if (pendingNode) clearPending();
            }}
          />
        )}

        <Chat
          lines={lines}
          busy={busy}
          error={err}
          expects={expects}
          mcq={mcq}
          budget={budget}
          resolvedWithSupport={resolvedWithSupport}
          complete={complete}
          pendingLabel={pendingLabel}
          onConfirm={confirmPending}
          onUndo={clearPending}
          onMcq={answerMcq}
          onText={answerText}
        />
      </aside>
    </div>
  );
}
