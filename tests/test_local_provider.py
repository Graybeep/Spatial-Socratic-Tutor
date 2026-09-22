"""A third provider, served from this machine.

The seam already existed for two wire formats (CLAUDE.md §13.1 put base URLs and
model ids in config; day 12 added the second provider behind `LLM_PROVIDER`).
A local OpenAI-compatible server is a third, and the whole point of these tests
is that it is a third *provider*, not a third *contract*: the request body, the
schema and the extraction are shared with Groq, so a decision that validates on
one validates on the other.

What is genuinely different is small and measured:

- LM Studio rejects the object form of `tool_choice` outright. `required` is
  equivalent here because each call defines exactly one tool.
- There is no key, because it is this machine.
- A local 9B model measured 40.3s to a validated Call 1 against Groq's 2.3s p50,
  so a shared 10s timeout would fail every local call before it finished.

No test here makes a network call. `tests/conftest.py` forces `mock_mode` on and
`test_dependency_freeze.py` still governs imports - this adds none.
"""
from __future__ import annotations

import json

import httpx
import pytest

from server import llm as llm_mod
from server.config import CONFIG, LOCAL_PROVIDERS, OPENAI_SHAPED

from .conftest import config_override


@pytest.fixture()
def _local():
    with config_override(llm_provider="local", mock_mode=False):
        yield


# --- the seam --------------------------------------------------------------

def test_the_local_provider_is_registered_and_needs_no_auth_header():
    path, auth, build, extract = llm_mod._PROVIDERS["local"]
    assert path == "/v1/chat/completions", (
        "LM Studio serves /v1/..., not Groq's /openai/v1/...")
    assert auth("") == {}, "a local server was sent an Authorization header"
    assert extract is llm_mod._groq_extract, (
        "extraction diverged from Groq's; the two would become different contracts")


def test_the_body_is_groqs_with_one_field_changed():
    """Shared body, shared schema. If these drift, a response that validates on
    one provider stops validating on the other and nothing would say so."""
    args = (CONFIG.call1, "sys", "user", llm_mod.CALL1_TOOL)
    groq = llm_mod._groq_request(*args)
    local = llm_mod._local_request(*args)

    assert local["tool_choice"] == "required"
    assert groq["tool_choice"] != local["tool_choice"]
    assert {k: v for k, v in local.items() if k != "tool_choice"} == \
           {k: v for k, v in groq.items() if k != "tool_choice"}


def test_required_is_unambiguous_because_there_is_one_tool():
    """`required` forces a tool call without naming one. That is only equivalent
    to naming it while each call offers exactly one tool - if a second is ever
    added, this stops being true and the model starts choosing."""
    for cfg, tool in ((CONFIG.call1, llm_mod.CALL1_TOOL),
                      (CONFIG.call2, llm_mod.CALL2_TOOL)):
        body = llm_mod._local_request(cfg, "s", "u", tool)
        assert len(body["tools"]) == 1


# --- config ----------------------------------------------------------------

def test_the_active_url_and_key_follow_the_provider(_local):
    assert CONFIG.llm_base_url == CONFIG.local_base_url
    assert CONFIG.llm_key == "", "a local provider was given a credential"
    assert CONFIG.llm_is_local is True


def test_a_remote_provider_is_not_local():
    with config_override(llm_provider="groq"):
        assert CONFIG.llm_is_local is False
    with config_override(llm_provider="anthropic"):
        assert CONFIG.llm_is_local is False


def test_the_provider_groups_agree_with_the_registry():
    """`OPENAI_SHAPED` and `LOCAL_PROVIDERS` steer defaults; a name in either
    that the registry does not serve is a config that cannot be run."""
    for name in OPENAI_SHAPED + LOCAL_PROVIDERS:
        assert name in llm_mod._PROVIDERS, f"{name!r} is not a registered provider"
    assert "local" in OPENAI_SHAPED and "local" in LOCAL_PROVIDERS


def _defaults_for(monkeypatch, provider):
    """The defaults `_by_provider` resolves for a provider.

    NOT `CONFIG.call1`. That is built once at import from the environment, and
    this repo's `.env` pins CALL1_TIMEOUT_S and CALL1_MAX_TOKENS explicitly - so
    asserting on CONFIG would test the developer's `.env` rather than the
    defaults, and would pass whatever the local branch said. `config_override`
    on `llm_provider` does not help either: the call configs are already frozen
    by the time it runs.
    """
    from server import config as config_mod

    monkeypatch.setenv("LLM_PROVIDER", provider)
    return config_mod._by_provider


