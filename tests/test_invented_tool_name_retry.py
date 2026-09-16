"""A tool name the model made up is a bad sample, and gets the parse-failure retry.

gpt-oss leaks its own channel names into the tool call - `json` from 20b,
`commentary` from 120b - and Groq rejects the call server-side with a 400
`tool_use_failed`. The loop read every 4xx as "will not fix itself" and fell
back at once. Measured on day 13: 3 of ~16 Call 2s and 1 of ~16 Call 1s, the last
of which stopped a §9.5 run at field 12. The next sample is usually fine.

Truncation shares the error code and is NOT retried: it fails identically at the
same max_tokens, so a retry is a second bill for the same answer.
"""
from __future__ import annotations

import json

import httpx
import pytest

from server import llm as llm_mod

from .conftest import config_override

INVENTED = {"error": {
    "message": "Tool call validation failed: tool call validation failed: "
               "attempted to call tool 'commentary' which was not in request.tools",
    "type": "invalid_request_error", "code": "tool_use_failed"}}
TRUNCATED = {"error": {
    "message": "Tool call validation failed: model did not call a tool",
    "type": "invalid_request_error", "code": "tool_use_failed"}}
BAD_REQUEST = {"error": {"message": "invalid model", "type": "invalid_request_error",
                         "code": "model_not_found"}}
OK = {"choices": [{"message": {"tool_calls": [{"function": {
    "name": "say", "arguments": json.dumps({"utterance": "Which lit one fits?"})}}]}}]}


def _wire(monkeypatch, *responses):
    """Serve `responses` in order; record how many requests were made."""
    queue = list(responses)
    sent = []

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, headers=None, json=None):
            sent.append(json)
            status, body = queue.pop(0)
            return httpx.Response(status, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm_mod.httpx, "Client", FakeClient)
    return sent


def _call2():
    return llm_mod.call2(action="ask", hint_level=0, focus_labels=[], n_lit=52, recent=[])


@pytest.fixture(autouse=True)
def _groq():
    with config_override(llm_provider="groq", groq_api_key="g-key", llm_max_retries=1):
        yield


def test_an_invented_tool_name_is_retried_and_recovers(monkeypatch):
    sent = _wire(monkeypatch, (400, INVENTED), (200, OK))
    before = llm_mod.STATS["parse_failures"]
    assert _call2().utterance == "Which lit one fits?"
    assert len(sent) == 2
    assert llm_mod.STATS["parse_failures"] == before + 1, "§10 counts it"


def test_the_retry_is_bounded_by_the_existing_budget(monkeypatch):
    sent = _wire(monkeypatch, (400, INVENTED), (400, INVENTED), (200, OK))
    with pytest.raises(llm_mod.LLMError, match="TOOL NAME"):
        _call2()
    assert len(sent) == 2


def test_truncation_shares_the_code_and_is_not_retried(monkeypatch):
    sent = _wire(monkeypatch, (400, TRUNCATED), (200, OK))
    with pytest.raises(llm_mod.LLMError, match="TRUNCATION"):
        _call2()
    assert len(sent) == 1


def test_an_ordinary_400_still_stops_at_once(monkeypatch):
    sent = _wire(monkeypatch, (400, BAD_REQUEST), (200, OK))
    with pytest.raises(llm_mod.LLMError):
        _call2()
    assert len(sent) == 1
