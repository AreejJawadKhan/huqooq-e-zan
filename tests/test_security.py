"""Hardening checks: input bounds, rate limit, security headers, no provider detail in errors."""
import backend.app.main as main
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from tests.test_pipeline import FakeLLM, harassment_analysis, make_pipeline
from backend.app.llm import Composition


def client(llm=None):
    llm = llm or FakeLLM(harassment_analysis(), Composition("اردو", "English", ["h:s3"], "high"))
    return TestClient(create_app(pipeline=make_pipeline(llm), settings=Settings(anthropic_api_key="x")))


LETTER = {"letter_type": "harassment_complaint", "complainant_name": "Test User", "facts": "Repeated unwelcome messages."}


def test_letter_fields_are_bounded():
    c = client()
    assert c.post("/api/letter", json={**LETTER, "relief": "x" * 1600}).status_code == 422
    assert c.post("/api/letter", json={**LETTER, "complainant_name": "n" * 121}).status_code == 422
    assert c.post("/api/letter", json={**LETTER, "legal_basis": ["a"] * 11}).status_code == 422
    assert c.post("/api/letter", json={**LETTER, "complainant_name": ""}).status_code == 422


def test_ask_question_is_bounded():
    assert client().post("/api/ask", json={"question": "q" * 2001}).status_code == 422


def test_security_headers_present():
    r = client().get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"


def test_rate_limit_returns_429_with_retry_after():
    c = client()
    codes = [c.post("/api/ask", json={"question": "manager harassment complaint"}).status_code for _ in range(main.RATE_LIMIT + 3)]
    assert codes[: main.RATE_LIMIT] == [200] * main.RATE_LIMIT
    assert codes[-1] == 429
    r = c.post("/api/ask", json={"question": "manager harassment complaint"})
    assert r.headers["retry-after"] == str(main.RATE_WINDOW_S)


def test_upstream_errors_do_not_leak_details():
    class Boom:
        def analyze(self, *a):
            raise RuntimeError("HTTP 400: secret request body https://provider/key=SECRET")

        compose = analyze

    r = client(Boom()).post("/api/ask", json={"question": "manager harassment complaint"})
    # A model failure no longer surfaces as an error page: the answer is built from the law text, and the reason is a
    # short code. Nothing from the exception reaches the browser.
    assert r.status_code == 200 and r.headers["x-huqooq-degraded"] == "unavailable"
    assert "SECRET" not in r.text and "provider" not in r.text and "SECRET" not in str(r.headers)


def test_cors_rejects_unlisted_origin():
    c = client()
    r = c.options("/api/ask", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers


def test_letter_survives_control_characters():
    r = client().post("/api/letter", json={**LETTER, "complainant_name": "A\x00B", "facts": "hello\x0b there"})
    assert r.status_code == 200 and r.content[:2] == b"PK"
