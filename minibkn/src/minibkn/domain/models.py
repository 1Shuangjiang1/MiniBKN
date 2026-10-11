"""Business Knowledge Network domain contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field

from minibkn.domain.base import DomainModel
from minibkn.domain.evidence import EvidenceItem
from minibkn.domain.modeling import BknLifecycleStatus


class DocumentType(StrEnum):
    KNOWLEDGE_NETWORK = "knowledge_network"
    OBJECT_TYPE = "object_type"
    RELATION_TYPE = "relation_type"
    ACTION_TYPE = "action_type"
    RISK_TYPE = "risk_type"


class DataProperty(DomainModel):
    name: str
    display_name: str
    value_type: str
    description: str = ""
    mapped_field: str


class DataSourceBinding(DomainModel):
    source_type: str
    source_id: str
    name: str = ""


class ObjectType(DomainModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    properties: list[DataProperty] = Field(default_factory=list)
    primary_keys: list[str] = Field(default_factory=list)
    display_key: str = ""
    incremental_key: str = ""
    data_source: DataSourceBinding | None = None
    source_path: str


class RelationEndpoint(DomainModel):
    source_object_type: str
    target_object_type: str
    relation_kind: str = "direct"


class RelationMapping(DomainModel):
    source_property: str
    target_property: str


class RelationType(DomainModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    endpoint: RelationEndpoint
    mappings: list[RelationMapping] = Field(default_factory=list)
    source_path: str


class ToolBinding(DomainModel):
    binding_type: str
    toolbox_id: str
    tool_id: str


class ParameterBinding(DomainModel):
    parameter: str
    source: str
    binding: str
    description: str = ""


class ActionType(DomainModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    action_kind: str = "modify"
    enabled: bool = True
    risk_level: str = "low"
    requires_approval: bool = False
    bound_object_type: str
    trigger_condition: dict[str, Any] = Field(default_factory=dict)
    tool: ToolBinding
    parameters: list[ParameterBinding] = Field(default_factory=list)
    source_path: str


class RiskType(DomainModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    level: str = "high"
    policy: str = "confirm"
    applies_to_actions: list[str] = Field(default_factory=list)
    condition: dict[str, Any] = Field(default_factory=dict)
    source_path: str


class KnowledgeNetwork(DomainModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    business_domain: str = "default"
    version: int = Field(default=1, ge=1)
    lifecycle_status: BknLifecycleStatus = BknLifecycleStatus.PUBLISHED
    source_path: str
    object_types: list[ObjectType] = Field(default_factory=list)
    relation_types: list[RelationType] = Field(default_factory=list)
    action_types: list[ActionType] = Field(default_factory=list)
    risk_types: list[RiskType] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DataSourceKind(StrEnum):
    CSV = "csv"
    SQLITE = "sqlite"


class ResourceField(DomainModel):
    name: str
    value_type: str
    nullable: bool = True
    primary_key: bool = False
    non_null_count: int = Field(default=0, ge=0)
    distinct_count: int = Field(default=0, ge=0)
    null_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    uniqueness_ratio: float = Field(default=0.0, ge=0.0, le=1.0)


class KeyCandidate(DomainModel):
    kind: Literal["primary", "foreign"]
    fields: list[str] = Field(min_length=1)
    target_resource_id: str = ""
    target_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    recommended: bool = False


class Resource(DomainModel):
    id: str
    source_id: str
    name: str
    locator: str
    fields: list[ResourceField] = Field(default_factory=list)
    row_count: int = 0
    primary_key_candidates: list[KeyCandidate] = Field(default_factory=list)
    foreign_key_candidates: list[KeyCandidate] = Field(default_factory=list)


class DataSource(DomainModel):
    id: str
    name: str
    kind: DataSourceKind
    path: str
    resources: list[Resource] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ObjectInstance(DomainModel):
    network_id: str
    object_type_id: str
    instance_id: str
    display_name: str
    resource_id: str
    row_number: int
    properties: dict[str, Any]


class RelationInstance(DomainModel):
    network_id: str
    relation_type_id: str
    source_object_type_id: str
    source_instance_id: str
    target_object_type_id: str
    target_instance_id: str


class SearchLevel(StrEnum):
    SCHEMA = "schema"
    INSTANCE = "instance"
    ACTION = "action"


class SearchMode(StrEnum):
    HYBRID = "hybrid"
    BM25 = "bm25"
    VECTOR = "vector"


class SearchDocument(DomainModel):
    id: str
    network_id: str
    level: SearchLevel
    entity_type: str
    entity_id: str
    title: str
    content: str
    citation: str
    vector: list[float] = Field(default_factory=list)


class SearchIndexManifest(DomainModel):
    network_id: str
    embedding_version: str
    dimensions: int = Field(ge=1)
    document_count: int = Field(ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SearchHit(DomainModel):
    document: SearchDocument
    score: float
    bm25_rank: int | None = None
    vector_rank: int | None = None


class Subgraph(DomainModel):
    nodes: list[ObjectInstance] = Field(default_factory=list)
    edges: list[RelationInstance] = Field(default_factory=list)


class ContextBundle(DomainModel):
    schema_hits: list[SearchHit] = Field(
        default_factory=list, validation_alias="schema", serialization_alias="schema"
    )
    instances: list[SearchHit] = Field(default_factory=list)
    subgraph: Subgraph = Field(default_factory=Subgraph)
    actions: list[SearchHit] = Field(default_factory=list)


class AskResult(DomainModel):
    question: str
    answer: str
    context: ContextBundle
    citations: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ActionExecutionStatus(StrEnum):
    PENDING_CONFIRMATION = "pending_confirmation"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


class RiskDecision(DomainModel):
    risk_type_id: str
    policy: str
    matched: bool
    reason: str


class RiskSimulationResult(DomainModel):
    network_id: str
    action_type_id: str
    object_type_id: str
    instance_id: str
    decision: str
    risk_decisions: list[RiskDecision] = Field(default_factory=list)


class ActionExecution(DomainModel):
    id: str
    network_id: str
    action_type_id: str
    object_type_id: str
    instance_id: str
    status: ActionExecutionStatus
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_decisions: list[RiskDecision] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    trace_id: str
    idempotency_key: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TraceEvent(DomainModel):
    id: str
    trace_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
