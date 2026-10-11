# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Shared configuration for immutable MiniBKN domain contracts."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)
