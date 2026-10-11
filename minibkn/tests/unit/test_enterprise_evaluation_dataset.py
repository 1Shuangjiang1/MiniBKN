import json
from pathlib import Path

from minibkn.adapters.bkn_lang import BknLangParser
from minibkn.adapters.datasource import CsvDataSourceAdapter
from minibkn.domain.models import DataSource, DataSourceKind

ROOT = Path(__file__).resolve().parents[2]


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_enterprise_frozen_datasets_have_expected_size_and_unique_ids() -> None:
    datasets = {
        "enterprise_retrieval_holdout_120.jsonl": 120,
        "enterprise_query_planner_holdout_15.jsonl": 15,
        "enterprise_query_planner_holdout_60.jsonl": 60,
        "enterprise_query_adversarial_6.jsonl": 6,
        "enterprise_actions_holdout_45.jsonl": 45,
    }
    all_ids: list[str] = []
    for name, expected_size in datasets.items():
        rows = _jsonl(ROOT / "evals" / "datasets" / name)
        assert len(rows) == expected_size
        all_ids.extend(str(row["id"]) for row in rows)
    assert len(all_ids) == len(set(all_ids))


def test_enterprise_bkn_networks_are_valid_and_not_supply_chain_specific() -> None:
    expected = {"procurement": (5, 4), "finance": (5, 3), "hr": (4, 3)}
    for domain, (objects, relations) in expected.items():
        network = BknLangParser().parse_directory(ROOT / "evals" / "enterprise" / domain / "bkn")
        assert len(network.object_types) == objects
        assert len(network.relation_types) == relations
        assert len(network.action_types) == 1
        assert len(network.risk_types) == 2


def test_data_quality_suite_finds_composite_and_partial_foreign_keys() -> None:
    path = ROOT / "evals" / "enterprise" / "data_quality"
    source = DataSource(id="quality", name="Quality", kind=DataSourceKind.CSV, path=str(path))
    resources = {item.id: item for item in CsvDataSourceAdapter().discover(source)}

    parent = resources["composite_parent_csv"]
    assert parent.primary_key_candidates[0].fields == ["tenant_id", "code"]
    assert parent.primary_key_candidates[0].recommended is True

    child = resources["composite_child_csv"]
    composite_relation = next(
        item for item in child.foreign_key_candidates if item.target_resource_id == parent.id
    )
    assert composite_relation.fields == ["tenant_id", "code"]
    assert composite_relation.recommended is True

    orphan = resources["orphan_child_csv"]
    orphan_relation = next(
        item for item in orphan.foreign_key_candidates if item.target_resource_id == "parent_csv"
    )
    assert orphan_relation.fields == ["parent_id"]
    assert orphan_relation.recommended is True
    assert "80%" in orphan_relation.reasons[0]

    noisy = resources["duplicate_and_null_csv"]
    assert not any("business_id" in item.fields for item in noisy.primary_key_candidates)


def test_finance_composite_code_key_and_transaction_keys_are_not_conflated() -> None:
    path = ROOT / "evals" / "enterprise" / "finance" / "data"
    source = DataSource(id="finance", name="Finance", kind=DataSourceKind.CSV, path=str(path))
    resources = {item.id: item for item in CsvDataSourceAdapter().discover(source)}

    departments = resources["departments_csv"]
    assert departments.primary_key_candidates[0].fields == ["company_code", "department_code"]
    assert departments.primary_key_candidates[0].recommended is True
    assert resources["receipts_csv"].primary_key_candidates[0].fields == ["receipt_id"]
    assert resources["invoices_csv"].primary_key_candidates[0].fields == ["invoice_id"]
