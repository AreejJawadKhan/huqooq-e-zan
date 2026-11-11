#!/usr/bin/env python3
"""Check that every configured model name still works. Model names get retired without warning (Gemini 2.5 and
Groq Llama 3.x both vanished), and a dead fallback is invisible until the primary also fails.

    python scripts/check_models.py          # one real forced tool call per configured model (a few tokens each)
    python scripts/check_models.py --list   # also print the model names each provider offers right now

Being LISTED does not mean a model works for your key (gemini-2.5-flash-lite is listed but returns 404 for new
accounts), so the smoke test is a real call. Exit code 1 if any configured model fails.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import PROVIDER_ORDER, get_settings  # noqa: E402
from backend.app.providers import build_provider  # noqa: E402

PING_TOOL = {
    "name": "ping",
    "description": "Report that the model is reachable.",
    "input_schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
}


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
    configured = [n for n in PROVIDER_ORDER if settings.api_key_for(n)]
    if not configured:
        print("No provider key set. Add GEMINI_API_KEY, GROQ_API_KEY or ANTHROPIC_API_KEY to .env.", file=sys.stderr)
        return 2

    failed = limited = 0
    for name in configured:
        analyzer, answer = settings.models_for(name)
        role = "primary" if name == settings.llm_provider else "fallback"
        print(f"{name} ({role})")
        llm = build_provider(name, settings)
        for stage, model in (("analyzer", analyzer), ("answer", answer)):
            try:
                out = llm._tool_call(model, "Call the ping tool with ok=true.", "ping", PING_TOOL, max_tokens=50)  # type: ignore[union-attr]
                print(f"  OK    {stage:8s} {model}" + ("" if out.get("ok") is True else f"  (unexpected args {out})"))
            except Exception as exc:  # noqa: BLE001 - report every failure, do not stop at the first
                if "HTTP 429" in str(exc):
                    # The name was accepted; the account is out of quota. Not a dead model, so not a failure.
                    limited += 1
                    print(f"  LIMIT {stage:8s} {model}  name is valid but the quota is exhausted (HTTP 429)")
                    continue
                failed += 1
                print(f"  FAIL  {stage:8s} {model}  {type(exc).__name__}: {str(exc)[:160]!r}")
        if args.list:
            print("  offered:", ", ".join(list_models(name, settings.api_key_for(name))))
    if limited:
        print(f"{limited} model(s) are rate-limited right now: the names are fine, retry later or use another key/provider.")
    if failed:
        print(f"{failed} configured model(s) FAILED: fix the names in .env or providers.py.")
    elif not limited:
        print("All configured models work.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
