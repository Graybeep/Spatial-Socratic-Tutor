import { useRef, useState } from "react";
import { Graph } from "./Graph";
import { Chat, NodePanel, type Line } from "./Chat";
import { Brand, Landing } from "./Landing";
import { createSession, loadGraph, loadMode, streamTurn } from "./api";
import type {
  EdgeRef,
  Expects,
  FrozenGraph,
  GraphState,
  McqOption,
  SessionStatus,
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
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<boolean | null>(null);
  const [zoom, setZoom] = useState<number | null>(null);
  const activeItem = useRef<string | null>(null);
  const [expects, setExpects] = useState<Expects>("text");
  const [mcq, setMcq] = useState<McqOption[]>([]);
  const [hint, setHint] = useState(0);
  const [budget, setBudget] = useState<TurnBudget | null>(null);
  const [resolvedWithSupport, setResolvedWithSupport] = useState(false);
  // Server-owned, per ITEM not per turn. The client never computes this.
  const [panelLocked, setPanelLocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // WHICH ending, not just whether. `mastered` is the student finishing the
  // graph; `concluded` is the tutor stopping after the support ceiling. They
  // are not the same news and must not read as the same news.
  const [sessionState, setSessionState] = useState<SessionStatus>("active");

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

  // The session no longer opens on mount. A student who lands on 52 lit nodes
  // with no framing cannot place the question they are being asked, so Landing
  // comes first and this runs when they choose to begin. See Landing.tsx.
  const [entered, setEntered] = useState(false);

  async function enter() {
    if (started.current) return;
    started.current = true;
    setErr(null);
    setEntered(true);
    try {
      const [g, sid] = await Promise.all([loadGraph(), createSession()]);
      setGraph(g);
      session.current = sid;
      void loadMode().then(setMode);
      void send(null);
    } catch {
      // Back to Landing rather than a dead screen: the student has somewhere
      // to press again, and the reason is on the surface they pressed from.
      started.current = false;
      setEntered(false);
      setErr("Could not reach the tutor. Check that the backend is running, then try again.");
    }
  }

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
          if (activeItem.current !== (p.item?.id ?? null)) setQuestion("");
          activeItem.current = p.item?.id ?? null;
          setGs(p.graph_state);
          setExpects(p.expects);
          setHint(p.hint_level);
          setMcq(p.mcq_options);
          setBudget(p.turn_budget);
          setResolvedWithSupport(p.resolved_with_support);
          setPanelLocked(p.panel_locked);
          setSessionState(p.session_state);
        },
        onUtterance: (text) => {
          // The server appends the authored question as the last paragraph of
          // the existing whitelisted utterance. No answer fields reach the UI.
          const split = activeItem.current ? text.lastIndexOf("\n\n") : -1;
          if (split >= 0) setQuestion(text.slice(split + 2));
          setLines((l) => [...l, { who: "tutor", text: split >= 0 ? text.slice(0, split) : text }]);
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

  if (!entered) {
    return <Landing onStart={() => void enter()} error={err} />;
  }

  if (!graph) {
    return <div style={{ padding: 32 }}>{err ?? "Loading the graph."}</div>;
  }

  const total = graph.nodes.length;
  const lit = total - (gs?.dimmed_nodes.length ?? 0);
  const narrowed = lit < total;

  // A pending node takes over the panel: same surface, but it is now the thing
  // you are about to answer with, so it shows its name and not its definition.
  // That case survives panel_locked - naming the node the student just clicked
  // tells them nothing they did not just do, and it is where Confirm lives.
  // Reading does not: `inspected` is ignored entirely while locked.
  const panelNodeId = pendingNode ?? (panelLocked ? null : inspected);
  const panelNode = panelNodeId
    ? (graph.nodes.find((n) => n.id === panelNodeId) ?? null)
    : null;

  const pendingLabel = pendingNode
    ? labelOf(pendingNode)
    : pendingEdge
      ? pendingEdgeLabel()
      : null;

  return (
    <div className="study-shell">
      <header className="study-header"><Brand /><div className="study-course"><span>CHAPTER 06</span> Congestion Control</div><span className="mode-badge"><span className="status-dot" />{mode === true ? "Offline demo · scripted tutor" : mode === false ? "AI tutor enabled" : "Local study session"}</span></header>
      <div className="study-body">
      {/* minHeight:0 is load-bearing. A grid item's automatic minimum size is
          content-based, and an SVG with width:100% has an intrinsic height from
          its viewBox aspect - so without this the row grows to ~866px at 50
          nodes, the graph runs off the bottom and the readout goes with it.
          Invisible at 16 nodes, obvious at 50. */}
      <main className="map-panel">
        <div className="map-heading"><div><span className="eyebrow">YOUR LEARNING LANDSCAPE</span><h1>Follow the connections.</h1></div><span className="pill">{total} concepts · fixed map</span></div>
        <div className="map-viewport">
        <div className="map-canvas" style={zoom === null ? undefined : {width: 1400 * zoom, height: 1040 * zoom, minWidth: "100%", minHeight: "100%"}}>
        <Graph
          graph={graph}
          state={gs}
          expects={expects}
          pendingNode={pendingNode}
          pendingEdge={pendingEdge}
          inspectedNode={panelLocked ? null : inspected}
          panelLocked={panelLocked}
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
        </div></div>

        {/* The research variable, and the demo's punchline. Large, quiet, mono.
            Mono appears exactly here and nowhere else. */}
        <div className="map-footer"><div className="candidate-card" aria-live="polite">
          <div className="readout" style={{ fontSize: 34, lineHeight: 1 }}>
            {lit}
            <span style={{ opacity: 0.35 }}> / {total}</span>
          </div>
          <div style={{ fontSize: 13, opacity: 0.65, marginTop: 4 }}>
            {narrowed ? `${total - lit} ruled out` : "Concepts in play"}
            {hint > 0 && ` · hint ${hint} of 4`}
          </div>
        </div><div className="map-legend"><span><i />In play</span><span><i className="legend-dim" />Ruled out</span></div><div className="zoom-controls" aria-label="Map zoom"><button aria-label="Zoom out" onClick={() => setZoom(Math.max(.7, (zoom ?? 1) - .2))}>−</button><button onClick={() => setZoom(null)} aria-label="Fit entire map">Fit map</button><button aria-label="Zoom in" onClick={() => setZoom(Math.min(2, (zoom ?? .8) + .2))}>+</button></div></div>
      </main>

      <aside className="tutor-panel">
        <div className="tutor-heading"><span className="tutor-avatar" aria-hidden="true">✦</span><div><h2>Your thinking partner</h2><p>Take a moment. Make a connection.</p></div></div>
        {activeItem.current && <section className="question-card" aria-live="polite"><span className="eyebrow">THE QUESTION</span><p>{question || "Preparing your next question…"}</p><span className="question-instruction">{expects === "edge_click" ? "Select a connection on the map" : expects === "mcq" ? "Choose an option below" : "Select a concept on the map"}</span></section>}
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
          sessionState={sessionState}
          pendingLabel={pendingLabel}
          onConfirm={confirmPending}
          onUndo={clearPending}
          onMcq={answerMcq}
          onText={answerText}
        />
      </aside>
      </div>
    </div>
  );
}
