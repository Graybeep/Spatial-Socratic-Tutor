/**
 * The screen before the session. Nothing here talks to the server.
 *
 * WHY IT EXISTS
 * -------------
 * The app used to open straight onto 52 lit nodes. A student who has not read
 * the report has no idea what the map is, that a click is an answer, or that
 * getting it wrong is what makes the map do its work - so the first thing the
 * interface did was ask a question its user could not place.
 *
 * WHAT IT DELIBERATELY DOES NOT DO
 * --------------------------------
 * It does not preview the narrowing. App.tsx sets the rule this follows: "The
 * only motion in this app is the dim transition. No entrance animations, no
 * hover transitions - that is what makes the narrowing the memorable moment."
 * An animated 52 -> 12 demo here would spend that moment on a teaser, and the
 * student would meet the real one already knowing the trick. So the narrowing
 * is described in one line of plain language and shown for the first time when
 * it actually happens, on their own wrong answer.
 *
 * It also uses no jargon the tutor does not use: no "nodes", no "hint ladder",
 * no "narrowing schedule". Concepts, clicking, and the map getting smaller.
 */

const STEPS: Array<{ n: string; head: string; body: string }> = [
  {
    n: "1",
    head: "You get a map",
    body: "52 concepts from one networking chapter, with arrows for what you need to know first. It never moves, so you can learn where things are.",
  },
  {
    n: "2",
    head: "You answer by pointing",
    body: "Click the concept you think it is, then confirm. Nothing is submitted until you do — a stray click costs you nothing.",
  },
  {
    n: "3",
    head: "Stuck? The map shrinks",
    body: "Get it wrong and the concepts that cannot be the answer fade out. The search gets smaller instead of the hint getting louder.",
  },
];

export function Landing({ onStart, error }: { onStart: () => void; error: string | null }) {
  return (
    <div
      style={{
        height: "100vh",
        overflowY: "auto",
        display: "grid",
        placeItems: "center",
        padding: "32px 20px",
        // A single soft wash off the mastery ramp: enough to read as a front
        // door rather than a form, without introducing a second palette.
        background:
          "radial-gradient(1100px 620px at 12% -10%, rgba(15,107,99,.10), transparent 62%), " +
          "radial-gradient(900px 520px at 100% 108%, rgba(127,168,163,.16), transparent 60%), " +
          "var(--ground)",
      }}
    >
      <main style={{ width: "100%", maxWidth: 760 }}>
        <p
          style={{
            margin: "0 0 14px",
            fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
            fontSize: 11,
            letterSpacing: ".14em",
            textTransform: "uppercase",
            color: "var(--m-100)",
          }}
        >
          Computer Networks · Congestion Control
        </p>

        <h1
          style={{
            margin: "0 0 18px",
            fontSize: "clamp(30px, 5.4vw, 46px)",
            lineHeight: 1.08,
            letterSpacing: "-.025em",
            fontWeight: 600,
            textWrap: "balance",
          }}
        >
          A tutor that helps by showing less
        </h1>

        <p
          style={{
            margin: "0 0 30px",
            fontSize: 17,
            lineHeight: 1.6,
            maxWidth: "54ch",
            color: "#41474a",
          }}
        >
          Most tutors help by saying more, and every extra sentence is another place
          the answer can slip out. This one dims the map instead. When you are stuck,
          the concepts that cannot be the answer fade — and nobody says a word.
        </p>

        <ol
          style={{
            listStyle: "none",
            margin: "0 0 30px",
            padding: 0,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
            gap: 1,
            background: "var(--rule)",
            border: "1px solid var(--rule)",
            borderRadius: 10,
            overflow: "hidden",
          }}
        >
          {STEPS.map((s) => (
            <li key={s.n} style={{ background: "var(--paper)", padding: "18px 18px 20px" }}>
              <div
                style={{
                  fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
                  fontSize: 11,
                  color: "var(--m-100)",
                  letterSpacing: ".12em",
                  marginBottom: 8,
                }}
              >
                {s.n.padStart(2, "0")}
              </div>
              <h2 style={{ margin: "0 0 6px", fontSize: 15.5, fontWeight: 600 }}>{s.head}</h2>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: "#41474a" }}>
                {s.body}
              </p>
            </li>
          ))}
        </ol>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center" }}>
          <button
            type="button"
            onClick={onStart}
            style={{
              font: "inherit",
              fontSize: 16,
              fontWeight: 600,
              color: "var(--paper)",
              background: "var(--m-100)",
              border: "1px solid var(--m-100)",
              borderRadius: 8,
              padding: "13px 26px",
              cursor: "pointer",
            }}
          >
            Start learning
          </button>
          <span style={{ fontSize: 13.5, color: "#5b6265" }}>
            No account, no sign-in. Your progress stays on this machine.
          </span>
        </div>

        {error ? (
          <p style={{ marginTop: 18, color: "var(--alert)", fontSize: 14 }}>{error}</p>
        ) : null}
      </main>
    </div>
  );
}
