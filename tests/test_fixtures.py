import json
from pathlib import Path

import pytest

from backend.app.schemas import AskResponse

FIXTURES = sorted((Path(__file__).resolve().parents[1] / "docs" / "fixtures").glob("ask_*.json"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture_matches_schema(path):
    AskResponse.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_all_four_states_covered():
    statuses = {json.loads(p.read_text(encoding="utf-8"))["status"] for p in FIXTURES}
    assert statuses == {"answered", "not_found", "out_of_scope", "danger"}
