"""API contract. The frontend's src/types.ts mirrors these models (see docs/API.md)."""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

Jurisdiction = Literal["pakistan", "punjab", "sindh", "kp", "balochistan", "ict"]
Topic = Literal["harassment", "wages", "property", "tenancy", "other"]
Status = Literal["answered", "not_found", "out_of_scope", "danger"]
Confidence = Literal["high", "medium", "low", "none"]
LetterType = Literal["harassment_complaint", "wage_complaint", "property_complaint"]


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    # Optional hint from the UI (e.g. a province picker). The model also infers it from the question.
    jurisdiction: Optional[Jurisdiction] = None


class Citation(BaseModel):
    chunk_id: str
    act: str
    section: str
    heading: str = ""
    jurisdiction: str
    source_url: str = ""
    excerpt: str


class Referral(BaseModel):
    name: str
    number: Optional[str] = None
    note: str = ""
    source_url: str = ""
    verified: bool = False


class WageInfo(BaseModel):
    jurisdiction: str
    monthly_pkr: Optional[int] = None
    status: str  # notified_reported | proposed | unconfirmed
    effective_from: Optional[str] = None
    notification_date: Optional[str] = None
    as_of: str
    verified: bool = False
    source_url: str = ""
    note: str = ""


class Caveat(BaseModel):
    en: str
    ur: str


class Detected(BaseModel):
    language: str = "unknown"
    topic: Topic = "other"
    jurisdiction: Optional[Jurisdiction] = None
    english_query: str = ""


class AskResponse(BaseModel):
    status: Status
    answer_ur: str
    answer_en: str
    # Roman Urdu version of the answer, only when the person wrote Roman Urdu (Urdu in Latin letters); "" otherwise.
    answer_roman: str = ""
    confidence: Confidence = "none"
    citations: list[Citation] = []
    where_to_go: list[Referral] = []
    wage: Optional[WageInfo] = None
    caveats: list[Caveat] = []
    needs_province: bool = False
    letter_type: Optional[LetterType] = None
    detected: Detected = Detected()
    disclaimer_ur: str
    disclaimer_en: str


class LetterRequest(BaseModel):
    letter_type: LetterType
    complainant_name: str = Field(min_length=1, max_length=120)
    complainant_address: str = Field("", max_length=300)
    complainant_cnic: str = Field("", max_length=20)
    respondent_name: str = Field("", max_length=120)
    respondent_details: str = Field("", max_length=300)
    city: str = Field("", max_length=80)
    facts: str = Field(min_length=5, max_length=6000)
    relief: str = Field("", max_length=1500)
    # e.g. ["Protection against Harassment of Women at the Workplace Act 2010, s.8"]
    legal_basis: list[Annotated[str, Field(max_length=250)]] = Field(default_factory=list, max_length=10)
