"""Quota, deadline and outage resilience, and Roman Urdu / code-mixed behaviour of the pipeline."""
import time

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import messages as M
from backend.app.config import Settings
from backend.app.deadline import request_deadline
from backend.app.limits import Admission, AnswerCache, client_ip
from backend.app.llm import Analysis, Composition
from backend.app.main import create_app
from backend.app.providers import AllProvidersFailed, FallbackLLM, ProviderError, _post_with_retry, failure_reason
from backend.app.schemas import AskRequest, AskResponse
from tests.test_pipeline import FakeLLM, harassment_analysis, make_pipeline, property_analysis

ROMAN_PROPERTY = "mere bhai walid ki zameen mein mera hissa nahi de rahe, Lahore"


# ------------------------------------------------------------------ rate limiting and admission
def test_client_ip_ignores_forwarded_for_unless_proxies_are_trusted():
    assert client_ip("6.6.6.6", "10.0.0.1", 0) == "10.0.0.1"  # default: a spoofed header changes nothing
    assert client_ip("", "10.0.0.1", 1) == "10.0.0.1"
    assert client_ip("203.0.113.7", "10.0.0.1", 1) == "203.0.113.7"
    assert client_ip("6.6.6.6, 203.0.113.7", "10.0.0.1", 1) == "203.0.113.7"  # what the client prepended is ignored
    assert client_ip("6.6.6.6, 203.0.113.7, 198.51.100.2", "10.0.0.1", 2) == "203.0.113.7"
    assert client_ip("203.0.113.7", "10.0.0.1", 3) == "10.0.0.1"  # fewer hops than trusted: fall back to the peer


def test_a_spoofed_forwarded_for_header_cannot_dodge_the_rate_limit():
    import backend.app.main as main

    c = TestClient(create_app(pipeline=make_pipeline(FakeLLM(harassment_analysis(), Composition("ا", "e", ["h:s3"], "high"))),
                              settings=Settings(anthropic_api_key="x", answer_cache_ttl_s=0)))
    codes = [
        c.post("/api/ask", json={"question": "manager harassment complaint"}, headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code
        for i in range(main.RATE_LIMIT + 3)
    ]
    assert codes[-1] == 429 and "rate_limited" in c.post("/api/ask", json={"question": "manager harassment complaint"}).text


def test_admission_caps_concurrent_and_per_minute_requests():
    a = Admission(max_inflight=2, global_rpm=100)
    assert a.enter() and a.enter() and not a.enter()  # a third at once is refused
    a.leave()
    assert a.enter()
    b = Admission(max_inflight=10, global_rpm=3)
    assert [b.enter() for _ in range(4)] == [True, True, True, False]  # per-minute budget across all clients
    for _ in range(3):
        b.leave()


# ------------------------------------------------------------------ answer cache
def _resp(status="answered"):
    return AskResponse(status=status, answer_ur="ا", answer_en="e", disclaimer_ur="d", disclaimer_en="d")


def test_answer_cache_expires_evicts_and_returns_copies(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("backend.app.limits.time.monotonic", lambda: now[0])
    c = AnswerCache(ttl_s=60, max_size=2)
    c.put("a", _resp())
    got = c.get("a")
    got.answer_en = "changed by a caller"
    assert c.get("a").answer_en == "e"  # a stored answer cannot be mutated through a returned copy
    c.put("b", _resp()), c.put("c", _resp())
    assert c.get("a") is None and c.get("b") and c.get("c")  # LRU: the oldest was evicted
    now[0] += 61
    assert c.get("b") is None  # expired


def test_only_validated_answers_are_cached_never_refusals_or_danger():
    c = AnswerCache(ttl_s=60, max_size=10)
    for status in ("danger", "not_found", "out_of_scope"):
        c.put(status, _resp(status))
        assert c.get(status) is None, status  # a one-off model "not found" must not be repeated for an hour
    c.put("ok", _resp("answered"))
    assert c.get("ok") is not None
    assert AnswerCache(ttl_s=0, max_size=10).get("x") is None


def test_a_flaky_not_found_is_not_served_again_on_the_next_identical_question():
    class Flaky(FakeLLM):
        def compose(self, question, analysis, chunks, wages):
            self.compose_calls += 1
            if self.compose_calls == 1:
                return Composition("", "", [], "none")  # the model gives up this time
            return Composition("اردو", "English", ["h:s3"], "high")

    llm = Flaky(harassment_analysis())
    c = TestClient(create_app(pipeline=make_pipeline(llm), settings=Settings(anthropic_api_key="x")))
    q = {"question": "manager harassment complaint"}
    assert c.post("/api/ask", json=q).json()["status"] == "not_found"
    assert c.post("/api/ask", json=q).json()["status"] == "answered"  # retried for real, not served from cache


def test_repeated_question_is_served_from_cache_without_calling_the_model_again():
    llm = FakeLLM(harassment_analysis(), Composition("اردو", "English", ["h:s3"], "high"))
    c = TestClient(create_app(pipeline=make_pipeline(llm), settings=Settings(anthropic_api_key="x")))
    q = {"question": "manager harassment complaint"}
    first, second = c.post("/api/ask", json=q), c.post("/api/ask", json=q)
    assert first.json() == second.json() and llm.compose_calls == 1
    assert second.headers.get("x-huqooq-cache") == "hit" and "x-huqooq-cache" not in first.headers


# ------------------------------------------------------------------ deadline
def test_no_model_call_starts_without_time_left():
    calls = []
    c = httpx.Client(transport=httpx.MockTransport(lambda r: calls.append(1) or httpx.Response(200, json={})))
    with request_deadline(0.5):
        with pytest.raises(ProviderError, match="deadline"):
            _post_with_retry(c, "https://x/y", json={})
    assert calls == []


def test_a_429_is_not_retried_when_there_is_no_time_for_the_wait(monkeypatch):
    slept = []
    monkeypatch.setattr("backend.app.providers.time.sleep", lambda s: slept.append(s))
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"retry-after": "8"}, text="slow")))
    with request_deadline(6):  # an 8 s wait cannot fit
        with pytest.raises(ProviderError, match="429"):
            _post_with_retry(c, "https://x/y", json={})
    assert slept == []


