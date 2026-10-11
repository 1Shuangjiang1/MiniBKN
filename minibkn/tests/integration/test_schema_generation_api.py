from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DATA = PROJECT_ROOT / "examples" / "supply_chain" / "data"


@pytest.mark.asyncio
async def test_discovered_files_generate_a_materializable_network(tmp_path: Path) -> None:
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
            await client.post(
                "/api/v1/sources",
                json={
                    "id": "generated_source",
                    "name": "Generated source",
                    "kind": "csv",
                    "path": str(EXAMPLE_DATA),
                },
            )
            discovered = await client.post("/api/v1/sources/generated_source/discover")
            assert discovered.status_code == 200, discovered.text

            generated = await client.post(
                "/api/v1/sources/generated_source/generate-network",
                json={
                    "network_id": "generated_supply_chain",
                    "name": "Generated Supply Chain",
                },
            )
            assert generated.status_code == 200, generated.text
            schema = generated.json()
            assert {item["id"] for item in schema["object_types"]} == {
                "material",
                "supplier",
            }
            assert schema["relation_types"][0]["id"] == "material_to_supplier"
            assert schema["object_types"][1]["primary_keys"] == ["supplier_id"]

            materialized = await client.post("/api/v1/networks/generated_supply_chain/materialize")
            assert materialized.status_code == 200, materialized.text
            assert materialized.json()["object_count"] == 5
            assert materialized.json()["relation_count"] == 3

            ai_without_configuration = await client.post(
                "/api/v1/sources/generated_source/generate-network",
                json={
                    "network_id": "ai_network",
                    "name": "AI Network",
                    "use_ai": True,
                },
            )
            assert ai_without_configuration.status_code == 409
            assert ai_without_configuration.json()["error_code"] == "AI_SCHEMA_NOT_CONFIGURED"
