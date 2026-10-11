import json
from pathlib import Path

import httpx
import pytest

from minibkn.adapters.document_knowledge import LightRAGDocumentKnowledge


@pytest.mark.asyncio
async def test_lightrag_full_rest_contract_and_collection_isolation(tmp_path: Path) -> None:
    endpoints = tmp_path / "endpoints.json"
    endpoints.write_text(
        json.dumps(
            {
                "crm": {
                    "public": "https://public.test",
                    "finance": "https://finance.test",
                }
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.host or "", request.url.path))
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        if request.url.path == "/documents/text":
            body = json.loads(request.content)
            assert body["file_source"] == "员工手册.md"
            return httpx.Response(200, json={"status": "success", "track_id": "track-1"})
        if request.url.path == "/documents/track_status/track-1":
            return httpx.Response(200, json={"status": "completed", "documents": []})
        if request.url.path == "/query/data":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "chunks": [
                            {
                                "id": "chunk-1",
                                "content": f"{request.url.host} 的制度内容",
                                "file_path": "员工手册.md",
                                "score": 0.91,
                            }
                        ]
                    },
                },
            )
        return httpx.Response(404)

    adapter = LightRAGDocumentKnowledge(
        endpoints, "sidecar-key", transport=httpx.MockTransport(handler)
    )
    status = await adapter.status()
    assert status.details == {"crm/public": "healthy", "crm/finance": "healthy"}

    ingested = await adapter.ingest_text("crm", "public", "员工手册.md", "审批规则")
    assert ingested.track_id == "track-1"
    job = await adapter.job_status("crm", "public", "track-1")
    assert job.status == "completed"

    evidence = await adapter.query("crm", "审批规则是什么", 5, {"public"})
    assert len(evidence) == 1
    assert evidence[0].attributes["collection"] == "public"
    query_hosts = [host for host, path in calls if path == "/query/data"]
    assert query_hosts == ["public.test"]
