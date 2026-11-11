"""Model providers. All of them take the same provider-neutral tool schema from llm.py and return the
tool's arguments as a dict, so the rest of the app never knows which model answered.

- gemini: Google AI Studio REST API (free tier available; see the privacy note in README).
- groq: Groq's OpenAI-compatible API (free plan available). Any OpenAI-compatible host works via OPENAI_BASE_URL.
- anthropic: paid, via the official SDK (llm.AnthropicLLM).

Plain httpx is used for Gemini and Groq so no extra SDK is needed.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from .deadline import MAX_CALL_S, MIN_CALL_BUDGET_S, time_left
from .llm import Analysis, AnthropicLLM, Composition, LLM, ToolLLM
from .retrieval import Chunk
from .schemas import WageInfo

log = logging.getLogger("huqooq.providers")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Model names change often. Check AI Studio / Groq console and override with the *_MODEL env vars.
DEFAULT_MODELS = {
    "gemini": ("gemini-3.5-flash-lite", "gemini-2.5-flash"),  # lite=analyzer (fast), 2.5-flash=composer (reliable forced tool call)
    # Groq retired the Llama 3.x names above (model_not_found, 2026-11-11). gpt-oss-20b/120b verified working with
    # forced tool calls; qwen/qwen3.8-27b was tried and rejected (invented a tool name). Re-check with scripts/check_models.py.
    "groq": ("openai/gpt-oss-20b", "openai/gpt-oss-120b"),
    "anthropic": ("claude-haiku-5-5", "claude-sonnet-5-5"),
}
PROVIDERS = tuple(DEFAULT_MODELS)

# Which providers serve each pipeline stage, in order, when LLM_PROVIDER / ANALYZER_PROVIDER / ANSWER_PROVIDER are
# not set. The analyzer only classifies and extracts search terms (a small, structured job) so the fast Groq model
# does it (about 1 s versus about 5 s on Gemini); the answer needs the best Urdu, so Gemini writes it. Each stage
# falls back to the other provider. Providers without an API key are skipped. Changing this changes answers:
# the eval gate (tests/test_eval_baseline.py) fails until `scripts/run_eval.py --save` is rerun.
STAGES = ("analyzer", "answer")
DEFAULT_CHAINS = {
    "analyzer": ("groq", "gemini", "anthropic"),
    "answer": ("gemini", "groq", "anthropic"),
}
_STAGE_OF_METHOD = {"analyze": "analyzer", "compose": "answer"}


class ProviderError(RuntimeError):
    """A provider call failed in a way another provider might not."""


def _post_with_retry(client: httpx.Client, url: str, *, retries: int = 1, **kwargs) -> httpx.Response:
    """POST; on 429/503 wait (honouring Retry-After, capped) and retry once, then raise ProviderError. Respects the
    per-request deadline: the call's timeout is the time left, and no retry starts without time for it."""
    for attempt in range(retries + 1):
        left = time_left()
        if left is not None:
            if left < MIN_CALL_BUDGET_S:
                raise ProviderError("deadline exceeded before the call")
            kwargs["timeout"] = min(left, MAX_CALL_S)
        resp = client.post(url, **kwargs)
        if resp.status_code in (429, 503) and attempt < retries:
            try:
                wait = float(resp.headers.get("retry-after", "2"))
            except ValueError:
                wait = 2.0
            wait = min(max(wait, 0.5), 8.0)
            left = time_left()
            if left is None or left - wait >= MIN_CALL_BUDGET_S + 1:
                time.sleep(wait)
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

    # Reasoning models (gpt-oss) count their hidden reasoning against max_tokens, exactly like Gemini 3.x thinking:
    # a long think can leave no room for the forced tool call. Keep headroom, and ask gpt-oss for low effort (faster).
    OUTPUT_HEADROOM = 1500
    MAX_OUTPUT_CAP = 8192

    def _tool_call(self, model: str, system: str, user: str, tool: dict, max_tokens: int = 1500) -> dict:
        body = {
            "model": model,
            "temperature": 0,
            "max_tokens": min(max_tokens + self.OUTPUT_HEADROOM, self.MAX_OUTPUT_CAP),
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
        if "gpt-oss" in model:
            body["reasoning_effort"] = "low"
        resp = _post_with_retry(
            self.client,
            self.url,
            headers={"authorization": f"Bearer {self.api_key}", "content-type": "application/json"},
            json=body,
        )
        data = resp.json()
        try:
            call = data["choices"][0]["message"]["tool_calls"][0]["function"]
            return dict(json.loads(call["arguments"]))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            try:
                finish = data["choices"][0].get("finish_reason")
            except (KeyError, IndexError, TypeError, AttributeError):
                finish = None
            raise ProviderError(
                f"{self.name} returned no usable tool call for {tool['name']} (finish_reason={finish}): {exc}"
            ) from exc


def _short_error(exc: Exception) -> str:
    """A label safe to expose in /api/health: never the provider's message, which can echo request details."""
    text = str(exc)
    m = re.match(r"HTTP (\d{3})", text)
    if m:
        return f"HTTP {m.group(1)}"
    if "no tool call" in text or "no usable tool call" in text:
        return "no_tool_call"
    return type(exc).__name__


class AllProvidersFailed(ProviderError):
    """Every provider in a chain failed. `errors` holds short codes (HTTP 429, no_tool_call, ...) for classification."""

    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


def failure_reason(exc: BaseException) -> str:
    """Why a model-backed request failed, as a short code the UI can act on:
    busy (a provider is rate-limited), deadline (out of time), no_model (no key configured), unavailable (anything else)."""
    status = getattr(exc, "status_code", None)
    if status == 503 and "No model API key" in str(getattr(exc, "detail", "")):
        return "no_model"
    codes = list(getattr(exc, "errors", [])) or [_short_error(exc)]
    text = " ".join(codes) + " " + str(exc)
    if "deadline" in text:
        return "deadline"
    if "HTTP 429" in text:
        return "busy"
    return "unavailable"


class ProviderStats:
    """In-memory, per-process counters per provider and stage. They turn silent failures (a dead fallback, a model
    that keeps being skipped) into something visible in /api/health and in the logs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, dict] = {}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _row(self, provider: str, stage: str) -> dict:
        return self._rows.setdefault(
            f"{provider}:{stage}",
            {"ok": 0, "fail": 0, "served_as_fallback": 0, "last_ok": None, "last_error": None, "last_error_at": None},
        )

    def record_ok(self, provider: str, stage: str, fallback: bool) -> None:
        with self._lock:
            row = self._row(provider, stage)
            row["ok"] += 1
            row["last_ok"] = self._now()
            if fallback:
                row["served_as_fallback"] += 1

    def record_failure(self, provider: str, stage: str, exc: Exception) -> None:
        with self._lock:
            row = self._row(provider, stage)
            row["fail"] += 1
            row["last_error"] = _short_error(exc)
            row["last_error_at"] = self._now()

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._rows.items()}

    def reset(self) -> None:
        with self._lock:
            self._rows.clear()


STATS = ProviderStats()


class FallbackLLM:
    """Try the first provider; if it fails (rate limit, outage, bad output), try the next one.

    Each call falls back independently, so one flaky analyzer call does not move the whole question. Every failure
    is counted, and every request that a NON-first provider had to serve logs a WARNING, so a primary that is
    quietly failing (or a fallback that is dead) shows up instead of hiding behind answers that still arrive.
    """

    def __init__(self, providers: list[LLM]):
        if not providers:
            raise ValueError("FallbackLLM needs at least one provider")
        self.providers = providers

    def _run(self, method: str, *args):
        stage = _STAGE_OF_METHOD.get(method, method)
        last: Optional[Exception] = None
        failed: list[str] = []
        errors: list[str] = []
        for i, p in enumerate(self.providers):
            name = getattr(p, "name", str(p))
            if i > 0:
                left = time_left()
                if left is not None and left < MIN_CALL_BUDGET_S:
                    log.warning("no time left for %s on %s (deadline)", name, method)
                    errors.append("deadline")
                    break
            try:
                out = getattr(p, method)(*args)
            except Exception as exc:  # noqa: BLE001 - any provider failure should try the next one
                log.warning("provider %s failed on %s: %s", name, method, exc)
                STATS.record_failure(name, stage, exc)
                failed.append(name)
                errors.append(_short_error(exc))
                last = exc
                continue
            STATS.record_ok(name, stage, fallback=i > 0)
            if i > 0:
                log.warning("FALLBACK USED: %s served the %s stage after %s failed", name, stage, ", ".join(failed))
            return out
        raise AllProvidersFailed(f"All providers failed. Last error: {last}", errors)

    def analyze(self, question: str, jurisdiction_hint: Optional[str]) -> Analysis:
        return self._run("analyze", question, jurisdiction_hint)

    def compose(
        self, question: str, analysis: Analysis, chunks: list[Chunk], wages: list[WageInfo]
    ) -> Composition:
        return self._run("compose", question, analysis, chunks, wages)


class StageRouter:
    """Send the analyzer stage and the answer stage to different provider chains (each with its own fallbacks)."""

    def __init__(self, analyzer: FallbackLLM, answerer: FallbackLLM):
        self.analyzer_chain = analyzer
        self.answer_chain = answerer

    def analyze(self, question: str, jurisdiction_hint: Optional[str]) -> Analysis:
        return self.analyzer_chain.analyze(question, jurisdiction_hint)

    def compose(
        self, question: str, analysis: Analysis, chunks: list[Chunk], wages: list[WageInfo]
    ) -> Composition:
        return self.answer_chain.compose(question, analysis, chunks, wages)


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
    """The per-stage provider chains from settings. None means no provider has a key."""
    built: dict[str, Optional[ToolLLM]] = {}

    def provider(name: str) -> Optional[ToolLLM]:
        if name not in built:
            built[name] = build_provider(name, settings)
        return built[name]

    chains = {stage: [b for b in (provider(n) for n in settings.stage_chain(stage)) if b is not None] for stage in STAGES}
    if not chains["analyzer"] and not chains["answer"]:
        return None
    analyzer = chains["analyzer"] or chains["answer"]
    answerer = chains["answer"] or chains["analyzer"]
    if [p.name for p in analyzer] == [p.name for p in answerer]:
        return FallbackLLM(analyzer)
    return StageRouter(FallbackLLM(analyzer), FallbackLLM(answerer))


# ---------------------------------------------------------------------------------------------------------------
# Introspection: what is configured, a fingerprint of it for the eval gate, and a live smoke test.
# ---------------------------------------------------------------------------------------------------------------
def describe_stages(settings) -> dict[str, list[dict]]:
    """The provider chain and model per stage that this process will actually use (reflects .env overrides)."""
    out: dict[str, list[dict]] = {}
    for stage in STAGES:
        rows = []
        for name in settings.stage_chain(stage):
            analyzer, answer = settings.models_for(name)
            rows.append({"provider": name, "model": analyzer if stage == "analyzer" else answer})
        out[stage] = rows
    return out


def default_stages() -> dict[str, list[dict]]:
    """What ships by default, independent of which keys or environment overrides a machine has."""
    return {
        stage: [{"provider": n, "model": DEFAULT_MODELS[n][0 if stage == "analyzer" else 1]} for n in DEFAULT_CHAINS[stage]]
        for stage in STAGES
    }


def config_fingerprint(stages: dict) -> str:
    return hashlib.sha256(json.dumps(stages, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def prompts_fingerprint() -> str:
    """Hash of everything that tells a model what to do: both system prompts and both tool schemas."""
    from . import prompts
    from .llm import _ANALYZE_TOOL, _COMPOSE_TOOL

    blob = json.dumps([prompts.ANALYZER_SYSTEM, prompts.ANSWER_SYSTEM, _ANALYZE_TOOL, _COMPOSE_TOOL], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def default_fingerprints() -> dict[str, str]:
    """Fingerprints of the shipped defaults. tests/test_eval_baseline.py compares these to data/eval_baseline.json."""
    from .config import DEFAULT_MIN_SCORE, DEFAULT_TOP_K

    return {
        "models": config_fingerprint(default_stages()),
        "prompts": prompts_fingerprint(),
        "retrieval": f"min_score={DEFAULT_MIN_SCORE},top_k={DEFAULT_TOP_K}",
    }


_PING_TOOL = {
    "name": "ping",
    "description": "Report that the model is reachable.",
    "input_schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
}


def smoke_test(settings) -> list[dict]:
    """One tiny real forced tool call per configured model. status: ok | limited (HTTP 429: the name is valid but the
    quota is exhausted) | fail (retired name, bad key, outage). Being LISTED by a provider proves nothing:
    gemini-2.5-flash-lite is listed yet returns 404."""
    from .config import PROVIDER_ORDER

    rows: list[dict] = []
    for name in PROVIDER_ORDER:
        llm = build_provider(name, settings)
        if llm is None:
            continue
        analyzer, answer = settings.models_for(name)
        for stage, model in (("analyzer", analyzer), ("answer", answer)):
            row = {"provider": name, "stage": stage, "model": model}
            try:
                out = llm._tool_call(model, "Call the ping tool with ok=true.", "ping", _PING_TOOL, max_tokens=50)
                row["status"] = "ok" if out.get("ok") is True else "fail"
                if row["status"] == "fail":
                    row["error"] = "unexpected_arguments"
            except Exception as exc:  # noqa: BLE001 - report every model, do not stop at the first failure
                row["status"] = "limited" if "HTTP 429" in str(exc) else "fail"
                row["error"] = _short_error(exc)
            rows.append(row)
    return rows
