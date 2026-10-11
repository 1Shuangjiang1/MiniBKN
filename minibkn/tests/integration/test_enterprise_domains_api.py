import json
from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

ROOT = Path(__file__).resolve().parents[2]
ENTERPRISE = ROOT / "evals" / "enterprise"
DATASETS = ROOT / "evals" / "datasets"

DOMAIN_COUNTS = {
    "procurement": {"objects": 2000, "relations": 2300, "object_types": 5, "relation_types": 4},
    "finance": {"objects": 1320, "relations": 1200, "object_types": 5, "relation_types": 3},
    "hr": {"objects": 1120, "relations": 1100, "object_types": 4, "relation_types": 3},
}


def _jsonl(name: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (DATASETS / name).read_text(encoding="utf-8").splitlines()
        if line
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", ["procurement", "finance", "hr"])
async def test_enterprise_domain_build_search_plan_and_risk_chain(
    domain: str, tmp_path: Path
) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / f'{domain}.db').as_posix()}",
            data_dir=tmp_path / "runtime",
            embedding_dimensions=64,
        )
    )
    network_id = f"{domain}_holdout"
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            imported = await client.post(
                "/api/v1/networks/import",
                json={"path": str(ENTERPRISE / domain / "bkn")},
            )
            assert imported.status_code == 201, imported.text

            source_id = f"{domain}_files"
            registered = await client.post(
                "/api/v1/sources",
                json={
                    "id": source_id,
                    "name": f"{domain} files",
                    "kind": "csv",
                    "path": str(ENTERPRISE / domain / "data"),
                },
            )
            assert registered.status_code == 201, registered.text
            discovered = await client.post(f"/api/v1/sources/{source_id}/discover")
            assert discovered.status_code == 200, discovered.text

            built = await client.post(f"/api/v1/networks/{network_id}/builds")
            assert built.status_code == 200, built.text
            assert built.json()["status"] == "published"
            assert len(built.json()["change_set"]["inserted"]) == DOMAIN_COUNTS[domain]["objects"]
            assert built.json()["relation_inserted"] == DOMAIN_COUNTS[domain]["relations"]
            assert built.json()["embedded_documents"] == (
                DOMAIN_COUNTS[domain]["objects"]
                + DOMAIN_COUNTS[domain]["object_types"]
                + DOMAIN_COUNTS[domain]["relation_types"]
                + 1
            )

            retrieval_case = next(
                item
                for item in _jsonl("enterprise_retrieval_holdout_120.jsonl")
                if item["domain"] == domain
            )
            searched = await client.post(
                f"/api/v1/networks/{network_id}/search",
                json={"query": retrieval_case["question"], "mode": "bm25", "limit": 5},
            )
            assert searched.status_code == 200, searched.text
            actual_ids = {item["document"]["id"] for item in searched.json()}
            assert set(retrieval_case["expected_document_ids"]) & actual_ids

            planner_case = next(
                item
                for item in _jsonl("enterprise_query_planner_holdout_15.jsonl")
                if item["domain"] == domain and item["expected_status"] == "ready"
            )
            previewed = await client.post(
                f"/api/v1/networks/{network_id}/query-plans/preview",
                json={"question": planner_case["question"]},
            )
            assert previewed.status_code == 200, previewed.text

            action_cases = [
                item
                for item in _jsonl("enterprise_actions_holdout_45.jsonl")
                if item["domain"] == domain
            ]
            for case in action_cases:
                simulated = await client.post(
                    f"/api/v1/networks/{network_id}/actions/{case['action_type_id']}/risks/simulate",
                    json={
                        "object_type_id": case["object_type_id"],
                        "instance_id": case["instance_id"],
                    },
                )
                assert simulated.status_code == 200, simulated.text
                assert simulated.json()["decision"] == case["expected_decision"]

            unchanged = await client.post(f"/api/v1/networks/{network_id}/builds")
            assert unchanged.status_code == 200, unchanged.text
            assert unchanged.json()["change_set"] == {
                "inserted": [],
                "updated": [],
                "deleted": [],
            }
            assert unchanged.json()["embedded_documents"] == 0
