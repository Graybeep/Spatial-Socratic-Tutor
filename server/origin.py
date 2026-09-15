"""Who drove this turn. One string, owned by the server, declared by the caller.

WHY THIS IS NOT THE SAME QUESTION AS `build_info.CODE`

`code` says which *build* wrote a log line, and `eval/leak_monitor.py` refuses to
pool builds because of it. That partitions the log by version. It does not
partition it by **what was sitting at the keyboard**, and for one eval that is
the only distinction that matters.

§9.5 is a hand-read of 30 logged `diagnosis` fields, and it exists to find out
whether the tutor's model of the student bears any relationship to a real one. It
is the only check in §9 that no metric can stand in for. Reading a simulated
student's dialogue for that purpose answers a different question than the one
asked - the simulated students in `eval/adversarial.py` are three scripted
policies, and the tutor's read of them is a read of a policy.

Today `mock` separates them by accident: eval runs under `MOCK_MODE` and a keyed
demo session does not. That accident expires on the day a key lands, which is the
day §9.5 becomes possible - after which an eval run and a person are both
`mock: false`, at the same `code`, in the same file, and §9.5's sample pool is
whatever was run most recently.

DEFAULT IS THE HONEST ONE

`"server"` - a turn served to whoever is on the other end of the HTTP request.
Anything that drives `server.turn` in-process is not that, and has to say so.
A caller that forgets is recorded as `server`, which is the failure that shows up
in the read-through rather than one that hides in it: a simulated dialogue
mislabelled as human gets read and looks wrong, where a human dialogue
mislabelled as simulated is silently dropped from the sample.

This is not configuration (CLAUDE.md §13.1). Nothing here is read from the
environment and "who is driving" is not a knob a human sets before a run - it is
a fact the calling code already knows.
"""
from __future__ import annotations

from contextlib import contextmanager

#: The honest default: an ordinary HTTP turn. See the module docstring.
SERVER = "server"

_origin = SERVER


def current() -> str:
    """What to stamp on a record written right now."""
    return _origin


@contextmanager
def declare(name: str):
    """Declare who is driving, for the duration of the block.

    Restores on the way out, including on an exception - a crashed eval must not
    leave the process stamping every later turn as an eval.

    Not thread-safe, and deliberately not: the server never calls this, and the
    things that do (`eval/`, the test suite) are single-threaded drivers. A
    ContextVar would buy async-correctness for a caller that does not exist and
    would make the default harder to read.
    """
    global _origin
    if not name:
        raise ValueError("an empty origin is worse than the default; name the driver")
    previous = _origin
    _origin = name
    try:
        yield name
    finally:
        _origin = previous
