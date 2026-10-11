"""Unified API error responses."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MiniBKNError(Exception):
    """An expected application error that can be rendered as an API response."""

    error_code: str
    message: str
    status_code: int = 400
    details: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return self.message


class ResourceNotFoundError(MiniBKNError):
    """Raised when a requested domain resource does not exist."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            error_code="RESOURCE_NOT_FOUND",
            message=f"{resource} '{resource_id}' does not exist",
            status_code=404,
        )
