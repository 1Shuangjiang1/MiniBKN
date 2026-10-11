"""Explicit allowlist for tools that may be called by ActionType definitions."""

from typing import Any
from uuid import uuid4

from minibkn.api.errors import MiniBKNError
from minibkn.ports.tools import ToolExecutor


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[tuple[str, str], ToolExecutor] = {}

    def register(self, toolbox_id: str, tool_id: str, tool: ToolExecutor) -> None:
        self._tools[(toolbox_id, tool_id)] = tool

    def get(self, toolbox_id: str, tool_id: str) -> ToolExecutor:
        tool = self._tools.get((toolbox_id, tool_id))
        if tool is None:
            raise MiniBKNError(
                error_code="TOOL_NOT_ALLOWED",
                message=f"tool '{toolbox_id}/{tool_id}' is not registered in the allowlist",
                status_code=403,
            )
        return tool


class ReplenishmentAlertTool:
    """Safe in-process demo tool; it never places an order or calls an external system."""

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "created",
            "alert_id": f"alert-{uuid4().hex[:12]}",
            "message": "Replenishment alert created in the local demo tool",
            "input": parameters,
        }
