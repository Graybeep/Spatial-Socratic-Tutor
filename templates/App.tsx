import { useEffect, useRef, useState } from "react";
import { Graph } from "./Graph";
import { loadGraph, streamTurn } from "./api";
import type { FrozenGraph, GraphState, McqOption, TurnRequest } from "./types";
import "./tokens.css";

type Line = { who: "tutor" | "you"; text: string };

export default function App() {
  const [graph, setGraph] = useState<FrozenGraph | null>(null);
  const [gs, setGs] = useState<GraphState | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [expects, setExpects] = useState("text");
  const [mcq, setMcq] = useState<McqOption[] | null>(null);
  const [hint, setHint] = useState(0);
  const [thinking, setThinking] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const session = useRef(crypto.randomUUID());
  const draft = useRef("");

  useEffect(() => {
    loadGraph().then(setGraph).catch(() => setErr("Could not load the graph."));
  }, []);

  async function send(req: TurnRequest) {
    setThinking(true);
    setErr(null);
    setMcq(null);
    await streamTurn(
      req,
      // Phase 1. Graph moves here, ~0.8s ahead of any text. This gap is the
      // point — do not hold it back to sync with the utterance.
      (d) => {
        setGs(d);
        setExpects(d.expects);
        setHint(d.hint_level);
        setMcq(d.mcq_options ?? null);
        if (d.resolved_with_support) {
          setLines((l) => [...l, { who: "tutor", text: "Let's walk through this one together." }]);
        }
      },
      (text) => {
        setLines((l) => [...l, { who: "tutor", text }]);
        setThinking(false);
      },
      (m) => {
        setErr(m);
        setThinking(false);
      },
    );
  }

  function answer(kind: TurnRequest["answer"] extends undefined ? never : "text" | "node_click" | "edge_click" | "mcq", value: string, echo: string) {
    setLines((l) => [...l, { who: "you", text: echo }]);
    send({ session_id: session.current, answer: { kind, value } });
  }

  if (!graph) return <div style={{ padding: 32 }}>{err ?? "Loading the graph."}</div>;

  const total = graph.nodes.length;
  const lit = total - (gs?.dimmed_nodes.length ?? 0);

  return (
    <div style={{ display: "grid", gridTemplateColumns: `1fr var(--rail)`, height: "100vh" }}>
      <main style={{ position: "relative", minWidth: 0 }}>
        <Graph
          graph={graph}
          state={gs}
          expects={expects}
          onNodeClick={(id) => answer("node_click", id, graph.nodes.find((n) => n.id === id)?.label ?? id)}
          onEdgeClick={(k) => answer("edge_click", k, "that connection")}
        />

        {/* The research variable, and the demo's punchline. Large, quiet, mono. */}
        <div style={{ position: "absolute", left: 28, bottom: 24 }}>
          <div className="readout" style={{ fontSize: 42, lineHeight: 1 }}>
            {lit}<span style={{ opacity: 0.35 }}> / {total}</span>
          </div>
          <div style={{ fontSize: 13, opacity: 0.65, marginTop: 4 }}>
            {lit === total ? "Nothing ruled out yet" : `${total - lit} ruled out`}
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
          {lines.length === 0 && (
            <p style={{ opacity: 0.6, margin: 0 }}>
              Pick a concept on the map, or say what you'd like to work on.
            </p>
          )}
          {lines.map((l, i) => (
            <p
              key={i}
              style={{
                margin: "0 0 16px",
                maxWidth: "62ch",
                color: l.who === "you" ? "var(--ink)" : "var(--ink)",
                opacity: l.who === "you" ? 0.62 : 1,
              }}
            >
              {l.text}
            </p>
          ))}
          {thinking && <p style={{ opacity: 0.45, margin: 0 }}>Thinking</p>}
          {err && <p style={{ color: "var(--alert)", margin: "8px 0 0" }}>{err}</p>}
        </div>

        <div style={{ borderTop: "1px solid var(--rule)", padding: 18 }}>
          {expects === "node_click" && <Prompt>Click the node you think it is.</Prompt>}
          {expects === "edge_click" && <Prompt>Click the connection you mean.</Prompt>}
          {expects === "mcq" && mcq && (
            <div style={{ display: "grid", gap: 8 }}>
              {mcq.map((o) => (
                <button
                  key={o.id}
                  onClick={() => answer("mcq", o.id, o.label)}
                  disabled={thinking}
                  style={btn}
                >
                  {o.label}
                </button>
              ))}
            </div>
          )}
          {expects === "text" && (
            <div style={{ display: "flex", gap: 8 }}>
              <input
                onChange={(e) => (draft.current = e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && draft.current.trim() && !thinking) {
                    const v = draft.current.trim();
                    draft.current = "";
                    (e.target as HTMLInputElement).value = "";
                    answer("text", v, v);
                  }
                }}
                placeholder="Type your answer"
                style={{ ...btn, flex: 1, textAlign: "left" }}
              />
            </div>
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

function Prompt({ children }: { children: React.ReactNode }) {
  return <p style={{ margin: 0, fontSize: 14, opacity: 0.7 }}>{children}</p>;
}
