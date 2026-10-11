from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = PROJECT_ROOT / "examples" / "crm"


@pytest.mark.asyncio
async def test_search_requires_rebuild_after_embedding_version_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = (tmp_path / "minibkn.db").as_posix()
    first_app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            data_dir=tmp_path / "data",
            embedding_dimensions=64,
        )
    )
    async with first_app.router.lifespan_context(first_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=first_app), base_url="http://test"
        ) as client:
            await client.post("/api/v1/networks/import", json={"path": str(EXAMPLE / "bkn")})
            await client.post(
                "/api/v1/sources",
                json={
                    "id": "crm_files",
                    "name": "CRM",
                    "kind": "csv",
                    "path": str(EXAMPLE / "data"),
                },
            )
            await client.post("/api/v1/sources/crm_files/discover")
            await client.post("/api/v1/networks/crm/materialize")
            built = await client.post("/api/v1/networks/crm/index")
            assert built.json()["embedding_version"] == "token_hashing:v1:64"

            graph = first_app.state.retrieval_service._graph
            original = graph.list_search_documents
            calls = 0

            async def counted(network_id: str):
                nonlocal calls
                calls += 1
                return await original(network_id)

            monkeypatch.setattr(graph, "list_search_documents", counted)
            for _ in range(2):
                search = await client.post(
                    "/api/v1/networks/crm/search",
                    json={"query": "星河科技", "mode": "bm25"},
                )
                assert search.status_code == 200
            assert calls == 0

    second_app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            data_dir=tmp_path / "data",
            embedding_dimensions=96,
        )
    )
    async with second_app.router.lifespan_context(second_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=second_app), base_url="http://test"
        ) as client:
            search = await client.post("/api/v1/networks/crm/search", json={"query": "星河科技"})
            assert search.status_code == 409
            assert search.json()["error_code"] == "INDEX_VERSION_MISMATCH"
