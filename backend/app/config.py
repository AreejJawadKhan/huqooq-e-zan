"""Central settings. Everything tunable lives here or in .env (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

load_dotenv(ROOT / ".env")

PROVIDER_ORDER = ("gemini", "groq", "anthropic")


def _split(value: str) -> list[str]:
    return [v.strip().lower() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_url: str = field(
        default_factory=lambda: os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
    )
    # LLM_PROVIDER: gemini | groq | anthropic. Empty = first provider that has a key (in that order).
    # LLM_FALLBACK: comma-separated providers tried, in order, when the primary fails.
    # Empty = every other provider that has a key.
    llm_provider_setting: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "").strip().lower())
    llm_fallback_setting: str = field(default_factory=lambda: os.getenv("LLM_FALLBACK", "").strip().lower())
    chunks_path: Path = field(
        default_factory=lambda: Path(os.getenv("CHUNKS_PATH", str(DATA_DIR / "processed" / "chunks.jsonl")))
    )
    wages_path: Path = DATA_DIR / "wages.json"
    referrals_path: Path = DATA_DIR / "referrals.json"
    # BM25 score below this means "nothing relevant found" -> refuse instead of guessing.
    # Tune with scripts/run_eval.py and GET /api/debug/search (needs DEBUG=1).
    min_score: float = field(default_factory=lambda: float(os.getenv("MIN_SCORE", "1.0")))
    top_k: int = field(default_factory=lambda: int(os.getenv("TOP_K", "5")))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "0") == "1")
    cors_origins: list[str] = field(
        default_factory=lambda: _split(os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
    )

    def api_key_for(self, name: str) -> str:
        return {"gemini": self.gemini_api_key, "groq": self.groq_api_key, "anthropic": self.anthropic_api_key}.get(
            name, ""
        )

    @property
    def any_llm_key(self) -> bool:
        return any(self.api_key_for(n) for n in PROVIDER_ORDER)

    @property
    def llm_provider(self) -> str:
        if self.llm_provider_setting:
            return self.llm_provider_setting
        return next((n for n in PROVIDER_ORDER if self.api_key_for(n)), "gemini")

    @property
    def llm_fallbacks(self) -> list[str]:
        explicit = _split(self.llm_fallback_setting)
        if explicit:
            return explicit
        return [n for n in PROVIDER_ORDER if self.api_key_for(n) and n != self.llm_provider]

    def models_for(self, name: str) -> tuple[str, str]:
        """(analyzer, answer) model names. Override with e.g. GEMINI_ANALYZER_MODEL / GEMINI_ANSWER_MODEL."""
        from .providers import DEFAULT_MODELS

        analyzer, answer = DEFAULT_MODELS[name]
        up = name.upper()
        return os.getenv(f"{up}_ANALYZER_MODEL", analyzer), os.getenv(f"{up}_ANSWER_MODEL", answer)


def get_settings() -> Settings:
    return Settings()
