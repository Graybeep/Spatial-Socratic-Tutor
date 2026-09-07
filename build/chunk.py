"""Chapter -> section-level chunks. The swappable seam (CLAUDE.md §4).

    python -m build.chunk --pdf data/chapter.pdf
    python -m build.chunk --text data/chapter.txt

Writes `data/chunks.json`: one chunk per section, retaining the heading path.
Runs manually, offline, never at runtime.

# Why this is a seam and not just a function

This is the part of the pipeline most likely to be wrong about real input.
Everything downstream — concept extraction, edge candidates, answer spans,
retrieval — consumes chunks and assumes they are clean and section-aligned. A
hand-written test fixture will be exactly that. PyMuPDF over a real chapter will
not: it produces running heads, page numbers mid-sentence, hyphenated line
breaks, figure captions inlined into body text, and two-column reading order
that interleaves paragraphs.

So `Chunker` is an interface with two implementations, and the pipeline depends
on the interface. When the real chapter lands and the output is a mess, the fix
is confined to one class rather than distributed through four scripts that each
made their own assumption about what a chunk looks like.

# PyMuPDF is imported lazily and on purpose

It is not in requirements.txt. There is no PDF to test it against, so pinning a
dependency we cannot exercise would be pinning a guess — and §1.8 closes the
door on new dependencies at the end of week 2. The import happens inside the
method, so the whole pipeline runs, and is tested, on the text chunker today.

# Equations and tables

§4: "Pick a prose-heavy chapter. Equation and table extraction will eat two days
and buys nothing." Neither implementation attempts either. A line that is mostly
symbols is dropped rather than mangled into a chunk that then poisons retrieval.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Protocol

from build.config import BUILD

#: A heading like "6.3.1 Additive Increase/Multiplicative Decrease".
HEADING = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(\S.*?)\s*$")
#: Operators that mark a line as a candidate formula. See _is_equation.
_SYMBOLS = re.compile(r"[=+\-*/^<>|∑∫≤≥±×÷]")


@dataclass
class Chunk:
    id: str
    section: str
    heading_path: str
    text: str


class Chunker(Protocol):
    def chunks(self) -> list[Chunk]: ...


def _is_equation(line: str) -> bool:
    """Prose is mostly letters; a formula is mostly everything else.

    Counting operators against letters is not enough: `F_i = max(F_{i-1}, A_i)
    + P_i` has eleven letters and three operators and reads as prose to that
    rule, while being exactly the line that must not end up in a chunk. What
    separates them is the density of subscripts, braces and digits, so the test
    is the LETTER RATIO over non-space characters, with an operator required so
    an ordinary short sentence is never dropped.
    """
    dense = [c for c in line if not c.isspace()]
    if not dense or not _SYMBOLS.search(line):
        return False
    letters = sum(c.isalpha() for c in dense)
    return letters / len(dense) < 0.5


def _sections(lines: Iterable[str]) -> list[Chunk]:
    """Split on numbered headings, keeping the heading path.

    Shared by both implementations, because the *sectioning* rule is the same
    whatever produced the lines. Only getting the lines differs.
    """
    out: list[Chunk] = []
    section, heading, body = "", "", []

    def flush() -> None:
        text = " ".join(body).strip()
        if section and text:
            out.append(Chunk(
                id=f"chunk_{section.replace('.', '_')}",
                section=section,
                heading_path=heading,
                text=text,
            ))

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = HEADING.match(line)
        if m:
            flush()
            section, heading, body = m.group(1), m.group(2), []
            continue
        if _is_equation(line):
            continue
        body.append(line)

    flush()
    return out


@dataclass
class TextChunker:
    """Plain text, one heading per line. Works today, tested today."""

    path: Path

    def chunks(self) -> list[Chunk]:
        return _sections(self.path.read_text(encoding="utf-8").splitlines())


@dataclass
class PdfChunker:
    """PyMuPDF. Untested — there is no chapter PDF in the repo yet.

    Deliberately thin. When a real PDF arrives this will produce something
    wrong, and the right response is to fix it here, having looked at the
    output, rather than to have guessed at de-hyphenation and column ordering in
    advance and been confidently wrong in four places.
    """

    path: Path

    def chunks(self) -> list[Chunk]:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover - no PDF to test against
            raise SystemExit(
                "PyMuPDF is not installed and is not in requirements.txt: there "
                "is no chapter PDF to test it against, so it was not pinned "
                "(CLAUDE.md §1.8). `pip install pymupdf`, add it to "
                "requirements.txt in the same commit, and expect to fix "
                "PdfChunker once you have seen what it produces."
            ) from exc

        lines: list[str] = []
        with fitz.open(self.path) as doc:
            for page in doc:
                lines.extend(page.get_text().splitlines())
        return _sections(lines)


def write(chunks: list[Chunk], out: Path) -> None:
    out.write_text(
        json.dumps({"version": "1.0", "chunks": [asdict(c) for c in chunks]}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--pdf", type=Path, default=None)
    src.add_argument("--text", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=BUILD.chunks_path)
    args = ap.parse_args(argv)

    if args.text:
        chunker: Chunker = TextChunker(args.text)
    elif args.pdf:
        chunker = PdfChunker(args.pdf)
    elif BUILD.source_pdf.exists():
        chunker = PdfChunker(BUILD.source_pdf)
    else:
        raise SystemExit(
            f"no source. Pass --text or --pdf, or put a chapter at "
            f"{BUILD.source_pdf}. There is no chapter in the repo: the graph was "
            f"hand-authored (data/SOURCE.md), so nothing downstream needs this "
            f"to run yet."
        )

    chunks = chunker.chunks()
    print(f"{len(chunks)} chunks")
    for c in chunks[:5]:
        print(f"  {c.section:<8} {c.heading_path[:48]:<50} {len(c.text):>6} chars")
    if len(chunks) > 5:
        print(f"  ... and {len(chunks) - 5} more")

    write(chunks, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
