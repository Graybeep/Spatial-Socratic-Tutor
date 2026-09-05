# Source

The concept graph in `graph.json` covers **Chapter 6, Congestion Control** of:

> Larry Peterson and Bruce Davie, *Computer Networks: A Systems Approach*,
> <https://book.systemsapproach.org/congestion.html>

Released under [Creative Commons Attribution 4.0 International (CC BY
4.0)](https://creativecommons.org/licenses/by/4.0). Licensing is therefore
clear, and §13.2's "gitignore the source if licensing is unclear" does not
apply — though we commit no copy of the chapter itself, only our own graph of it.

Sections covered: 6.1 (Issues in Resource Allocation), 6.2 (Queuing
Disciplines), 6.3 (TCP Congestion Control), 6.4 (Advanced Congestion Control).
6.5 (Quality of Service) is deliberately excluded: it is a different subject
that happens to share a chapter, and including it would have pushed the graph
past §3's 60-node bound with concepts no item in the bank asks about.

**Node definitions are paraphrases, not quotations.** They were written to be
one sentence, teachable in about five minutes, and uniform in granularity
(§3) — which the chapter's own prose is not, since it explains some ideas over
three paragraphs and others in a clause.

This attribution lives here rather than in `graph.json` because the `Graph`
schema is frozen and forbids extra fields (§3). The schema rejected a `source`
key, correctly.

## Why the graph is hand-authored

§4 permits it: *"if extraction quality is poor by day 3, hand-write graph.json
in a text editor. A hand-authored 40-node graph is a valid input to everything
downstream."* We did not reach day 3 and find poor extraction — we had no
chapter file and no API key, so there was nothing to extract from.

The ordering turned out to be the methodologically better one, and it is worth
stating why rather than presenting it as a rescue.

`gold_graph.json` is a byte-identical copy of `graph.json` at the commit that
froze both, and **it must never be edited again**. It is the hand annotation
that §9.3 scores automated extraction against. Had we extracted first and then
hand-corrected the output, the gold annotation would be a derivative of the very
thing being scored — the annotator anchored by the extractor's output, which is
a known way to inflate a precision/recall figure and one a reviewer who knows
the literature will look for. Annotating first, blind to any extractor, is the
clean version.

So the sequence is deliberate:

1. Hand-author the graph from the chapter's structure. **Done, frozen.**
2. Freeze the same bytes as `gold_graph.json`. **Done.**
3. When a chapter file and key arrive, run extraction over the *same* chapter
   and score it against this frozen gold. §9.3 survives, and the demo never
   depended on extraction working at all.

If step 3 never happens, the demo ships on the curated graph, §9.3 goes into
limitations, and the leakage and identity-leak results — the two stronger
numbers — are untouched.
