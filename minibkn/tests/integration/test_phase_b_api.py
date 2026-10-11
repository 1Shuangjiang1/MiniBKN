from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = PROJECT_ROOT / "examples" / "supply_chain"


@pytest.mark.asyncio
async def test_data_to_hybrid_retrieval_and_context_chain(tmp_path: Path) -> None:
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

            registered = await client.post(
                "/api/v1/sources",
                json={
                    "id": "supply_chain_files",
                    "name": "Supply chain CSV files",
                    "kind": "csv",
                    "path": str(EXAMPLE / "data"),
                },
            )
            assert registered.status_code == 201, registered.text

            discovered = await client.post("/api/v1/sources/supply_chain_files/discover")
            assert discovered.status_code == 200, discovered.text
            resources = {item["id"]: item for item in discovered.json()["resources"]}
            assert resources["materials_csv"]["row_count"] == 3
            assert resources["suppliers_csv"]["row_count"] == 2
            assert resources["materials_csv"]["fields"][2]["value_type"] == "integer"

            materialized = await client.post("/api/v1/networks/supply_chain/materialize")
            assert materialized.status_code == 200, materialized.text
            assert materialized.json()["object_count"] == 5
            assert materialized.json()["relation_count"] == 3

            materials = await client.get(
                "/api/v1/networks/supply_chain/object-types/material/instances"
            )
            assert materials.status_code == 200
            assert [item["instance_id"] for item in materials.json()] == [
                "MAT-001",
                "MAT-002",
                "MAT-003",
            ]

            subgraph = await client.post(
                "/api/v1/networks/supply_chain/subgraph",
                json={"object_type_id": "material", "instance_id": "MAT-001", "depth": 1},
            )
            assert subgraph.status_code == 200, subgraph.text
            node_ids = {item["instance_id"] for item in subgraph.json()["nodes"]}
            assert node_ids == {"MAT-001", "SUP-001"}
            assert len(subgraph.json()["edges"]) == 1

            indexed = await client.post("/api/v1/networks/supply_chain/index")
            assert indexed.status_code == 200, indexed.text
            assert indexed.json() == {
                "network_id": "supply_chain",
                "total": 9,
                "schema": 3,
                "instance": 5,
                "action": 1,
                "embedding_version": "token_hashing:v1:128",
                "embedding_dimensions": 128,
            }

            searched = await client.post(
                "/api/v1/networks/supply_chain/search",
                json={"query": "Temperature Sensor MAT-001", "limit": 3},
            )
            assert searched.status_code == 200, searched.text
            first = searched.json()[0]
            assert first["document"]["entity_id"] == "MAT-001"
            assert first["bm25_rank"] == 1
            assert first["vector_rank"] == 1

            asked = await client.post(
                "/api/v1/networks/supply_chain/ask",
                json={"question": "哪些物料库存低于安全库存，它们由谁供应？"},
            )
            assert asked.status_code == 200, asked.text
            payload = asked.json()
            assert "MAT-001" in payload["answer"]
            assert "MAT-003" in payload["answer"]
            assert "Precision Components" in payload["answer"]
            assert payload["context"]["schema"]
            assert payload["context"]["instances"]
            assert payload["context"]["actions"]
            assert any(
                value.startswith("resource://materials_csv") for value in payload["citations"]
            )
