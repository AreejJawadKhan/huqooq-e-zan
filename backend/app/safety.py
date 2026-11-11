"""Deterministic danger detection. Runs BEFORE any model call, in English, Urdu and Roman Urdu.

False positives are acceptable (an extra help banner costs little); false negatives are not.
Extend the patterns freely; tests/test_safety.py shows the expected behaviour.
"""
from __future__ import annotations

import re
import unicodedata

_PATTERNS: dict[str, str] = {
    # English
    "en_violence": (
        r"\b(beat|beats|beating|beaten|hit|hits|hurt|hurts|slap\w*|choke\w*|burn\w*)\s+(me|my|us)\b"
        r"|\b(kill|kills|killing)\s+(me|us|myself)\b|\bthreaten\w*|\brape\w*|\bacid\b|\bdomestic violence\b"
    ),
    "en_fear": r"\b(scared|afraid|unsafe|in danger)\b.{0,30}\b(tonight|home|life|now|him|husband|family)\b|\blife in danger\b",
    "en_selfharm": r"\bsuicid\w*|\bkill myself\b|\bend my life\b",
    # Roman Urdu
    "ru_violence": r"\b(maar\s*peet|marpeet|maarta|marta\s+hai|marti\s+hai|maarte|peet\w*|pitai|tashaddud|qatl)\b",
    "ru_threat": r"\bdhamki\w*|\bjaan\s+(ka|se|ko)\b|\bkhudkushi\b|\bzabardasti\b",
    # Urdu script
    "ur_violence": r"مار\s*پیٹ|مارتا|مارتی|مارتے|پٹائی|تشدد|قتل",
    "ur_threat": r"دھمکی|دھمکیاں|جان\s*(کو|سے|کا)|خودکشی|زبردستی",
}
_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in _PATTERNS.items()}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def detect_danger(text: str) -> list[str]:
    """Return the labels of matched danger patterns (empty list = no signal)."""
    t = _normalize(text)
    return [label for label, rx in _COMPILED.items() if rx.search(t)]


def is_danger(text: str) -> bool:
    return bool(detect_danger(text))
