import type { CSSProperties, ReactNode } from "react";
import type { Expects, GraphNode, McqOption, TurnBudget } from "./types";

/**
 * The rail. Two components, both of them rail furniture, both in this file
 * because CLAUDE.md §2 fixes the client layout at Graph / Chat / api and the
 * node panel is part of the chat surface, not a fourth layer: it is where a
 * node the student pointed at becomes something the dialogue can refer to.
 *
 * Neither component fetches, holds session state, or decides anything. App owns
 * all of that. These render what they are handed and call back.
 *
 * §1.6 / guard layer 0: the ONLY model-authored string that renders here is
 * `utterance`, arriving as a Line with who="tutor". Everything else on screen is
 * server-owned data - node labels and definitions from GET /graph, mcq labels
 * from items.json, integers from turn_budget. That is a whitelist, not a filter:
 * no field reaches this file unless App destructured it deliberately.
 */

export type Line = { who: "tutor" | "you"; text: string };

interface ChatProps {
  lines: Line[];
  busy: boolean;
  error: string | null;
  expects: Expects;
  mcq: McqOption[];
  budget: TurnBudget | null;
  resolvedWithSupport: boolean;
  complete: boolean;
  /** A click is a PROPOSAL until confirmed (CLAUDE.md §8). Non-null = one waiting. */
  pendingLabel: string | null;
  onConfirm: () => void;
  onUndo: () => void;
  onMcq: (option: McqOption) => void;
  onText: (value: string) => void;
}

export function Chat({
  lines,
  busy,
  error,
  expects,
  mcq,
  budget,
  resolvedWithSupport,
  complete,
  pendingLabel,
  onConfirm,
  onUndo,
  onMcq,
  onText,
}: ChatProps) {
  return (
    <>
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
        {error && <p style={{ color: "var(--alert)", margin: "8px 0 0" }}>{error}</p>}
      </div>

      <Budget budget={budget} resolvedWithSupport={resolvedWithSupport} />

      <div style={{ borderTop: "1px solid var(--rule)", padding: 18 }}>
        {complete ? (
          <p style={{ margin: 0, opacity: 0.7 }}>That is the whole chapter.</p>
        ) : pendingLabel !== null ? (
          // The only gate between a stray click and a permanent mastery penalty.
          <div style={{ display: "grid", gap: 10 }}>
            <p style={{ margin: 0, fontSize: 14 }}>
              Answer with <strong>{pendingLabel}</strong>?
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={onConfirm} disabled={busy} style={primaryBtn}>
                Confirm
              </button>
              <button onClick={onUndo} disabled={busy} style={btn}>
                Undo
              </button>
            </div>
          </div>
        ) : expects === "node_click" ? (
          <Hint>Click the node you think it is.</Hint>
        ) : expects === "edge_click" ? (
          <Hint>Click the connection you mean.</Hint>
        ) : expects === "mcq" && mcq.length > 0 ? (
          <div style={{ display: "grid", gap: 8 }}>
            {mcq.map((o) => (
              <button key={o.id} onClick={() => onMcq(o)} disabled={busy} style={btn}>
                {o.label}
              </button>
            ))}
          </div>
        ) : (
          <TextComposer busy={busy} onSubmit={onText} />
        )}
      </div>
    </>
  );
}

/**
 * "The difference between a student who knows help is coming and one who feels
 * trapped" (docs/API.md). The server forces a reveal at max and awards zero
 * mastery; showing the count is what stops that landing as a surprise.
 *
 * Two rules, and the copy carries both:
 *
 * Silent until over halfway. A meter visible from turn 1 of 8 reads as a
 * countdown to failure, which is the opposite of the reassurance it exists for.
 *
 * It names what happens AT zero, not just that zero is coming. "3 turns left"
 * is a countdown at any point in an item; "3 turns, then I show you" is the
 * promise that there is a floor. It also says the shown item will not count,
 * because a student who discovers that only afterwards has learnt that the
 * interface withheld the price - which costs more than the zero does.
 */
