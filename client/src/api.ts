import type {
  FrozenGraph,
  GraphStatePhase,
  StreamEvent,
  TurnRequest,
  TurnResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

/**
 * Build against p95, not the mock's p50. The mock fakes 0.9s / 1.4s; a UI that
 * only looks right at the median goes janky on demo day.
 */
export const BUDGET = {
  graphStateP95Ms: 1500,
  utteranceP95Ms: 4500,
};

export async function loadGraph(): Promise<FrozenGraph> {
  const r = await fetch(`${BASE}/graph`);
  if (!r.ok) throw new Error(`graph load failed: ${r.status}`);
  return r.json();
}

/**
 * The server owns session state, so a client-invented UUID is not a session.
 */
export async function createSession(): Promise<string> {
  const r = await fetch(`${BASE}/session`, { method: "POST" });
  if (!r.ok) throw new Error(`session create failed: ${r.status}`);
  return (await r.json()).session_id;
}

interface StreamHandlers {
  /** Fires first, ~0.8s in. MUST render before the utterance arrives - that
   *  ordering is the entire perceived-latency argument in CLAUDE.md §5. */
  onGraphState: (phase: GraphStatePhase) => void;
  onUtterance: (text: string) => void;
  onDone?: (full: TurnResponse) => void;
  onError: (message: string) => void;
}

export async function streamTurn(req: TurnRequest, h: StreamHandlers): Promise<void> {
  const ctrl = new AbortController();
  // Two separate budgets: the graph has its own deadline because it is allowed
  // to be on screen long before the text is.
  const hardStop = setTimeout(
    () => ctrl.abort(),
    BUDGET.graphStateP95Ms + BUDGET.utteranceP95Ms,
  );
  let sawGraphState = false;

  try {
    const res = await fetch(`${BASE}/turn?stream=true`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: ctrl.signal,
    });
    if (!res.ok || !res.body) throw new Error(`turn failed: ${res.status}`);

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });

      let split: number;
      while ((split = buf.indexOf("\n\n")) !== -1) {
        const frame = buf.slice(0, split);
        buf = buf.slice(split + 2);
        const parsed = parseFrame(frame);
        if (!parsed) continue;
        if (parsed.event === "graph_state") {
          sawGraphState = true;
          h.onGraphState(parsed.data);
        } else if (parsed.event === "utterance") {
          h.onUtterance(parsed.data.utterance);
        } else if (parsed.event === "done") {
          h.onDone?.(parsed.data);
        }
      }
    }
  } catch (err) {
    // If the graph already landed, the student is looking at a narrowed screen
    // with no text. Say so in a way that does not imply the narrowing was wrong.
    // The six canned per-action fallbacks live server-side (CLAUDE.md §5); this
    // is only the floor for when the socket itself dies.
    const timedOut = err instanceof DOMException && err.name === "AbortError";
    h.onError(
      sawGraphState
        ? "I've narrowed the map, but lost my train of thought. Answer from what's lit, or try again."
        : timedOut
          ? "The tutor took too long. Try answering again."
          : "Lost the connection to the tutor.",
    );
  } finally {
    clearTimeout(hardStop);
  }
}

function parseFrame(frame: string): StreamEvent | null {
  let event = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!event || !data) return null;
  try {
    return { event, data: JSON.parse(data) } as StreamEvent;
  } catch {
    return null;
  }
}
