"""FastAPI app. CLAUDE.md §2, §5: one meaningful endpoint, POST /turn.

Two transports, one contract:

  POST /turn                  -> TurnResponse as JSON. Simplest thing that works.
  POST /turn?stream=true      -> SSE: a `graph_state` event, then an `utterance`
                                 event, then `done` carrying the full TurnResponse.

The streaming form exists because of CLAUDE.md §8: the graph must react on Call 1
return, before the utterance arrives, and must never block on the text. Build the
client against the streaming form - the JSON form hides the latency profile the
whole interface design depends on.

The mock inserts the real timings (config: MOCK_CALL1_DELAY_S / MOCK_CALL2_DELAY_S)
so what Person B builds against feels like the finished system.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from server import turn as turn_mod
from server.config import CONFIG
from server.graph_store import GraphStore
from server.schemas import SCHEMA_VERSION, TurnRequest, TurnResponse
from server.state import Store

STORE: Optional[GraphStore] = None
DB: Optional[Store] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global STORE, DB
    # Tests inject their own store and DB before the app starts; respect that.
    if STORE is None:
        STORE = GraphStore.load()
    if DB is None:
        DB = Store()
    yield


app = FastAPI(title="Spatial Socratic Tutor", version=SCHEMA_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _deps():
    if STORE is None or DB is None:
        raise HTTPException(status_code=503, detail="server not initialised")
    return STORE, DB


# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    store, _ = _deps()
    return {
        "ok": True,
        "mock_mode": CONFIG.mock_mode,
        "schema_version": SCHEMA_VERSION,
        "domain": store.graph.domain,
        "nodes": len(store.graph.nodes),
        "items": len(store.bank.items),
    }


@app.get("/graph")
def graph() -> dict:
    """The frozen graph, for the initial render.

    Fetched once at session start. Nothing here changes for the life of the
    session - CLAUDE.md §1.2 and §8: the layout is frozen and nodes never move.
    Per-turn state arrives in TurnResponse.graph_state instead.
    """
    store, _ = _deps()
    return store.graph.model_dump(by_alias=True)


@app.post("/session")
def create_session() -> dict:
    store, db = _deps()
    state = db.create(store.initial_theta_map())
    db.save(state)
    return {"session_id": state.session_id, "schema_version": SCHEMA_VERSION}


@app.post("/turn", response_model=TurnResponse, response_model_exclude_none=False)
async def post_turn(req: TurnRequest, stream: bool = Query(default=False)):
    store, db = _deps()
    state = db.get(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"unknown session {req.session_id}")

    if not stream:
        await asyncio.sleep(CONFIG.mock_call1_delay_s)
        phase1 = turn_mod.begin_turn(store, db, state, req.response)
        await asyncio.sleep(CONFIG.mock_call2_delay_s)
        return turn_mod.complete_turn(store, db, phase1)

    async def events():
        # Call 1
        await asyncio.sleep(CONFIG.mock_call1_delay_s)
        phase1 = turn_mod.begin_turn(store, db, state, req.response)

        # The graph moves NOW. Everything below this line is text arriving late.
        #
        # This event carries `expects`, `item` and `mcq_options` as well as the
        # graph, because the client has to become INTERACTIVE here, not just
        # repaint. Withholding them until `done` would leave the student looking
        # at a narrowed graph they cannot click for another ~1.4s, which throws
        # away most of what the split bought (CLAUDE.md §5, §8).
        yield _sse(
            "graph_state",
            {
                "session_id": state.session_id,
                "turn_id": state.turn_id,
                "action": phase1.action,
                "hint_level": phase1.hint_level,
                "expects": phase1.expects,
                "item": phase1.item_public().model_dump() if phase1.item_public() else None,
                "mcq_options": [o.model_dump() for o in phase1.mcq_options],
                "turn_budget": {
                    "used": state.turns_on_item,
                    "max": CONFIG.turn_budget,
                },
                "resolved_with_support": phase1.resolved_with_support,
                "session_complete": phase1.session_complete,
                "graph_state": phase1.graph_state.model_dump(by_alias=True),
            },
        )

        # Call 2
        await asyncio.sleep(CONFIG.mock_call2_delay_s)
        response = turn_mod.complete_turn(store, db, phase1)
        yield _sse("utterance", {"utterance": response.utterance})
        yield _sse("done", response.model_dump(by_alias=True))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def run() -> None:
    import uvicorn

    uvicorn.run("server.main:app", host=CONFIG.host, port=CONFIG.port, reload=True)


if __name__ == "__main__":
    run()
