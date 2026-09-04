"""Shared fixtures.

CONFIG is a frozen dataclass on purpose - config is read once at startup and
never mutated at call time (CLAUDE.md §13.1). Tests that need a different ladder
or schedule go through `config_override`, which uses object.__setattr__ and always
restores. Nothing in the server does this; only tests.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from server import main as main_mod
from server.config import CONFIG
from server.graph_store import GraphStore
from server.state import Store


@contextmanager
def config_override(**values):
    saved = {k: getattr(CONFIG, k) for k in values}
    for k, v in values.items():
        object.__setattr__(CONFIG, k, v)
    try:
        yield CONFIG
    finally:
        for k, v in saved.items():
            object.__setattr__(CONFIG, k, v)


@pytest.fixture()
def no_latency(tmp_path):
    """Strip the mock's artificial delays so the suite doesn't sleep 2s a turn."""
    with config_override(
        mock_call1_delay_s=0.0,
        mock_call2_delay_s=0.0,
        log_dir=tmp_path / "logs",
    ):
        yield


@pytest.fixture(scope="session")
def _graph_store():
    """Loaded once. Parsing 50 nodes and 250 items per test is pure overhead."""
    return GraphStore.load()


@pytest.fixture()
def store(_graph_store):
    """Usable WITHOUT the client fixture - eval tests need the graph but no app."""
    return _graph_store


@pytest.fixture()
def client(no_latency, _graph_store):
    main_mod.STORE = _graph_store
    main_mod.DB = Store(db_path=":memory:")
    with TestClient(main_mod.app) as c:
        yield c


@pytest.fixture()
def session(client):
    return client.post("/session").json()["session_id"]


def turn(client, session_id, response=None):
    r = client.post("/turn", json={"session_id": session_id, "response": response})
    assert r.status_code == 200, r.text
    return r.json()


def wrong_response(data, store):
    """A deliberately wrong answer of whatever type the server expects."""
    if data["item"] is None:
        return None
    answer = store.item(data["item"]["id"]).answer
    expects = data["expects"]
    if expects == "node_click":
        return {"type": "node_click", "node_id": next(n for n in store.node_ids if n != answer)}
    if expects == "mcq":
        return {"type": "mcq", "choice_id": next(o["id"] for o in data["mcq_options"] if o["id"] != answer)}
    if expects == "edge_click":
        e = next(e for e in store.graph.edges if f"{e.from_}->{e.to}" != answer)
        return {"type": "edge_click", "edge": {"from": e.from_, "to": e.to}}
    return {"type": "text", "text": "no idea"}


def correct_response(data, store):
    if data["item"] is None:
        return None
    answer = store.item(data["item"]["id"]).answer
    expects = data["expects"]
    if expects == "node_click":
        return {"type": "node_click", "node_id": answer}
    if expects == "mcq":
        return {"type": "mcq", "choice_id": answer}
    if expects == "edge_click":
        src, _, dst = answer.partition("->")
        return {"type": "edge_click", "edge": {"from": src, "to": dst}}
    return {"type": "text", "text": answer}


def drive_to_mcq(client, session_id, store, limit=40):
    """Walk the session until the server asks for an MCQ answer."""
    data = turn(client, session_id)
    for _ in range(limit):
        if data["expects"] == "mcq":
            return data
        nxt = correct_response(data, store)
        if nxt is None:
            break
        data = turn(client, session_id, nxt)
    return None
