"""Deterministic danger detection. Runs BEFORE any model call, in English, Urdu and Roman Urdu.

False negatives are the costly error here (a woman in danger gets a legal essay instead of help lines); an extra
help banner costs little. But the danger state hides all legal text, so patterns must not fire on the ordinary
workplace, wage and property questions this app exists to answer ("sexually harassed me", "forced me to resign",
"won't let me leave the job"). tests/test_safety.py holds both lists; add to them whenever you add a pattern.

Urdu text is normalised before matching because the same word is typed with different code points: Arabic yeh
and kaf (ي ك) from Arabic-layout keyboards and many Android keyboards versus Urdu yeh and kaf (ی ک), Arabic heh
versus Urdu heh, diacritics, tatweel and invisible joiners. Patterns below are therefore written with the Urdu
letters only.
"""
from __future__ import annotations

import re
import unicodedata

# Arabic-script variants -> the Urdu letter that patterns use; curly quotes -> straight.
_CHAR_MAP = str.maketrans(
    {
        "ي": "ی",  # ي -> ی
        "ى": "ی",  # ى -> ی
        "ك": "ک",  # ك -> ک
        "ه": "ہ",  # ه -> ہ
        "أ": "ا",  # أ -> ا
        "إ": "ا",  # إ -> ا
        "’": "'",
        "‘": "'",
    }
)
# Arabic diacritics, tatweel, Quranic marks, zero-width and bidi control characters, soft hyphen, BOM.
_STRIP = re.compile("[ً-ٰٟـۖ-ۭ​-‏‪-‮⁦-⁩﻿­]")
_SPACES = re.compile(r"\s+")

