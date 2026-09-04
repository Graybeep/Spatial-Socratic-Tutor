"""The client's view of the wire, checked against the server's.

`client/src/types.ts` is Person B's half of the §1.9 contract, and until this
file existed nothing compared it to `server/schemas.py`. test_turn_contract.py
pins the phase-1 field set against a hand-written literal and names types.ts in
a docstring, which is a comment, not a check.

That gap had already cost something. When `node_id` was removed from
`ItemPublic` server-side - the fix for the identity leak, where the item's node
IS the answer for a click item - the TypeScript interface kept declaring it.
The field simply stopped arriving. Every client read of `item.node_id` would
have been `undefined`, typed as `string`, with the compiler asserting it was
fine; and the one field whose removal was a security fix looked available.

So: parse the interfaces, compare the field names, fail on drift in either
direction. A missing field is a client that cannot see something it was sent; an
extra field is a client that believes in something that is not there, which is
the worse of the two and the one that happened.

Deliberately shallow - names only, not types. A real TS parser is a dependency
(§1.8) to catch a narrower class of bug than the one that bit us.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from server import schemas

TYPES_TS = Path(__file__).resolve().parents[1] / "client" / "src" / "types.ts"

# TS interface -> pydantic model. Only the types that cross the wire; Action,
# Expects and StudentResponse are unions, not interfaces, and are pinned by the
# server rejecting anything else with a 422.
PAIRS = [
    ("GraphNode", schemas.Node),
    ("GraphEdge", schemas.Edge),
    ("FrozenGraph", schemas.Graph),
    ("ItemPublic", schemas.ItemPublic),
    ("McqOption", schemas.MCQOption),
    ("EdgeRef", schemas.EdgeRef),
    ("TurnBudget", schemas.TurnBudget),
    ("GraphState", schemas.GraphState),
    ("TurnResponse", schemas.TurnResponse),
]

_COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def ts_interface_fields(source: str, name: str) -> set[str]:
    """Field names of `export interface <name>`.

    Comments go first, so a field name mentioned in a doc comment - and
    types.ts mentions `node_id` in several - cannot be mistaken for a
    declaration. Brace counting then bounds the body, since a field may be an
    inline object literal.
    """
    m = re.search(rf"export\s+interface\s+{name}\s*\{{", source)
    assert m, f"no `export interface {name}` in types.ts"

    depth, i = 1, m.end()
    while depth and i < len(source):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        i += 1
    body = _COMMENTS.sub("", source[m.end(): i - 1])

    fields, depth = set(), 0
    for line in body.splitlines():
        # Only depth 0 is this interface's own fields; deeper is a nested literal.
        if depth == 0:
            decl = re.match(r"\s*(\w+)\??\s*:", line)
            if decl:
                fields.add(decl.group(1))
        depth += line.count("{") - line.count("}")
    return fields


@pytest.fixture(scope="module")
def source() -> str:
    return TYPES_TS.read_text(encoding="utf-8")


def wire_fields(model) -> set[str]:
    """What the model actually puts on the wire, which is not its field names.

    `from` is a Python keyword, so Edge and EdgeRef declare `from_` with
    `alias="from"` - and `from` is what the client sees. Comparing
    `model_fields` keys directly would report drift on every edge type forever,
    and the obvious way to quieten that is to drop those types from PAIRS, which
    would leave the client's edge handling unchecked.
    """
    return {f.alias or name for name, f in model.model_fields.items()}


@pytest.mark.parametrize("ts_name,model", PAIRS, ids=[p[0] for p in PAIRS])
def test_client_interface_matches_server_model(source, ts_name, model):
    ts = ts_interface_fields(source, ts_name)
    py = wire_fields(model)

    assert ts == py, (
        f"{ts_name} has drifted from {model.__name__}.\n"
        f"  client declares but server never sends: {sorted(ts - py) or 'none'}\n"
        f"  server sends but client cannot see:     {sorted(py - ts) or 'none'}"
    )


def test_item_public_still_has_no_node_id(source):
    """Guarded on both sides by name, because this one is not a typo risk.

    For a node_click or mcq item the answer IS the item's node, so a client that
    can read node_id has been handed the answer. It held for 204 of the 250
    fixture items. If it ever comes back it will come back as a convenience.
    """
    assert "node_id" not in wire_fields(schemas.ItemPublic)
    assert "node_id" not in ts_interface_fields(source, "ItemPublic")


def test_the_parser_can_actually_see_a_field(source):
    """A field-name extractor that silently returns nothing would pass every
    assertion above by matching an empty set against an empty set."""
    assert ts_interface_fields(source, "TurnBudget") == {"used", "max"}
    assert "definition" in ts_interface_fields(source, "GraphNode")
    assert wire_fields(schemas.EdgeRef) == {"from", "to"}
