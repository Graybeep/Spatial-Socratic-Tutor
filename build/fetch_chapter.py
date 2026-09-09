"""Download the chapter into `BUILD.chapter_html_dir` (CLAUDE.md §4).

    python -m build.fetch_chapter

Runs manually, offline-able, never at runtime. Writes one file per URL in
`BUILD.chapter_urls`, in reading order, then `build.chunk --html` turns them
into `data/chunks.json`.

# Why a script and not a curl line in the README

The URL list is a pipeline input, not a convenience. `extract_edges` builds a
section -> reading-position map and the precedence filter (§4) is entirely
downstream of it, so the ORDER these arrive in is load-bearing. A README
incantation drifts from the config; this cannot.

# Why the chapter is not committed

CC BY 4.0, attribution in data/SOURCE.md. The licence would permit committing
it; we keep the repo to our own derived artefacts anyway and let this script
reproduce the input. `data/chapter_html/` is gitignored.

stdlib only: urllib, not httpx. §1.8 closes the door on new dependencies and
this needs nothing httpx would give it.
"""
from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from pathlib import Path

from build.config import BUILD

#: Sphinx renders these; a default urllib agent gets a 403 from some CDNs.
_UA = "Mozilla/5.0 (compatible; spatial-socratic-tutor build pipeline)"
_TIMEOUT = 45


def filename_for(url: str) -> str:
    """`.../congestion/tcpcc.html` -> `tcpcc.html`, order-prefixed by caller."""
    return url.rstrip("/").rsplit("/", 1)[-1] or "index.html"


def fetch(urls=None, out_dir=None) -> list[Path]:
    urls = list(urls or BUILD.chapter_urls)
    out_dir = Path(out_dir or BUILD.chapter_html_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for i, url in enumerate(urls):
        # The numeric prefix preserves reading order on disk, so a later
        # `--html data/chapter_html/*.html` glob cannot silently reorder the
        # chapter alphabetically.
        dest = out_dir / f"{i:02d}_{filename_for(url)}"
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = resp.read().decode(resp.headers.get_content_charset() or "utf-8")
        except urllib.error.URLError as exc:
            raise SystemExit(f"fetch failed for {url}: {exc}") from exc
        dest.write_text(body, encoding="utf-8")
        print(f"  {dest.name:<28} {len(body):>7} chars  <- {url}")
        written.append(dest)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Download the chapter pages.")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    written = fetch(out_dir=args.out)
    print(f"wrote {len(written)} file(s) to {args.out or BUILD.chapter_html_dir}")
    print("next: python -m build.chunk --html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
