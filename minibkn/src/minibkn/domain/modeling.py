# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Contracts for reviewable AI-assisted modeling and BKN version lifecycle."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from minibkn.domain.base import DomainModel


class ProposalKind(StrEnum):
    OBJECT_TYPE = "object_type"
    PROPERTY = "property"
    PRIMARY_KEY = "primary_key"
    RELATION = "relation"
    ACTION = "action"
    RISK = "risk"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


class BknLifecycleStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    PUBLISHED = "published"


class ModelingSessionStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    READY = "ready"
    PUBLISHED = "published"


class SchemaProposal(DomainModel):
    id: str
    session_id: str
    kind: ProposalKind
    target_id: str
    payload: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""
    status: ProposalStatus = ProposalStatus.PENDING
    reviewed_by: str = ""
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BknVersion(DomainModel):
    network_id: str
    version: int = Field(ge=1)
    status: BknLifecycleStatus = BknLifecycleStatus.DRAFT
    content_hash: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None


class ModelingSession(DomainModel):
    id: str
    source_id: str
    network_id: str
    name: str
    instruction: str = ""
    use_ai: bool = False
    status: ModelingSessionStatus = ModelingSessionStatus.DRAFT
    proposals: list[SchemaProposal] = Field(default_factory=list)
    published_network_version: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
