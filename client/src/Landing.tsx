const previewNodes = [
  [70, 80, "Packet flow", false], [300, 80, "Resources", true],
  [70, 200, "Throughput", false], [300, 200, "Congestion", true],
  [530, 200, "Flow control", false], [70, 320, "Fair queuing", false],
  [300, 320, "TCP window", true], [530, 320, "Feedback", true],
  [190, 440, "Slow start", true], [420, 440, "AIMD", true],
] as const;

export function Brand() {
  return <span className="brand"><span className="brand-mark" aria-hidden="true">S<span>·</span></span><span>spatial<span className="brand-light"> / socratic tutor</span></span></span>;
}

export function Landing({ onStart, error }: { onStart: () => void; error: string | null }) {
  return <div className="landing">
    <nav className="landing-nav"><Brand /><span className="pill">A new way to find your answer</span></nav>
    <main className="landing-main">
      <section className="hero-copy">
        <div className="eyebrow"><span className="status-dot" /> LESS TELLING. MORE THINKING.</div>
        <h1>A little less noise.<br />A lot more <em>understanding.</em></h1>
        <p className="hero-description">Find your way through a map of ideas. When you get stuck, the map narrows, giving you room to think, and a clearer place to look.</p>
        <button className="start-button" onClick={onStart}>Explore the chapter <span aria-hidden="true">↗</span></button>
        <p className="hero-footnote">No account needed · Progress stored on this machine</p>
        {error && <p className="error-message" role="alert">{error}</p>}
        <div className="chapter-card"><span className="chapter-icon" aria-hidden="true">06</span><div><span className="eyebrow">YOUR CHAPTER</span><h3>Congestion Control</h3><p>Computer Networks · Peterson & Davie</p></div><span className="chapter-count">52<br /><small>concepts</small></span></div>
      </section>
      <section className="hero-visual" aria-label="Illustration of a concept map narrowing">
        <div className="preview-top"><span className="eyebrow">A MAP THAT HELPS YOU THINK</span><span className="preview-badge">Visual hints</span></div>
        <svg viewBox="0 0 720 530" role="img" aria-label="Illustrative concept map with six concepts highlighted">
          <g fill="none" stroke="#b9cebf" strokeWidth="2"><path d="M140 126V200M370 126V200M140 246V320M370 246V320M600 246V320M370 366L260 440M370 366L490 440M600 366L490 440M140 126L370 200M370 126L600 200M140 246L370 320" /></g>
          {previewNodes.map(([x,y,label,lit]) => <g key={label} opacity={lit ? 1 : .26}><rect x={x} y={y} width="142" height="46" rx="12" fill={lit ? "#e0eee5" : "#e8ece6"} stroke={lit ? "#2c6352" : "#adbcb2"} strokeWidth={lit ? 2 : 1}/><text x={x+71} y={y+28} textAnchor="middle" fill="#234a3e" fontSize="14" fontWeight="600">{label}</text></g>)}
        </svg>
        <div className="preview-bottom"><div><span className="preview-number">10 <span>→</span> 6</span><p>Fewer possibilities. Your reasoning.</p></div><span className="preview-note">Illustrative preview<br />Your map has 52 concepts</span></div>
      </section>
    </main>
    <section className="how-it-works" aria-label="How it works">
      {[['01','See the connections','A stable map shows how the ideas fit together.'],['02','Make your choice','Point to a concept. Confirm when you are ready.'],['03','Find your way forward','Visual hints narrow the search, one step at a time.']].map(([n,title,body])=><article key={n}><span className="step-number">{n}</span><div><h2>{title}</h2><p>{body}</p></div></article>)}
    </section>
    <footer className="landing-footer"><span>Built for curiosity. Designed for deliberate practice.</span><span>One chapter · A research prototype</span></footer>
  </div>;
}
