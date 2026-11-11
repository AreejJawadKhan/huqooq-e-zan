"""Roman Urdu / Urdu-script / code-mixed understanding without a model. Add a row here for every lexicon row you add."""
import pytest

from backend.app.lexicon import analyze, detect_register


@pytest.mark.parametrize(
    "text, topic, province",
    [
        # Roman Urdu, including the English words people mix in
        ("mera manager mujhe harass kar raha hai office mein", "harassment", None),
        ("mujhe 3 mahine se tankhwaah nahi mili, factory Lahore mein", "wages", "punjab"),
        ("meri salry kat gayi aur overtime ke paise nahi diye", "wages", None),
        ("mere bhai walid ki zameen mein mera hissa nahi de rahe, Karachi", "property", "sindh"),
        ("kam az kam ujrat kitni hai Peshawar mein", "wages", "kp"),
        ("bhaiyon ne qabza kar liya jaidad par", "property", None),
        # Urdu script with English words typed or transliterated (what voice recognition produces)
        ("میری salary تین مہینے سے نہیں ملی", "wages", None),
        ("سیلری نہیں ملی کراچی کی فیکٹری", "wages", "sindh"),
        ("میرا مینیجر مجھے ہراس کر رہا ہے آفس میں", "harassment", None),
        ("میرے بھائی مجھے والد کی زمین میں حصہ نہیں دے رہے", "property", None),
        ("پنجاب میں کم از کم اجرت کتنی ہے؟", "wages", "punjab"),
        # English still works
        ("What is the minimum wage in Lahore?", "wages", "punjab"),
    ],
)
def test_topic_and_province_from_code_mixed_text(text, topic, province):
    hits = analyze(text)
    assert hits.topic == topic, (text, hits)
    assert hits.jurisdiction == province, (text, hits)
    assert hits.terms, "a recognised message must give the retriever English statute words"


def test_spelling_variants_and_typos_are_understood():
    for spelling in ("tankhwah", "tankhwaah", "tankha", "tankhah", "tankhwa"):
        assert analyze(f"meri {spelling} nahi mili").topic == "wages", spelling
    assert analyze("meri tankhwahh nahi mili").topic == "wages"  # a typo that is not listed: fuzzy match
    assert analyze("mazdoori aur ujrath ka masla").topic == "wages"


def test_strong_means_two_independent_cues():
    assert analyze("zameen mein hissa nahi mila").strong  # property + inheritance cues
    assert not analyze("kya mohtasib ko complaint kar sakti hoon").strong  # generic words only
    assert analyze("kya mohtasib ko complaint kar sakti hoon").topic is None  # ombudsperson alone picks no topic


@pytest.mark.parametrize("text", ["talaq ke baad nafaqa kaise milega", "meri talaq ho gayi aur custody chahiye", "طلاق کے بعد نفقہ"])
def test_out_of_scope_cues_are_flagged_and_never_strong(text):
    hits = analyze(text)
    assert hits.out_of_scope and not hits.strong


def test_chatter_matches_nothing():
    hits = analyze("aaj mausam kaisa hai")
    assert hits.topic is None and hits.terms == [] and not hits.out_of_scope


@pytest.mark.parametrize(
    "text, script, mixed, language",
    [
        ("My manager keeps sending me unwelcome messages", "english", False, "en"),
        ("What is the minimum wage in Lahore?", "english", False, "en"),
        ("میرا مینیجر مجھے کام پر تنگ کرتا ہے", "urdu", False, "ur"),
        ("پنجاب میں کم از کم اجرت کتنی ہے؟", "urdu", False, "ur"),
        ("mere bhai walid ki zameen mein mera hissa nahi de rahe", "roman", False, "roman_ur"),
        ("mera manager mujhe harass kar raha hai office mein", "roman", True, "roman_ur"),
        ("mujhe salary nahi mili, kya complaint kar sakti hoon", "roman", True, "roman_ur"),
        ("میری salary تین مہینے سے نہیں ملی", "urdu", True, "mixed"),
        ("my manager ne mujhe message kiya, mujhe bura laga", "roman", True, "roman_ur"),
    ],
)
def test_register_detection(text, script, mixed, language):
    r = detect_register(text)
    assert (r.script, r.code_mixed, r.language) == (script, mixed, language), text


def test_only_roman_input_wants_a_roman_answer():
    assert detect_register("mera hissa nahi de rahe").wants_roman_answer
    assert not detect_register("میرا حصہ نہیں دے رہے").wants_roman_answer
    assert not detect_register("my share is being withheld").wants_roman_answer


# ---------------------------------------------------------------- urduize: the Urdu-script answer never contains Latin letters
import re as _re

from backend.app.lexicon import urduize


def _latin(s: str) -> int:
    return len(_re.findall("[A-Za-z]", s))


def test_urduize_writes_known_terms_in_urdu_script():
    assert urduize("آپ Ombudsperson یا Inquiry Committee کو شکایت کر سکتے ہیں") == "آپ محتسب یا انکوائری کمیٹی کو شکایت کر سکتے ہیں"
    assert urduize("Section 8 کے تحت Show Cause Notice جاری ہوتا ہے") == "دفعہ 8 کے تحت وجہ بتاؤ نوٹس جاری ہوتا ہے"
    assert urduize("آپ HR اور Manager کو بتائیں") == "آپ ایچ آر اور مینیجر کو بتائیں"


def test_urduize_replaces_an_english_act_name_and_keeps_the_year():
    out = urduize("پنجاب Enforcement of Women's Property Rights Act, 2021 کے تحت شکایت کریں")
    assert "ایکٹ 2021" in out and _latin(out) == 0
    out = urduize("Protection against Harassment of Women at the Workplace Act 2010 لاگو ہے")
    assert out.startswith("ایکٹ 2010") and _latin(out) == 0


def test_urduize_drops_unknown_latin_words_and_keeps_digits_and_urdu():
    out = urduize("رقم 40,000 روپے ہے، mediation کی کوشش کریں")
    assert _latin(out) == 0 and "40,000" in out and "کوشش کریں" in out and "  " not in out


def test_urduize_leaves_clean_urdu_untouched():
    for text in ("دفعہ 11 (ذیلی دفعہ 2) دیکھیں", "رقم (40,000) روپے", "آپ کو اپنی تنخواہ کا حق ہے۔"):
        assert urduize(text) == text


def test_urduize_removes_bracketed_english_like_before():
    assert urduize("شکایت کریں (Inquiry Committee) میں۔") == "شکایت کریں میں۔"
