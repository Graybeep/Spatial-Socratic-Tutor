"""Central configuration. CLAUDE.md 1.10 / 13.1: no tunable value is a literal
anywhere else in the codebase.

Read once at import into a frozen object. No module reads os.environ at call time.
Every value has a default that makes the demo run with no setup but an API key.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader. Avoids a dependency for six lines of parsing."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(ROOT / ".env")


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: str) -> Path:
    value = Path(os.environ.get(name, default))
    return value if value.is_absolute() else ROOT / value


@dataclass(frozen=True)
class LLMCallConfig:
    model: str
    max_tokens: int
    temperature: float
    timeout_s: float


@dataclass(frozen=True)
class Config:
    # --- credentials ---------------------------------------------------------
    api_key: str = field(default_factory=lambda: _str("ANTHROPIC_API_KEY", ""))
    base_url: str = field(default_factory=lambda: _str("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))

    # --- the two calls (CLAUDE.md 5) ----------------------------------------
    call1: LLMCallConfig = field(default_factory=lambda: LLMCallConfig(
        model=_str("CALL1_MODEL", "claude-sonnet-5"),
        max_tokens=_int("CALL1_MAX_TOKENS", 300),
        temperature=_float("CALL1_TEMPERATURE", 0.0),
        timeout_s=_float("CALL1_TIMEOUT_S", 10.0),
    ))
    call2: LLMCallConfig = field(default_factory=lambda: LLMCallConfig(
        model=_str("CALL2_MODEL", "claude-sonnet-5"),
        max_tokens=_int("CALL2_MAX_TOKENS", 250),
        temperature=_float("CALL2_TEMPERATURE", 0.7),
        timeout_s=_float("CALL2_TIMEOUT_S", 10.0),
    ))

    # --- paths ---------------------------------------------------------------
    graph_path: Path = field(default_factory=lambda: _path("GRAPH_PATH", "data/graph.json"))
    items_path: Path = field(default_factory=lambda: _path("ITEMS_PATH", "data/items.json"))
    gold_graph_path: Path = field(default_factory=lambda: _path("GOLD_GRAPH_PATH", "data/gold_graph.json"))
    prompts_dir: Path = field(default_factory=lambda: _path("PROMPTS_DIR", "prompts"))
    state_db_path: Path = field(default_factory=lambda: _path("STATE_DB_PATH", "state.db"))
    log_dir: Path = field(default_factory=lambda: _path("LOG_DIR", "logs"))

    # --- server --------------------------------------------------------------
    host: str = field(default_factory=lambda: _str("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int("PORT", 8000))
    cors_origins: str = field(default_factory=lambda: _str("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))

    # --- guards (CLAUDE.md 6) -----------------------------------------------
    hint_max: int = field(default_factory=lambda: _int("HINT_MAX", 4))
    turn_budget: int = field(default_factory=lambda: _int("TURN_BUDGET", 8))
    answer_fuzzy_threshold: float = field(default_factory=lambda: _float("ANSWER_FUZZY_THRESHOLD", 0.9))
    answer_cosine_threshold: float = field(default_factory=lambda: _float("ANSWER_COSINE_THRESHOLD", 0.85))
    short_answer_token_cutoff: int = field(default_factory=lambda: _int("SHORT_ANSWER_TOKEN_CUTOFF", 5))
    retrieval_score_floor: float = field(default_factory=lambda: _float("RETRIEVAL_SCORE_FLOOR", 0.35))

    # --- mastery (CLAUDE.md 7) ----------------------------------------------
    mastery_threshold: float = field(default_factory=lambda: _float("MASTERY_THRESHOLD", 0.6))
    k_start: float = field(default_factory=lambda: _float("K_START", 0.4))
    k_min: float = field(default_factory=lambda: _float("K_MIN", 0.15))
    k_decay: float = field(default_factory=lambda: _float("K_DECAY", 0.15))
    hint_difficulty_slope: float = field(default_factory=lambda: _float("HINT_DIFFICULTY_SLOPE", 0.5))
    prereq_decay: float = field(default_factory=lambda: _float("PREREQ_DECAY", 0.05))
    consecutive_failures_before_backtrack: int = field(
        default_factory=lambda: _int("CONSECUTIVE_FAILURES_BEFORE_BACKTRACK", 2))

    # --- narrowing ladder (CLAUDE.md §9.1, §9.2) -----------------------------
    # THE NARROWING SCHEDULE IS A RESEARCH VARIABLE, NOT A CONSTANT.
    #
    # Candidates left lit at hint level 0,1,2,...  A 0 entry means no narrowing
    # at that level. Eval §9.1 sweeps this: effective leakage as a function of
    # terminal candidate-set size is a curve, and the curve is the result. A
    # single hard-coded ladder would bake one point on that curve into the
    # client and throw the rest away.
    narrow_schedule_raw: str = field(default_factory=lambda: _str("NARROW_SCHEDULE", "0,12,9,7,5"))

    # The floor is set by GUESS PROBABILITY, not by node count. A terminal set of
    # k candidates hands a non-reasoning student a 1/k chance, which is effective
    # leakage under §9.1's own definition. At 0.2 the floor is 5 candidates; at
    # 0.5 it would be 2, which is a coin flip and would lose to the verbal
    # baseline the project is trying to beat.
    max_guess_probability: float = field(default_factory=lambda: _float("MAX_GUESS_PROBABILITY", 0.2))

    # interleaved -> production: alternate visual and verbal, last rung verbal
    # visual_only -> eval arm: every hint narrows, no verbal elimination
    # verbal_only -> eval arm: nothing ever dims; focus/dimmed stay empty
    # none        -> eval arm: NO HINTS AT ALL. The true no-interface baseline.
    #
    # `none` exists because verbal_only is not a no-help condition: a verbal hint
    # still eliminates candidates by name, so a solve rate measured against it
    # includes whatever the verbal channel gave away. Subtracting verbal_only
    # therefore understates the visual channel's marginal contribution - a
    # conservative error, but only `none` measures the student's own competence
    # with nothing added.
    #
    # §9.2 is unrunnable on an interleaved ladder: a verbal hint that follows a
    # visual one is operating on an already-narrowed graph and only has to
    # eliminate the remainder to "match", which measures nothing. The eval arms
    # must run pure.
    ladder_mode: str = field(default_factory=lambda: _str("LADDER_MODE", "interleaved"))

    # --- mock server ---------------------------------------------------------
    # Real Call 1 is ~1s; the mock fakes that gap so the client is built against
    # the true latency profile (CLAUDE.md 5, 8: graph must react before text).
    mock_mode: bool = field(default_factory=lambda: _bool("MOCK_MODE", True))
    mock_call1_delay_s: float = field(default_factory=lambda: _float("MOCK_CALL1_DELAY_S", 0.9))
    mock_call2_delay_s: float = field(default_factory=lambda: _float("MOCK_CALL2_DELAY_S", 1.4))
    mock_seed: int = field(default_factory=lambda: _int("MOCK_SEED", 20260904))

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def candidate_floor(self) -> int:
        """Smallest terminal candidate set the ladder may narrow to.

        A policy bound on how far the interface is willing to narrow. It is not
        a prediction of the solve rate at that size - see the note on
        max_guess_probability, and eval/adversarial.py for the measured number.
        """
        return max(2, math.ceil(1.0 / max(self.max_guess_probability, 1e-9)))

    @property
    def narrow_schedule(self) -> list[int]:
        """Candidates lit per hint level, clamped to the guess-probability floor.

        Index 0 is hint level 0. A 0 entry means no narrowing. The list is padded
        or truncated to hint_max + 1 so indexing by hint level is always safe.
        """
        parsed = []
        for chunk in self.narrow_schedule_raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            value = int(chunk)
            parsed.append(0 if value <= 0 else max(value, self.candidate_floor))

        if not parsed:
            parsed = [0]
        want = self.hint_max + 1
        if len(parsed) < want:
            parsed += [parsed[-1]] * (want - len(parsed))
        return parsed[:want]


CONFIG = Config()
