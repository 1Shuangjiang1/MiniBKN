# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Provider-neutral evidence contracts used by retrieval and answering."""

from enum import StrEnum
from typing import Any

from pydantic import Field

from minibkn.domain.base import DomainModel


class EvidenceKind(StrEnum):
    SCHEMA = "schema"
    INSTANCE = "instance"
    RELATION = "relation"
    ACTION = "action"
    COMPUTED = "computed"
    DOCUMENT = "document"


class EvidenceItem(DomainModel):
    id: str
    network_id: str
    kind: EvidenceKind
    title: str
    content: str
    citation: str
    entity_type: str = ""
    entity_id: str = ""
    score: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
