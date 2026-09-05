"""The build pipeline's LLM seam.

Every offline pass that wants a model goes through `complete()`. There are two
implementations behind it: a mock that is deterministic and needs no key, and a
real one that does. The mock is the default, so the whole pipeline runs, and is
tested, on a laptop with no credentials.

WHY A SEAM RATHER THAN CALLING THE API DIRECTLY. The chapter and the API key are
not here yet and may not arrive with slack to spare. Writing the passes against
an interface means they exist, run and are tested now, and the day the key lands
the only change is `BUILD_LLM=real`. Writing them against the API directly would
mean writing them the week they can first be run, which is the week there is no
time.

This is NOT `server/llm.py` and must never become it. That one is the two
hand-written runtime calls of §1.1 and §5, with the answer-isolation rules that
make the whole leak argument work. This one is offline, runs manually, and never
touches a turn. Sharing them would put a build-time convenience one import away
from the runtime call that must not see the answer.

The mock is deliberately not clever. It is not trying to be a small language
model; it produces structurally valid output so the surrounding code - chunking,
prompt assembly, parsing, validation, file writing - is exercised end to end.
What it cannot tell you is whether the prompts are any good, and no amount of
mock sophistication would.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, Protocol


class LLM(Protocol):
    def complete(self, prompt: str, *, schema_hint: str = "") -> str: ...


@dataclass
class MockLLM:
    """Deterministic, offline, keyless.

    Handlers are registered per task so each build pass supplies its own canned
    shape. An unregistered task raises rather than returning something plausible
    - a mock that silently invents output is how a broken pass looks healthy.
    """

    handlers: dict = None

    def __post_init__(self) -> None:
        self.handlers = self.handlers or {}
        self.calls: list[tuple[str, str]] = []

    def register(self, task: str, fn: Callable[[dict], object]) -> None:
        self.handlers[task] = fn

    def run(self, task: str, payload: dict) -> object:
        self.calls.append((task, json.dumps(payload, sort_keys=True)[:200]))
        if task not in self.handlers:
            raise KeyError(
                f"MockLLM has no handler for task {task!r}. Register one; do not "
                f"let the pass fall through to invented output."
            )
        return self.handlers[task](payload)


@dataclass
class RealLLM:
    """Placeholder for the day the key lands.

    Left unimplemented on purpose rather than half-written against an API
    signature nobody has run. It raises with instructions instead of failing
    somewhere less obvious. `server/llm.py` (week 2) is the file that works out
    the httpx call; this one copies whatever that settles on.
    """

    def run(self, task: str, payload: dict) -> object:
        raise NotImplementedError(
            "build.llm.RealLLM is not written yet. The offline passes run under "
            "BUILD_LLM=mock today. Implement this against the same httpx call "
            "server/llm.py settles on, then set BUILD_LLM=real."
        )


def get_llm():
    """Mock unless BUILD_LLM says otherwise. Read once, at call time, on
    purpose: this is a build script that runs manually, not a server holding a
    frozen config for the life of a process."""
    return RealLLM() if os.environ.get("BUILD_LLM") == "real" else MockLLM()
