"""Demo pre-flight. Fails loudly, one line per check, before a take is wasted.

    python -m server.preflight                 # check, exit 1 on any failure
    python -m server.preflight --expect-mock false
    python -m server.preflight --report        # token ledger summary, no checks
    python -m server.preflight --probe         # add a 1-token live pass/fail

WHY THIS EXISTS
---------------
The recording is one sitting with a hard date, and every way it can go wrong is
silent at the moment it matters:

- A server started days ago is serving code from days ago. `docs/schedule.md`
  already carries a note for whoever runs the projector test saying exactly
  this, because three behavioural changes landed after 2026-09-10 that alter
  what the demo does on screen.
- A `-dirty` tree means the recording cannot be tied to a commit afterwards.
  This project has withdrawn a measurement for precisely that (day 12,
  `77b7e5d-dirty`).
- A carried-over `state.db` opens the demo on a student who is already part way
  through, which is a legitimate thing to record but not an accident to discover
  on camera.
- `MOCK_MODE` is read once at startup, and both settings look identical until
  the tutor says something a template would not.
- The daily token budget is the one that ends a session outright, and it is
  invisible: the provider reports a per-MINUTE remaining figure in response
  headers and nothing at all about the day.

Each check below is a thing that has a definite answer locally, printed whether
it passes or fails, because a pre-flight that only speaks up on failure teaches
nobody what it actually verified.

WHY THE TOKEN CHECK READS A LEDGER AND NOT A HEADER
---------------------------------------------------
The obvious design is to ask the provider. It does not work: Groq's
`x-ratelimit-remaining-tokens` is the per-minute window, and there is no daily
equivalent in the headers. A probe would report a number that refills in sixty
seconds and say nothing about the limit that actually ends the day.

So spend is counted locally. `server/llm.py` appends one line per provider
response to `logs/tokens.jsonl`, and this sums the trailing 24 hours for the
Call 1 model against `TPD_LIMIT`. The ledger starts empty on a machine that has
never made a call, which reads as zero spend - correct, and stated in the output
rather than assumed.

`--probe` is available and is deliberately weak: it sends a 1-token request and
reports only whether credentials and connectivity work. It cannot tell you about
the day's budget and does not claim to.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from server import llm as llm_mod
from server.config import CONFIG

WINDOW_S = 24 * 60 * 60

#: Groq free tier, tokens per minute. Used only to state the pacing floor in
#: `--report`; nothing here enforces it, the retry path in `llm.py` does.
TPM_LIMIT = 8_000


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    #: A check that could not be decided is not a pass. It prints as [warn] and
    #: does not fail the run on its own, because "no ledger yet" is a legitimate
    #: state on a fresh machine and should not block a take.
    undecided: bool = False

    def render(self) -> str:
        tag = "warn" if self.undecided else ("ok" if self.ok else "FAIL")
        return f"[{tag:>4}] {self.name}: {self.detail}"


def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(("git", *args), capture_output=True, text=True,
                             timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def check_clean_main() -> Check:
    """A recording that cannot be tied to a commit is not evidence of anything."""
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    sha = _git("rev-parse", "--short", "HEAD")
    if branch is None or sha is None:
        return Check("build", False, "git is unavailable; cannot identify the build")
    dirty = _git("status", "--porcelain")
    if dirty is None:
        return Check("build", False, "git status failed; cannot identify the build")
    problems = []
    if branch != "main":
        problems.append(f"on branch {branch!r}, not main")
    if dirty:
        problems.append(f"{len(dirty.splitlines())} uncommitted change(s)")
    if problems:
        return Check("build", False, f"{sha}: " + "; ".join(problems))
    return Check("build", True, f"clean main at {sha}")


def check_fresh_state(path: Optional[Path] = None) -> Check:
    """A carried-over state.db opens on a part-way student."""
    path = path or CONFIG.state_db_path
    if not path.exists():
        return Check("state.db", True, f"absent ({path}); a fresh one is created on first session")
    size = path.stat().st_size
    return Check("state.db", False,
                 f"{path} exists ({size} bytes) - delete it, or record deliberately "
                 f"from a returning student")


def check_mock_mode(expected: Optional[bool]) -> Check:
    """`MOCK_MODE` is read once at startup and the two settings look alike."""
    actual = bool(CONFIG.mock_mode)
    if expected is None:
        return Check("MOCK_MODE", False,
                     f"is {str(actual).lower()}, but no expectation was declared - "
                     f"pass --expect-mock true|false so the take is recorded on purpose",
                     undecided=False)
    if actual != expected:
        return Check("MOCK_MODE", False,
                     f"is {str(actual).lower()}, expected {str(expected).lower()}")
    return Check("MOCK_MODE", True, f"{str(actual).lower()} as declared")


def read_ledger(path: Optional[Path] = None) -> list:
    path = path or (CONFIG.log_dir / llm_mod.LEDGER_NAME)
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def window_spend(rows: list, model: str, now: Optional[float] = None) -> int:
    """Tokens spent on `model` in the trailing 24 hours."""
    now = time.time() if now is None else now
    return sum(r.get("total_tokens") or 0
               for r in rows
               if r.get("model") == model and (now - (r.get("ts") or 0)) < WINDOW_S)


def check_token_budget(rows: list, now: Optional[float] = None) -> Check:
    #: A local server has no quota and no daily window, so there is no budget to
    #: be short of. Reported rather than silently skipped: "this check does not
    #: apply" and "this check passed" are different things, and a reader of the
    #: output is entitled to know which one they got.
    if CONFIG.llm_is_local:
        spent = window_spend(rows, CONFIG.call1.model, now=now)
        return Check("tokens", True,
                     f"not applicable: {CONFIG.llm_provider} is local, no daily "
                     f"quota ({spent:,} tokens used in 24h, for information)",
                     undecided=True)
    model = CONFIG.call1.model
    spent = window_spend(rows, model, now=now)
    remaining = CONFIG.tpd_limit - spent
    detail = (f"{spent:,} spent on {model} in 24h; {remaining:,} of "
              f"{CONFIG.tpd_limit:,} left, take budget {CONFIG.take_budget:,}")
    if not rows:
        return Check("tokens", True,
                     f"ledger empty ({CONFIG.log_dir / llm_mod.LEDGER_NAME}) - "
                     f"reads as zero spend; true on a machine that has not called out",
                     undecided=True)
    if remaining < CONFIG.take_budget:
        return Check("tokens", False, detail)
    return Check("tokens", True, detail)


def check_no_recent_eval(rows: list, now: Optional[float] = None) -> Check:
    """`docs/schedule.md` books an eval freeze in the 24h before the recording.

    Decided from the ledger rather than from `turns.jsonl`: an eval run that
    touched the model is exactly a run that spent tokens, and an offline eval
    (`leak_monitor`, `graph_quality`, `distractor_screen`) makes no call and is
    correctly invisible here.
    """
    now = time.time() if now is None else now
    recent = [r for r in rows if (now - (r.get("ts") or 0)) < WINDOW_S]
    if not recent:
        return Check("eval freeze", True, "no model call in the last 24h")
    newest = max(r.get("ts") or 0 for r in recent)
    ago = (now - newest) / 3600.0
    return Check("eval freeze", False,
                 f"{len(recent)} model call(s) in the last 24h, most recent "
                 f"{ago:.1f}h ago")


def probe() -> Check:
    """A 1-token request. Pass/fail on credentials and connectivity only."""
    if CONFIG.mock_mode:
        return Check("probe", True, "skipped: MOCK_MODE is on, no provider to reach",
                     undecided=True)
    if not CONFIG.llm_key:
        return Check("probe", False, f"no key for provider {CONFIG.llm_provider!r}")
    try:
        import httpx

        #: Assembled exactly as `llm._invoke` does, so a probe that passes means
        #: the real call's URL and auth are the ones that work. The body is the
        #: minimum each wire format accepts - no tool, no system prompt.
        path, auth, _build, _extract = llm_mod.provider()
        url = f"{CONFIG.llm_base_url.rstrip('/')}{path}"
        headers = {"content-type": "application/json", **auth(CONFIG.llm_key)}
        body = {
            "model": CONFIG.call1.model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "."}],
        }
        with httpx.Client(timeout=15) as client:
            r = client.post(url, headers=headers, json=body)
        if r.status_code == 200:
            return Check("probe", True, "provider reachable, credentials accepted")
        #: A 429 here is a live key that is rate limited, which is a pass for
        #: what this probe claims to test and emphatically not a budget check.
        if r.status_code == 429:
            return Check("probe", True, "credentials accepted (429 rate limited)")
        return Check("probe", False, f"HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001 - a probe reports, never raises
        return Check("probe", False, f"{type(exc).__name__}: {exc}")


def report(rows: list) -> str:
    """Per-turn token cost from the ledger. For after the rehearsal."""
    if not rows:
        return ("token ledger is empty. Run a take, then this reports what it "
                "cost and TAKE_BUDGET can stop being a guess.")
    model = CONFIG.call1.model
    call1 = [r["total_tokens"] for r in rows
             if r.get("call") == "call1" and r.get("model") == model]
    call2 = [r["total_tokens"] for r in rows if r.get("call") == "call2"]
    turns = min(len(call1), len(call2))
    lines = [f"ledger: {len(rows)} responses, {len(call1)} call1 on {model}, "
             f"{len(call2)} call2"]
    if not turns:
        lines.append("no complete turn (call1 + call2) recorded yet")
        return "\n".join(lines)

    per_turn = [call1[i] + call2[i] for i in range(turns)]
    mean = sum(per_turn) / turns
    worst = max(per_turn)
    lines.append(f"per-turn tokens over {turns} turns: mean {mean:,.0f}, max {worst:,}")
    lines.append(f"takes per day at TPD {CONFIG.tpd_limit:,} and "
                 f"TAKE_BUDGET {CONFIG.take_budget:,}: "
                 f"{CONFIG.tpd_limit // max(CONFIG.take_budget, 1)}")
    #: The per-minute limit paces a take rather than ending it: a turn costing
    #: `mean` tokens cannot be served faster than mean/TPM of a minute.
    lines.append(f"minimum seconds per turn at {TPM_LIMIT:,} TPM: "
                 f"mean {mean / TPM_LIMIT * 60:.1f}s, worst {worst / TPM_LIMIT * 60:.1f}s")
    return "\n".join(lines)


def run(expect_mock: Optional[bool], with_probe: bool = False) -> list:
    rows = read_ledger()
    checks = [
        check_clean_main(),
        check_fresh_state(),
        check_mock_mode(expect_mock),
        check_token_budget(rows),
        check_no_recent_eval(rows),
    ]
    if with_probe:
        checks.append(probe())
    return checks


def _expect_mock(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-mock", default=None,
                        help="true|false - what MOCK_MODE must be for this take")
    parser.add_argument("--probe", action="store_true",
                        help="add a 1-token live request; credentials only, "
                             "it cannot see the daily budget")
    parser.add_argument("--report", action="store_true",
                        help="print token-ledger statistics and run no checks")
    args = parser.parse_args()

    if args.report:
        print(report(read_ledger()))
        return 0

    checks = run(_expect_mock(args.expect_mock), with_probe=args.probe)
    for check in checks:
        print(check.render())
    failed = [c for c in checks if not c.ok and not c.undecided]
    if failed:
        print(f"\nNOT READY: {len(failed)} check(s) failed. Do not record.")
        return 1
    print("\nready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
