import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import pytest  # noqa: E402

_ENV_TO_CLEAR = (
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "LLM_PROVIDER", "LLM_FALLBACK",
    "DEMO_CACHE", "DEBUG", "GEMINI_ANALYZER_MODEL", "GEMINI_ANSWER_MODEL", "GROQ_ANALYZER_MODEL", "GROQ_ANSWER_MODEL",
)


@pytest.fixture(autouse=True)
def _no_real_keys_or_provider_settings(monkeypatch):
    """config.py loads .env at import, so on a developer machine every Settings() would hold real keys and a test
    could make live model calls (spending quota and giving different results per machine). Tests that need a key pass
    one explicitly."""
    for name in _ENV_TO_CLEAR:
        monkeypatch.delenv(name, raising=False)
