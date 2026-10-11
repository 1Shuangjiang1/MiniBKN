import json
from collections import Counter
from pathlib import Path

from minibkn.domain.query import QueryPlan

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> list[dict[str, object]]:
    path = ROOT / "evals" / "datasets" / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_frozen_crm_dataset_has_expected_business_coverage() -> None:
    cases = _load("crm_200.jsonl")
    assert len(cases) == 200
    assert Counter(case["category"] for case in cases) == {
        "single_entity": 70,
        "multi_hop": 70,
        "filter_aggregate": 60,
    }
    assert len({case["id"] for case in cases}) == 200
    plans = [QueryPlan.model_validate(case["query_plan"]) for case in cases if "query_plan" in case]
    assert len(plans) == 130

    actions = _load("crm_actions_30.jsonl")
    assert len(actions) == 30
    assert Counter(case["expected_decision"] for case in actions) == {
        "allow": 10,
        "confirm": 10,
        "deny": 10,
    }
