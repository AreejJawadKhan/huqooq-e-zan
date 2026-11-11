"""Pipeline behaviour with a fake LLM: no network, no API key."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import messages as M
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
    assert res.wage and res.wage.monthly_pkr == 40000 and res.wage.verified
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
    # No model at all: the question is still answered from the law text (retrieval only), flagged as degraded.
    r = client.post("/api/ask", json={"question": "minimum wage in Lahore"})
    assert r.status_code == 200 and r.headers["x-huqooq-degraded"] == "no_model"
    body = r.json()
    assert body["status"] == "answered" and body["confidence"] == "low" and body["citations"]
    assert body["answer_en"] == M.DEGRADED_EN and body["letter_type"] is None


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
    assert cleaned != M.URDU_UNAVAILABLE_UR
    assert "Minimum" not in cleaned and "Punjab Minimum" not in cleaned
    assert "40,000" in cleaned and "دفعہ 11" in cleaned and "  " not in cleaned
    # brackets that hold Urdu or numbers are kept
    assert clean_urdu("دفعہ 11 (ذیلی دفعہ 2) دیکھیں") == "دفعہ 11 (ذیلی دفعہ 2) دیکھیں"
    assert clean_urdu("کم از کم ماہانہ اجرت (40,000) روپے ہے") == "کم از کم ماہانہ اجرت (40,000) روپے ہے"


def test_pipeline_cleans_answer_ur_but_leaves_answer_en_untouched():
    comp = Composition("آپ اپنی شکایت دفتر کی کمیٹی (Inquiry Committee) میں تحریری طور پر جمع کروا سکتے ہیں۔", "File it with the Inquiry Committee (IC).", ["h:s3"], "high")
    res = make_pipeline(FakeLLM(harassment_analysis(), comp)).ask(AskRequest(question="manager harassment complaint"))
    assert res.answer_ur == "آپ اپنی شکایت دفتر کی کمیٹی میں تحریری طور پر جمع کروا سکتے ہیں۔"
    assert res.answer_en == "File it with the Inquiry Committee (IC)."


def test_self_harm_gets_its_own_message_and_helplines():
    res = make_pipeline(FakeLLM(harassment_analysis())).ask(AskRequest(question="I want to die"))
    assert res.status == "danger"
    assert "harming yourself" in res.answer_en and "You are not alone" in res.answer_en
    numbers = [r.number for r in res.where_to_go]
    assert numbers[0] == "15" and "1099" in numbers
    umang = next(r for r in res.where_to_go if r.name.startswith("Umang"))
    assert umang.verified is False  # NOT verified: the UI must show "Not yet verified" on it
    assert "1043" not in numbers  # the Punjab violence helpline is not the self-harm list
    assert res.citations == [] and res.letter_type is None


def test_violence_still_gets_the_general_danger_message_even_if_self_harm_is_also_mentioned():
    res = make_pipeline(FakeLLM(harassment_analysis())).ask(
        AskRequest(question="My husband beats me and I want to die", jurisdiction="punjab")
    )
    assert res.status == "danger" and "harming yourself" not in res.answer_en
    assert any(r.number == "1043" for r in res.where_to_go)


def test_every_unverified_referral_is_flagged_unverified_in_the_response():
    res = make_pipeline(FakeLLM(harassment_analysis())).ask(AskRequest(question="mujhe khudkushi ka khayal aata hai"))
    assert res.status == "danger" and all(isinstance(r.verified, bool) for r in res.where_to_go)


def test_caveats_state_only_sourced_claims():
    from backend.app import messages as M

    punjab = M.caveats_for("property", "punjab", None)[0]
    assert "60 days" in punjab.en and "section 4" in punjab.en and "target, not a guarantee" in punjab.en
    assert "delay" not in (punjab.en + punjab.ur).lower()  # "delays have been reported" had no source

    ict = M.caveats_for("property", "ict", None)[0]
    assert "529/2021" in ict.en and "ICA 85/2023" in ict.en and "confirm its current status" in ict.en
    assert "2023" not in ict.en.replace("ICA 85/2023", "")  # the unverified suspension date is not stated

    sindh = M.caveats_for("property", "sindh", None)[0]
    assert "does not hold" in sindh.en and "was found" not in sindh.en  # says what the app holds, not what exists in law


def test_an_english_answer_in_the_urdu_field_never_becomes_an_empty_answer():
    comp = Composition("You have the right to complain to the Inquiry Committee.", "English", ["h:s3"], "high")
    res = make_pipeline(FakeLLM(harassment_analysis(), comp)).ask(AskRequest(question="manager harassment complaint"))
    assert res.status == "answered" and res.answer_ur == M.URDU_UNAVAILABLE_UR and res.answer_ur.strip()


def test_khudkushi_in_roman_urdu_gets_the_self_harm_message():
    res = make_pipeline(FakeLLM(harassment_analysis())).ask(AskRequest(question="mujhe khudkushi ka khayal aata hai"))
    assert res.status == "danger" and "harming yourself" in res.answer_en
