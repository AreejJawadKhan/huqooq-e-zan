"""The eval gate: models, prompts and retrieval defaults cannot change without the 15-question eval being rerun.

data/eval_baseline.json is written by `python scripts/run_eval.py --save` and records the fingerprints of the shipped
defaults it was measured on. If you change a default model (providers.py), the analyzer or answer prompt or tool
schema, DEFAULT_CHAINS, MIN_SCORE or TOP_K, this test fails on purpose.
"""
import json
from pathlib import Path

import pytest

from backend.app.providers import default_fingerprints

BASELINE = Path(__file__).resolve().parents[1] / "data" / "eval_baseline.json"

HOW = (
    "\nThe models, prompts or retrieval defaults changed since the last recorded eval, so answers may have changed "
    "without anyone noticing.\n  1. python scripts/check_models.py   (the new models work)\n"
    "  2. python scripts/run_eval.py -v   (read every failure)\n  3. python scripts/run_eval.py --save   (record it)\n"
    "and commit data/eval_baseline.json with the change."
)


def load():
    if not BASELINE.exists():
        # The gate cannot enforce anything before a first eval has been recorded on the shipped defaults (that needs
        # every default provider reachable: `run_eval.py --save` refuses a run in which a fallback answered). Skipped
        # on purpose, and loudly, instead of breaking the build. Once the file is committed this is a hard check.
        pytest.skip("EVAL GATE NOT ACTIVE: no data/eval_baseline.json yet. Run `python scripts/run_eval.py --pace 15 --save`." + HOW)
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_baseline_was_measured_on_the_current_defaults():
    recorded, current = load()["defaults"], default_fingerprints()
    changed = [k for k in current if recorded.get(k) != current[k]]
    assert not changed, f"changed since the last eval: {changed}.{HOW}"


def test_baseline_meets_the_target():
    b = load()
    assert b["total"] == 15, "the baseline must come from a full run of all 15 questions"
    assert b["passed"] >= b["target"], f"last recorded eval: {b['passed']}/{b['total']}, below the target of {b['target']}"


def test_the_gate_fires_when_a_default_model_or_prompt_changes(tmp_path, monkeypatch):
    """Prove the mechanism with a temporary baseline: matching defaults pass, a changed model or prompt fails."""
    from backend.app import prompts, providers

    fake = tmp_path / "eval_baseline.json"
    fake.write_text(json.dumps({"defaults": default_fingerprints(), "passed": 14, "total": 15, "target": 12}), encoding="utf-8")
    monkeypatch.setattr(__name__ + ".BASELINE", fake)
    test_baseline_was_measured_on_the_current_defaults()  # unchanged defaults: passes

    monkeypatch.setitem(providers.DEFAULT_MODELS, "gemini", ("a-new-model", providers.DEFAULT_MODELS["gemini"][1]))
    with pytest.raises(AssertionError, match="models"):
        test_baseline_was_measured_on_the_current_defaults()
    monkeypatch.undo()

    fake.write_text(json.dumps({"defaults": default_fingerprints(), "passed": 14, "total": 15, "target": 12}), encoding="utf-8")
    monkeypatch.setattr(__name__ + ".BASELINE", fake)
    monkeypatch.setattr(prompts, "ANSWER_SYSTEM", prompts.ANSWER_SYSTEM + " One more rule.")
    with pytest.raises(AssertionError, match="prompts"):
        test_baseline_was_measured_on_the_current_defaults()
