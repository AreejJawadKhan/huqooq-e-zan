"""API contract. The frontend's src/types.ts mirrors these models (see docs/API.md)."""
from __future__ import annotations

from typing import Literal, Optional

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
    complainant_name: str
    complainant_address: str = ""
    complainant_cnic: str = ""
    respondent_name: str = ""
    respondent_details: str = ""
    city: str = ""
    facts: str = Field(min_length=5, max_length=6000)
    relief: str = ""
    # e.g. ["Protection against Harassment of Women at the Workplace Act 2010, s.8"]
    legal_basis: list[str] = []
