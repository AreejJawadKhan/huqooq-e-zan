"""Model providers. All of them take the same provider-neutral tool schema from llm.py and return the
tool's arguments as a dict, so the rest of the app never knows which model answered.

- gemini: Google AI Studio REST API (free tier available; see the privacy note in README).
- groq: Groq's OpenAI-compatible API (free plan available). Any OpenAI-compatible host works via OPENAI_BASE_URL.
- anthropic: paid, via the official SDK (llm.AnthropicLLM).

Plain httpx is used for Gemini and Groq so no extra SDK is needed.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

import httpx

from .llm import Analysis, AnthropicLLM, Composition, LLM, ToolLLM
from .retrieval import Chunk
from .schemas import WageInfo

log = logging.getLogger("huqooq.providers")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Model names change often. Check AI Studio / Groq console and override with the *_MODEL env vars.
DEFAULT_MODELS = {
    "gemini": ("gemini-3.5-flash-lite", "gemini-3.5-flash"),  # verified working 2026-11-11; 2.5 names return 404
    "groq": ("llama-3.1-8b-instant", "llama-3.3-70b-versatile"),
    "anthropic": ("claude-haiku-5-5", "claude-sonnet-5-5"),
}
PROVIDERS = tuple(DEFAULT_MODELS)


class ProviderError(RuntimeError):
    """A provider call failed in a way another provider might not."""


def _post_with_retry(client: httpx.Client, url: str, *, retries: int = 1, **kwargs) -> httpx.Response:
    """POST; on 429/503 wait (honouring Retry-After, capped) and retry once, then raise ProviderError."""
    for attempt in range(retries + 1):
        resp = client.post(url, **kwargs)
        if resp.status_code in (429, 503) and attempt < retries:
            try:
                wait = float(resp.headers.get("retry-after", "2"))
            except ValueError:
                wait = 2.0
            time.sleep(min(max(wait, 0.5), 8.0))
            continue
        if resp.status_code >= 400:
            raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return resp
    raise ProviderError("unreachable")  # pragma: no cover


class GeminiLLM(ToolLLM):
    name = "gemini"

    def __init__(self, api_key: str, analyzer_model: str, answer_model: str, client: Optional[httpx.Client] = None):
        super().__init__(analyzer_model, answer_model)
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=60)
        self._no_thinking_config: set[str] = set()

    # Gemini 3.x models "think" before answering and those tokens count against maxOutputTokens. With a small budget
    # a long think leaves no room for the forced function call (finishReason MAX_TOKENS, no call): the intermittent
    # 502s seen on 2026-11-11 (976 to 1545 thought tokens against a 1800 limit). We turn thinking off (the task is
    # extraction from supplied text, not reasoning) and keep headroom in case a model ignores that.
    THINKING_BUDGET = 0
    OUTPUT_HEADROOM = 1500
    MAX_OUTPUT_CAP = 8192

    def _body(self, system: str, user: str, tool: dict, max_out: int, thinking: bool) -> dict:
        gen: dict = {"temperature": 0, "maxOutputTokens": max_out}
        if thinking:
            gen["thinkingConfig"] = {"thinkingBudget": self.THINKING_BUDGET}
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {"name": tool["name"], "description": tool["description"], "parameters": tool["input_schema"]}
                    ]
                }
            ],
            "toolConfig": {"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": [tool["name"]]}},
            "generationConfig": gen,
        }

    def _tool_call(self, model: str, system: str, user: str, tool: dict, max_tokens: int = 1500) -> dict:
        max_out = min(max_tokens + self.OUTPUT_HEADROOM, self.MAX_OUTPUT_CAP)
        thinking = model not in self._no_thinking_config
        last_finish = None
        for attempt in range(3):
            try:
                resp = _post_with_retry(
                    self.client,
                    GEMINI_URL.format(model=model),
                    headers={"x-goog-api-key": self.api_key, "content-type": "application/json"},
                    json=self._body(system, user, tool, max_out, thinking),
                )
            except ProviderError as e:
                # Some models (flash-lite returns a generic "invalid argument") cannot take thinkingConfig. Retry
                # without it, with more room, and remember so later calls to that model skip the failed attempt.
                if thinking and "HTTP 400" in str(e):
                    log.warning("gemini model %s rejected thinkingConfig; retrying without it", model)
                    self._no_thinking_config.add(model)
                    thinking = False
                    max_out = self.MAX_OUTPUT_CAP
                    continue
                raise
            data = resp.json()
            for cand in data.get("candidates", []):
                last_finish = cand.get("finishReason", last_finish)
                for part in (cand.get("content") or {}).get("parts", []):
                    call = part.get("functionCall")
                    if call and call.get("name") == tool["name"]:
                        return dict(call.get("args") or {})
            if last_finish == "MAX_TOKENS" and max_out < self.MAX_OUTPUT_CAP:
                log.warning("gemini %s hit MAX_TOKENS at %s; retrying with more room", model, max_out)
                max_out = self.MAX_OUTPUT_CAP
                continue
            break
        raise ProviderError(f"Gemini returned no tool call for {tool['name']} (finishReason={last_finish})")


class OpenAICompatLLM(ToolLLM):
    """Groq by default; point `url` elsewhere for any OpenAI-compatible chat completions API."""

    def __init__(
        self,
        api_key: str,
        analyzer_model: str,
        answer_model: str,
        *,
        name: str = "groq",
        url: str = GROQ_URL,
        client: Optional[httpx.Client] = None,
    ):
        super().__init__(analyzer_model, answer_model)
        self.name = name
        self.api_key = api_key
        self.url = url
        self.client = client or httpx.Client(timeout=60)

    def _tool_call(self, model: str, system: str, user: str, tool: dict, max_tokens: int = 1500) -> dict:
        body = {
            "model": model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": tool["name"]}},
        }
        resp = _post_with_retry(
            self.client,
            self.url,
            headers={"authorization": f"Bearer {self.api_key}", "content-type": "application/json"},
            json=body,
        )
        try:
            call = resp.json()["choices"][0]["message"]["tool_calls"][0]["function"]
            return dict(json.loads(call["arguments"]))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError(f"{self.name} returned no usable tool call for {tool['name']}: {exc}") from exc


class FallbackLLM:
    """Try the primary provider; if it fails (rate limit, outage, bad output), try the next one.

    Each call falls back independently, so one flaky analyzer call does not move the whole question.
    """

    def __init__(self, providers: list[LLM]):
        if not providers:
            raise ValueError("FallbackLLM needs at least one provider")
        self.providers = providers

    def _run(self, method: str, *args):
        last: Optional[Exception] = None
        for p in self.providers:
            try:
                return getattr(p, method)(*args)
            except Exception as exc:  # noqa: BLE001 - any provider failure should try the next one
                log.warning("provider %s failed on %s: %s", getattr(p, "name", p), method, exc)
                last = exc
        raise ProviderError(f"All providers failed. Last error: {last}")

    def analyze(self, question: str, jurisdiction_hint: Optional[str]) -> Analysis:
        return self._run("analyze", question, jurisdiction_hint)

    def compose(
        self, question: str, analysis: Analysis, chunks: list[Chunk], wages: list[WageInfo]
    ) -> Composition:
        return self._run("compose", question, analysis, chunks, wages)


def build_provider(name: str, settings) -> Optional[ToolLLM]:
    """Build one provider from settings, or None if it has no API key."""
    key = settings.api_key_for(name)
    if not key:
        return None
    analyzer, answer = settings.models_for(name)
    if name == "gemini":
        return GeminiLLM(key, analyzer, answer)
    if name == "groq":
        return OpenAICompatLLM(key, analyzer, answer, name="groq", url=settings.groq_url)
    if name == "anthropic":
        return AnthropicLLM(key, analyzer, answer)
    raise ValueError(f"Unknown provider {name!r}; expected one of {PROVIDERS}")


def build_llm(settings) -> Optional[LLM]:
    """Primary provider plus an optional fallback. None means no provider has a key."""
    order = [settings.llm_provider] + [p for p in settings.llm_fallbacks if p != settings.llm_provider]
    built = [b for b in (build_provider(n, settings) for n in order) if b is not None]
    if not built:
        return None
    return built[0] if len(built) == 1 else FallbackLLM(built)