def _default_expr(env_var):
    """The default expression wired to `env_var` in `server/config.py`, as AST.

    Read from source rather than from CONFIG. `CONFIG.call1` is frozen at import
    and `_load_dotenv` uses `os.environ.setdefault`, so this repo's `.env` - which
    pins CALL1_TIMEOUT_S, CALL1_MAX_TOKENS and CALL1_MODEL - wins over any default
    and over any subprocess environment. There is no runtime vantage point from
    which the default is observable, so the wiring is asserted where it is
    written. `tests/test_student_state_is_inert.py` reads source for the same
    reason.
    """
    import ast
    import pathlib

    src = pathlib.Path("server/config.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call) or len(node.args) != 2:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and first.value == env_var:
            return node.args[1]
    raise AssertionError(f"no default wired for {env_var!r} in server/config.py")


def _is_by_provider(expr, n_args):
    import ast

    return (isinstance(expr, ast.Call)
            and isinstance(expr.func, ast.Name)
            and expr.func.id == "_by_provider"
            and len(expr.args) == n_args)


def test_the_call_sites_resolve_local_defaults_through_by_provider():
    """The helper dispatching correctly is worth nothing if the call site does
    not use it. A bare literal here is how the local provider silently inherits
    a 10s timeout and Groq's model ids."""
    for env_var in ("CALL1_TIMEOUT_S", "CALL2_TIMEOUT_S",
                    "CALL1_MODEL", "CALL2_MODEL"):
        expr = _default_expr(env_var)
        assert _is_by_provider(expr, 3), (
            f"{env_var} does not resolve through _by_provider(anthropic, groq, "
            f"local); a local run would inherit the cloud value")


def test_the_local_timeout_default_is_not_the_cloud_default(monkeypatch):
    """40.3s measured for one Call 1 on this machine. A 10s default would fail
    every local call before it finished thinking."""
    by = _defaults_for(monkeypatch, "local")
    assert by(10.0, 10.0, 180.0) == 180.0

    by = _defaults_for(monkeypatch, "groq")
    assert by(10.0, 10.0, 180.0) == 10.0


def test_the_local_model_defaults_are_not_groqs(monkeypatch):
    """LM Studio does not serve gpt-oss-120b. Falling through to Groq's ids
    would default the local provider to models it cannot load."""
    by = _defaults_for(monkeypatch, "local")
    assert by("claude-opus-5", "openai/gpt-oss-120b", "qwen/qwen3.5-9b") == "qwen/qwen3.5-9b"


def test_a_shared_value_still_falls_through_to_groq(monkeypatch):
    """The completion budget is the same on both OpenAI-shaped providers: local
    models emit reasoning before the tool call exactly as gpt-oss does (measured
    252 and 625 reasoning tokens). Only ids and timeouts needed a third value."""
    by = _defaults_for(monkeypatch, "local")
    assert by(300, 1500) == 1500
    assert by(300, 1500, None) == 1500


# --- the key guard ---------------------------------------------------------

def test_a_local_call_does_not_demand_a_key(monkeypatch, _local):
    """`_invoke` refuses to run without a credential. A local server has none to
    be missing, and the old guard would have refused every local call."""
    body = {"choices": [{"message": {"tool_calls": [{"function": {
        "name": "say", "arguments": json.dumps({"utterance": "Which lit one?"})}}]}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5}}

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, headers=None, json=None):
            assert "Authorization" not in (headers or {})
            assert url.startswith(CONFIG.local_base_url)
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm_mod.httpx, "Client", FakeClient)
    out = llm_mod.call2(action="ask", hint_level=0, focus_labels=[], n_lit=52, recent=[])
    assert out.utterance == "Which lit one?"


def test_a_remote_provider_still_demands_a_key():
    """The guard that day 12 added must not have been loosened for everyone."""
    with config_override(llm_provider="groq", groq_api_key="", mock_mode=False):
        with pytest.raises(llm_mod.LLMError, match="GROQ_API_KEY"):
            llm_mod.call2(action="ask", hint_level=0, focus_labels=[], n_lit=52,
                          recent=[])


# --- the shipped example ---------------------------------------------------

def test_the_env_example_does_not_pin_provider_specific_values():
    """`.env.example` is what a new user copies, and `_load_dotenv` uses
    `os.environ.setdefault` - so anything set there beats the provider default
    for good. A pinned `CALL1_MODEL=claude-opus-5` is sent verbatim to a local
    server and comes back a 400, which is the opposite of letting someone pick
    a provider.
    """
    import pathlib

    pinned = []
    for raw in pathlib.Path(".env.example").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key in {"CALL1_MODEL", "CALL2_MODEL", "CALL1_MAX_TOKENS",
                   "CALL2_MAX_TOKENS", "CALL1_TIMEOUT_S", "CALL2_TIMEOUT_S"}:
            pinned.append(line)
    assert not pinned, (
        "these resolve from LLM_PROVIDER and must stay commented in the "
        f"example: {pinned}")


def test_the_env_example_names_every_registered_provider():
    """A provider nobody can find is a provider nobody uses."""
    import pathlib

    text = pathlib.Path(".env.example").read_text(encoding="utf-8")
    for name in llm_mod._PROVIDERS:
        assert name in text, f"{name!r} is registered but absent from .env.example"
