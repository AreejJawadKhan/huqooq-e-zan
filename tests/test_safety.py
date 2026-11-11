import pytest

from backend.app.safety import detect_danger, is_danger, is_self_harm, normalize


@pytest.mark.parametrize(
    "text",
    [
        "My husband beat me and I am scared tonight.",
        "He threatens to kill me",
        "I want to end my life",
        "mera shohar mujhe maar peet karta hai",
        "wo dhamki deta hai",
        "میرا شوہر مجھے مارتا ہے",
        "مجھے جان کا خطرہ ہے",
    ],
)
def test_danger_detected(text):
    assert is_danger(text), text


@pytest.mark.parametrize(
    "text",
    [
        "My manager keeps sending me unwelcome messages. What can I do?",
        "What is the minimum wage in Lahore?",
        "My brothers took my share of our father's land.",
        "Can a man file a harassment complaint?",
    ],
)
def test_normal_questions_not_flagged(text):
    assert detect_danger(text) == [], text


# ---- Added after a review found 11 of 12 serious phrasings undetected (Arabic-keyboard Urdu, self-harm,
# ---- sexual violence, coercion, Roman Urdu threats). Every line here must raise the danger banner.
MUST_FLAG = [
    # Urdu
    "وہ مجھے مار ڈالے گا",
    "میں مرنا چاہتی ہوں",
    "میں جینا نہیں چاہتی",
    "اس نے مجھے کمرے میں بند کر دیا",
    "وہ مجھے بلیک میل کر رہا ہے",
    "میرے ساتھ عصمت دری ہوئی",
    "وہ زبردستی شادی کروا رہے ہیں",
    "وہ مجھے دھمکیاں دیتا ہے",
    "میرا شوہر مجھے مار پیٹ کرتا ہے",
    # English
    "I don't want to live anymore",
    "I want to die",
    "my boss sexually assaulted me yesterday",
    "he grabbed me and molested me in the office",
    "he is blackmailing me with my private photos",
    "my in-laws locked me in a room and took my phone",
    "they are forcing me to marry my cousin",
    "he held a knife to me",
    "he said he will kill me",
    # Roman Urdu
    "woh mujhe maar dalega",
    "usne kaha jaan se maar dunga",
    "main apni jaan dena chahti hoon",
    "main marna chahti hoon",
    "woh mujhe blackmail kar raha hai",
]

# Ordinary questions inside the app's scope. Flagging these would hide the legal answer behind a danger banner.
MUST_NOT_FLAG = [
    "He sexually harassed me at work. What can I do?",
    "My employer forced me to resign without notice",
    "My manager forced me to work overtime without pay",
    "My employer won't let me leave the job before my contract ends",
    "I don't want to live with my in-laws, can I get my share of the house?",
    "The company locked me out of the office email after I complained",
    "Can the employer hold back my salary for three months?",
    "My brothers took my share of our father's land in Lahore.",
    "What is the minimum wage in Karachi?",
    "Mujhe 3 mahine se tankhwah nahi mili.",
    "میرا مینیجر مجھے کام پر تنگ کرتا ہے، میں کیا کر سکتی ہوں؟",
    "پنجاب میں کم از کم اجرت کتنی ہے؟",
    "میرے بھائی مجھے والد کی زمین میں حصہ نہیں دے رہے",
]


def _arabic_keyboard(text: str) -> str:
    """The same Urdu as typed on an Arabic-layout keyboard: Arabic yeh, kaf and heh instead of the Urdu letters."""
    return text.replace("\u06cc", "\u064a").replace("\u06a9", "\u0643").replace("\u06c1", "\u0647")


@pytest.mark.parametrize("text", MUST_FLAG)
def test_serious_phrasings_are_flagged(text):
    assert is_danger(text), text


@pytest.mark.parametrize("text", [t for t in MUST_FLAG if any("\u0600" <= ch <= "\u06ff" for ch in t)])
def test_urdu_phrasings_are_flagged_with_arabic_keyboard_letters(text):
    typed = _arabic_keyboard(text)
    assert typed != text or "ی" not in text  # the variant really differs when it can
    assert is_danger(typed), typed


@pytest.mark.parametrize("text", MUST_NOT_FLAG)
def test_ordinary_in_scope_questions_are_not_flagged(text):
    assert detect_danger(text) == [], text


def test_normalize_unifies_variants_and_drops_invisible_characters():
    assert normalize("مار\u200cپ\u064aٹ") == normalize("مارپیٹ")  # ZWNJ + Arabic yeh
    assert normalize("دھم\u0643ی") == normalize("دھمکی")  # Arabic kaf
    assert normalize("مار\u0640\u0640 پ\u0650یٹ") == normalize("مار پیٹ")  # tatweel and a diacritic
    assert normalize("I DON\u2019T want to live ANYMORE") == "i don't want to live anymore"  # curly quote, case


def test_self_harm_is_distinguished_from_violence_against_her():
    assert is_self_harm("I want to die") and is_self_harm("میں مرنا چاہتی ہوں") and is_self_harm("main marna chahti hoon")
    assert not is_self_harm("My husband beat me and I am scared tonight.")
    assert not is_self_harm("What is the minimum wage in Lahore?")