function Budget({
  budget,
  resolvedWithSupport,
}: {
  budget: TurnBudget | null;
  resolvedWithSupport: boolean;
}) {
  if (resolvedWithSupport) {
    return (
      <div style={budgetBar}>
        <span style={{ color: "var(--alert)" }}>
          I showed you that one — it does not count towards mastery.
        </span>
      </div>
    );
  }
  if (!budget || budget.max <= 0) return null;
  if (budget.used * 2 <= budget.max) return null;

  const left = Math.max(0, budget.max - budget.used);
  return (
    <div style={budgetBar}>
      <span className="readout">{left}</span>
      <span style={{ opacity: 0.7 }}>
        {left === 1 ? " more turn on this one" : " more turns on this one"}
        , then I show you the answer and we move on. A shown one does not count
        towards mastery.
      </span>
    </div>
  );
}

/**
 * Uncontrolled on purpose. A controlled input re-renders the rail on every
 * keystroke, and the rail's sibling is a 50-node SVG mid-dim-transition.
 */
function TextComposer({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (value: string) => void;
}) {
  return (
    <input
      onKeyDown={(e) => {
        if (e.key !== "Enter" || busy) return;
        const el = e.currentTarget;
        const value = el.value.trim();
        if (!value) return;
        el.value = "";
        onSubmit(value);
      }}
      placeholder="Type your answer"
      aria-label="Type your answer"
      disabled={busy}
      style={{ ...btn, width: "100%", cursor: "text" }}
    />
  );
}

interface NodePanelProps {
  node: GraphNode;
  mastery: number;
  /**
   * True when this node is a click waiting to be confirmed. The panel is then
   * the confirm surface, and shows the node's NAME and nothing else.
   *
   * This is not the leak gate - `panel_locked` is, it comes from the server,
   * and App never renders this component for a read while it is set. This flag
   * only picks which of the two things the panel is: somewhere to read, or
   * somewhere to commit. Naming a node the student just clicked tells them
   * nothing they did not just do; showing its definition would.
   */
  answering: boolean;
  onClose: () => void;
}

export function NodePanel({ node, mastery, answering, onClose }: NodePanelProps) {
  return (
    <section
      style={{
        borderBottom: "1px solid var(--rule)",
        padding: "18px 22px",
        background: "var(--ground)",
      }}
      aria-label={`About ${node.label}`}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: 15, flex: 1 }}>{node.label}</h2>
        <button onClick={onClose} style={plainBtn} aria-label="Close">
          ✕
        </button>
      </div>

      {answering ? (
        <p style={{ margin: "8px 0 0", fontSize: 14, opacity: 0.7 }}>
          Confirm below to answer with this one.
        </p>
      ) : (
        <>
          <p style={{ margin: "8px 0 0", fontSize: 14, maxWidth: "48ch" }}>
            {node.definition}
          </p>
          <p style={{ margin: "10px 0 0", fontSize: 13, opacity: 0.6 }}>
            <span className="readout">{Math.round(mastery * 100)}%</span> mastered
            {node.source_sections.length > 0 &&
              ` · §${node.source_sections.join(", §")}`}
          </p>
        </>
      )}
    </section>
  );
}

const budgetBar: CSSProperties = {
  borderTop: "1px solid var(--rule)",
  padding: "10px 22px",
  fontSize: 13,
};

const btn: CSSProperties = {
  font: "inherit",
  padding: "10px 12px",
  border: "1px solid var(--rule)",
  borderRadius: 4,
  background: "var(--ground)",
  color: "var(--ink)",
  textAlign: "left",
  cursor: "pointer",
};

const primaryBtn: CSSProperties = {
  ...btn,
  background: "var(--pending)",
  borderColor: "var(--pending)",
  color: "var(--paper)",
  fontWeight: 600,
};

const plainBtn: CSSProperties = {
  font: "inherit",
  fontSize: 13,
  border: "none",
  background: "none",
  color: "var(--ink)",
  opacity: 0.5,
  cursor: "pointer",
  padding: 0,
};

function Hint({ children }: { children: ReactNode }) {
  return <p style={{ margin: 0, fontSize: 14, opacity: 0.7 }}>{children}</p>;
}
