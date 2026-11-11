#!/usr/bin/env python3
"""Build data/demo_cache.json from data/demo_questions.yaml using the REAL pipeline (needs a model key).

    python scripts/build_demo_cache.py            # (re)build every entry
    python scripts/build_demo_cache.py --check    # only list which questions are missing from the cache

Review the output before the demo: a cached answer is shown exactly as stored. Danger questions are skipped
on purpose because danger always takes the deterministic path.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import get_settings  # noqa: E402
from backend.app.demo_cache import cache_key  # noqa: E402
from backend.app.safety import detect_danger  # noqa: E402
from backend.app.schemas import AskRequest  # noqa: E402

QUESTIONS = ROOT / "data" / "demo_questions.yaml"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report missing entries without calling a model")
    args = ap.parse_args()

    settings = get_settings()
    items = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    existing = json.loads(settings.demo_cache_path.read_text(encoding="utf-8")) if settings.demo_cache_path.exists() else {}

    if args.check:
        missing = [i["q"] for i in items if cache_key(i["q"], i.get("jurisdiction")) not in existing]
        print(f"{len(items) - len(missing)}/{len(items)} cached")
        for q in missing:
            print("  missing:", q)
        return 1 if missing else 0

    if not settings.any_llm_key:
        print("No model API key set. Add GEMINI_API_KEY or GROQ_API_KEY to .env first.", file=sys.stderr)
        return 2

    from backend.app.main import build_pipeline

    pipeline = build_pipeline(settings)
    out: dict[str, dict] = {}
    for item in items:
        q, j = item["q"], item.get("jurisdiction")
        if detect_danger(q):
            print("skip (danger always live):", q)
            continue
        res = pipeline.ask(AskRequest(question=q, jurisdiction=j))
        out[cache_key(q, j)] = res.model_dump(mode="json")
        print(f"{res.status:13s} {len(res.citations)} cites  {q[:60]}")

    settings.demo_cache_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(out)} answers to {settings.demo_cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
