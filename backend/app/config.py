"""Central settings. Everything tunable lives here or in .env (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

load_dotenv(ROOT / ".env")


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    # Small/fast model for query analysis, stronger model for the grounded answer.
    analyzer_model: str = field(default_factory=lambda: os.getenv("ANALYZER_MODEL", "claude-haiku-5-5"))
    answer_model: str = field(default_factory=lambda: os.getenv("ANSWER_MODEL", "claude-sonnet-5-5"))
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


def get_settings() -> Settings:
    return Settings()