_PATTERNS: dict[str, str] = {
    # ---------------- English ----------------
    "en_violence": (
        r"\b(beat|beats|beating|beaten|hit|hits|hurt|hurts|slap\w*|choke\w*|burn\w*)\s+(me|my|us)\b"
        r"|\b(kill|kills|killing)\s+(me|us|myself)\b|\bthreaten\w*|\bacid\b|\bdomestic violence\b"
        r"|\b(will|going to|gonna|'ll)\s+(kill|hurt|beat|murder)\b"
        r"|\b(stab\w*|strangl\w*|suffocat\w*)\b|\b(shoot|shot|shooting)\s+(me|us)\b"
    ),
    "en_fear": r"\b(scared|afraid|unsafe|in danger)\b.{0,30}\b(tonight|home|life|now|him|husband|family)\b|\blife in danger\b",
    "en_selfharm": (
        r"\bsuicid\w*|\bkill\s+myself\b|\bend\s+my\s+life\b|\bwant\s+to\s+die\b|\bbetter\s+off\s+dead\b"
        r"|\bwish\s+i\s+(was|were)\s+dead\b|\bend\s+it\s+all\b|\b(hurt|harm)\s+myself\b|\bself[- ]harm\b"
        r"|\b(don'?t|do\s+not|no\s+longer|not)\s+want\s+to\s+(live\s+any\s*more|be\s+alive|go\s+on)\b"
    ),
    "en_sexual": (
        r"\brape\w*|\bsexual(ly)?\s+(assault\w*|abus\w*|violen\w*)|\bmolest\w*|\bgrop(ed|ing|es)\b"
        r"|\b(grabbed|groped|fondled)\s+(me|my)\b|\bforced\s+himself\b"
    ),
    "en_coercion": (
        r"\bblackmail\w*|\bextort\w*|\bsextort\w*"
        r"|\block(ed|ing)?\s+(me|us|her)\s+(in|inside|up)\b"
        r"|\b(won'?t|will\s+not|doesn'?t|not)\s+let\s+me\s+(leave|go\s+out)\s+(the\s+|my\s+)?(house|home|room)\b"
        r"|\bheld\s+(me\s+)?(captive|hostage)\b"
        r"|\bforc(e|ed|es|ing)\s+(me\s+|her\s+)?(to\s+|into\s+)?marr\w*|\bforced\s+marriage\b"
        r"|\b(gun|knife|pistol|weapon|axe)\b.{0,25}\b(me|us|my)\b|\bwith\s+a\s+(gun|knife|pistol)\b"
    ),
    # ---------------- Roman Urdu ----------------
    "ru_violence": (
        r"\b(maar\s*peet|marpeet|maarta|marta\s+hai|marti\s+hai|maarte|peet\w*|pitai|tashaddud|qatl)\b"
        r"|\bma+r+\s*(pe+t|pi+t)\w*"
        r"|\bmaa?r\s*(dal|dun|denge|dengi|dega|degi|doon|doonga|dungi|dunga|diya|dala)\w*"
    ),
    "ru_threat": r"\bdhamk(i|ee)\w*|\bjaan\s+(ka|se|ko)\b|\bkhudkushi\b|\bzabardasti\b",
    "ru_selfharm": (
        r"\bkhud\s*kushi\b|\bkhud\s*ko\s+(khatam|maar)\w*|\bapni\s+jaan\b|\bmarna\s+chah\w*"
        r"|\bmar\s*(jana|jaana|jaon|jaun)\s+chah\w*|\bzindagi\s+khatam\w*|\b(jeena|jina)\s+nahi\w*"
    ),
    "ru_coercion": (
        r"\bblack\s*mail\w*|\bkamre\s+(mein|me)\s+band\w*|\bjabri\s+shadi\b|\bzabardasti\s+(ki\s+)?shadi\b"
        r"|\bizzat\s+lut\w*|\brape\b|\bmolest\w*"
    ),
    # ---------------- Urdu script (letters already normalised to the Urdu forms) ----------------
    "ur_violence": (
        r"مار\s*پیٹ|مارتا|مارتی|مارتے|پٹائی|تشدد|قتل|قاتلانہ|تیزاب"
        r"|مار\s*(ڈال|دو|دے|دوں|دیں|دیا)\w*|جان\s*سے\s*مار|گلا\s*(گھونٹ|دبا)\w*|جلا\s*(دیا|دوں|دے)\w*"
    ),
    "ur_threat": r"دھمکی|دھمکیاں|دھمکا\w*|جان\s*(کو|سے|کا)|خودکشی|زبردستی",
    "ur_selfharm": (
        r"خودکشی|مرنا\s*چاہ\w*|مر\s*جانا\s*چاہ\w*|مر\s*جاؤں|جان\s*دے\s*د\w*|جینا\s*نہیں"
        r"|زندگی\s*ختم|اپنی\s*جان|خود\s*کو\s*(ختم|مار)\w*"
    ),
    "ur_coercion": (
        r"بلیک\s*میل\w*|جبری\s*شادی|زبردستی\s*(کی\s*)?شادی|کمرے\s*میں\s*بند|قید\s*(کر|میں)"
        r"|عصمت\s*دری|ریپ|جنسی\s*(حملہ|زیادتی|تشدد)"
    ),
}
_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in _PATTERNS.items()}

# Labels that mean the person may harm herself; callers can show different resources for these.
SELF_HARM_LABELS = frozenset(label for label in _PATTERNS if label.endswith("_selfharm"))


def normalize(text: str) -> str:
    """Lowercase, NFKC, unify Arabic/Urdu letter variants, drop diacritics and invisible characters."""
    t = unicodedata.normalize("NFKC", text).translate(_CHAR_MAP)
    t = _STRIP.sub("", t).lower()
    return _SPACES.sub(" ", t).strip()


def detect_danger(text: str) -> list[str]:
    """Return the labels of matched danger patterns (empty list = no signal)."""
    t = normalize(text)
    return [label for label, rx in _COMPILED.items() if rx.search(t)]


def is_danger(text: str) -> bool:
    return bool(detect_danger(text))


def is_self_harm(text: str) -> bool:
    return any(label in SELF_HARM_LABELS for label in detect_danger(text))
