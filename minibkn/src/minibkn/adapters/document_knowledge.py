"""Disabled and LightRAG REST sidecar document-knowledge adapters."""

import json
from pathlib import Path
from typing import Any, NoReturn

import httpx

from minibkn.api.errors import MiniBKNError
from minibkn.domain.document_knowledge import (
    DocumentIngestResult,
    DocumentJobStatus,
    DocumentKnowledgeStatus,
)
from minibkn.domain.evidence import EvidenceItem, EvidenceKind


class DisabledDocumentKnowledge:
    async def status(self) -> DocumentKnowledgeStatus:
        return DocumentKnowledgeStatus(provider="disabled", enabled=False)

    async def query(
        self, network_id: str, question: str, limit: int, collections: set[str] | None = None
    ) -> list[EvidenceItem]:
        del network_id, question, limit, collections
        self._disabled()

    async def ingest_text(
        self, network_id: str, collection: str, title: str, text: str
    ) -> DocumentIngestResult:
        del network_id, collection, title, text
        self._disabled()

    async def job_status(
        self, network_id: str, collection: str, track_id: str
    ) -> DocumentJobStatus:
        del network_id, collection, track_id
        self._disabled()

    @staticmethod
    def _disabled() -> NoReturn:
        raise MiniBKNError(
            error_code="DOCUMENT_KNOWLEDGE_DISABLED",
            message="Document knowledge is not enabled; configure a provider adapter first",
            status_code=503,
        )


class LightRAGDocumentKnowledge:
    """Call isolated LightRAG endpoints, one endpoint/workspace per security collection."""

    def __init__(
        self,
        endpoint_map_file: Path,
        api_key: str = "",
        query_mode: str = "mix",
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        raw = json.loads(endpoint_map_file.read_text(encoding="utf-8-sig"))
        self._endpoints: dict[str, dict[str, str]] = {
            network: {collection: url.rstrip("/") for collection, url in collections.items()}
            for network, collections in raw.items()
        }
        self._headers = {"X-API-Key": api_key} if api_key else {}
        self._mode = query_mode
        self._timeout = timeout
        self._transport = transport

    async def status(self) -> DocumentKnowledgeStatus:
        details: dict[str, str] = {}
        for network, collections in self._endpoints.items():
            for collection, endpoint in collections.items():
                key = f"{network}/{collection}"
                try:
                    async with self._client(endpoint) as client:
                        response = await client.get("/health")
                        response.raise_for_status()
                    details[key] = "healthy"
                except httpx.HTTPError:
                    details[key] = "unreachable"
        return DocumentKnowledgeStatus(
            provider="lightrag",
            enabled=bool(self._endpoints),
            capabilities=["ingest_text", "track_status", "query_data", "isolated_collections"],
            details=details,
        )

    async def query(
        self, network_id: str, question: str, limit: int, collections: set[str] | None = None
    ) -> list[EvidenceItem]:
        endpoints = self._selected(network_id, collections)
        evidence: list[EvidenceItem] = []
        failures = []
        for collection, endpoint in endpoints.items():
            try:
                async with self._client(endpoint) as client:
                    response = await client.post(
                        "/query/data",
                        json={
                            "query": question,
                            "mode": self._mode,
                            "top_k": limit,
                            "chunk_top_k": limit,
                        },
                    )
                    response.raise_for_status()
                    evidence.extend(self._evidence(network_id, collection, response.json(), limit))
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                failures.append(f"{collection}:{type(exc).__name__}")
        if not evidence and failures:
            raise MiniBKNError(
                "DOCUMENT_PROVIDER_UNAVAILABLE",
                "LightRAG query failed for all authorized collections",
                503,
                [{"failures": failures}],
            )
        return evidence[:limit]

    async def ingest_text(
        self, network_id: str, collection: str, title: str, text: str
    ) -> DocumentIngestResult:
        endpoint = self._endpoint(network_id, collection)
        async with self._client(endpoint) as client:
            try:
                response = await client.post(
                    "/documents/text", json={"text": text, "file_source": title}
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 409:
                    raise MiniBKNError(
                        "DOCUMENT_ALREADY_EXISTS", "LightRAG already contains this document", 409
                    ) from exc
                raise MiniBKNError(
                    "DOCUMENT_INGEST_FAILED", "LightRAG rejected the document", 502
                ) from exc
            except httpx.HTTPError as exc:
                raise MiniBKNError(
                    "DOCUMENT_INGEST_FAILED", "LightRAG could not be reached", 502
                ) from exc
        payload = response.json()
        return DocumentIngestResult(
            network_id=network_id,
            collection=collection,
            track_id=str(payload.get("track_id", "")),
            status=str(payload.get("status", "pending")),
            message=str(payload.get("message", "")),
        )

    async def job_status(
        self, network_id: str, collection: str, track_id: str
    ) -> DocumentJobStatus:
        endpoint = self._endpoint(network_id, collection)
        async with self._client(endpoint) as client:
            try:
                response = await client.get(f"/documents/track_status/{track_id}")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise MiniBKNError(
                    "DOCUMENT_STATUS_FAILED", "Could not read LightRAG indexing status", 502
                ) from exc
        payload = response.json()
        documents = payload.get("documents", payload.get("data", []))
        if isinstance(documents, list) and documents:
            statuses = {str(item.get("status", "unknown")) for item in documents}
            derived_status = statuses.pop() if len(statuses) == 1 else "mixed"
        else:
            derived_status = "unknown"
        return DocumentJobStatus(
            network_id=network_id,
            collection=collection,
            track_id=track_id,
            status=str(payload.get("status", derived_status)),
            documents=documents if isinstance(documents, list) else [],
        )

    def _selected(self, network_id: str, collections: set[str] | None) -> dict[str, str]:
        available = self._endpoints.get(network_id, {})
        if collections is None or "*" in collections:
            return available
        return {key: value for key, value in available.items() if key in collections}

    def _endpoint(self, network_id: str, collection: str) -> str:
        endpoint = self._endpoints.get(network_id, {}).get(collection)
        if endpoint is None:
            raise MiniBKNError(
                "DOCUMENT_COLLECTION_NOT_FOUND",
                f"document collection '{network_id}/{collection}' is not configured",
                404,
            )
        return endpoint

    def _client(self, endpoint: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=endpoint,
            headers=self._headers,
            timeout=self._timeout,
            transport=self._transport,
        )

    @staticmethod
    def _evidence(
        network_id: str, collection: str, payload: dict[str, Any], limit: int
    ) -> list[EvidenceItem]:
        data = payload.get("data", payload)
        chunks = data.get("chunks", []) if isinstance(data, dict) else []
        result = []
        for index, chunk in enumerate(chunks[:limit]):
            content = str(chunk.get("content", "")).strip()
            if not content:
                continue
            file_path = str(chunk.get("file_path") or chunk.get("source_id") or "document")
            reference_id = str(chunk.get("reference_id") or chunk.get("id") or index)
            result.append(
                EvidenceItem(
                    id=f"document:{collection}:{reference_id}",
                    network_id=network_id,
                    kind=EvidenceKind.DOCUMENT,
                    title=Path(file_path).name,
                    content=content,
                    citation=f"document://{collection}/{file_path}#chunk={reference_id}",
                    score=float(chunk["score"]) if chunk.get("score") is not None else None,
                    attributes={"collection": collection, "file_path": file_path},
                )
            )
        return result
