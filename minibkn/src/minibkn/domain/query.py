# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Validated query-plan contracts; no raw SQL or executable code is allowed."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from minibkn.domain.base import DomainModel
from minibkn.domain.evidence import EvidenceItem


class QueryIntent(StrEnum):
    SEARCH = "search"
    LOOKUP = "lookup"
    TRAVERSE = "traverse"
    AGGREGATE = "aggregate"
    ACTION = "action"


class FilterOperator(StrEnum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    EXIST = "exist"
    NOT_EXIST = "not_exist"


class TraversalDirection(StrEnum):
    OUT = "out"
    IN = "in"
    BOTH = "both"


class AggregateFunction(StrEnum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class QueryAnalysisStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"


class FilterCondition(DomainModel):
    field: str
    operator: FilterOperator
    value: Any = None
    value_field: str = ""

    @model_validator(mode="after")
    def validate_operand(self) -> "FilterCondition":
        no_value = self.operator in {FilterOperator.EXIST, FilterOperator.NOT_EXIST}
        if no_value and (self.value is not None or self.value_field):
            raise ValueError("exist operators do not accept a comparison value")
        if not no_value and self.value is None and not self.value_field:
            raise ValueError("filter requires value or value_field")
        if self.value is not None and self.value_field:
            raise ValueError("filter cannot use both value and value_field")
        if self.operator in {FilterOperator.IN, FilterOperator.NOT_IN} and not isinstance(
            self.value, list
        ):
            raise ValueError("in operators require a list value")
        return self


class TraversalStep(DomainModel):
    relation: str
    direction: TraversalDirection = TraversalDirection.OUT
    max_hops: int = Field(default=1, ge=1, le=5)


class AggregateSpec(DomainModel):
    function: AggregateFunction
    field: str = ""
    alias: str

    @model_validator(mode="after")
    def require_field_for_numeric_aggregate(self) -> "AggregateSpec":
        if self.function != AggregateFunction.COUNT and not self.field:
            raise ValueError("field is required for non-count aggregates")
        return self


class SortSpec(DomainModel):
    field: str
    direction: SortDirection = SortDirection.ASC


class EvidenceBudget(DomainModel):
    max_items: int = Field(default=20, ge=1, le=100)
    max_tokens: int = Field(default=4000, ge=256, le=32000)


class ActionRequest(DomainModel):
    action_type_id: str
    object_type_id: str
    instance_id: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class QueryPlan(DomainModel):
    version: Literal["1.0"] = "1.0"
    intent: QueryIntent
    object_types: list[str] = Field(default_factory=list)
    select: list[str] = Field(default_factory=list)
    filters: list[FilterCondition] = Field(default_factory=list)
    traversals: list[TraversalStep] = Field(default_factory=list)
    aggregates: list[AggregateSpec] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[SortSpec] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
    evidence_budget: EvidenceBudget = Field(default_factory=EvidenceBudget)
    answer_mode: Literal["text", "table", "list"] = "text"
    action_request: ActionRequest | None = None

    @model_validator(mode="after")
    def validate_intent_payload(self) -> "QueryPlan":
        if self.intent == QueryIntent.ACTION and self.action_request is None:
            raise ValueError("action_request is required for action intent")
        if self.intent != QueryIntent.ACTION and self.action_request is not None:
            raise ValueError("action_request is only allowed for action intent")
        if self.aggregates and self.intent != QueryIntent.AGGREGATE:
            raise ValueError("plans with aggregates must use aggregate intent")
        if self.traversals and not self.aggregates and self.intent != QueryIntent.TRAVERSE:
            raise ValueError("plans with traversals must use traverse intent")
        return self


class QueryAmbiguity(DomainModel):
    id: str
    reason: str
    question: str
    options: list[str] = Field(default_factory=list)


class QueryAnalysis(DomainModel):
    original_question: str
    rewritten_question: str
    keywords: list[str] = Field(default_factory=list)
    synonym_expansions: dict[str, list[str]] = Field(default_factory=dict)
    sub_questions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[QueryAmbiguity] = Field(default_factory=list)
    clarification_answers: dict[str, str] = Field(default_factory=dict)
    status: QueryAnalysisStatus
    planner: Literal["rule", "llm"]
    plan: QueryPlan | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> "QueryAnalysis":
        if self.status == QueryAnalysisStatus.READY and self.plan is None:
            raise ValueError("ready analysis requires a query plan")
        if self.status == QueryAnalysisStatus.NEEDS_CLARIFICATION and not self.ambiguities:
            raise ValueError("clarification status requires at least one ambiguity")
        if self.status == QueryAnalysisStatus.NEEDS_CLARIFICATION and self.plan is not None:
            raise ValueError("ambiguous analysis cannot contain an executable plan")
        return self


class QueryExecutionResult(DomainModel):
    plan: QueryPlan
    rows: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    scanned_objects: int = Field(default=0, ge=0)
