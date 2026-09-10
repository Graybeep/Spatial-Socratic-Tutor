"""Which build is running. One string, read once at import.

Two consumers, and they are the same question asked of two different artefacts:

    server/turn.py     stamps every logged turn, so `logs/turns.jsonl` can be
                       partitioned by the code that wrote each line rather than
                       pooled across the whole project (eval/leak_monitor.py).

    server/state.py    stamps every session row, so a student's mastery cannot
                       be resumed under logic that did not compute it.

It lives in its own module because `state.py` cannot import `turn.py` - turn
imports state - and because this is not configuration. Nothing here is read from
the environment and nothing here is a knob: CLAUDE.md §13.1 governs values a
human might want to change, and the answer to "which commit is this" is not one
of them.

WHAT THE STAMP DOES AND DOES NOT CATCH

It distinguishes commits. It does NOT distinguish two different uncommitted
working trees, because both stamp as `<sha>-dirty`. That is deliberate: a stamp
that changed on every keystroke would invalidate a session on every edit and
make the guard unusable during development. The consequence is stated rather
than hidden - within one dirty tree, drift is invisible to this check.
"""
from __future__ import annotations

import subprocess

from server.config import ROOT


def code_fingerprint() -> str:
    """`<short sha>`, `<short sha>-dirty`, or "unknown".

    Never raises. A provenance stamp that can fail a turn or refuse a session is
    worse than no stamp: a clone without git, or a source tarball, still has to
    serve the demo.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        )
        rev = out.stdout.strip()
        if not rev:
            return "unknown"
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        )
        return f"{rev}-dirty" if dirty.stdout.strip() else rev
    except Exception:  # noqa: BLE001 - see docstring
        return "unknown"


#: Read once at import, like everything else that must not vary per request.
CODE = code_fingerprint()
