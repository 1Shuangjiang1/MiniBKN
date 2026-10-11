"""HTTP request and response models."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from minibkn.domain.document_knowledge import KnowledgeRoute
from minibkn.domain.modeling import BknLifecycleStatus, ProposalStatus
from minibkn.domain.models import AskResult, DataSourceKind, SearchMode
from minibkn.domain.query import QueryAnalysis, QueryAnalysisStatus, QueryExecutionResult, QueryPlan


class ImportNetworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path = Field(description="Local directory containing network.bkn and related documents")


class NetworkSummary(BaseModel):
    id: str
    name: str
    business_domain: str
    version: int
    lifecycle_status: BknLifecycleStatus
    object_type_count: int
    relation_type_count: int
    action_type_count: int
    risk_type_count: int
    updated_at: datetime


class NetworkListResponse(BaseModel):
    entries: list[NetworkSummary]
    total: int


class RegisterSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: DataSourceKind
    path: str


class MaterializeResponse(BaseModel):
    network_id: str
    object_count: int
    relation_count: int


class IndexResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    network_id: str
    total: int
    schema_count: int = Field(validation_alias="schema", serialization_alias="schema")
    instance: int
    action: int
    embedding_version: str
    embedding_dimensions: int


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=10, ge=1, le=50)
    mode: SearchMode = SearchMode.HYBRID


class SubgraphRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type_id: str = Field(min_length=1, max_length=128)
    instance_id: str = Field(min_length=1, max_length=256)
    depth: int = Field(default=1, ge=1, le=5)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)


class RoutedAskRequest(AskRequest):
    route: KnowledgeRoute = KnowledgeRoute.AUTO


class IngestDocumentTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1, max_length=1_000_000)


class ExecuteQueryPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: QueryPlan


class AnalyzeQueryRequest(AskRequest):
    clarification_answers: dict[str, str] = Field(default_factory=dict)


class PlannedAskResponse(BaseModel):
    question: str
    answer: str
    execution: QueryExecutionResult


class IntelligentAskResponse(BaseModel):
    question: str
    status: QueryAnalysisStatus
    analysis: QueryAnalysis
    answer: str = ""
    execution: QueryExecutionResult | None = None
    retrieval: AskResult | None = None
    requires_action_confirmation: bool = False


class ExecuteActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type_id: str = Field(min_length=1, max_length=128)
    instance_id: str = Field(min_length=1, max_length=256)
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(default="", max_length=128)


class SimulateRiskRequest(ExecuteActionRequest):
    subject: dict[str, Any] = Field(default_factory=dict)


class ConfirmActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool


class GenerateNetworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network_id: str
    name: str
    use_ai: bool = False


class CreateModelingSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    network_id: str
    name: str
    instruction: str = ""
    use_ai: bool = False


class ReviewProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ProposalStatus
    reviewed_by: str = Field(min_length=1)
    payload: dict[str, Any] | None = None


class PublishModelingSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    published_by: str = Field(min_length=1)
