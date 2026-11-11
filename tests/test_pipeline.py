"""Pipeline behaviour with a fake LLM: no network, no API key."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.data import ReferralTable, WageTable
from backend.app.llm import Analysis, Composition
from backend.app.main import create_app
from backend.app.pipeline import Pipeline
from backend.app.retrieval import Chunk, Retriever
from backend.app.schemas import AskRequest

DATA = Path(__file__).resolve().parents[1] / "data"

CHUNKS = [
    Chunk("h:s3", "h", "Toy Harassment Act", "pakistan", "harassment", "3", "Complaint",
          "Any employee may make a written complaint to the Inquiry Committee about harassment at the workplace.", "u"),
    Chunk("h:s8", "h", "Toy Harassment Act", "pakistan", "harassment", "8", "Ombudsperson",
          "The Ombudsperson shall enquire into complaints of harassment and may impose penalties.", "u"),
    Chunk("p:s1", "p", "Punjab Women's Property Act", "punjab", "property", "1", "Short title, extent and commencement .‎–‎ (1) This Act may be cited as",
          "This Act may be cited as the Toy Women's Property Act and extends to the whole of Punjab.", "u"),
    Chunk("p:s4", "p", "Punjab Women's Property Act", "punjab", "property", "4", "Complaint to Ombudsperson",
          "A woman deprived of ownership or possession of property may file a complaint with the Ombudsperson.", "u"),
]


class FakeLLM:
    def __init__(self, analysis: Analysis, composition: Composition | None = None):
        self.analysis, self.composition = analysis, composition
        self.compose_calls = 0

    def analyze(self, question, hint):
        return self.analysis

    def compose(self, question, analysis, chunks, wages):
        self.compose_calls += 1
        return self.composition


def make_pipeline(llm, min_score=0.0) -> Pipeline:
    settings = Settings(anthropic_api_key="x", min_score=min_score)
    return Pipeline(llm, Retriever(CHUNKS), WageTable(DATA / "wages.json"), ReferralTable(DATA / "referrals.json"), settings)


def harassment_analysis(**kw):
    base = dict(language="en", english_query="complaint harassment workplace", search_terms=["inquiry committee", "complaint"],
                topic="harassment", jurisdiction=None)
    base.update(kw)
    return Analysis(**base)


def test_danger_keyword_skips_the_model_entirely():
    llm = FakeLLM(harassment_analysis())
    res = make_pipeline(llm).ask(AskRequest(question="My husband beat me and I am scared tonight."))
    assert res.status == "danger"
    assert res.where_to_go[0].number == "15"
    assert llm.compose_calls == 0


def test_answer_has_validated_citations_and_referrals():
    comp = Composition("اردو", "English", ["h:s3", "made:up:id"], "high")
    res = make_pipeline(FakeLLM(harassment_analysis(), comp)).ask(AskRequest(question="manager sends unwelcome messages"))
    assert res.status == "answered"
    assert [c.chunk_id for c in res.citations] == ["h:s3"]  # fabricated id dropped
    assert any(r.number == "1099" for r in res.where_to_go)


def test_uncited_answer_becomes_not_found():
    comp = Composition("اردو", "English", [], "medium")
    res = make_pipeline(FakeLLM(harassment_analysis(), comp)).ask(AskRequest(question="manager harassment complaint"))
    assert res.status == "not_found"
    assert res.citations == []


def test_nothing_retrieved_means_not_found_without_calling_compose():
    llm = FakeLLM(harassment_analysis(english_query="zzz qqq", search_terms=["xyzzy"]))
    res = make_pipeline(llm, min_score=0.1).ask(AskRequest(question="zzz"))
    assert res.status == "not_found"
    assert llm.compose_calls == 0


@pytest.mark.parametrize("scope", ["out_of_scope", "harmful", "prediction"])
def test_refusal_scopes(scope):
    llm = FakeLLM(harassment_analysis(scope=scope))
    res = make_pipeline(llm).ask(AskRequest(question="anything"))
    assert res.status == "out_of_scope"
    assert llm.compose_calls == 0


def test_wage_answer_attaches_wage_and_caveats():
    a = Analysis(language="en", english_query="minimum wage", search_terms=["minimum wage"], topic="wages", jurisdiction="punjab")
    comp = Composition("اردو", "Rs40,000", [], "medium")
    res = make_pipeline(FakeLLM(a, comp)).ask(AskRequest(question="minimum wage in Lahore"))
    assert res.status == "answered"
    assert res.wage and res.wage.monthly_pkr == 40000 and not res.wage.verified
    assert any("Labour Department" in c.en for c in res.caveats)


def test_unknown_province_shows_only_nationwide_referrals():
    comp = Composition("اردو", "English", ["p:s4"], "medium", needs_province=True)
    a = Analysis(language="en", english_query="deprived property complaint ombudsperson", search_terms=[], topic="property", jurisdiction=None)
    res = make_pipeline(FakeLLM(a, comp)).ask(AskRequest(question="my brothers took my land"))
    assert all(r.number != "1043" for r in res.where_to_go)


def test_http_endpoints():
    comp = Composition("اردو", "English", ["h:s3"], "high")
    app = create_app(pipeline=make_pipeline(FakeLLM(harassment_analysis(), comp)), settings=Settings(anthropic_api_key="x"))
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.post("/api/ask", json={"question": "manager harassment complaint"})
    assert r.status_code == 200 and r.json()["status"] == "answered"
    assert client.get("/api/wages").json()[0]["jurisdiction"] == "punjab"
    letter = client.post("/api/letter", json={
        "letter_type": "harassment_complaint", "complainant_name": "Test User", "facts": "My manager sent repeated unwelcome messages.",
        "legal_basis": ["Toy Harassment Act, s.3"],
    })
    assert letter.status_code == 200
    assert letter.content[:2] == b"PK"  # a .docx is a zip file
    assert "attachment" in letter.headers["content-disposition"]


def test_danger_works_without_api_key():
    """With no key configured, danger messages must still return help lines (no model needed)."""
    from backend.app.main import build_pipeline

    client = TestClient(create_app(pipeline=build_pipeline(Settings(anthropic_api_key="", gemini_api_key="", groq_api_key="")), settings=Settings()))
    r = client.post("/api/ask", json={"question": "mera shohar mujhe maar peet karta hai"})
    assert r.status_code == 200 and r.json()["status"] == "danger"
    assert client.post("/api/ask", json={"question": "minimum wage in Lahore"}).status_code == 503


def property_analysis():
    return Analysis(language="en", english_query="woman deprived of property complaint ombudsperson",
                    search_terms=["property", "ombudsperson", "deprived"], topic="property", jurisdiction="punjab")


def test_short_title_section_is_dropped_when_a_substantive_section_is_cited():
    comp = Composition("اردو", "English", ["p:s1", "p:s4"], "high")
    res = make_pipeline(FakeLLM(property_analysis(), comp)).ask(AskRequest(question="my brothers keep my land in Punjab"))
    assert res.status == "answered"
    assert [c.chunk_id for c in res.citations] == ["p:s4"]


def test_boilerplate_only_citation_is_kept_so_the_answer_is_not_left_ungrounded():
    comp = Composition("اردو", "English", ["p:s1"], "high")
    res = make_pipeline(FakeLLM(property_analysis(), comp)).ask(AskRequest(question="my brothers keep my land in Punjab"))
    assert [c.chunk_id for c in res.citations] == ["p:s1"]


def test_definitions_are_not_treated_as_boilerplate():
    from backend.app.pipeline import _is_boilerplate

    defs = Chunk("x:s2", "x", "Act", "pakistan", "harassment", "2", "Definitions.‎–‎ In this Act:", "t", "u")
    assert not _is_boilerplate(defs)
    for heading in ("Short title, extent and commencement", "Repeal and Savings. (1) The Ordinance", "Power to make rules", "Rules"):
        assert _is_boilerplate(Chunk("x:s9", "x", "Act", "pakistan", "wages", "9", heading, "t", "u"))


def test_english_in_brackets_is_removed_from_the_urdu_answer_only():
    from backend.app.pipeline import clean_urdu

    ur = "پنجاب میں کم از کم اجرت (Minimum Wage) 40,000 روپے ہے۔ پنجاب منیمم ویجز ایکٹ، 2019 (Punjab Minimum Wages Act, 2019) کی دفعہ 11 دیکھیں۔"
    cleaned = clean_urdu(ur)
    assert "Minimum" not in cleaned and "Punjab Minimum" not in cleaned
    assert "40,000" in cleaned and "دفعہ 11" in cleaned and "  " not in cleaned
    # brackets that hold Urdu or numbers are kept
    assert clean_urdu("دفعہ 11 (ذیلی دفعہ 2) دیکھیں") == "دفعہ 11 (ذیلی دفعہ 2) دیکھیں"
    assert clean_urdu("رقم (40,000) روپے") == "رقم (40,000) روپے"


def test_pipeline_cleans_answer_ur_but_leaves_answer_en_untouched():
    comp = Composition("شکایت کریں (Inquiry Committee) میں۔", "File it with the Inquiry Committee (IC).", ["h:s3"], "high")
    res = make_pipeline(FakeLLM(harassment_analysis(), comp)).ask(AskRequest(question="manager harassment complaint"))
    assert res.answer_ur == "شکایت کریں میں۔"
    assert res.answer_en == "File it with the Inquiry Committee (IC)."
