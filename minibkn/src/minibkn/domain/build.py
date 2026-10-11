# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Contracts for future incremental materialization and indexing."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from minibkn.domain.base import DomainModel


class BuildJobStatus(StrEnum):
    PENDING = "pending"
    PROFILING = "profiling"
    MATERIALIZING = "materializing"
    INDEXING = "indexing"
    VALIDATING = "validating"
    PUBLISHED = "published"
    FAILED = "failed"


class RecordChange(DomainModel):
    object_type_id: str
    instance_id: str
    content_hash: str = ""


class ChangeSet(DomainModel):
    inserted: list[RecordChange] = Field(default_factory=list)
    updated: list[RecordChange] = Field(default_factory=list)
    deleted: list[RecordChange] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.inserted) + len(self.updated) + len(self.deleted)


class BuildJob(DomainModel):
    id: str
    network_id: str
    target_version: int = Field(ge=1)
    status: BuildJobStatus = BuildJobStatus.PENDING
    change_set: ChangeSet = Field(default_factory=ChangeSet)
    relation_inserted: int = Field(default=0, ge=0)
    relation_deleted: int = Field(default=0, ge=0)
    index_inserted: int = Field(default=0, ge=0)
    index_updated: int = Field(default=0, ge=0)
    index_deleted: int = Field(default=0, ge=0)
    embedded_documents: int = Field(default=0, ge=0)
    full_rebuild: bool = False
    error: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
