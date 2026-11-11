"""The question-answering pipeline.

Order matters and is the core of the safety story:
  1. Deterministic danger check (no model involved) -> help lines first, no legal lecture.
  2. Analyze (model) -> topic, jurisdiction, scope flags. Out-of-scope / prediction / harmful -> fixed refusal.
  3. Retrieve statute sections (BM25) and look up wage data.
  4. Nothing relevant -> fixed "not found" answer plus referrals. The model is never asked to guess.
  5. Compose (model) -> grounded answer. Citations are validated against what was retrieved;
     an answer with no valid citation and no wage data is replaced by "not found".
  6. Referrals and caveats are added deterministically from data files, never by the model.
"""
from __future__ import annotations

import re
from typing import Optional

from . import messages as M
from .config import Settings
from .data import ReferralTable, WageTable
from .llm import LLM, Analysis
from .retrieval import Chunk, Retriever
from .safety import detect_danger
from .schemas import AskRequest, AskResponse, Citation, Detected


def _excerpt(text: str, n: int = 420) -> str:
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# Sections that say nothing about the person's problem. A model sometimes cites them because they are the first
# excerpts it sees. They are dropped from the citations whenever a substantive section is also cited. "Definitions"
# is deliberately NOT here: answers often rely on a defined term (for example the Schedule of harassment).
_BOILERPLATE_HEADING = re.compile(
    r"^(short title|extent|commencement|repeal|savings?|power to make rules|rules)\b", re.IGNORECASE
)
_DIRECTION_MARKS = re.compile("[\u200e\u200f\u202a-\u202e\uf02d]")


def _is_boilerplate(chunk: Chunk) -> bool:
    heading = _DIRECTION_MARKS.sub("", chunk.heading or "").strip()
    return bool(_BOILERPLATE_HEADING.match(heading))


def drop_boilerplate(cited: list[Chunk]) -> list[Chunk]:
    """Remove short-title, commencement, repeal and rule-making sections unless they are all there is."""
    substantive = [c for c in cited if not _is_boilerplate(c)]
    return substantive or cited


class Pipeline:
    def __init__(
        self, llm: LLM, retriever: Retriever, wages: WageTable, referrals: ReferralTable, settings: Settings
    ):
        self.llm = llm
        self.retriever = retriever
        self.wages = wages
        self.referrals = referrals
        self.settings = settings

    # ---- helpers -------------------------------------------------------------------------------
    def _static(
        self,
        status: str,
        ur: str,
        en: str,
        detected: Detected,
        topic: str = "other",
        danger: bool = False,
    ) -> AskResponse:
        return AskResponse(
            status=status,  # type: ignore[arg-type]
            answer_ur=ur,
            answer_en=en,
            confidence="none",
            where_to_go=self.referrals.select(topic, detected.jurisdiction, danger=danger),
            detected=detected,
            disclaimer_ur=M.DISCLAIMER_UR,
            disclaimer_en=M.DISCLAIMER_EN,
        )

    def _danger(self, detected: Detected) -> AskResponse:
        return self._static("danger", M.DANGER_UR, M.DANGER_EN, detected, danger=True)

    # ---- main entry ----------------------------------------------------------------------------
    def ask(self, req: AskRequest) -> AskResponse:
        question = req.question.strip()
        base = Detected(jurisdiction=req.jurisdiction)

        # 1. deterministic danger check, before any model call
        if detect_danger(question):
            return self._danger(base)

        # 2. analyze
        a: Analysis = self.llm.analyze(question, req.jurisdiction)
        jurisdiction = a.jurisdiction or req.jurisdiction
        detected = Detected(
            language=a.language, topic=a.topic, jurisdiction=jurisdiction, english_query=a.english_query  # type: ignore[arg-type]
        )
        if a.in_danger:
            return self._danger(detected)
        if a.scope == "prediction":
            return self._static("out_of_scope", M.PREDICTION_UR, M.PREDICTION_EN, detected, a.topic)
        if a.scope in ("out_of_scope", "harmful") or a.topic == "other":
            return self._static("out_of_scope", M.OUT_OF_SCOPE_UR, M.OUT_OF_SCOPE_EN, detected, a.topic)

        # 3. retrieve + wage lookup
        query = " ".join([a.english_query, *a.search_terms])
        hits = self.retriever.search(
            query,
            topic=a.topic,
            jurisdiction=jurisdiction,
            k=self.settings.top_k,
            min_score=self.settings.min_score,
        )
        chunks: list[Chunk] = [c for c, _ in hits]
        wage = self.wages.get(jurisdiction) if a.topic == "wages" else None
        wage_rows = ([wage] if wage else self.wages.all()) if a.topic == "wages" else []

        # 4. nothing to ground on -> fixed refusal
        if not chunks and not wage_rows:
            return self._static("not_found", M.NOT_FOUND_UR, M.NOT_FOUND_EN, detected, a.topic)

        # 5. compose, then validate citations
        comp = self.llm.compose(question, a, chunks, wage_rows)
        by_id = {c.id: c for c in chunks}
        cited = drop_boilerplate([by_id[i] for i in dict.fromkeys(comp.cited_chunk_ids) if i in by_id])
        grounded = bool(cited) or wage is not None
        if comp.confidence == "none" or (not grounded and not comp.needs_province):
            return self._static("not_found", M.NOT_FOUND_UR, M.NOT_FOUND_EN, detected, a.topic)

        return AskResponse(
            status="answered",
            answer_ur=comp.answer_ur,
            answer_en=comp.answer_en,
            confidence=comp.confidence,  # type: ignore[arg-type]
            citations=[
                Citation(
                    chunk_id=c.id,
                    act=c.act,
                    section=c.section,
                    heading=c.heading,
                    jurisdiction=c.jurisdiction,
                    source_url=c.source_url,
                    excerpt=_excerpt(c.text),
                )
                for c in cited
            ],
            where_to_go=self.referrals.select(a.topic, jurisdiction),
            wage=wage,
            caveats=M.caveats_for(a.topic, jurisdiction, wage),
            needs_province=comp.needs_province,
            letter_type=comp.letter_type,  # type: ignore[arg-type]
            detected=detected,
            disclaimer_ur=M.DISCLAIMER_UR,
            disclaimer_en=M.DISCLAIMER_EN,
        )
