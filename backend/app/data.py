"""Loaders and selectors for the small, hand-maintained data files (wages, referrals)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .schemas import Referral, WageInfo


class WageTable:
    def __init__(self, path: Path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.as_of: str = raw["as_of"]
        self._rows: dict[str, dict] = {r["jurisdiction"]: r for r in raw["rates"]}

    def get(self, jurisdiction: Optional[str]) -> Optional[WageInfo]:
        if not jurisdiction:
            return None
        row = self._rows.get(jurisdiction)
        if not row:
            return None
        return WageInfo(as_of=self.as_of, **row)

    def all(self) -> list[WageInfo]:
        return [WageInfo(as_of=self.as_of, **r) for r in self._rows.values()]


class ReferralTable:
    def __init__(self, path: Path):
        self._rows: list[dict] = json.loads(path.read_text(encoding="utf-8"))["referrals"]

    @staticmethod
    def _to_model(row: dict) -> Referral:
        return Referral(
            name=row["name"],
            number=row.get("number"),
            note=row.get("note", ""),
            source_url=row.get("source_url", ""),
            verified=row.get("verified", False),
        )

    def select(self, topic: str, jurisdiction: Optional[str], danger: bool = False, limit: int = 5) -> list[Referral]:
        def juris_ok(row: dict) -> bool:
            js = row.get("jurisdictions", ["all"])
            if "all" in js:
                return True
            # Province unknown: only show services that apply everywhere, never a Punjab-only number.
            return jurisdiction is not None and jurisdiction in js

        out: list[dict] = []
        if danger:
            out += [r for r in self._rows if "danger" in r.get("topics", []) and juris_ok(r)]
        out += [
            r
            for r in self._rows
            if topic in r.get("topics", []) and juris_ok(r) and r not in out
        ]
        # Always keep the generic legal-advice line as a fallback.
        if not out:
            out = [r for r in self._rows if "fallback" in r.get("topics", [])]
        return [self._to_model(r) for r in out[:limit]]
