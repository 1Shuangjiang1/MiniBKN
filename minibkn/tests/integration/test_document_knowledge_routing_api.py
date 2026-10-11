from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.domain.document_knowledge import (
    DocumentIngestResult,
    DocumentJobStatus,
    DocumentKnowledgeStatus,
)
from minibkn.domain.evidence import EvidenceItem, EvidenceKind
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRM = PROJECT_ROOT / "examples" / "crm"


class FakeDocumentKnowledge:
    async def status(self) -> DocumentKnowledgeStatus:
        return DocumentKnowledgeStatus(
            provider="fake-sidecar", enabled=True, capabilities=["query"]
        )

    async def query(
        self, network_id: str, question: str, limit: int, collections: set[str] | None = None
    ) -> list[EvidenceItem]:
        del question, limit, collections
        return [
            EvidenceItem(
                id="document:employee-handbook:approval",
                network_id=network_id,
                kind=EvidenceKind.DOCUMENT,
                title="Approval policy",
                content="Orders above the internal threshold require manager approval.",
                citation="document://employee-handbook#approval",
            )
        ]

    async def ingest_text(
        self, network_id: str, collection: str, title: str, text: str
    ) -> DocumentIngestResult:
        del title, text
        return DocumentIngestResult(
            network_id=network_id,
            collection=collection,
            track_id="track-1",
            status="success",
        )

    async def job_status(
        self, network_id: str, collection: str, track_id: str
    ) -> DocumentJobStatus:
        return DocumentJobStatus(
            network_id=network_id,
            collection=collection,
            track_id=track_id,
            status="processed",
        )


async def _prepare(client: httpx.AsyncClient) -> None:
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
                "path": str(CRM / "data"),
            },
        )
    ).status_code == 201
    assert (await client.post("/api/v1/sources/crm_files/discover")).status_code == 200
    assert (await client.post("/api/v1/networks/crm/builds")).status_code == 200


@pytest.mark.asyncio
async def test_document_port_can_be_injected_without_changing_core_routes(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "runtime",
        ),
        document_knowledge=FakeDocumentKnowledge(),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _prepare(client)
            status = await client.get("/api/v1/document-knowledge/status")
            assert status.json()["provider"] == "fake-sidecar"

            ingestion = await client.post(
                "/api/v1/networks/crm/documents/text",
                json={"collection": "public", "title": "制度.md", "text": "审批制度"},
            )
            assert ingestion.status_code == 202
            assert ingestion.json()["track_id"] == "track-1"
            job = await client.get("/api/v1/networks/crm/document-collections/public/jobs/track-1")
            assert job.status_code == 200
            assert job.json()["status"] == "processed"

            document = await client.post(
                "/api/v1/networks/crm/ask-routed",
                json={"question": "审批制度是什么？", "route": "document"},
            )
            assert document.status_code == 200
            assert document.json()["executed_routes"] == ["document"]
            assert document.json()["evidence"][0]["kind"] == "document"

            hybrid = await client.post(
                "/api/v1/networks/crm/ask-routed",
                json={"question": "订单与审批制度", "route": "hybrid"},
            )
            assert hybrid.status_code == 200
            assert hybrid.json()["executed_routes"] == ["structured", "document"]
            assert "document://employee-handbook#approval" in hybrid.json()["citations"]


@pytest.mark.asyncio
async def test_disabled_document_port_is_explicit_and_auto_route_can_degrade(
    tmp_path: Path,
) -> None:
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
            await _prepare(client)
            status = await client.get("/api/v1/document-knowledge/status")
            assert status.json() == {
                "provider": "disabled",
                "enabled": False,
                "capabilities": [],
                "details": {},
            }

            explicit = await client.post(
                "/api/v1/networks/crm/ask-routed",
                json={"question": "员工手册怎么规定？", "route": "document"},
            )
            assert explicit.status_code == 503
            assert explicit.json()["error_code"] == "DOCUMENT_KNOWLEDGE_DISABLED"

            automatic = await client.post(
                "/api/v1/networks/crm/ask-routed",
                json={"question": "员工手册里的客户信息", "route": "auto"},
            )
            assert automatic.status_code == 200
            assert automatic.json()["executed_routes"] == ["structured"]
            assert automatic.json()["warnings"]
