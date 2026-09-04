"""FROZEN SCHEMAS. CLAUDE.md §3 and §5.

Frozen on day 2. This module is the contract between Person A (content/graph/
scoring) and Person B (interface/tutor loop). Neither edits the other's layer;
this file is what they agree on instead (CLAUDE.md §1.9).

Changing anything here after day 2 costs both people a day.
tests/test_schemas_frozen.py snapshots every model below to schemas/*.schema.json
and fails on any drift, so a change is always deliberate and always visible in
review.

Three groups:
  1. DATA FILES     - graph.json, items.json            (CLAUDE.md §3)
  2. LLM BOUNDARY   - Call 1 decision, Call 2 utterance (CLAUDE.md §5)
  3. WIRE           - POST /turn request and response
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"

StudentState = Literal["on_track", "confused_prereq", "stuck", "correct", "guessing"]
Action = Literal["ask", "hint_visual", "hint_verbal", "advance", "backtrack", "explain"]
Expects = Literal["text", "node_click", "edge_click", "mcq"]
ItemType = Literal["node_click", "edge_click", "mcq"]
EdgeType = Literal["prereq", "related"]

#: Items answered by a click are the only ones scorable without an LLM.
#: CLAUDE.md §1.4: free text teaches, it never scores.
SCORABLE_EXPECTS: frozenset = frozenset({"node_click", "edge_click", "mcq"})


class Strict(BaseModel):
    """Reject unknown fields everywhere. An unexpected key is a contract breach,
    not something to drop silently - especially on the LLM boundary, where a
    hallucinated extra field is exactly what the guards exist to catch."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# 1. DATA FILES (CLAUDE.md §3) - frozen, built offline, committed
# ---------------------------------------------------------------------------


class Node(Strict):
    id: str
    label: str
    definition: str = Field(description="one sentence, from source")
    source_sections: list[str] = Field(default_factory=list)
    difficulty: float = Field(ge=0.0, le=1.0)
    # Layout is frozen into the file. CLAUDE.md §1.2 and §8: nodes never move and
    # nothing re-runs dagre at runtime.
    x: float
    y: float


class Edge(Strict):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    type: EdgeType


class Graph(Strict):
    version: str
    domain: str
    nodes: list[Node]
    edges: list[Edge]


class Item(Strict):
    """One item from the bank. NEVER serialised to the client - see ItemPublic.

    answer, answer_aliases, answer_spans and distractors are the leak surface.
    They exist for Call 1 (CLAUDE.md §5), for masking, and for deterministic
    scoring. They must not cross the wire.
    """

    id: str
    node_id: str
    type: ItemType
    prompt: str
    answer: str
    answer_aliases: list[str] = Field(default_factory=list)
    distractors: list[str] = Field(default_factory=list)
    difficulty: float = Field(ge=0.0, le=1.0)
    # CLAUDE.md §3: true only if the answer is a node or edge ON the graph.
    # The matched-hint eval (§9.2) runs on the true subset only.
    visually_answerable: bool
    # Character offsets into the source chunk, for masking on advance/explain.
    answer_spans: list[tuple[int, int]] = Field(default_factory=list)


class ItemBank(Strict):
    version: str
    domain: str
    items: list[Item]


# ---------------------------------------------------------------------------
# 2. LLM BOUNDARY (CLAUDE.md §5)
# ---------------------------------------------------------------------------


class Call1Decision(Strict):
    """Call 1 output: diagnosis and decision.

    Call 1 sees the answer. Its output is logged in full and never rendered.

    There is deliberately NO `answer_known` field. Call 1 reads the answer from
    items.json; restating it only puts the answer into the generation stream for
    zero gain. CLAUDE.md §5 says do not add it back - extra="forbid" means a model
    that emits it anyway fails the parse loudly instead of succeeding quietly.

    `correct` is a boolean and nothing else. CLAUDE.md §1.3: the model may not emit
    a score, a percentage or a mastery estimate. There is no field here to put one
    in.

    Everything the model asks for is prefixed `requested_` (CLAUDE.md §1.7). The
    server decides; these are requests.
    """

    student_state: StudentState
    diagnosis: str = Field(description="internal reasoning; never rendered, always logged")
    correct: bool
    requested_action: Action
    requested_hint_level: int = Field(ge=0)
    focus_nodes: list[str] = Field(default_factory=list)
    expects: Expects