def test_the_next_provider_is_skipped_when_the_budget_is_spent():
    class Boom:
        name = "boom"

        def analyze(self, *a):
            raise ProviderError("HTTP 429: quota")

    class Never:
        name = "never"

        def analyze(self, *a):
            raise AssertionError("must not be called: no time left")

    with request_deadline(1.0):  # already under the minimum call budget
        with pytest.raises(AllProvidersFailed) as e:
            FallbackLLM([Boom(), Never()]).analyze("q", None)
    assert "deadline" in e.value.errors


def test_failure_reason_codes():
    assert failure_reason(AllProvidersFailed("x", ["HTTP 429", "HTTP 404"])) == "busy"
    assert failure_reason(AllProvidersFailed("x", ["deadline"])) == "deadline"
    assert failure_reason(ProviderError("deadline exceeded before the call")) == "deadline"
    assert failure_reason(HTTPException(503, "No model API key is set.")) == "no_model"
    assert failure_reason(RuntimeError("boom")) == "unavailable"
    assert failure_reason(AllProvidersFailed("x", ["no_tool_call", "HTTP 500"])) == "unavailable"


# ------------------------------------------------------------------ degraded (retrieval-only) answers
class _Down:
    """A model layer that is rate-limited."""

    def analyze(self, *a):
        raise AllProvidersFailed("All providers failed. Last error: HTTP 429", ["HTTP 429"])

    compose = analyze


def degraded_client(llm=None, **settings):
    p = make_pipeline(llm or _Down())
    return TestClient(create_app(pipeline=p, settings=Settings(anthropic_api_key="x", answer_cache_ttl_s=0, **settings)))


