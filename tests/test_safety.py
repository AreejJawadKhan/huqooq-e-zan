import pytest

from backend.app.safety import detect_danger, is_danger


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
