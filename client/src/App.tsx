import { useEffect, useRef, useState } from "react";
import { Graph } from "./Graph";
import { createSession, loadGraph, streamTurn } from "./api";
import type {
  EdgeRef,
  Expects,
  FrozenGraph,
  GraphState,
  McqOption,
  StudentResponse,
} from "./types";
import "./tokens.css";

/**
 * Dependency direction: App -> Graph -> types, App -> api -> types.
 * Nothing imports upward.
 *
 * The only motion in this app is the dim transition. No entrance animations, no
 * hover transitions - that is what makes the narrowing the memorable moment.
 */

type Line = { who: "tutor" | "you"; text: string };

export default function App() {
  const [graph, setGraph] = useState<FrozenGraph | null>(null);
  const [gs, setGs] = useState<GraphState | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [expects, setExpects] = useState<Expects>("text");
  const [mcq, setMcq] = useState<McqOption[]>([]);
  const [hint, setHint] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [complete, setComplete] = useState(false);

  // Confirm-or-undo (CLAUDE.md §8). A click is a PROPOSAL. Nothing reaches
  // /turn until the student confirms, because a misclick scored as wrong
  // corrupts mastery permanently and there is no undo on the server.
  const [pendingNode, setPendingNode] = useState<string | null>(null);
  const [pendingEdge, setPendingEdge] = useState<EdgeRef | null>(null);

  const session = useRef<string | null>(null);
  const draft = useRef("");
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

  function confirmPending() {
    if (!graph) return;
    if (pendingNode) {
      const label = graph.nodes.find((n) => n.id === pendingNode)?.label ?? pendingNode;
      setLines((l) => [...l, { who: "you", text: label }]);
      void send({ type: "node_click", node_id: pendingNode });
    } else if (pendingEdge) {
      setLines((l) => [...l, { who: "you", text: "that connection" }]);
      void send({ type: "edge_click", edge: pendingEdge });
    }
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
  const hasPending = Boolean(pendingNode || pendingEdge);

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
          busy={busy}
          onNodeClick={(id) => {
            setPendingEdge(null);
            setPendingNode(id);
          }}
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
        <div style={{ flex: 1, overflowY: "auto", padding: "24px 22px" }}>
          {lines.length === 0 && !busy && (
            <p style={{ opacity: 0.6, margin: 0 }}>Getting started.</p>
          )}
          {lines.map((l, i) => (
            <p
              key={i}
              style={{
                margin: "0 0 16px",
                maxWidth: "62ch",
                opacity: l.who === "you" ? 0.62 : 1,
              }}
            >
              {l.text}
            </p>
          ))}
          {busy && <p style={{ opacity: 0.45, margin: 0 }}>Thinking</p>}
          {err && <p style={{ color: "var(--alert)", margin: "8px 0 0" }}>{err}</p>}
        </div>

        <div style={{ borderTop: "1px solid var(--rule)", padding: 18 }}>
          {complete ? (
            <p style={{ margin: 0, opacity: 0.7 }}>That's the whole chapter.</p>
          ) : hasPending ? (
            // Confirm-or-undo. The only gate between a stray click and a
            // permanent mastery penalty.
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button onClick={confirmPending} disabled={busy} style={primaryBtn}>
                Confirm
              </button>
              <button onClick={clearPending} disabled={busy} style={btn}>
                Undo
              </button>
            </div>
          ) : expects === "node_click" ? (
            <Prompt>Click the node you think it is.</Prompt>
          ) : expects === "edge_click" ? (
            <Prompt>Click the connection you mean.</Prompt>
          ) : expects === "mcq" && mcq.length > 0 ? (
            <div style={{ display: "grid", gap: 8 }}>
              {mcq.map((o) => (
                <button key={o.id} onClick={() => answerMcq(o)} disabled={busy} style={btn}>
                  {o.label}
                </button>
              ))}
            </div>
          ) : (
            <input
              onChange={(e) => (draft.current = e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && draft.current.trim() && !busy) {
                  const v = draft.current.trim();
                  draft.current = "";
                  (e.target as HTMLInputElement).value = "";
                  answerText(v);
                }
              }}
              placeholder="Type your answer"
              style={{ ...btn, width: "100%" }}
            />
          )}
        </div>
      </aside>
    </div>
  );
}

const btn: React.CSSProperties = {
  font: "inherit",
  padding: "10px 12px",
  border: "1px solid var(--rule)",
  borderRadius: 4,
  background: "var(--ground)",
  color: "var(--ink)",
  textAlign: "left",
  cursor: "pointer",
};

const primaryBtn: React.CSSProperties = {
  ...btn,
  background: "var(--pending)",
  borderColor: "var(--pending)",
  color: "var(--paper)",
  fontWeight: 600,
};

function Prompt({ children }: { children: React.ReactNode }) {
  return <p style={{ margin: 0, fontSize: 14, opacity: 0.7 }}>{children}</p>;
}
