"""Replaceable port for unstructured document knowledge providers."""

from typing import Protocol

from minibkn.domain.document_knowledge import (
    DocumentIngestResult,
    DocumentJobStatus,
    DocumentKnowledgeStatus,
)
from minibkn.domain.evidence import EvidenceItem


class DocumentKnowledgePort(Protocol):
    async def status(self) -> DocumentKnowledgeStatus: ...

    async def query(
        self, network_id: str, question: str, limit: int, collections: set[str] | None = None
    ) -> list[EvidenceItem]: ...

    async def ingest_text(
        self, network_id: str, collection: str, title: str, text: str
    ) -> DocumentIngestResult: ...

    async def job_status(
        self, network_id: str, collection: str, track_id: str
    ) -> DocumentJobStatus: ...
