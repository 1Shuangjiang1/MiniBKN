"""Safe tool execution port."""

from typing import Any, Protocol


class ToolExecutor(Protocol):
    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]: ...
