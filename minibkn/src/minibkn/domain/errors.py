"""BKN parsing and validation errors."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    message: str


class BknLangError(ValueError):
    """Base class for invalid BKN Lang input."""

    def __init__(self, message: str, issues: list[ValidationIssue] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


class BknParseError(BknLangError):
    """Raised when the syntax of one BKN document cannot be parsed."""


class BknValidationError(BknLangError):
    """Raised when parsed BKN documents violate domain constraints."""
