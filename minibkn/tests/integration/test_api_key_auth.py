from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app


@pytest.mark.asyncio
async def test_configured_api_key_protects_business_routes(tmp_path: Path) -> None:
    database_path = (tmp_path / "minibkn.db").as_posix()
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            data_dir=tmp_path / "data",
            api_key="demo-secret",
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200

            unauthorized = await client.get("/api/v1/networks")
            assert unauthorized.status_code == 401
            assert unauthorized.json()["error_code"] == "UNAUTHORIZED"
            assert unauthorized.headers["x-trace-id"] == unauthorized.json()["trace_id"]

            wrong_key = await client.post(
                "/api/v1/networks/import",
                headers={"x-api-key": "demo-secret-wrong"},
                json={"path": "."},
            )
            assert wrong_key.status_code == 401

            authorized = await client.get("/api/v1/networks", headers={"x-api-key": "demo-secret"})
            assert authorized.status_code == 200


@pytest.mark.asyncio
async def test_oversized_search_and_ask_inputs_are_rejected(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "data",
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            oversized = "x" * 4001
            search = await client.post(
                "/api/v1/networks/not-needed/search", json={"query": oversized}
            )
            ask = await client.post("/api/v1/networks/not-needed/ask", json={"question": oversized})

            assert search.status_code == 400
            assert ask.status_code == 400
            assert search.json()["error_code"] == "INVALID_PARAMETER"
            assert ask.json()["error_code"] == "INVALID_PARAMETER"
