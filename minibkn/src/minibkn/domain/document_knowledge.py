"""Provider-neutral document knowledge and routing contracts."""

from enum import StrEnum

from pydantic import Field

from minibkn.domain.base import DomainModel
from minibkn.domain.evidence import EvidenceItem


class KnowledgeRoute(StrEnum):
    AUTO = "auto"
    STRUCTURED = "structured"
    DOCUMENT = "document"
    HYBRID = "hybrid"


class DocumentKnowledgeStatus(DomainModel):
    provider: str
    enabled: bool
    capabilities: list[str] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)


class DocumentIngestResult(DomainModel):
    network_id: str
    collection: str
    track_id: str
    status: str
    message: str = ""


class DocumentJobStatus(DomainModel):
    network_id: str
    collection: str
    track_id: str
    status: str
    documents: list[dict[str, object]] = Field(default_factory=list)


class RoutedAskResult(DomainModel):
    question: str
    answer: str
    requested_route: KnowledgeRoute
    executed_routes: list[KnowledgeRoute]
    citations: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
