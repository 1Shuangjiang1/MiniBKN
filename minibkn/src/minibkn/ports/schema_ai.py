"""Optional AI enrichment port for generated business Schema drafts."""

from typing import Any, Protocol


class SchemaEnhancer(Protocol):
    async def enhance(self, draft: dict[str, Any]) -> dict[str, Any]: ...
