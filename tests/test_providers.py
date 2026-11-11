"""Provider tests run fully offline using httpx.MockTransport."""
import json

import httpx
import pytest

from backend.app.config import Settings
from backend.app.llm import Analysis
from backend.app.providers import (
    DEFAULT_MODELS,
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


def _call_resp(args=None):
    return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"functionCall": {"name": "report_analysis", "args": args or ANALYSIS_ARGS}}]}}]})


def _max_tokens_resp():
    # What Gemini 3.x returns when thinking used the whole output budget: no parts at all.
    return httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS", "content": {"role": "model"}}]})


def test_gemini_turns_thinking_off_and_leaves_headroom():
    seen = {}

    def handler(request: httpx.Request):
        seen["gen"] = json.loads(request.content)["generationConfig"]
        return _call_resp()

    GeminiLLM("k", "a", "b", client=client(handler)).analyze("q", None)
    assert seen["gen"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert seen["gen"]["maxOutputTokens"] > 600  # analyze asks for 600; headroom is added on top


def test_gemini_retries_once_with_more_room_on_max_tokens():
    sizes = []

    def handler(request: httpx.Request):
        sizes.append(json.loads(request.content)["generationConfig"]["maxOutputTokens"])
        return _max_tokens_resp() if len(sizes) == 1 else _call_resp()

    a = GeminiLLM("k", "a", "b", client=client(handler)).analyze("q", None)
    assert a.topic == "harassment" and len(sizes) == 2 and sizes[1] > sizes[0]


def test_gemini_gives_up_after_the_retry_and_reports_finish_reason():
    llm = GeminiLLM("k", "a", "b", client=client(lambda r: _max_tokens_resp()))
    with pytest.raises(ProviderError, match="MAX_TOKENS"):
        llm.analyze("q", None)


def test_gemini_retries_without_thinking_config_if_model_rejects_it():
    gens = []

    def handler(request: httpx.Request):
        gens.append(json.loads(request.content)["generationConfig"])
        if "thinkingConfig" in gens[-1]:
            # flash-lite answers with this generic message, which does not mention thinking
            return httpx.Response(400, text='{"error": {"message": "Request contains an invalid argument.", "status": "INVALID_ARGUMENT"}}')
        return _call_resp()

    llm = GeminiLLM("k", "a", "b", client=client(handler))
    a = llm.analyze("q", None)
    assert a.topic == "harassment" and len(gens) == 2 and "thinkingConfig" not in gens[1]
    llm.analyze("q", None)  # remembered: the second call goes straight to the working request
    assert len(gens) == 3 and "thinkingConfig" not in gens[2]


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


def _openai_ok():
    return httpx.Response(
        200,
        json={"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": [{"function": {"name": "report_analysis", "arguments": json.dumps(ANALYSIS_ARGS)}}]}}]},
    )


def test_groq_defaults_are_the_verified_models_not_the_retired_llama_names():
    analyzer, answer = DEFAULT_MODELS["groq"]
    assert (analyzer, answer) == ("openai/gpt-oss-20b", "openai/gpt-oss-120b")
    assert not any("llama-3" in m for pair in DEFAULT_MODELS.values() for m in pair)  # retired on Groq, model_not_found
    assert not any("gemini-2.5" in m for m in DEFAULT_MODELS["gemini"])  # 404 for new users


def test_openai_compat_gives_reasoning_models_headroom_and_low_effort():
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        return _openai_ok()

    OpenAICompatLLM("g", "openai/gpt-oss-20b", "openai/gpt-oss-120b", client=client(handler)).analyze("q", None)
    assert seen["body"]["reasoning_effort"] == "low"
    assert seen["body"]["max_tokens"] > 600  # analyze asks for 600; hidden reasoning tokens need room on top


def test_openai_compat_does_not_send_reasoning_effort_to_other_models():
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        return _openai_ok()

    OpenAICompatLLM("g", "some/other-model", "some/other-model", client=client(handler)).analyze("q", None)
    assert "reasoning_effort" not in seen["body"]


def test_openai_compat_error_reports_the_finish_reason():
    resp = httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": None}}]})
    llm = OpenAICompatLLM("g", "m", "m", client=client(lambda r: resp))
    with pytest.raises(ProviderError, match="finish_reason=length"):
        llm.analyze("q", None)
