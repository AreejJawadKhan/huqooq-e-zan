"""Understanding Roman Urdu, Urdu script and the Urdu-English mix people actually speak, WITHOUT a model.

Most users do not write "clean" Urdu or English. They write "mera manager mujhe harass kar raha hai", or speak
"میری salary تین مہینے سے نہیں ملی", and a speech recogniser turns English words into Urdu letters ("سیلری",
"مینیجر"). This module gives the pipeline three deterministic abilities:

1. detect_register(text): what the person wrote (Urdu script, Roman Urdu, English, or a mix), so the answer can be
   written the same way.
2. analyze(text): topic, province and English statute search terms from a hand-written lexicon with spelling
   variants (tankhwah / tankhah / tankha ...) and fuzzy matching. It backs up a weak model (it adds search terms to
   retrieval) and it is the ONLY understanding available when every model is down (see Pipeline.ask_degraded).
3. nothing here ever answers a legal question: it only classifies and supplies search words.

The lexicon is small on purpose and easy to extend: add a row to CONCEPTS with the English statute words it should
trigger. Add a test in tests/test_lexicon.py for every row you add.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Optional

from .safety import normalize

# (topic, english search terms, roman/latin variants, urdu-script variants). topic None = context only.
CONCEPTS: list[tuple[Optional[str], list[str], list[str], list[str]]] = [
    # ---------------- harassment ----------------
    ("harassment", ["harassment", "unwelcome conduct", "complaint"],
     ["harass", "harassment", "harasment", "harassed", "harassing", "hiraasaan", "haraasaan", "hirasan", "harasmnt", "hirasaan", "harasaan"],
     ["ہراساں", "ہراسانی", "ہراسمنٹ", "ہراس", "ہراسمینٹ", "ہراسگی"]),
    ("harassment", ["harassment", "unwelcome conduct"],
     ["tang", "tangg", "tang karta", "tang karti", "tang kar", "pareshan", "pareshaan", "dhamka", "dhamkata"],
     ["تنگ", "پریشان"]),
    ("harassment", ["harassment", "unwelcome advances", "sexual favours"],
     ["chhed", "chheda", "chherna", "chhairna", "chher chhaar", "chhed chhaad", "cheed chaad", "ghalat nazar", "ganda", "gandi", "ganday"],
     ["چھیڑ", "چھیڑ چھاڑ", "چھیڑخانی", "غلط نظر", "گندا", "گندی"]),
    ("harassment", ["unwelcome messages", "communication", "harassment"],
     ["message", "messages", "msg", "msgs", "whatsapp", "call", "calls", "photo", "photos"],
     ["میسج", "میسجز", "پیغام", "پیغامات", "واٹس ایپ", "کال", "تصویر", "تصاویر"]),
    ("harassment", ["unwelcome physical contact", "harassment"],
     ["chhua", "chhoo", "chhoota", "haath lagaya", "haath lagata"],
     ["چھوا", "چھوتا", "ہاتھ لگایا", "ہاتھ لگاتا"]),
    ("harassment", ["inquiry committee", "competent authority", "complaint"],
     ["hr", "committee", "inquiry", "enquiry"],
     ["ایچ آر", "کمیٹی", "انکوائری"]),
    (None, ["ombudsperson", "complaint"],  # the Ombudsperson also hears property complaints: no topic on its own
     ["mohtasib", "muhtasib", "mohtasiba", "ombudsman", "ombudsperson", "federal ombudsman"],
     ["محتسب", "محتسبہ", "وفاقی محتسب"]),
    (None, ["employer", "supervisor", "workplace"],
     ["manager", "boss", "sahab", "sahib", "supervisor", "incharge", "malik", "owner", "seth", "sir", "colleague", "coworker"],
     ["مینیجر", "باس", "صاحب", "سپروائزر", "انچارج", "مالک", "سیٹھ", "سر", "کولیگ", "ساتھی"]),
    (None, ["workplace", "organization", "employer"],
     ["office", "daftar", "company", "factory", "karkhana", "karkhanay", "dukaan", "shop", "school", "college", "university", "hospital", "mill", "bank"],
     ["آفس", "دفتر", "کمپنی", "فیکٹری", "کارخانہ", "کارخانے", "دکان", "سکول", "کالج", "یونیورسٹی", "ہسپتال", "ملز"]),
    (None, ["complaint", "report"],
     ["shikayat", "shikaayat", "shikayet", "complaint", "complain", "report", "darj"],
     ["شکایت", "کمپلینٹ", "رپورٹ", "درج"]),
    (None, ["termination", "retaliation", "employer"],
     ["nikal", "nikala", "nikaal", "terminate", "terminated", "fired", "naukri", "job", "jawab", "resign"],
     ["نکال", "نکالا", "نکال دیا", "نوکری", "ملازمت", "جاب", "استعفیٰ"]),
    # ---------------- wages ----------------
    ("wages", ["wages", "salary", "payment of wages"],
     ["tankhwah", "tankhwa", "tankha", "tankhah", "tankhuwa", "tankhawa", "tankhwahh", "salary", "salry", "saleri", "sallary", "maash", "maashi", "pay", "paisay", "paise", "paisa", "payment"],
     ["تنخواہ", "تنخوا", "تنخواه", "سیلری", "سیلری", "ماہانہ", "پیسے", "پیسہ", "ادائیگی"]),
    ("wages", ["wages", "minimum wage", "worker"],
     ["ujrat", "ujrath", "mazdoori", "mazdori", "dihari", "dehari", "daily wage", "wage", "wages"],
     ["اجرت", "اجرتیں", "مزدوری", "دہاڑی", "دیہاڑی"]),
    ("wages", ["minimum wage", "minimum rate of wages"],
     ["kam az kam", "kam se kam", "minimum wage", "minimum", "min wage"],
     ["کم از کم", "کم سے کم", "مینیمم"]),
    ("wages", ["unpaid wages", "non-payment of wages", "deduction from wages"],
     ["nahi mili", "nahi di", "nahin mili", "nahi mila", "nahi milay", "rok li", "roka", "kaat liya", "kaat li", "katauti", "kat gaya", "unpaid"],
     ["نہیں ملی", "نہیں ملا", "نہیں دی", "روک لی", "روکی", "کاٹ لی", "کٹوتی", "کٹ گئی"]),
    ("wages", ["overtime", "wages"],
     ["overtime", "over time"],
     ["اوور ٹائم", "اوورٹائم"]),
    ("wages", ["worker", "employer", "domestic worker"],
     ["mazdoor", "mazdur", "worker", "workers", "labour", "labor", "naukar", "naukrani", "maid", "masi", "domestic", "karigar"],
     ["مزدور", "ورکر", "لیبر", "ملازم", "نوکرانی", "ماسی", "گھریلو", "کاریگر"]),
    ("wages", ["labour department", "labour inspector"],
     ["labour department", "labor department", "labour office", "mehkama mehnat"],
     ["لیبر ڈیپارٹمنٹ", "محکمہ محنت", "لیبر آفس"]),
    (None, ["monthly", "month"],
     ["mahina", "mahine", "mahinay", "mahinon", "month", "months", "maheena"],
     ["مہینہ", "مہینے", "مہینوں", "ماہ"]),
    # ---------------- property ----------------
    ("property", ["property", "land", "ownership", "possession"],
     ["zameen", "zamin", "zameen", "jaidad", "jayedad", "jaydad", "jaaidaad", "property", "plot", "makan", "ghar", "house", "khet", "zarai", "land"],
     ["زمین", "جائیداد", "جایداد", "پلاٹ", "مکان", "گھر", "کھیت", "پراپرٹی"]),
    ("property", ["inheritance", "share", "legal heirs"],
     ["wirasat", "virasat", "warasat", "mirath", "miraas", "hissa", "hissay", "hisa", "hisay", "share", "inheritance", "wirsa", "virsa", "heir", "heirs"],
     ["وراثت", "میراث", "حصہ", "حصے", "ورثہ", "ورثاء", "وارث"]),
    ("property", ["brother", "legal heirs", "deprived of property"],
     ["bhai", "bhaiyon", "bhaion", "walid", "waalid", "baap", "abu", "baba", "father", "dada", "chacha", "taya", "susral", "sasural", "saas", "sasur"],
     ["بھائی", "بھائیوں", "والد", "باپ", "ابو", "بابا", "دادا", "چچا", "تایا", "سسرال", "ساس", "سسر"]),
    ("property", ["possession", "dispossession", "deprived of property", "illegal occupation"],
     ["qabza", "kabza", "qabzah", "qabza kar", "hadap", "hadap liya", "occupy", "occupied"],
     ["قبضہ", "قبضے", "ہڑپ", "ہتھیا"]),
    ("property", ["deprived of property", "denied share", "complaint to ombudsperson"],
     ["mehroom", "mahroom", "nahi de rahe", "nahi dete", "hissa nahi", "hisa nahi", "chheen", "chheen liya", "dhoka", "dhoke"],
     ["محروم", "نہیں دے رہے", "نہیں دیتے", "چھین", "چھین لیا", "دھوکہ", "دھوکے"]),
    ("property", ["ombudsperson", "civil court", "complaint"],
     ["patwari", "registry", "intiqal", "intiqaal", "fard", "revenue"],
     ["پٹواری", "رجسٹری", "انتقال", "فرد", "ریونیو"]),
    (None, ["court", "civil court", "pending proceedings"],
     ["court", "adalat", "kachehri", "kachahri", "civil court", "case", "muqadma", "muqaddama", "stay", "hukm imtinai"],
     ["عدالت", "کورٹ", "کچہری", "کیس", "مقدمہ", "اسٹے", "حکم امتناعی"]),
]

# Words that mean the question is about something the app does not cover. Used only as a guard (never to answer).
OUT_OF_SCOPE_CUES = [
    "talaq", "talak", "khula", "khulla", "nafaqa", "nafqa", "custody", "jahez", "dowry", "divorce", "tax", "visa",
    "passport", "nikah", "rishta", "mehr", "haq mehr", "loan", "inheritance shares",
    "طلاق", "خلع", "نفقہ", "جہیز", "حق مہر", "ٹیکس", "ویزا", "پاسپورٹ", "نکاح", "رشتہ", "قرض",
]

# Places that tell us the province (Roman and Urdu script).
PLACES: dict[str, list[str]] = {
    "punjab": ["punjab", "lahore", "faisalabad", "multan", "rawalpindi", "gujranwala", "sialkot", "bahawalpur", "sargodha", "gujrat", "sahiwal",
               "پنجاب", "لاہور", "فیصل آباد", "ملتان", "راولپنڈی", "گوجرانوالہ", "سیالکوٹ", "بہاولپور", "سرگودھا", "گجرات", "ساہیوال"],
    "sindh": ["sindh", "karachi", "hyderabad", "sukkur", "larkana", "mirpurkhas", "nawabshah",
              "سندھ", "کراچی", "حیدرآباد", "سکھر", "لاڑکانہ", "میرپورخاص", "نواب شاہ"],
    "kp": ["kpk", "khyber", "peshawar", "mardan", "swat", "abbottabad", "kohat", "mansehra", "pakhtunkhwa",
           "کے پی", "خیبر", "پشاور", "مردان", "سوات", "ایبٹ آباد", "کوہاٹ", "مانسہرہ", "پختونخوا"],
    "balochistan": ["balochistan", "quetta", "gwadar", "turbat", "بلوچستان", "کوئٹہ", "گوادر", "تربت"],
    "ict": ["islamabad", "isb", "اسلام آباد"],
}

# English words that appear inside Roman Urdu text: their presence marks a code-mixed message.
ENGLISH_LOANWORDS = {
    "manager", "boss", "office", "company", "factory", "salary", "harass", "harassment", "harassed", "complaint", "case", "court",
    "job", "message", "messages", "property", "share", "plot", "overtime", "worker", "contract", "lawyer", "police", "hr", "report",
    "supervisor", "college", "school", "bank", "legal", "help", "problem", "mobile", "photo", "call", "minimum", "wage", "wages",
}

# Common Roman Urdu function words (how Urdu is typed in Latin letters) versus common English function words.
_ROMAN_FUNCTION = {
    "mera", "meri", "mere", "mujhe", "mujh", "mujhse", "hum", "hamara", "hamari", "aap", "aapka", "aapki", "tum", "tumhara", "hai", "hain",
    "hoon", "hun", "tha", "thi", "thay", "the", "nahi", "nahin", "na", "kya", "kyun", "kyu", "kaise", "kaun", "kahan", "kab", "ko", "ka", "ki",
    "ke", "se", "mein", "main", "me", "par", "pe", "aur", "ya", "lekin", "magar", "kar", "karta", "karti", "karte", "kiya", "kiye", "rahi",
    "raha", "rahe", "sakta", "sakti", "sakte", "chahiye", "chahta", "chahti", "agar", "to", "bhi", "sirf", "bahut", "zyada", "kuch", "koi",
    "yeh", "ye", "woh", "wo", "is", "us", "un", "ne", "jo", "jab", "tab", "abhi", "phir", "mujhay", "usne", "unhon", "dete", "deta", "deti",
    "gaya", "gayi", "gaye", "mili", "mila", "milay", "liya", "li", "diya", "di", "wala", "wali", "kuchh", "apne", "apni", "apna", "inko",
    "unko", "unka", "unki", "humein", "hamein", "mahine", "saal", "din", "bata", "batao", "batain", "karna", "karni", "karein", "hota", "hoti",
}
_ENGLISH_FUNCTION = {
    "the", "is", "are", "was", "were", "and", "my", "me", "i", "you", "he", "she", "it", "they", "what", "how", "can", "do", "does", "did",
    "have", "has", "had", "not", "to", "of", "in", "on", "for", "with", "at", "by", "from", "this", "that", "will", "would", "should",
    "could", "am", "be", "been", "if", "but", "or", "so", "keeps", "took", "get", "got", "make", "makes", "his", "her", "their", "our",
}


# --------------------------------------------------------------------------------------------------------------
# Normalisation and indexes
# --------------------------------------------------------------------------------------------------------------
_WORD = re.compile(r"[a-z0-9']+|[؀-ۿ]+")
_URDU_LETTER = re.compile(r"[؀-ۿ]")
_LATIN_LETTER = re.compile(r"[a-z]")


def _collapse(token: str) -> str:
    """Roman spelling is not fixed: tankhwaah / tankhwah, mazdoori / mazdori. Collapse doubled letters."""
    return re.sub(r"(.)\1+", r"\1", token)


def _tokens(text: str) -> list[str]:
    return _WORD.findall(normalize(text))


_INDEX: dict[str, int] = {}  # single-word variant -> concept index
_PHRASES: list[tuple[str, int]] = []  # multi-word variant -> concept index
for _i, (_topic, _en, _roman, _urdu) in enumerate(CONCEPTS):
    for _v in _roman:
        _words = _WORD.findall(normalize(_v))
        if len(_words) == 1:
            _INDEX.setdefault(_collapse(_words[0]), _i)
        elif _words:
            _PHRASES.append((" ".join(_collapse(w) for w in _words), _i))
    for _v in _urdu:
        _words = _WORD.findall(normalize(_v))
        if len(_words) == 1:
            _INDEX.setdefault(_words[0], _i)
        elif _words:
            _PHRASES.append((" ".join(_words), _i))
_FUZZY_KEYS = [k for k in _INDEX if k.isascii() and len(k) >= 5]
_OOS = {" ".join(_collapse(w) if w.isascii() else w for w in _WORD.findall(normalize(c))) for c in OUT_OF_SCOPE_CUES}
_PLACE_INDEX: dict[str, str] = {}
for _prov, _names in PLACES.items():
    for _n in _names:
        _PLACE_INDEX[" ".join(_collapse(w) if w.isascii() else w for w in _WORD.findall(normalize(_n)))] = _prov


# --------------------------------------------------------------------------------------------------------------
# Register detection: how did the person write or speak?
# --------------------------------------------------------------------------------------------------------------
@dataclass
class Register:
    script: str  # "urdu" | "roman" | "english"
    code_mixed: bool  # Urdu and English words in the same message, in either script
    language: str  # what Detected.language carries: "ur" | "roman_ur" | "en" | "mixed"

    @property
    def wants_roman_answer(self) -> bool:
        """Latin-letter Urdu in, Latin-letter Urdu out."""
        return self.script == "roman"


def detect_register(text: str) -> Register:
    n = normalize(text)
    urdu = len(_URDU_LETTER.findall(n))
    latin = len(_LATIN_LETTER.findall(n))
    words = [w for w in _WORD.findall(n) if w.isascii()]
    roman_hits = sum(1 for w in words if w in _ROMAN_FUNCTION and w not in _ENGLISH_FUNCTION)
    english_hits = sum(1 for w in words if w in _ENGLISH_FUNCTION)
    loanwords = sum(1 for w in words if w in ENGLISH_LOANWORDS)

    if urdu and urdu >= latin:  # Urdu script dominates
        mixed = latin >= 4 and len(words) >= 1  # English words typed in Latin letters inside Urdu text
        return Register("urdu", mixed, "mixed" if mixed else "ur")
    if urdu:  # Latin dominates but there is Urdu script too
        return Register("roman" if roman_hits else "english", True, "mixed")
    if roman_hits >= 1 and roman_hits >= english_hits:
        return Register("roman", loanwords > 0 or english_hits > 0, "roman_ur")
    return Register("english", False, "en")


# --------------------------------------------------------------------------------------------------------------
# Lexicon analysis
# --------------------------------------------------------------------------------------------------------------
@dataclass
class LexiconHits:
    topic: Optional[str] = None
    topic_scores: dict[str, int] = field(default_factory=dict)
    terms: list[str] = field(default_factory=list)
    jurisdiction: Optional[str] = None
    out_of_scope: bool = False
    matched: list[str] = field(default_factory=list)

    @property
    def strong(self) -> bool:
        """At least two independent cues for the chosen topic: safe to override a model that said 'other'."""
        return bool(self.topic) and self.topic_scores.get(self.topic, 0) >= 2 and not self.out_of_scope


def analyze(text: str) -> LexiconHits:
    toks = _tokens(text)
    ctoks = [_collapse(t) if t.isascii() else t for t in toks]
    joined = " ".join(ctoks)
    hit_ids: list[int] = []
    matched: list[str] = []

    for tok, c in zip(toks, ctoks):
        idx = _INDEX.get(c)
        if idx is None and c.isascii() and len(c) >= 5:  # spelling variant we have not listed: fuzzy match
            close = difflib.get_close_matches(c, _FUZZY_KEYS, n=1, cutoff=0.82)
            idx = _INDEX[close[0]] if close else None
        if idx is not None:
            hit_ids.append(idx)
            matched.append(tok)
    for phrase, idx in _PHRASES:
        if phrase in joined:
            hit_ids.append(idx)
            matched.append(phrase)

    scores: dict[str, int] = {}
    terms: list[str] = []
    for idx in dict.fromkeys(hit_ids):
        topic, en, _r, _u = CONCEPTS[idx]
        if topic:
            scores[topic] = scores.get(topic, 0) + 1
        terms += [t for t in en if t not in terms]

    best = None
    if scores:
        top = max(scores.values())
        leaders = [t for t, s in scores.items() if s == top]
        best = leaders[0] if len(leaders) == 1 else None

    province = None
    for place, prov in _PLACE_INDEX.items():
        if place in joined.split() or (" " in place and place in joined):
            province = prov
            break
    oos = any((cue in joined.split()) or (" " in cue and cue in joined) for cue in _OOS)
    return LexiconHits(topic=best, topic_scores=scores, terms=terms[:14], jurisdiction=province, out_of_scope=oos, matched=matched)


# --------------------------------------------------------------------------------------------------------------
# Keeping the Urdu-script answer free of Latin letters (needed for text-to-speech and for right-to-left layout)
# --------------------------------------------------------------------------------------------------------------
URDU_FOR_ENGLISH: dict[str, str] = {
    "federal ombudsperson": "وفاقی محتسب", "ombudsperson": "محتسب", "ombudsman": "محتسب", "ombudspersons": "محتسب",
    "inquiry committee": "انکوائری کمیٹی", "enquiry committee": "انکوائری کمیٹی", "committee": "کمیٹی",
    "competent authority": "مجاز اتھارٹی", "authority": "اتھارٹی", "show cause notice": "وجہ بتاؤ نوٹس", "show cause": "وجہ بتاؤ",
    "show-cause": "وجہ بتاؤ", "notice": "نوٹس", "appeal": "اپیل", "representation": "نمائندگی",
    "harassment": "ہراسانی", "complaint": "شکایت", "complaints": "شکایات", "complainant": "شکایت کنندہ",
    "employer": "آجر", "employers": "آجر", "employee": "ملازم", "employees": "ملازمین", "worker": "مزدور", "workers": "مزدور",
    "salary": "تنخواہ", "wages": "اجرت", "wage": "اجرت", "minimum wage": "کم از کم اجرت", "overtime": "اوور ٹائم",
    "labour department": "محکمہ محنت", "labor department": "محکمہ محنت", "labour court": "لیبر کورٹ", "labour": "لیبر",
    "civil court": "سول کورٹ", "high court": "ہائیکورٹ", "court": "عدالت", "deputy commissioner": "ڈپٹی کمشنر",
    "section": "دفعہ", "schedule": "شیڈول", "act": "ایکٹ", "office": "آفس", "manager": "مینیجر", "company": "کمپنی",
    "factory": "فیکٹری", "hr": "ایچ آر", "police": "پولیس", "fir": "ایف آئی آر", "lawyer": "وکیل",
    "possession": "قبضہ", "ownership": "ملکیت", "property": "جائیداد", "inheritance": "وراثت", "helpline": "ہیلپ لائن",
    "helplines": "ہیلپ لائنز", "whatsapp": "واٹس ایپ", "message": "میسج", "messages": "میسجز",
}
_URDUIZE_TERMS = sorted(URDU_FOR_ENGLISH, key=len, reverse=True)
_TERM_RX = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(t) for t in _URDUIZE_TERMS) + r")(?![A-Za-z])", re.IGNORECASE)
# An English Act name: capitalised words (with small connectors) ending in "Act", optionally followed by a year.
_ACT_NAME_RX = re.compile(
    r"(?:(?:[A-Z][A-Za-z\u2019'\-]*|of|and|the|for|in|against|at|to|on)[ \t]+){1,14}Act\b,?(?:[ \t]*\(?(\d{4})\)?)?"
)
_LATIN_WORD = re.compile(r"(?<![0-9])[A-Za-z][A-Za-z\u2019'\-]*")
_LATIN_BRACKETS = re.compile(r"\s*[(\[]\s*[A-Za-z][A-Za-z0-9 ,.'\u2019\-/&]*[)\]]")


def urduize(text: str) -> str:
    """Make an Urdu-script answer contain no Latin letters. The composer is told to write Urdu only, but models slip
    ("آپ Ombudsperson کو شکایت کر سکتے ہیں"), and English words inside right-to-left text scramble the line and are read
    out wrongly by text-to-speech. Steps, in order: bracketed English is dropped; an English Act name becomes "ایکٹ <year>"
    (the exact name is always shown in the citation); known legal and everyday terms are written in Urdu script
    (Ombudsperson -> محتسب); any other Latin word is dropped. Digits and Urdu text are untouched."""
    out = _LATIN_BRACKETS.sub("", text)
    out = _ACT_NAME_RX.sub(lambda m: f"ایکٹ {m.group(1)}" if m.group(1) else "ایکٹ", out)
    out = _TERM_RX.sub(lambda m: URDU_FOR_ENGLISH[m.group(1).lower()], out)
    out = _LATIN_WORD.sub("", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([،۔؟!,.])", r"\1", out)
    return out.strip()
