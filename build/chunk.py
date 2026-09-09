"""Chapter -> section-level chunks. The swappable seam (CLAUDE.md §4).

    python -m build.fetch_chapter && python -m build.chunk --html
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
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Protocol

from build.config import BUILD

#: A heading like "6.3.1 Additive Increase/Multiplicative Decrease".
#:
#: Deliberately NOT `\d+(\.\d+)*`. That also matches the line
#: "1 unit of data per second. We can see that the ..." - a sentence fragment
#: left by a line break - which then becomes section "1" and injects a fake
#: position into the reading order the whole precedence filter depends on. Real
#: input produced exactly that. A heading is short, has no sentence punctuation,
#: and its number is either dotted or followed by a very short title.
HEADING = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(\S[^.!?]{0,78})\s*$")

#: Chrome from an HTML render, and the page furniture around a chapter.
_NAV = frozenset({
    "view page source", "previous", "next", "contents", "on this page",
    "table of contents", "index", "search", "copyright",
})

#: Private-use glyphs (anchor-link icons) and zero-width junk survive an HTML
#: strip and then crash a Windows console on the first print.
_JUNK = re.compile(r"[-​-‏﻿]")

#: Below this a "chunk" is a heading that was immediately followed by another
#: heading. Real input produced eight of them out of twenty-nine.
MIN_CHUNK_CHARS = 200
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

    Everything after the loop exists because of real input. A rendered chapter
    repeats each heading two or three times (page title, nav, then the real
    one), so the same section number arrives more than once; downstream,
    extract_edges maps section -> reading position in a dict, where a duplicate
    silently overwrites and the precedence filter then works from the wrong
    order. Bodies for a repeated section are therefore MERGED, not appended as
    separate chunks.
    """
    collected: dict[str, dict] = {}
    order: list[str] = []
    section, heading, body = "", "", []

    def flush() -> None:
        text = " ".join(body).strip()
        if not section or not text:
            return
        if section not in collected:
            collected[section] = {"heading": heading, "parts": []}
            order.append(section)
        collected[section]["parts"].append(text)
        # Keep the longest heading seen: the nav copy is usually bare, the page
        # title carries the book name, the real one is in between.
        if len(heading) > len(collected[section]["heading"]):
            collected[section]["heading"] = heading

    for raw in lines:
        line = _JUNK.sub("", raw).strip()
        if not line or line.lower() in _NAV:
            continue
        m = HEADING.match(line)
        if m:
            flush()
            section, heading, body = m.group(1), _JUNK.sub("", m.group(2)).strip(), []
            continue
        if _is_equation(line):
            continue
        body.append(line)

    flush()

    out: list[Chunk] = []
    for sec in order:
        text = " ".join(collected[sec]["parts"]).strip()
        if len(text) < MIN_CHUNK_CHARS:
            # A heading followed straight by another heading. Not a section.
            continue
        out.append(Chunk(
            id=f"chunk_{sec.replace('.', '_')}",
            section=sec,
            heading_path=collected[sec]["heading"],
            text=text,
        ))
    return out


@dataclass
class TextChunker:
    """Plain text, one heading per line. Works today, tested today."""

    path: Path

    def chunks(self) -> list[Chunk]:
        return _sections(self.path.read_text(encoding="utf-8").splitlines())


#: Tags whose text is furniture, never chapter prose.
_HTML_DROP = frozenset({"script", "style", "nav", "header", "footer", "aside"})
#: Tags that end a line. Headings must land on a line of their own or HEADING
#: never matches them and the whole chapter becomes one section.
_HTML_BLOCK = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "div", "section",
    "tr", "blockquote", "figcaption", "dt", "dd",
})


class _HtmlLines(HTMLParser):
    """HTML -> one line per block element, main content only.

    Scoped to <article> / role=main on purpose. The book's rendered pages carry
    the chapter's own heading three times - page title, sidebar nav, then the
    real one - and `_sections` merges repeats rather than letting a duplicate
    section overwrite its reading position. Dropping the chrome here means that
    safety net is never asked to do the work.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._buf: list[str] = []
        self._depth = 0
        self._in_main = False
        self._main_depth: int | None = None
        self._skip_depth: int | None = None

    def handle_starttag(self, tag, attrs) -> None:
        a = dict(attrs)
        self._depth += 1
        if self._skip_depth is None and tag in _HTML_DROP:
            self._skip_depth = self._depth
            return
        if not self._in_main and (tag == "article" or a.get("role") == "main"):
            self._in_main, self._main_depth = True, self._depth
        # The anchor-link icon after every heading. Its glyph is private-use and
        # would otherwise ride into the heading text; _JUNK strips it later, but
        # not before HEADING has already failed to match the line.
        if tag == "a" and "headerlink" in (a.get("class") or ""):
            self._skip_depth = self._depth
            return
        if tag in _HTML_BLOCK:
            self._flush()

    def handle_endtag(self, tag) -> None:
        if self._skip_depth is not None and self._depth <= self._skip_depth:
            self._skip_depth = None
        if tag in _HTML_BLOCK:
            self._flush()
        if self._in_main and self._main_depth is not None and self._depth <= self._main_depth:
            self._in_main = False
        self._depth -= 1

    def handle_data(self, data) -> None:
        if self._skip_depth is None and self._in_main:
            self._buf.append(data)

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf = []
        if text:
            self.lines.append(text)


def html_lines(markup: str) -> list[str]:
    p = _HtmlLines()
    p.feed(markup)
    p._flush()
    return p.lines


@dataclass
class HtmlChunker:
    """The book's rendered HTML. This is what the chapter actually is.

    The source is published as a Sphinx site under CC BY 4.0, not as a PDF
    (data/SOURCE.md), so this - not `PdfChunker` - is the implementation the
    real chapter goes through. It gets the two things `PdfChunker` was written
    to fight *for free*: there is no column order to recover and no running head
    to strip, because the renderer already put the prose in reading order and
    the furniture in tags this drops by name.

    `paths` is ordered and stays ordered. See build/config.py chapter_urls.
    """

    paths: list = field(default_factory=list)

    def chunks(self) -> list[Chunk]:
        lines: list[str] = []
        for path in self.paths:
            lines.extend(html_lines(Path(path).read_text(encoding="utf-8")))
        return _sections(lines)


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
    src.add_argument(
        "--html", type=Path, nargs="*", default=None,
        help="rendered chapter pages, in reading order. No paths = whatever "
             "build.fetch_chapter left in BUILD.chapter_html_dir.",
    )
    ap.add_argument("--out", type=Path, default=BUILD.chunks_path)
    args = ap.parse_args(argv)

    if args.text:
        chunker: Chunker = TextChunker(args.text)
    elif args.html is not None:
        # sorted(), because fetch_chapter order-prefixes the filenames. Reading
        # order is a pipeline input (§4's precedence filter), not cosmetic.
        paths = list(args.html) or sorted(Path(BUILD.chapter_html_dir).glob("*.html"))
        if not paths:
            raise SystemExit(
                f"no chapter HTML in {BUILD.chapter_html_dir}. Run "
                f"`python -m build.fetch_chapter` first."
            )
        chunker = HtmlChunker(paths)
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
        # Real chapter text carries glyphs a cp1252 console cannot encode, and
        # an UnicodeEncodeError in a progress line would fail the whole build.
        heading = c.heading_path[:48].encode("ascii", "replace").decode()
        print(f"  {c.section:<8} {heading:<50} {len(c.text):>6} chars")
    if len(chunks) > 5:
        print(f"  ... and {len(chunks) - 5} more")

    write(chunks, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
