"""BM25 retrieval over statute sections.

Why BM25 and not embeddings: the corpus is a few hundred sections of English legal text,
the user's question is translated to English with legal keywords by the analyzer model, and
BM25 needs no model download. To swap in embeddings later, keep the `Retriever.search` signature.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

_STOP = {
    "the", "a", "an", "of", "to", "in", "and", "or", "for", "on", "by", "is", "are", "be", "as", "at",
    "it", "that", "this", "with", "from", "shall", "may", "any", "such", "which", "has", "have", "been",
}
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


@dataclass
class Chunk:
    id: str
    source_id: str
    act: str
    jurisdiction: str  # pakistan | punjab | sindh | kp | balochistan | ict
    topic: str  # harassment | wages | property | tenancy
    section: str  # e.g. "4" or "Schedule"
    heading: str
    text: str
    source_url: str = ""
    as_of: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def allowed_jurisdictions(user_jurisdiction: Optional[str]) -> Optional[set[str]]:
    """Which chunk jurisdictions apply to a user in `user_jurisdiction`. None = no restriction."""
    if user_jurisdiction is None:
        return None
    allowed = {"pakistan", user_jurisdiction}
    return allowed


class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._tokens = [tokenize(f"{c.heading} {c.heading} {c.text}") for c in chunks]
        self._bm25 = BM25Okapi(self._tokens) if chunks else None

    @classmethod
    def from_jsonl(cls, path: Path) -> "Retriever":
        if not path.exists():
            return cls([])
        chunks = [Chunk(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return cls(chunks)

    def __len__(self) -> int:
        return len(self.chunks)

    def search(
        self,
        query: str,
        topic: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        k: int = 5,
        min_score: float = 0.0,
    ) -> list[tuple[Chunk, float]]:
        if not self._bm25:
            return []
        q = tokenize(query)
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        allowed = allowed_jurisdictions(jurisdiction)
        ranked: list[tuple[Chunk, float]] = []
        for chunk, score in zip(self.chunks, scores):
            if topic and topic != "other" and chunk.topic != topic:
                continue
            if allowed is not None and chunk.jurisdiction not in allowed:
                continue
            if score >= min_score:
                ranked.append((chunk, float(score)))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:k]
