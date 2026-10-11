import asyncio
from pathlib import Path
from time import perf_counter, sleep

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = PROJECT_ROOT / "examples" / "crm"


@pytest.mark.asyncio
async def test_blocking_retrieval_is_offloaded_from_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "data",
            embedding_dimensions=32,
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (
                await client.post("/api/v1/networks/import", json={"path": str(EXAMPLE / "bkn")})
            ).status_code == 201
            assert (
                await client.post(
                    "/api/v1/sources",
                    json={
                        "id": "crm_files",
                        "name": "CRM",
                        "kind": "csv",
                        "path": str(EXAMPLE / "data"),
                    },
                )
            ).status_code == 201
            await client.post("/api/v1/sources/crm_files/discover")
            await client.post("/api/v1/networks/crm/materialize")
            await client.post("/api/v1/networks/crm/index")

            retriever = app.state.retrieval_service._retriever
            original = retriever.search

            def delayed(*args: object, **kwargs: object):
                sleep(0.2)
                return original(*args, **kwargs)

            monkeypatch.setattr(retriever, "search", delayed)
            started = perf_counter()
            responses = await asyncio.gather(
                client.post("/api/v1/networks/crm/search", json={"query": "客户"}),
                client.post("/api/v1/networks/crm/search", json={"query": "订单"}),
            )
            elapsed = perf_counter() - started

            assert all(response.status_code == 200 for response in responses)
            assert elapsed < 0.35
