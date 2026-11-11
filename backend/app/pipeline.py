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

from . import lexicon
from . import messages as M
from .config import Settings
from .data import ReferralTable, WageTable
from .llm import LLM, Analysis
from .retrieval import Chunk, Retriever
from .safety import SELF_HARM_LABELS, detect_danger
from .lexicon import LexiconHits, Register, detect_register
from .schemas import AskRequest, AskResponse, Caveat, Citation, Detected


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


def clean_urdu(text: str) -> str:
    """answer_ur must contain no Latin letters (see lexicon.urduize): bracketed English is removed, known terms are
    written in Urdu script, anything else in Latin letters is dropped. If a fallback model wrote the "Urdu" answer in
    English, nothing readable is left: show a fixed note instead of an empty answer."""
    out = lexicon.urduize(text)
    if len(re.findall(r"[؀-ۿ]", out)) < 15:
        return M.URDU_UNAVAILABLE_UR
    return out


_URDU_LETTER = re.compile(r"[\u0600-\u06ff]")


def clean_roman(text: str) -> str:
    """answer_roman must be Latin letters only: Urdu script in it means the model ignored the instruction, and a
    Roman answer with Urdu letters would be read out wrongly. Reject it (the Urdu-script answer is still shown)."""
    text = (text or "").strip()
    return "" if _URDU_LETTER.search(text) else text


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

    def _danger(self, detected: Detected, self_harm: bool = False) -> AskResponse:
        if self_harm:
            # Self-harm gets its own words and its own helplines (15, 1099, a mental-health line), not the
            # violence-against-women list.
            return self._static("danger", M.DANGER_SELFHARM_UR, M.DANGER_SELFHARM_EN, detected, topic="selfharm")
        return self._static("danger", M.DANGER_UR, M.DANGER_EN, detected, danger=True)

    # ---- Roman Urdu / code-mixed support ---------------------------------------------------------
    @staticmethod
    def _reconcile(a: Analysis, reg: Register, lex: LexiconHits, ui_jurisdiction: Optional[str]) -> Analysis:
        """Merge what the model said with what the lexicon and register detection know deterministically.
        - register/code_mixed are always the deterministic ones (the composer writes in the user's register)
        - the lexicon's English search words are added to retrieval: a weak model's translation of Roman Urdu can miss
        - a model that calls a clearly in-scope Roman Urdu question 'other' or 'out of scope' is corrected, but only
          with at least two independent lexicon cues, and never for prediction / harmful / out-of-scope-cue questions
        - a place the lexicon recognises supplies the province when neither the model nor the UI did"""
        a.register, a.code_mixed = reg.script, reg.code_mixed
        if a.scope in ("in_scope", "out_of_scope") and (a.topic == "other" or a.scope == "out_of_scope") and lex.strong:
            a.topic, a.scope = lex.topic, "in_scope"  # type: ignore[assignment]
        if a.jurisdiction is None and ui_jurisdiction is None and lex.jurisdiction:
            a.jurisdiction = lex.jurisdiction
        a.search_terms = list(dict.fromkeys([*a.search_terms, *lex.terms]))[:20]
        return a

    def ask_degraded(self, req: AskRequest, reason: str = "unavailable") -> AskResponse:
        """Answer WITHOUT any model: used when every provider is rate-limited, out of time, not configured, or the server
        is at its model-request cap. Understanding comes from the lexicon (Roman Urdu, Urdu script, English), the content
        is the statute text itself, and every sentence of explanation is fixed text. It never explains the law, so it
        cannot mislead: it shows the best-matching sections, says plainly that no explanation is available, and always
        gives the helplines. Danger messages still take their normal deterministic path."""
        question = req.question.strip()
        reg = detect_register(question)
        labels = detect_danger(question)
        base = Detected(language=reg.language, jurisdiction=req.jurisdiction)
        if labels:
            return self._danger(base, self_harm=all(label in SELF_HARM_LABELS for label in labels))

        lex = lexicon.analyze(question)
        jurisdiction = req.jurisdiction or lex.jurisdiction
        detected = Detected(
            language=reg.language,
            topic=lex.topic or "other",  # type: ignore[arg-type]
            jurisdiction=jurisdiction,  # type: ignore[arg-type]
            english_query=" ".join(lex.terms[:6]),
        )

        def busy(status: str = "not_found") -> AskResponse:
            ur, en = (M.OUT_OF_SCOPE_UR, M.OUT_OF_SCOPE_EN) if status == "out_of_scope" else (M.BUSY_UR, M.BUSY_EN)
            res = self._static(status, ur, en, detected, lex.topic or "other")
            if status == "not_found" and reg.wants_roman_answer:
                res.answer_roman = M.BUSY_ROMAN
            return res

        if lex.out_of_scope:
            return busy("out_of_scope")
        if not lex.topic or not lex.terms:
            return busy()

        found = self.retriever.search(
            " ".join(lex.terms), topic=lex.topic, jurisdiction=jurisdiction, k=3, min_score=self.settings.min_score
        )
        wage = self.wages.get(jurisdiction) if lex.topic == "wages" else None
        if not found and wage is None:
            return busy()
        return AskResponse(
            status="answered",
            answer_ur=M.DEGRADED_UR,
            answer_en=M.DEGRADED_EN,
            answer_roman=M.DEGRADED_ROMAN if reg.wants_roman_answer else "",
            confidence="low",
            citations=[
                Citation(
                    chunk_id=c.id, act=c.act, section=c.section, heading=c.heading, jurisdiction=c.jurisdiction,
                    source_url=c.source_url, excerpt=_excerpt(c.text, 1200),
                )
                for c, _score in found
            ],
            where_to_go=self.referrals.select(lex.topic, jurisdiction),
            wage=wage,
            caveats=[M.DEGRADED_CAVEAT, *M.caveats_for(lex.topic, jurisdiction, wage)],
            needs_province=lex.topic in ("wages", "property") and jurisdiction is None,
            letter_type=None,
            detected=detected,
            disclaimer_ur=M.DISCLAIMER_UR,
            disclaimer_en=M.DISCLAIMER_EN,
        )

    def refresh_fixed_parts(self, res: AskResponse) -> AskResponse:
        """Re-derive everything that is NOT model text (caveats, helplines, wage, disclaimers) from the current data
        files, so a stored answer (demo cache) never shows caveat or helpline text that has since been corrected."""
        if res.status not in ("answered", "not_found", "out_of_scope"):
            return res
        topic, jurisdiction = res.detected.topic, res.detected.jurisdiction
        wage = self.wages.get(res.wage.jurisdiction) if res.wage is not None else None
        update: dict = {
            "where_to_go": self.referrals.select(topic, jurisdiction),
            "wage": wage or res.wage,
            "disclaimer_ur": M.DISCLAIMER_UR,
            "disclaimer_en": M.DISCLAIMER_EN,
        }
        if res.status == "answered":
            update["caveats"] = M.caveats_for(topic, jurisdiction, update["wage"])
        return res.model_copy(update=update)

    # ---- main entry ----------------------------------------------------------------------------
    def ask(self, req: AskRequest) -> AskResponse:
        question = req.question.strip()
        base = Detected(jurisdiction=req.jurisdiction)

        # 1. deterministic danger check, before any model call
        labels = detect_danger(question)
        if labels:
            # Self-harm wording only when it is the sole signal; any violence signal keeps the general danger path.
            return self._danger(base, self_harm=all(label in SELF_HARM_LABELS for label in labels))

        # 2. analyze (model), reconciled with what the lexicon and register detection know deterministically
        reg = detect_register(question)
        lex = lexicon.analyze(question)
        a: Analysis = self._reconcile(self.llm.analyze(question, req.jurisdiction), reg, lex, req.jurisdiction)
        jurisdiction = a.jurisdiction or req.jurisdiction
        detected = Detected(
            language=reg.language, topic=a.topic, jurisdiction=jurisdiction, english_query=a.english_query  # type: ignore[arg-type]
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
            answer_ur=clean_urdu(comp.answer_ur),
            answer_en=comp.answer_en,
            answer_roman=clean_roman(comp.answer_roman) if reg.wants_roman_answer else "",
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
