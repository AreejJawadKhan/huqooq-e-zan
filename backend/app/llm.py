"""Model layer. Two calls per question:

1. analyze: small model -> language, English query + legal search terms, topic, jurisdiction, scope flags.
2. compose: stronger model -> grounded Urdu + English answer that must cite the retrieved excerpts.

Both use forced tool calls so the output is always structured JSON. Tests swap this class for a fake
(see tests/test_pipeline.py), so nothing else in the app imports the Anthropic SDK.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Protocol

from .prompts import ANALYZER_SYSTEM, ANSWER_SYSTEM
from .retrieval import Chunk
from .schemas import WageInfo

JURISDICTIONS = ["pakistan", "punjab", "sindh", "kp", "balochistan", "ict", "unknown"]


@dataclass
class Analysis:
    language: str = "unknown"
    english_query: str = ""
    search_terms: list[str] = field(default_factory=list)
    topic: str = "other"
    jurisdiction: Optional[str] = None
    scope: str = "in_scope"  # in_scope | out_of_scope | prediction | harmful
    in_danger: bool = False


@dataclass
class Composition:
    answer_ur: str
    answer_en: str
    cited_chunk_ids: list[str] = field(default_factory=list)
    confidence: str = "low"
    needs_province: bool = False
    letter_type: Optional[str] = None


class LLM(Protocol):
    def analyze(self, question: str, jurisdiction_hint: Optional[str]) -> Analysis: ...

    def compose(
        self, question: str, analysis: Analysis, chunks: list[Chunk], wages: list[WageInfo]
    ) -> Composition: ...


_ANALYZE_TOOL = {
    "name": "report_analysis",
    "description": "Report the classification of the user's question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "language": {"type": "string", "enum": ["ur", "roman_ur", "en", "other"]},
            "english_query": {"type": "string"},
            "search_terms": {"type": "array", "items": {"type": "string"}},
            "topic": {"type": "string", "enum": ["harassment", "wages", "property", "tenancy", "other"]},
            "jurisdiction": {"type": "string", "enum": JURISDICTIONS},
            "scope": {"type": "string", "enum": ["in_scope", "out_of_scope", "prediction", "harmful"]},
            "in_danger": {"type": "boolean"},
        },
        "required": ["language", "english_query", "search_terms", "topic", "jurisdiction", "scope", "in_danger"],
    },
}

_COMPOSE_TOOL = {
    "name": "write_answer",
    "description": "Write the grounded answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer_ur": {"type": "string"},
            "answer_en": {"type": "string"},
            "cited_chunk_ids": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["high", "medium", "low", "none"]},
            "needs_province": {"type": "boolean"},
            "letter_type": {
                "type": "string",
                "enum": ["none", "harassment_complaint", "wage_complaint", "property_complaint"],
            },
        },
        "required": ["answer_ur", "answer_en", "cited_chunk_ids", "confidence", "needs_province", "letter_type"],
    },
}


def _format_excerpts(chunks: list[Chunk]) -> str:
    parts = []
    for c in chunks:
        parts.append(
            f'<excerpt id="{c.id}" act="{c.act}" section="{c.section}" jurisdiction="{c.jurisdiction}">\n'
            f"{c.text[:1800]}\n</excerpt>"
        )
    return "\n".join(parts) if parts else "(none)"


class AnthropicLLM:
    def __init__(self, api_key: str, analyzer_model: str, answer_model: str):
        import anthropic  # imported lazily so tests run without the SDK configured

        self.client = anthropic.Anthropic(api_key=api_key)
        self.analyzer_model = analyzer_model
        self.answer_model = answer_model

    def _tool_call(self, model: str, system: str, user: str, tool: dict, max_tokens: int = 1500) -> dict:
        resp = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        for block in resp.content:
            if block.type == "tool_use":
                return dict(block.input)
        raise RuntimeError(f"Model returned no tool call for {tool['name']}")

    def analyze(self, question: str, jurisdiction_hint: Optional[str]) -> Analysis:
        user = f"<jurisdiction_hint>{jurisdiction_hint or 'none'}</jurisdiction_hint>\n<question>{question}</question>"
        d = self._tool_call(self.analyzer_model, ANALYZER_SYSTEM, user, _ANALYZE_TOOL, max_tokens=600)
        jur = d.get("jurisdiction")
        return Analysis(
            language=d.get("language", "unknown"),
            english_query=d.get("english_query", ""),
            search_terms=list(d.get("search_terms", [])),
            topic=d.get("topic", "other"),
            jurisdiction=None if jur in (None, "unknown") else jur,
            scope=d.get("scope", "in_scope"),
            in_danger=bool(d.get("in_danger", False)),
        )

    def compose(
        self, question: str, analysis: Analysis, chunks: list[Chunk], wages: list[WageInfo]
    ) -> Composition:
        wage_json = json.dumps([w.model_dump() for w in wages], ensure_ascii=False)
        user = (
            f"<question>{question}</question>\n"
            f"<detected topic=\"{analysis.topic}\" jurisdiction=\"{analysis.jurisdiction or 'unknown'}\"/>\n"
            f"<excerpts>\n{_format_excerpts(chunks)}\n</excerpts>\n"
            f"<wage_data>{wage_json}</wage_data>"
        )
        d = self._tool_call(self.answer_model, ANSWER_SYSTEM, user, _COMPOSE_TOOL, max_tokens=1800)
        lt = d.get("letter_type")
        return Composition(
            answer_ur=d.get("answer_ur", ""),
            answer_en=d.get("answer_en", ""),
            cited_chunk_ids=list(d.get("cited_chunk_ids", [])),
            confidence=d.get("confidence", "low"),
            needs_province=bool(d.get("needs_province", False)),
            letter_type=None if lt in (None, "none") else lt,
        )
