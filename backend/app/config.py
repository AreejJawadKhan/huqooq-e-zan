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

# Retrieval defaults live here (not inline) so the eval gate can fingerprint them.
DEFAULT_MIN_SCORE = 1.0
DEFAULT_TOP_K = 5


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
    # Per-stage provider. ANALYZER_PROVIDER / ANSWER_PROVIDER: empty or "auto" = the default routing in
    # providers.DEFAULT_CHAINS (fast Groq for the analyzer, Gemini for the answer); "same" = follow LLM_PROVIDER;
    # or a provider name to force that stage. Providers without a key are skipped.
    analyzer_provider_setting: str = field(default_factory=lambda: os.getenv("ANALYZER_PROVIDER", "").strip().lower())
    answer_provider_setting: str = field(default_factory=lambda: os.getenv("ANSWER_PROVIDER", "").strip().lower())
    # HEALTH_DEEP=1 lets GET /api/health?deep=1 make one tiny real call per configured model (cached for 60 s).
    health_deep: bool = field(default_factory=lambda: os.getenv("HEALTH_DEEP", "0") == "1")
    chunks_path: Path = field(
        default_factory=lambda: Path(os.getenv("CHUNKS_PATH", str(DATA_DIR / "processed" / "chunks.jsonl")))
    )
    wages_path: Path = DATA_DIR / "wages.json"
    referrals_path: Path = DATA_DIR / "referrals.json"
    # BM25 score below this means "nothing relevant found" -> refuse instead of guessing.
    # Tune with scripts/run_eval.py and GET /api/debug/search (needs DEBUG=1).
    min_score: float = field(default_factory=lambda: float(os.getenv("MIN_SCORE", str(DEFAULT_MIN_SCORE))))
    top_k: int = field(default_factory=lambda: int(os.getenv("TOP_K", str(DEFAULT_TOP_K))))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "0") == "1")
    # DEMO_CACHE=1 serves pre-computed answers for the exact demo questions (data/demo_cache.json) so a
    # rate-limited or offline free tier cannot break the live demo. Danger messages never use the cache.
    demo_cache: bool = field(default_factory=lambda: os.getenv("DEMO_CACHE", "0") == "1")
    demo_cache_path: Path = DATA_DIR / "demo_cache.json"
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

    def stage_chain(self, stage: str) -> list[str]:
        """Providers to try, in order, for a pipeline stage ("analyzer" or "answer"). Only providers with a key."""
        from .providers import DEFAULT_CHAINS

        explicit = {"analyzer": self.analyzer_provider_setting, "answer": self.answer_provider_setting}[stage]
        if explicit in ("", "auto") and not self.llm_provider_setting:
            order = list(DEFAULT_CHAINS[stage])
        else:
            lead = explicit if explicit not in ("", "auto", "same") else self.llm_provider
            order = [lead, self.llm_provider, *self.llm_fallbacks]
        return [n for n in dict.fromkeys(order) if self.api_key_for(n)]

    def models_for(self, name: str) -> tuple[str, str]:
        """(analyzer, answer) model names. Override with e.g. GEMINI_ANALYZER_MODEL / GEMINI_ANSWER_MODEL."""
        from .providers import DEFAULT_MODELS

        analyzer, answer = DEFAULT_MODELS[name]
        up = name.upper()
        return os.getenv(f"{up}_ANALYZER_MODEL", analyzer), os.getenv(f"{up}_ANSWER_MODEL", answer)


def get_settings() -> Settings:
    return Settings()
