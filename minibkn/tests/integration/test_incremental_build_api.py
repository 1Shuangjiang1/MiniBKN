import csv
import shutil
from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRM = PROJECT_ROOT / "examples" / "crm"


@pytest.mark.asyncio
async def test_incremental_build_updates_only_changed_graph_and_index_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_data = tmp_path / "crm-data"
    shutil.copytree(CRM / "data", source_data)
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "runtime",
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (
                await client.post("/api/v1/networks/import", json={"path": str(CRM / "bkn")})
            ).status_code == 201
            assert (
                await client.post(
                    "/api/v1/sources",
                    json={
                        "id": "crm_files",
                        "name": "CRM",
                        "kind": "csv",
                        "path": str(source_data),
                    },
                )
            ).status_code == 201
            assert (await client.post("/api/v1/sources/crm_files/discover")).status_code == 200

            first = await client.post("/api/v1/networks/crm/builds")
            assert first.status_code == 200, first.text
            assert first.json()["status"] == "published"
            assert len(first.json()["change_set"]["inserted"]) == 7
            assert first.json()["relation_inserted"] == 4
            assert first.json()["embedded_documents"] == 10

            order_path = source_data / "orders.csv"
            with order_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["amount"] = "130000.50"
            rows.append(
                {
                    "order_id": "ORD-005",
                    "customer_id": "CUST-002",
                    "amount": "2500.00",
                    "status": "paid",
                    "created_at": "2026-08-16",
                }
            )
            with order_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

            second = await client.post("/api/v1/networks/crm/builds")
            assert second.status_code == 200, second.text
            payload = second.json()
            assert payload["status"] == "published"
            assert [item["instance_id"] for item in payload["change_set"]["inserted"]] == [
                "ORD-005"
            ]
            assert [item["instance_id"] for item in payload["change_set"]["updated"]] == ["ORD-001"]
            assert payload["relation_inserted"] == 1
            assert payload["index_inserted"] == 1
            assert payload["index_updated"] == 1
            assert payload["embedded_documents"] == 2

            unchanged = await client.post("/api/v1/networks/crm/builds")
            assert unchanged.status_code == 200
            assert unchanged.json()["change_set"] == {
                "inserted": [],
                "updated": [],
                "deleted": [],
            }
            assert unchanged.json()["embedded_documents"] == 0

            fetched = await client.get(f"/api/v1/builds/{second.json()['id']}")
            assert fetched.status_code == 200
            assert fetched.json() == second.json()

            rows[0]["amount"] = "999999.99"
            with order_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

            async def fail_index(_: str) -> dict[str, int | str]:
                raise RuntimeError("simulated index outage")

            monkeypatch.setattr(
                app.state.retrieval_service,
                "build_index_incremental",
                fail_index,
            )
            failed = await client.post("/api/v1/networks/crm/builds")
            assert failed.status_code == 200
            assert failed.json()["status"] == "failed"
            assert failed.json()["error"] == "simulated index outage"

            instances = await client.get("/api/v1/networks/crm/object-types/order/instances")
            assert instances.status_code == 200
            ord_001 = next(item for item in instances.json() if item["instance_id"] == "ORD-001")
            assert ord_001["properties"]["amount"] == "130000.50"
