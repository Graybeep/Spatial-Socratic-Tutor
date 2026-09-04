"""The schemas are frozen on day 2. This test is what enforces that.

Every model in server.schemas.FROZEN_MODELS is snapshotted to
schemas/<Model>.schema.json. Any change to a field, type, default or constraint
fails here, so a schema change is always deliberate and always shows in the diff
that both people review.

To change a schema on purpose:

    UPDATE_SCHEMA_SNAPSHOTS=1 python -m pytest tests/test_schemas_frozen.py

...and say so in the commit message, because it costs the other person a day
(CLAUDE.md §3).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from server.schemas import FROZEN_MODELS

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "schemas"
UPDATING = os.environ.get("UPDATE_SCHEMA_SNAPSHOTS") == "1"


@pytest.mark.parametrize("model", FROZEN_MODELS, ids=lambda m: m.__name__)
def test_schema_matches_snapshot(model):
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    path = SNAPSHOT_DIR / f"{model.__name__}.schema.json"
    current = json.dumps(model.model_json_schema(by_alias=True), indent=2, sort_keys=True)

    if UPDATING or not path.exists():
        path.write_text(current + "\n", encoding="utf-8")
        if not UPDATING:
            pytest.skip(f"created baseline snapshot {path.name}")
        return

    assert path.read_text(encoding="utf-8").strip() == current.strip(), (
        f"{model.__name__} drifted from its frozen snapshot. If this is intended, "
        f"rerun with UPDATE_SCHEMA_SNAPSHOTS=1 and flag it to the other person."
    )
