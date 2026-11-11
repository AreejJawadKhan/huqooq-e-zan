"""/api/health: cheap by default, shows the per-stage model setup and provider counters, deep check is opt-in."""
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.providers import STATS, ProviderError


def make(**kw):
    base = dict(gemini_api_key="x", groq_api_key="g", anthropic_api_key="", llm_provider_setting="", llm_fallback_setting="")
    base.update(kw)
    s = Settings(**base)
    return TestClient(create_app(settings=s)), s


def test_health_shows_stage_routing_models_and_fingerprints():
    c, _ = make()
    body = c.get("/api/health").json()
    stages = body["providers"]["stages"]
    assert [r["provider"] for r in stages["analyzer"]] == ["groq", "gemini"]
    assert [r["provider"] for r in stages["answer"]] == ["gemini", "groq"]
    assert body["providers"]["model_config"] and body["providers"]["prompts"]
    assert body["status"] == "ok" and body["api_key_set"] is True


def test_health_exposes_counters_but_never_provider_messages():
    STATS.reset()
    STATS.record_failure("gemini", "answer", ProviderError('HTTP 429: {"error": "quota exceeded for key AIzaSECRET"}'))
    STATS.record_ok("groq", "answer", fallback=True)
    c, _ = make()
    raw = c.get("/api/health").text
    stats = c.get("/api/health").json()["providers"]["stats"]
    assert stats["gemini:answer"]["fail"] == 1 and stats["gemini:answer"]["last_error"] == "HTTP 429"
    assert stats["groq:answer"]["served_as_fallback"] == 1
    assert "AIzaSECRET" not in raw and "quota exceeded" not in raw
    STATS.reset()


def test_deep_check_is_disabled_unless_enabled():
    c, _ = make()
    body = c.get("/api/health?deep=1").json()
    assert "HEALTH_DEEP=1" in body["providers"]["deep"]


def test_deep_check_runs_once_per_minute_when_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.app.main.smoke_test", lambda settings: calls.append(1) or [{"provider": "gemini", "stage": "answer", "model": "m", "status": "ok"}])
    c, _ = make(health_deep=True)
    first = c.get("/api/health?deep=1").json()["providers"]["deep"]
    c.get("/api/health?deep=1")
    assert first[0]["status"] == "ok" and len(calls) == 1  # cached: the second request did not call the models again
    assert "deep" not in c.get("/api/health").json()["providers"]  # not requested: not run
