"""Pre-computed answers for the demo questions (real pipeline output, built by scripts/build_demo_cache.py).

Lookup is an exact match on the normalised question plus the optional province, so only the questions we
rehearsed are served from the cache; everything else goes through the live pipeline.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

from .schemas import AskResponse

_PUNCT = re.compile(r"[\s​-‏.,;:!?\"'()\[\]۔،؟]+")


def normalise(question: str) -> str:
    """Lowercase, NFKC, strip punctuation and collapse whitespace."""
    text = unicodedata.normalize("NFKC", question).lower()
    return _PUNCT.sub(" ", text).strip()


def cache_key(question: str, jurisdiction: Optional[str]) -> str:
    return f"{normalise(question)}|{jurisdiction or ''}"


class DemoCache:
    def __init__(self, entries: dict[str, dict]):
        self.entries = entries

    @classmethod
    def load(cls, path: Path) -> "DemoCache":
        if not path.exists():
            return cls({})
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, question: str, jurisdiction: Optional[str]) -> Optional[AskResponse]:
        raw = self.entries.get(cache_key(question, jurisdiction))
        return AskResponse.model_validate(raw) if raw else None
