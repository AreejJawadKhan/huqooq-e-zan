"""Demo cache: exact normalised match only, never for danger, off by default."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.demo_cache import DemoCache, cache_key, normalise
from backend.app.llm import Composition
from backend.app.main import create_app
from backend.app.schemas import AskResponse
from tests.test_pipeline import FakeLLM, harassment_analysis, make_pipeline

CACHED = AskResponse(
    status="answered", answer_ur="کیشڈ", answer_en="cached answer", disclaimer_ur="d", disclaimer_en="d"
).model_dump(mode="json")


def test_normalise_ignores_case_punctuation_and_spacing():
    assert normalise("  What  is the Minimum Wage?? ") == normalise("what is the minimum wage")
    assert normalise("پنجاب میں کم از کم اجرت کتنی ہے؟") == normalise("پنجاب میں  کم از کم اجرت کتنی ہے")


def test_key_includes_province():
    assert cache_key("q", "punjab") != cache_key("q", None)


def make_client(tmp_path: Path, enabled: bool, question="cached question please"):
    path = tmp_path / "demo_cache.json"
    path.write_text(json.dumps({cache_key(question, None): CACHED}), encoding="utf-8")
    llm = FakeLLM(harassment_analysis(), Composition("اردو", "live answer", ["h:s3"], "high"))
    settings = Settings(anthropic_api_key="x", demo_cache=enabled, demo_cache_path=path)
    return TestClient(create_app(pipeline=make_pipeline(llm), settings=settings)), llm


def test_cache_hit_skips_the_model(tmp_path):
    client, llm = make_client(tmp_path, enabled=True)
    r = client.post("/api/ask", json={"question": "Cached question please!"})
    assert r.json()["answer_en"] == "cached answer"
    assert llm.compose_calls == 0


def test_cache_miss_uses_live_pipeline(tmp_path):
    client, _ = make_client(tmp_path, enabled=True)
    r = client.post("/api/ask", json={"question": "manager harassment complaint"})
    assert r.json()["answer_en"] == "live answer"


def test_disabled_by_default(tmp_path):
    client, _ = make_client(tmp_path, enabled=False)
    r = client.post("/api/ask", json={"question": "cached question please"})
    assert r.json()["answer_en"] == "live answer"


def test_danger_never_served_from_cache(tmp_path):
    q = "mera shohar mujhe maar peet karta hai"
    path = tmp_path / "c.json"
    path.write_text(json.dumps({cache_key(q, None): CACHED}), encoding="utf-8")
    llm = FakeLLM(harassment_analysis())
    settings = Settings(anthropic_api_key="x", demo_cache=True, demo_cache_path=path)
    client = TestClient(create_app(pipeline=make_pipeline(llm), settings=settings))
    assert client.post("/api/ask", json={"question": q}).json()["status"] == "danger"


def test_empty_cache_file_is_fine(tmp_path):
    assert len(DemoCache.load(tmp_path / "missing.json")) == 0
