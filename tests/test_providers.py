"""Provider tests run fully offline using httpx.MockTransport."""
import json

import httpx
import pytest

from backend.app.config import Settings
from backend.app.llm import Analysis
from backend.app.providers import (
    FallbackLLM,
    GeminiLLM,
    OpenAICompatLLM,
    ProviderError,
    build_llm,
)

ANALYSIS_ARGS = {
    "language": "ur",
    "english_query": "workplace harassment complaint",
    "search_terms": ["harassment", "inquiry committee"],
    "topic": "harassment",
    "jurisdiction": "punjab",
    "scope": "in_scope",
    "in_danger": False,
}


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gemini_parses_function_call_and_sends_forced_tool():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"functionCall": {"name": "report_analysis", "args": ANALYSIS_ARGS}}]}}]},
        )

    llm = GeminiLLM("k", "flash-lite", "flash", client=client(handler))
    a = llm.analyze("دفتر میں ہراسانی", None)
    assert isinstance(a, Analysis) and a.topic == "harassment" and a.jurisdiction == "punjab"
    assert "flash-lite:generateContent" in seen["url"] and seen["key"] == "k"
    cfg = seen["body"]["toolConfig"]["functionCallingConfig"]
    assert cfg["mode"] == "ANY" and cfg["allowedFunctionNames"] == ["report_analysis"]


def test_gemini_without_tool_call_raises():
    llm = GeminiLLM("k", "m", "m", client=client(lambda r: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})))
    with pytest.raises(ProviderError):
        llm.analyze("q", None)


def test_openai_compat_parses_tool_arguments_string():
    def handler(request: httpx.Request):
        assert request.headers["authorization"] == "Bearer g"
        body = json.loads(request.content)
        assert body["tool_choice"]["function"]["name"] == "report_analysis"
        msg = {"tool_calls": [{"function": {"name": "report_analysis", "arguments": json.dumps(ANALYSIS_ARGS)}}]}
        return httpx.Response(200, json={"choices": [{"message": msg}]})

    llm = OpenAICompatLLM("g", "small", "big", client=client(handler))
    assert llm.analyze("q", "punjab").topic == "harassment"


def test_openai_compat_bad_arguments_raise():
    msg = {"tool_calls": [{"function": {"name": "x", "arguments": "not json"}}]}
    llm = OpenAICompatLLM("g", "s", "b", client=client(lambda r: httpx.Response(200, json={"choices": [{"message": msg}]})))
    with pytest.raises(ProviderError):
        llm.analyze("q", None)


def test_rate_limit_retries_once_then_succeeds(monkeypatch):
    monkeypatch.setattr("backend.app.providers.time.sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "1"}, text="slow down")
        msg = {"tool_calls": [{"function": {"name": "report_analysis", "arguments": json.dumps(ANALYSIS_ARGS)}}]}
        return httpx.Response(200, json={"choices": [{"message": msg}]})

    llm = OpenAICompatLLM("g", "s", "b", client=client(handler))
    assert llm.analyze("q", None).topic == "harassment"
    assert calls["n"] == 2


def test_http_error_raises_provider_error(monkeypatch):
    monkeypatch.setattr("backend.app.providers.time.sleep", lambda s: None)
    llm = GeminiLLM("k", "m", "m", client=client(lambda r: httpx.Response(500, text="boom")))
    with pytest.raises(ProviderError, match="500"):
        llm.analyze("q", None)


class _Boom:
    name = "boom"

    def analyze(self, *a):
        raise ProviderError("down")

    compose = analyze


class _Ok:
    name = "ok"

    def analyze(self, *a):
        return Analysis(topic="wages")

    def compose(self, *a):
        return "composed"


def test_fallback_uses_second_provider_when_first_fails():
    assert FallbackLLM([_Boom(), _Ok()]).analyze("q", None).topic == "wages"
    assert FallbackLLM([_Boom(), _Ok()]).compose("q", None, [], []) == "composed"


def test_fallback_raises_when_all_fail():
    with pytest.raises(ProviderError, match="All providers failed"):
        FallbackLLM([_Boom(), _Boom()]).analyze("q", None)


def test_settings_pick_first_provider_with_key_and_fallbacks():
    s = Settings(gemini_api_key="", groq_api_key="g", anthropic_api_key="a", llm_provider_setting="", llm_fallback_setting="")
    assert s.llm_provider == "groq" and s.llm_fallbacks == ["anthropic"]
    s = Settings(gemini_api_key="x", groq_api_key="g", anthropic_api_key="", llm_provider_setting="", llm_fallback_setting="")
    assert s.llm_provider == "gemini" and s.llm_fallbacks == ["groq"]


def test_build_llm_returns_none_without_keys_and_wraps_when_two():
    none = Settings(gemini_api_key="", groq_api_key="", anthropic_api_key="", llm_provider_setting="", llm_fallback_setting="")
    assert build_llm(none) is None
    two = Settings(gemini_api_key="x", groq_api_key="g", anthropic_api_key="", llm_provider_setting="", llm_fallback_setting="")
    llm = build_llm(two)
    assert isinstance(llm, FallbackLLM) and [p.name for p in llm.providers] == ["gemini", "groq"]
    one = Settings(gemini_api_key="x", groq_api_key="", anthropic_api_key="", llm_provider_setting="", llm_fallback_setting="")
    assert isinstance(build_llm(one), GeminiLLM)


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_ANSWER_MODEL", "my-model")
    s = Settings(gemini_api_key="x")
    assert s.models_for("gemini")[1] == "my-model"