class Call2Utterance(Strict):
    """Call 2 output. One field. That is the whole point of the split."""

    utterance: str


# ---------------------------------------------------------------------------
# 3. WIRE - POST /turn
# ---------------------------------------------------------------------------


class EdgeRef(Strict):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    from_: str = Field(alias="from")
    to: str


class StudentResponse(Strict):
    """What the student did. Null on session open.

    `type` mirrors the `expects` the server last sent: node_click carries node_id,
    edge_click carries edge, mcq carries choice_id, text carries text. The server
    validates the pairing and rejects a mismatch rather than guessing.

    CLAUDE.md §8: click answers need confirm-or-undo. The client sends only
    confirmed clicks, so an unconfirmed misclick never reaches /turn and can never
    corrupt mastery.
    """

    type: Expects
    text: Optional[str] = None
    node_id: Optional[str] = None
    edge: Optional[EdgeRef] = None
    choice_id: Optional[str] = None


class TurnRequest(Strict):
    session_id: str
    response: Optional[StudentResponse] = None


class MCQOption(Strict):
    """A rendered MCQ choice.

    Carve-out to CLAUDE.md §1.6, and the only one. `label` is text that reaches
    the client and is not `utterance`. It is server-owned data read from
    items.json and graph.json - never model output - and MCQ is unrenderable
    without it. The rule exists to keep MODEL-generated text off the screen; this
    is the same class of data as the node labels the graph already renders.
    """

    id: str
    label: str


class GraphState(Strict):
    """Returned/streamed before the utterance. CLAUDE.md §5 step 5 and §8: the
    graph reacts on Call 1 return and never blocks on the text."""

    current_node: Optional[str] = None
    focus_nodes: list[str] = Field(default_factory=list)
    focus_edges: list[EdgeRef] = Field(default_factory=list)
    # Redundant with focus_nodes (it is the complement) but sent explicitly for
    # two reasons: the client renders dimming rather than deciding policy, and
    # eval §9.2 matches visual against verbal hints by THE SAME NAMED EXCLUDED
    # SET, which has to be logged verbatim to be matchable at all.
    dimmed_nodes: list[str] = Field(default_factory=list)
    # node_id -> mastery in [0,1]. Recolours nodes only; never resizes or
    # repositions them (CLAUDE.md §8).
    mastery: dict[str, float] = Field(default_factory=dict)


class ItemPublic(Strict):
    """The only part of an item the client may see.

    No prompt (the tutor's `utterance` IS the question), no answer, no aliases,
    no spans, no distractors. If a field is added here, assume it leaks until
    proven otherwise.
    """

    id: str
    node_id: str
    difficulty: float
    scorable: bool = Field(description="deterministic item; contributes to mastery")


class TurnBudget(Strict):
    used: int
    max: int


class TurnResponse(Strict):
    """THE WHITELIST (CLAUDE.md §1.6, guard layer 0).

    `utterance` is the only model-generated text in this object. `diagnosis`,
    `student_state`, `correct` and the raw Call 1 decision are logged and never
    serialised here. Adding a model-authored text field to this class is a
    severity-1 bug; tests/test_turn_contract.py asserts the exact field set.
    """

    session_id: str
    turn_id: int
    schema_version: str = SCHEMA_VERSION

    utterance: str

    # Server-decided, never the model's request (CLAUDE.md §1.7).
    action: Action
    hint_level: int
    expects: Expects
    mcq_options: list[MCQOption] = Field(default_factory=list)

    graph_state: GraphState
    item: Optional[ItemPublic] = None
    turn_budget: TurnBudget
    # Set when the turn budget forced a reveal. Mastery awarded is zero
    # (CLAUDE.md §6 layer 3).
    resolved_with_support: bool = False
    session_complete: bool = False


#: Every model that tests/test_schemas_frozen.py snapshots.
FROZEN_MODELS: tuple = (
    Node,
    Edge,
    Graph,
    Item,
    ItemBank,
    Call1Decision,
    Call2Utterance,
    EdgeRef,
    StudentResponse,
    TurnRequest,
    MCQOption,
    GraphState,
    ItemPublic,
    TurnBudget,
    TurnResponse,
)
