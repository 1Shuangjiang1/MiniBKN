from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = PROJECT_ROOT / "examples" / "crm"


@pytest.mark.asyncio
async def test_crm_uses_same_evidence_driven_question_answering_chain(tmp_path: Path) -> None:
    database_path = (tmp_path / "minibkn.db").as_posix()
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            data_dir=tmp_path / "data",
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            imported = await client.post(
                "/api/v1/networks/import", json={"path": str(EXAMPLE / "bkn")}
            )
            assert imported.status_code == 201, imported.text
            assert imported.json()["lifecycle_status"] == "published"

            registered = await client.post(
                "/api/v1/sources",
                json={
                    "id": "crm_files",
                    "name": "CRM CSV files",
                    "kind": "csv",
                    "path": str(EXAMPLE / "data"),
                },
            )
            assert registered.status_code == 201, registered.text
            discovered = await client.post("/api/v1/sources/crm_files/discover")
            assert discovered.status_code == 200, discovered.text
            resources = {item["id"]: item for item in discovered.json()["resources"]}
            order_fields = {item["name"]: item for item in resources["orders_csv"]["fields"]}
            assert order_fields["created_at"]["value_type"] == "date"

            materialized = await client.post("/api/v1/networks/crm/materialize")
            assert materialized.status_code == 200, materialized.text
            assert materialized.json() == {
                "network_id": "crm",
                "object_count": 7,
                "relation_count": 4,
            }
            indexed = await client.post("/api/v1/networks/crm/index")
            assert indexed.status_code == 200, indexed.text

            asked = await client.post(
                "/api/v1/networks/crm/ask",
                json={"question": "星河科技有哪些订单？"},
            )
            assert asked.status_code == 200, asked.text
            payload = asked.json()
            assert "星河科技" in payload["answer"]
            assert "ORD-001" in payload["answer"]
            assert "ORD-002" in payload["answer"]
            assert "placed_by" in payload["answer"]
            assert {item["kind"] for item in payload["evidence"]} >= {
                "schema",
                "instance",
                "relation",
            }
            assert any(
                item["citation"].startswith("resource://orders_csv") for item in payload["evidence"]
            )
