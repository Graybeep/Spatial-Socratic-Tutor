import type { FrozenGraph, StreamEvent, TurnRequest } from "./types";

const BASE = import.meta.env.VITE_API ?? "http://localhost:8000";

/**
 * Build against p95, not the mock's p50. The mock fakes 0.78s / 2.20s;
 * a UI that only looks right at the median goes janky on demo day.
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
 * Two-phase turn. onGraphState fires first and MUST render before the
 * utterance arrives — that ordering is the entire perceived-latency argument
 * in CLAUDE.md §5. Never block the graph on the text.
 */
export async function streamTurn(
  req: TurnRequest,
  onGraphState: (e: Extract<StreamEvent, { event: "graph_state" }>["data"]) => void,
  onUtterance: (text: string) => void,
  onError: (msg: string) => void,
): Promise<void> {
  const ctrl = new AbortController();
  const hardStop = setTimeout(
    () => ctrl.abort(),
    BUDGET.graphStateP95Ms + BUDGET.utteranceP95Ms,
  );

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
        if (parsed.event === "graph_state") onGraphState(parsed.data);
        else if (parsed.event === "utterance") onUtterance(parsed.data.utterance);
        else onError(parsed.data.message);
      }
    }
  } catch (err) {
    // Graph may already be on screen. Six canned fallbacks live server-side
    // (CLAUDE.md §5); this is the client-side floor when the socket dies.
    onError(
      err instanceof DOMException && err.name === "AbortError"
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
