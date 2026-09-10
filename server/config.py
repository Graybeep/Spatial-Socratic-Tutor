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
    """One of the two calls in CLAUDE.md 5.

    NO TEMPERATURE FIELD. Sampling parameters - temperature, top_p, top_k - are
    removed on the Claude 5 models and sending one returns a 400, so a knob here
    would be a knob that breaks the call. Depth is controlled by `effort`
    instead, which is the parameter that replaced it.
    """

    model: str
    max_tokens: int
    #: output_config.effort: low | medium | high | xhigh | max.
    effort: str
    timeout_s: float


@dataclass(frozen=True)
class Config:
    # --- credentials ---------------------------------------------------------
    api_key: str = field(default_factory=lambda: _str("ANTHROPIC_API_KEY", ""))
    base_url: str = field(default_factory=lambda: _str("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))

    # --- the two calls (CLAUDE.md 5) ----------------------------------------
    # Call 1 diagnoses. Its `diagnosis` field is what a human hand-reads thirty of
    # in week 3 (CLAUDE.md 9.5), so it gets the higher effort of the two.
    call1: LLMCallConfig = field(default_factory=lambda: LLMCallConfig(
        model=_str("CALL1_MODEL", "claude-opus-5"),
        max_tokens=_int("CALL1_MAX_TOKENS", 300),
        effort=_str("CALL1_EFFORT", "medium"),
        timeout_s=_float("CALL1_TIMEOUT_S", 10.0),
    ))
    # Call 2 writes ONE SENTENCE from an action, a hint level and some node
    # labels. The split deliberately left it nothing to reason about: it has no
    # answer, no item and no diagnosis. Opus on this path buys nothing and
    # spends seconds of a 4.5s p95 budget, so the default is Haiku and the
    # judgement stays on Call 1, whose diagnosis is hand-read in week 3.
    call2: LLMCallConfig = field(default_factory=lambda: LLMCallConfig(
        model=_str("CALL2_MODEL", "claude-haiku-4-5"),
        max_tokens=_int("CALL2_MAX_TOKENS", 250),
        effort=_str("CALL2_EFFORT", "low"),
        timeout_s=_float("CALL2_TIMEOUT_S", 10.0),
    ))
    #: Retries per call on a transport error or a schema-invalid response.
    #: CLAUDE.md 10: every retry is logged. There are no silent ones.
    llm_max_retries: int = field(default_factory=lambda: _int("LLM_MAX_RETRIES", 1))
    anthropic_version: str = field(
        default_factory=lambda: _str("ANTHROPIC_VERSION", "2023-06-01"))

    # --- paths ---------------------------------------------------------------
    graph_path: Path = field(default_factory=lambda: _path("GRAPH_PATH", "data/graph.json"))
    items_path: Path = field(default_factory=lambda: _path("ITEMS_PATH", "data/items.json"))
    gold_graph_path: Path = field(default_factory=lambda: _path("GOLD_GRAPH_PATH", "data/gold_graph.json"))
    prompts_dir: Path = field(default_factory=lambda: _path("PROMPTS_DIR", "prompts"))
    #: Which canned fallback to use when an action has no file of its own. The
    #: fallback handler is the one path that must never raise, so an unknown
    #: action degrades to this instead of to a FileNotFoundError. Every canned
    #: line is answer-free, so degrading is always safe (§5, §13.1).
    fallback_default_action: str = field(
        default_factory=lambda: _str("FALLBACK_DEFAULT_ACTION", "ask"))
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
    # NOT an embedding cosine. CLAUDE.md 6 specifies
    # cosine(embed(utterance), embed(answer)) > 0.85; embeddings would be a new
    # dependency (1.8) or a third API call on the latency path (5), so the
    # implemented metric is a cosine over token-frequency vectors. Different
    # metric, different calibration - hence a different name and a different
    # default, rather than reusing 0.85 as though it meant the same thing.
    # See server/guards.py and docs/writeup/limitations.md.
    answer_similarity_threshold: float = field(
        default_factory=lambda: _float("ANSWER_SIMILARITY_THRESHOLD", 0.55))
    short_answer_token_cutoff: int = field(default_factory=lambda: _int("SHORT_ANSWER_TOKEN_CUTOFF", 5))
    # CALIBRATED, not chosen. 0.35 was a guess made when data/chunks.json did
    # not exist, and against the real chapter it refused 100% of in-domain
    # queries - the ranking was right the whole time and the gate threw it away.
    # Measured over the 15 real chunks, query = node label + definition:
    #
    #     in-chapter (52 nodes)        min 0.1185   median 0.2094
    #     adjacent networking (8 q)    max 0.0786   <- DNS, BGP, Ethernet, TLS
    #     far out-of-domain (4 q)      max 0.0625
    #
    # 0.10 sits between the two populations. Re-measure it if the corpus or the
    # chunk sizes change: cosine against a 10k-char chunk is length-sensitive,
    # so this number is a property of THIS corpus, not a universal constant.
    retrieval_score_floor: float = field(default_factory=lambda: _float("RETRIEVAL_SCORE_FLOOR", 0.10))

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

    # The floor is set by GUESS PROBABILITY, not by node count: a terminal set of
    # k candidates hands a non-reasoning student a 1/k chance. At 0.2 the floor
    # is 5 candidates; at 0.5 it would be 2, which is a coin flip.
    #
    # WHAT THIS NUMBER IS NOT DERIVED FROM, since the old comment said otherwise.
    # It used to end "...and would lose to the verbal baseline the project is
    # trying to beat", which scoped a load-bearing constant to a visual-beats-
    # verbal comparison we have since withdrawn: on the scored bank the isolated
    # visual channel sits ON the no-hint baseline at zero knowledge (+.000), and
    # the only marginal distinguishable from zero is the interleaved arm's.
    # See docs/writeup/limitations.md.
    #
    # WHAT IT IS. A POLICY BOUND, set before any corrected eval existed, on how
    # far the interface is willing to narrow. It still holds, and it is
    # conservative in a way worth stating plainly: THE SHIPPED LADDER DOES NOT
    # REACH IT. `interleaved` alternates narrowing and verbal rungs, so with
    # NARROW_SCHEDULE=0,12,9,7,5 and an 8-turn budget a real dialogue bottoms
    # out at 9 lit. Only the `visual_only` EVAL arm ever lights 5.
    #
    # So no measurement licenses moving it in either direction: the rungs where
    # it would bind carry n=6 probes. Changing it is a policy decision about the
    # interface, not an inference from a number, and anyone tightening it should
    # re-run 9.1's sweep rather than cite this comment.
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

    # --- eval: distractor screen (CLAUDE.md §9.4) ---------------------------
    # The screen runs in two halves because the item bank has two kinds of
    # option set, and only one of them a simulated student can discriminate.
    #
    #   click items  -> options are NODE IDS. The region filter in
    #                   eval/adversarial.py accepts or rejects each one, so
    #                   selection frequency carries signal. Screened behaviourally.
    #   mcq items    -> options are PROSE. The region filter matches nothing,
    #                   falls through, and the student picks uniformly (measured:
    #                   .245/.253/.253/.249 over 4000 draws). A behavioural screen
    #                   there would flag 100% of items ambiguous and 0% dead, so
    #                   the mcq half is screened STRUCTURALLY instead.
    #
    # Do not "fix" this by giving the student prose reasoning: that needs a model
    # in the loop (§1.3 keeps judgement out of scoring, and it would need a key).
    distractor_screen_trials: int = field(
        default_factory=lambda: _int("DISTRACTOR_SCREEN_TRIALS", 400))
    # Selection rate at or below which a candidate is dead weight: the item is
    # silently (k-1)-choice while the interface presents k.
    distractor_dead_rate: float = field(
        default_factory=lambda: _float("DISTRACTOR_DEAD_RATE", 0.02))
    # A non-key option selected at least this often RELATIVE to the key is
    # competing with it - likely also-correct or ambiguous.
    distractor_ambiguous_ratio: float = field(
        default_factory=lambda: _float("DISTRACTOR_AMBIGUOUS_RATIO", 1.0))
    # Structural (mcq) screen. Key longer than the mean distractor by this factor
    # is the classic test-wiseness tell: a strong student picks the long option
    # without reading it.
    distractor_length_tell_ratio: float = field(
        default_factory=lambda: _float("DISTRACTOR_LENGTH_TELL_RATIO", 1.6))
    # Two options this similar are effectively one option.
    distractor_similarity_ceiling: float = field(
        default_factory=lambda: _float("DISTRACTOR_SIMILARITY_CEILING", 0.7))

    # --- eval: bootstrap (§9.1 error bars) -----------------------------------
    # Resampling unit is the ITEM, not the dialogue. Dialogues are drawn over a
    # bank of ~101 visually-answerable items; resampling dialogues would treat
    # repeated draws on one item as independent evidence and understate the
    # interval badly.
    bootstrap_resamples: int = field(
        default_factory=lambda: _int("BOOTSTRAP_RESAMPLES", 2000))
    bootstrap_confidence: float = field(
        default_factory=lambda: _float("BOOTSTRAP_CONFIDENCE", 0.95))
    bootstrap_seed: int = field(default_factory=lambda: _int("BOOTSTRAP_SEED", 20260908))

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