def test_rate_limited_models_still_give_the_law_text_and_say_busy_not_broken():
    r = degraded_client().post("/api/ask", json={"question": ROMAN_PROPERTY})
    assert r.status_code == 200 and r.headers["x-huqooq-degraded"] == "busy"
    b = r.json()
    assert b["status"] == "answered" and b["confidence"] == "low"
    assert [c["chunk_id"] for c in b["citations"]][0] == "p:s4"  # the section that matches, found without any model
    assert b["answer_en"] == M.DEGRADED_EN and b["answer_ur"] == M.DEGRADED_UR
    assert b["answer_roman"] == M.DEGRADED_ROMAN  # a Roman Urdu question gets the Roman Urdu notice
    assert b["caveats"][0]["en"] == M.DEGRADED_CAVEAT.en  # the UI is told no explanation was written
    assert b["letter_type"] is None and b["detected"]["topic"] == "property" and b["detected"]["jurisdiction"] == "punjab"
    assert b["where_to_go"], "helplines are always shown"


def test_degraded_answer_for_an_urdu_script_question_has_no_roman_text():
    r = degraded_client().post("/api/ask", json={"question": "میرے بھائی مجھے والد کی زمین میں حصہ نہیں دے رہے", "jurisdiction": "punjab"})
    assert r.status_code == 200 and r.json()["status"] == "answered" and r.json()["answer_roman"] == ""


def test_degraded_gives_an_honest_busy_message_when_nothing_can_be_matched():
    r = degraded_client().post("/api/ask", json={"question": "aaj mausam kaisa hai"})
    b = r.json()
    assert r.headers["x-huqooq-degraded"] == "busy" and b["status"] == "not_found"
    assert b["answer_en"] == M.BUSY_EN and b["answer_roman"] == M.BUSY_ROMAN and b["citations"] == []


def test_degraded_still_refuses_out_of_scope_questions():
    b = degraded_client().post("/api/ask", json={"question": "talaq ke baad nafaqa kaise milega"}).json()
    assert b["status"] == "out_of_scope"


def test_danger_never_needs_a_model_even_when_models_are_down():
    r = degraded_client().post("/api/ask", json={"question": "woh mujhe maar dalega"})
    assert r.status_code == 200 and r.json()["status"] == "danger" and "x-huqooq-degraded" not in r.headers


def test_when_the_server_is_at_its_model_request_cap_the_model_is_not_called():
    llm = FakeLLM(harassment_analysis(), Composition("اردو", "English", ["h:s3"], "high"))
    c = TestClient(create_app(pipeline=make_pipeline(llm), settings=Settings(anthropic_api_key="x", max_inflight=1, answer_cache_ttl_s=0)))
    # take the only slot, as a slow request would
    import backend.app.limits as limits

    original = limits.Admission.enter
    limits.Admission.enter = lambda self: False
    try:
        r = c.post("/api/ask", json={"question": "manager harassment complaint"})
    finally:
        limits.Admission.enter = original
    assert r.headers["x-huqooq-degraded"] == "busy" and llm.compose_calls == 0


# ------------------------------------------------------------------ Roman Urdu / code-mixed in the full pipeline
class RecordingLLM(FakeLLM):
    def compose(self, question, analysis, chunks, wages):
        self.seen = analysis
        return super().compose(question, analysis, chunks, wages)


def test_roman_urdu_question_gets_a_roman_answer_and_the_composer_is_told_the_register():
    comp = Composition("اردو", "English", ["p:s4"], "high", answer_roman="Aap Section 4 ke tahat Ombudsperson ko shikayat de sakte hain.")
    llm = RecordingLLM(property_analysis(), comp)
    res = make_pipeline(llm).ask(AskRequest(question="mera bhai zameen mein hissa nahi de raha, Lahore"))
    assert res.status == "answered" and res.answer_roman.startswith("Aap Section 4")
    assert res.detected.language == "roman_ur"
    assert (llm.seen.register, llm.seen.code_mixed) == ("roman", False)


def test_urdu_script_and_english_questions_never_get_a_roman_answer():
    comp = Composition("اردو", "English", ["p:s4"], "high", answer_roman="Aap shikayat kar sakte hain.")
    for q, lang in (("میرے بھائی مجھے والد کی زمین میں حصہ نہیں دے رہے", "ur"), ("my brothers took my share of the land", "en")):
        res = make_pipeline(FakeLLM(property_analysis(), comp)).ask(AskRequest(question=q))
        assert res.status == "answered" and res.answer_roman == "" and res.detected.language == lang


