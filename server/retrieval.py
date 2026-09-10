"""Chunk search, gated (CLAUDE.md §5, §6 layer 4, §11).

    search(query) -> Retrieved | None

Loaded once at startup from `BUILD.chunks_path` (`data/chunks.json`), which the
offline pipeline writes and nothing at runtime mutates.

# Read §11 before extending this

    "If week 3 slips, cut retrieval before you cut the tutor loop. One chapter
     fits in context. RAG is architecture theater at this scale — keep it
     because it is in the pitch, drop it without guilt if time goes."

So this file is deliberately small and deliberately boring. It is TF-IDF cosine
over section-level chunks: no embeddings (a dependency, §1.8), no reranking, no
query expansion, no vector store. Fifty concepts in one chapter do not need any
of that, and every hour spent here is an hour not spent on the three numbers in
§9 that the project is actually judged on.

# The corpus landed, and here is how well it is doing

`data/chunks.json` holds 15 section-level chunks over sections 6.1-6.4. Before
it existed `search()` returned None for every query and guard layer 4 turned
that into the tutor saying the chapter does not cover it — the correct behaviour
for an empty corpus rather than a stub, since the failure this file exists to
prevent is answering from parametric knowledge.

Now that it searches something, the number that matters is whether it searches
it WELL, and `build/validate.py` reports that on every run: for how many nodes
does the chunk this returns match the node's own declared `source_sections`?

**43 of 52 (83%).** The nine misses are mostly a length effect — cosine over a
long chunk is diluted by its own vocabulary, so a short section beats the long
one that actually teaches the concept ("Slow Start" is served 6.4 rather than
the 6.3.2 section named after it). BM25, the standard answer to exactly that,
was measured against the same 52 nodes and scored 45. Two nodes at n=52 is
inside the interval, and switching scorers would require recalibrating
RETRIEVAL_SCORE_FLOOR, which was measured (52 in / 12 out). So this stays
TF-IDF, the 83% is reported rather than fixed, and §11's "cut retrieval before
you cut the tutor loop" is why that is the right trade.

# What retrieval is FOR, which is narrower than it sounds

Only two actions ever receive a chunk: `advance` and `explain` (§5's gate
table). `ask`, `hint_visual` and `hint_verbal` get labels and nothing else,
because a chunk explains the concept in fluent, student-ready prose — it leaks
the answer in higher fidelity than any single field would. Retrieval is for the
turns where the tutor has already decided to explain.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from server import guards

log = logging.getLogger("tutor.retrieval")

_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Chunk:
    id: str
    section: str
    heading_path: str
    text: str


@dataclass(frozen=True)
class Retrieved:
    chunk: Chunk
    score: float


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


@lru_cache(maxsize=1)
def _corpus() -> tuple:
    """(chunks, idf). Loaded once; §1.2 — nothing is computed per turn."""
    from build.config import BUILD

    path = BUILD.chunks_path
    if not path.exists():
        log.info("retrieval: no corpus at %s; every query will refuse", path)
        return (), {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    chunks = tuple(
        Chunk(
            id=c["id"],
            section=c.get("section", ""),
            heading_path=c.get("heading_path", ""),
            text=c["text"],
        )
        for c in raw.get("chunks", [])
    )
    if not chunks:
        return (), {}

    seen = Counter()
    for c in chunks:
        seen.update(set(_tokens(c.text)))
    n = len(chunks)
    idf = {t: math.log(1 + n / (1 + df)) for t, df in seen.items()}
    log.info("retrieval: %d chunks loaded from %s", n, path)
    return chunks, idf


def _vector(text: str, idf: dict) -> dict:
    counts = Counter(_tokens(text))
    if not counts:
        return {}
    return {t: (1 + math.log(c)) * idf.get(t, 0.0) for t, c in counts.items()}


def _cosine(a: dict, b: dict) -> float:
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[t] * b[t] for t in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def search(query: str) -> Optional[Retrieved]:
    """Best chunk above the layer-4 floor, or None.

    None means "the chapter does not cover this", and the caller must say so
    rather than answering anyway. Every refusal is counted in guards.STATS and
    written to the log — §6 says to log every occurrence, and the rate is worth
    knowing: a tutor that constantly refuses has a retrieval problem, and one
    that never refuses is probably not gating anything.
    """
    chunks, idf = _corpus()
    if not chunks:
        guards.retrieval_gate(0.0)
        return None

    q = _vector(query, idf)
    best, best_score = None, 0.0
    for chunk in chunks:
        score = _cosine(q, _vector(chunk.text, idf))
        if score > best_score:
            best, best_score = chunk, score

    if best is None or not guards.retrieval_gate(best_score):
        return None
    return Retrieved(chunk=best, score=best_score)


def chunk_for_call2(query: str, answer_spans) -> Optional[str]:
    """A chunk ready to hand to Call 2: masked, then delimited (§5, §6 layer 6).

    Order matters and is not interchangeable. Mask the answer FIRST, so the
    spans still refer to offsets in the original text; delimiting prepends a
    header and would shift every offset by its own length.
    """
    hit = search(query)
    if hit is None:
        return None
    return guards.delimit_chunk(guards.mask_spans(hit.chunk.text, answer_spans or []))


def corpus_size() -> int:
    """For /health, so "retrieval is doing nothing" is visible rather than
    inferred from a tutor that keeps saying the chapter does not cover it."""
    chunks, _ = _corpus()
    return len(chunks)
