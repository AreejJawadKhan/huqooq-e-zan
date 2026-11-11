#!/usr/bin/env python3
"""Run tests/test_questions.yaml through the real pipeline (real model calls) and print a pass/fail table.

    python scripts/run_eval.py            # all questions
    python scripts/run_eval.py 5 8 12     # only these ids
    python scripts/run_eval.py -v         # also print English answers

Use it to tune MIN_SCORE (.env), the analyzer's search terms (prompts.py) and the chunking.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import get_settings  # noqa: E402
from backend.app.main import build_pipeline  # noqa: E402
from backend.app.schemas import AskRequest  # noqa: E402


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
    args = ap.parse_args()

    cases = yaml.safe_load((ROOT / "tests" / "test_questions.yaml").read_text(encoding="utf-8"))["questions"]
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]

    pipe = build_pipeline(get_settings())
    print(f"Index: {len(pipe.retriever)} chunks | min_score={pipe.settings.min_score}\n")
    failures = 0
    for case in cases:
        try:
            res = pipe.ask(AskRequest(question=case["q"]))
            problems = check(case, res)
        except Exception as exc:  # keep going so one API error does not hide the rest
            res, problems = None, [f"error: {exc}"]
        mark = "PASS" if not problems else "FAIL"
        failures += bool(problems)
        status = res.status if res else "-"
        print(f"[{mark}] #{case['id']:<2} {status:<12} {case['q'][:70]}")
        for p in problems:
            print(f"        - {p}")
        if args.verbose and res:
            print(f"        EN: {res.answer_en[:300]}")
            print(f"        cites: {[c.chunk_id for c in res.citations]}")
    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
