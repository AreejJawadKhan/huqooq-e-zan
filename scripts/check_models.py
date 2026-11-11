#!/usr/bin/env python3
"""Check that every configured model name still works. Model names get retired without warning (Gemini 2.5 and
Groq Llama 3.x both vanished), and a dead fallback is invisible until the primary also fails.

    python scripts/check_models.py          # one real forced tool call per configured model (a few tokens each)
    python scripts/check_models.py --list   # also print the model names each provider offers right now

Being LISTED does not mean a model works for your key (gemini-2.5-flash-lite is listed but returns 404 for new
accounts), so the smoke test is a real call. Exit code 1 if any configured model fails; HTTP 429 (quota exhausted) is
reported separately because the name is fine. The same check is available live at /api/health?deep=1 (HEALTH_DEEP=1).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import PROVIDER_ORDER, get_settings  # noqa: E402
from backend.app.providers import describe_stages, smoke_test  # noqa: E402


def list_models(name: str, key: str) -> list[str]:
    try:
        if name == "groq":
            r = httpx.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=20)
            r.raise_for_status()
            return sorted(m["id"] for m in r.json()["data"] if m.get("active", True))
        if name == "gemini":
            r = httpx.get(
                "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                headers={"x-goog-api-key": key},
                timeout=20,
            )
            r.raise_for_status()
            return sorted(
                m["name"].split("/")[-1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])
            )
    except Exception as exc:  # noqa: BLE001
        return [f"(could not list: {type(exc).__name__})"]
    return ["(listing not supported for this provider)"]


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="also print the models each provider offers")
    args = ap.parse_args()

    settings = get_settings()
    if not settings.any_llm_key:
        print("No provider key set. Add GEMINI_API_KEY, GROQ_API_KEY or ANTHROPIC_API_KEY to .env.", file=sys.stderr)
        return 2

    print("Routing (first = tried first):")
    for stage, rows in describe_stages(settings).items():
        print(f"  {stage:8s} " + " -> ".join(f"{r['provider']}:{r['model']}" for r in rows))
    print()

    rows = smoke_test(settings)
    failed = limited = 0
    current = None
    for r in rows:
        if r["provider"] != current:
            current = r["provider"]
            print(current)
        if r["status"] == "ok":
            print(f"  OK    {r['stage']:8s} {r['model']}")
        elif r["status"] == "limited":
            limited += 1
            print(f"  LIMIT {r['stage']:8s} {r['model']}  name is valid but the quota is exhausted (HTTP 429)")
        else:
            failed += 1
            print(f"  FAIL  {r['stage']:8s} {r['model']}  {r.get('error', '')}")
    if args.list:
        for name in PROVIDER_ORDER:
            if settings.api_key_for(name):
                print(f"{name} offers:", ", ".join(list_models(name, settings.api_key_for(name))))
    if limited:
        print(f"{limited} model(s) are rate-limited right now: the names are fine, retry later or use another key/provider.")
    if failed:
        print(f"{failed} configured model(s) FAILED: fix the names in .env or providers.py.")
    elif not limited:
        print("All configured models work.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