def test_a_roman_answer_containing_urdu_script_is_rejected():
    comp = Composition("اردو", "English", ["p:s4"], "high", answer_roman="Aap کو شکایت کا haq hai")
    res = make_pipeline(FakeLLM(property_analysis(), comp)).ask(AskRequest(question="bhai ne zameen mein hissa nahi diya"))
    assert res.status == "answered" and res.answer_roman == ""


def test_a_weak_model_that_calls_a_clear_roman_property_question_other_is_corrected_by_the_lexicon():
    weak = Analysis(language="roman_ur", english_query="", search_terms=[], topic="other", scope="out_of_scope")
    comp = Composition("اردو", "English", ["p:s4"], "high")
    llm = FakeLLM(weak, comp)
    res = make_pipeline(llm).ask(AskRequest(question="mere bhai walid ki zameen mein mera hissa nahi de rahe, Lahore"))
    assert res.status == "answered" and llm.compose_calls == 1 and res.detected.topic == "property"
    assert res.detected.jurisdiction == "punjab"  # the province came from the place name, not from the model


def test_the_lexicon_never_overrides_prediction_harmful_or_out_of_scope_cues():
    for scope in ("prediction", "harmful"):
        a = Analysis(topic="other", scope=scope)
        res = make_pipeline(FakeLLM(a, Composition("ا", "e", ["p:s4"], "high"))).ask(AskRequest(question="bhai ne zameen mein hissa nahi diya, kya main jeet jaungi"))
        assert res.status == "out_of_scope", scope
    a = Analysis(topic="other", scope="out_of_scope")
    res = make_pipeline(FakeLLM(a, Composition("ا", "e", ["p:s4"], "high"))).ask(AskRequest(question="talaq ke baad zameen mein hissa aur nafaqa"))
    assert res.status == "out_of_scope"  # an out-of-scope cue (talaq, nafaqa) blocks the override


def test_lexicon_terms_are_added_to_retrieval_even_when_the_model_gives_none():
    thin = Analysis(language="roman_ur", english_query="my share", search_terms=[], topic="property", scope="in_scope")
    llm = FakeLLM(thin, Composition("ا", "e", ["p:s4"], "high"))
    res = make_pipeline(llm).ask(AskRequest(question="walid ki zameen par bhaiyon ne qabza kar liya, Lahore"))
    assert res.status == "answered"  # "possession", "deprived of property" came from the lexicon, not the model


# ------------------------------------------------------------------ cached answers never show stale fixed text
def test_refresh_fixed_parts_replaces_stale_caveats_and_helplines():
    from backend.app.schemas import Caveat, Detected

    stale = AskResponse(
        status="answered", answer_ur="ا", answer_en="e", disclaimer_ur="old", disclaimer_en="old",
        caveats=[Caveat(en="delays at the Ombudsperson's office have been reported", ur="تاخیر")],
        detected=Detected(topic="property", jurisdiction="punjab"),
    )
    fresh = make_pipeline(FakeLLM(harassment_analysis())).refresh_fixed_parts(stale)
    assert "delay" not in fresh.caveats[0].en.lower() and "60 days" in fresh.caveats[0].en
    assert fresh.disclaimer_en == M.DISCLAIMER_EN and fresh.answer_en == "e"  # model text untouched
    assert any(r.number == "1043" for r in fresh.where_to_go)


# ------------------------------------------------------------------ honesty of fixed texts
def test_scope_messages_do_not_claim_tenancy_and_do_not_use_a_gendered_first_person():
    assert "tenancy" not in M.OUT_OF_SCOPE_EN.lower() and "کرایہ" not in M.OUT_OF_SCOPE_UR
    for text in (M.OUT_OF_SCOPE_UR, M.PREDICTION_UR):
        assert "سکتا ہوں" not in text and "سکتی ہوں" not in text
