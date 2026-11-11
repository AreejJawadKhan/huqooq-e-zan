#!/usr/bin/env python3
"""Run tests/test_questions.yaml through the real pipeline (real model calls) and print a pass/fail table.

    python scripts/run_eval.py            # all questions
    python scripts/run_eval.py 5 8 12     # only these ids
    python scripts/run_eval.py -v         # also print English answers
    python scripts/run_eval.py --save     # full run only: record the result in data/eval_baseline.json
    python scripts/run_eval.py --pace 15  # wait 15 s between questions: use on free tiers (a 429 makes a fallback answer, and
                                          # --save refuses a run that mixed models)

Use it to tune MIN_SCORE (.env), the analyzer's search terms (prompts.py) and the chunking.

EVAL GATE: data/eval_baseline.json records the result together with fingerprints of the default models, the
prompts and the retrieval settings. tests/test_eval_baseline.py fails when any of them changes without a new
`--save`, so a new model or an edited prompt cannot change answers unnoticed. --save refuses to run unless the models
used were the shipped defaults, and warns when a fallback provider answered some questions (results would mix models).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.config import get_settings  # noqa: E402
from backend.app.main import build_pipeline  # noqa: E402
from backend.app.providers import STATS, default_fingerprints, default_stages, describe_stages  # noqa: E402
from backend.app.schemas import AskRequest  # noqa: E402

BASELINE = ROOT / "data" / "eval_baseline.json"
TARGET = 12  # of the 15 acceptance questions


def uses_shipped_defaults(live: dict) -> bool:
    """True if every provider that answered is configured with its default model, in the default order."""
    shipped = default_stages()
    for stage, rows in live.items():
        present = {r["provider"] for r in rows}
        if rows != [r for r in shipped[stage] if r["provider"] in present]:
            return False
    return True


def check(case: dict, res) -> list[str]:
    problems = []
    if res.status != case["expect_status"]:
        problems.append(f"status {res.status} != {case['expect_status']}")
    if "expect_topic" in case and res.detected.topic != case["expect_topic"]:
        problems.append(f"topic {res.detected.topic} != {case['expect_topic']}")
    if "expect_jurisdiction" in case and res.detected.jurisdiction != case["expect_jurisdiction"]:
        problems.append(f"jurisdiction {res.detected.jurisdiction} != {case['expect_jurisdiction']}")
    if "expect_cite_contains" in case and not any(case["expect_cite_contains"].lower() in c.act.lower() for c in res.citations):
        problems.append(f"no citation containing '{case['expect_cite_contains']}'")
    if case.get("expect_wage") and not (res.wage and res.wage.monthly_pkr):
        problems.append("no wage figure returned")
    if "expect_first_referral" in case:
        first = res.where_to_go[0].number if res.where_to_go else None
        if first != case["expect_first_referral"]:
            problems.append(f"first referral {first} != {case['expect_first_referral']}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", type=int)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--pace", type=float, default=0.0, help="seconds to wait between questions (free tiers allow only a few requests per minute)")
    ap.add_argument("--save", action="store_true", help="write data/eval_baseline.json (full runs on the shipped models only)")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    cases = yaml.safe_load((ROOT / "tests" / "test_questions.yaml").read_text(encoding="utf-8"))["questions"]
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]

    settings = get_settings()
    pipe = build_pipeline(settings)
    live = describe_stages(settings)
    print(f"Index: {len(pipe.retriever)} chunks | min_score={settings.min_score} | top_k={settings.top_k}")
    for stage, rows in live.items():
        print(f"  {stage:8s} " + " -> ".join(f"{r['provider']}:{r['model']}" for r in rows))
    print()
    STATS.reset()
    failures = 0
    results: dict[str, dict] = {}
    for i, case in enumerate(cases):
        if i and args.pace:
            time.sleep(args.pace)
        try:
            res = pipe.ask(AskRequest(question=case["q"]))
            problems = check(case, res)
        except Exception as exc:  # keep going so one API error does not hide the rest
            res, problems = None, [f"error: {exc}"]
        mark = "PASS" if not problems else "FAIL"
        failures += bool(problems)
        results[str(case["id"])] = {"pass": not problems, "status": res.status if res else None, "problems": problems}
        status = res.status if res else "-"
        print(f"[{mark}] #{case['id']:<2} {status:<12} {case['q'][:70]}")
        for p in problems:
            print(f"        - {p}")
        if args.verbose and res:
            print(f"        EN: {res.answer_en[:300]}")
            print(f"        cites: {[c.chunk_id for c in res.citations]}")
    passed = len(cases) - failures
    print(f"\n{passed}/{len(cases)} passed (target {TARGET}/15)")

    snap = STATS.snapshot()
    fallback_served = {k: v["served_as_fallback"] for k, v in snap.items() if v["served_as_fallback"]}
    provider_failures = {k: f"{v['fail']}x {v['last_error']}" for k, v in snap.items() if v["fail"]}
    if provider_failures:
        print("Provider failures during this run:", provider_failures)
    if fallback_served:
        print("WARNING: a fallback provider answered some calls, so these results MIX models:", fallback_served)

    if args.save:
        if args.ids:
            print("Not saved: --save needs a full run (no question ids).", file=sys.stderr)
            return 2
        if not uses_shipped_defaults(live):
            print("Not saved: the models used differ from the shipped defaults (.env overrides?). The baseline must "
                  "describe what ships; unset the overrides and rerun.", file=sys.stderr)
            return 2
        if fallback_served:
            print("Not saved: a fallback provider answered, so the result does not describe the default models.", file=sys.stderr)
            return 2
        BASELINE.write_text(
            json.dumps(
                {
                    "date": date.today().isoformat(),
                    "target": TARGET,
                    "passed": passed,
                    "total": len(cases),
                    "defaults": default_fingerprints(),
                    "run": {"stages": live, "min_score": settings.min_score, "top_k": settings.top_k, "chunks": len(pipe.retriever)},
                    "results": results,
                },
                indent=1,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Baseline written to {BASELINE}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
