from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_BKN = PROJECT_ROOT / "examples" / "supply_chain" / "bkn"


@pytest.mark.asyncio
async def test_import_list_and_read_schema(tmp_path: Path) -> None:
    database_path = (tmp_path / "minibkn.db").as_posix()
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database_path}",
        data_dir=tmp_path / "data",
    )

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.headers["x-trace-id"].startswith("trace-")

            imported = await client.post("/api/v1/networks/import", json={"path": str(EXAMPLE_BKN)})
            assert imported.status_code == 201, imported.text
            assert imported.json()["id"] == "supply_chain"

            replaced = await client.post("/api/v1/networks/import", json={"path": str(EXAMPLE_BKN)})
            assert replaced.status_code == 201, replaced.text

            listing = await client.get("/api/v1/networks")
            assert listing.status_code == 200
            assert listing.json()["total"] == 1
            assert listing.json()["entries"][0]["object_type_count"] == 2

            schema = await client.get("/api/v1/networks/supply_chain/schema")
            assert schema.status_code == 200
            assert schema.json()["relation_types"][0]["id"] == "supplied_by"

            missing = await client.get("/api/v1/networks/unknown/schema")
            assert missing.status_code == 404
            assert missing.json()["error_code"] == "RESOURCE_NOT_FOUND"
            assert missing.json()["trace_id"].startswith("trace-")

            invalid_import = await client.post(
                "/api/v1/networks/import", json={"path": str(tmp_path / "not-found")}
            )
            assert invalid_import.status_code == 400
            assert invalid_import.json()["error_code"] == "INVALID_BKN_DEFINITION"
            assert invalid_import.headers["x-trace-id"] == invalid_import.json()["trace_id"]
