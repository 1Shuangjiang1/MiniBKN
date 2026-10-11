"""Native MCP 2.x server exposing MiniBKN retrieval and controlled actions."""

from typing import Any, Protocol

import httpx
from mcp.server import MCPServer

from minibkn.config import Settings


class MiniBKNGateway(Protocol):
    async def search(self, network_id: str, query: str, limit: int) -> list[dict[str, Any]]: ...

    async def ask(self, network_id: str, question: str) -> dict[str, Any]: ...

    async def execute_action(
        self,
        network_id: str,
        action_type_id: str,
        object_type_id: str,
        instance_id: str,
    ) -> dict[str, Any]: ...


class HttpMiniBKNGateway:
    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"x-api-key": api_key} if api_key else {}

    async def search(self, network_id: str, query: str, limit: int) -> list[dict[str, Any]]:
        value = await self._post(
            f"/api/v1/networks/{network_id}/search", {"query": query, "limit": limit}
        )
        if not isinstance(value, list):
            raise RuntimeError("MiniBKN search returned an unexpected response")
        return value

    async def ask(self, network_id: str, question: str) -> dict[str, Any]:
        value = await self._post(f"/api/v1/networks/{network_id}/ask", {"question": question})
        if not isinstance(value, dict):
            raise RuntimeError("MiniBKN ask returned an unexpected response")
        return value

    async def execute_action(
        self,
        network_id: str,
        action_type_id: str,
        object_type_id: str,
        instance_id: str,
    ) -> dict[str, Any]:
        value = await self._post(
            f"/api/v1/networks/{network_id}/actions/{action_type_id}/execute",
            {"object_type_id": object_type_id, "instance_id": instance_id},
        )
        if not isinstance(value, dict):
            raise RuntimeError("MiniBKN action returned an unexpected response")
        return value

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(
            base_url=self._base_url, headers=self._headers, timeout=30
        ) as client:
            response = await client.post(path, json=payload)
            response.raise_for_status()
            return response.json()


def build_mcp_server(gateway: MiniBKNGateway | None = None) -> MCPServer:
    settings = Settings()
    gateway = gateway or HttpMiniBKNGateway(settings.api_base_url, settings.api_key)
    server = MCPServer(
        "MiniBKN",
        instructions=(
            "Search business knowledge networks, ask cited questions, and request controlled "
            "business actions. Actions may require separate human confirmation through MiniBKN."
        ),
    )

    @server.tool()
    async def search_knowledge(network_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        """Hybrid-search Schema, business instances, and actions in a knowledge network."""
        return {"entries": await gateway.search(network_id, query, limit)}

    @server.tool()
    async def ask_knowledge(network_id: str, question: str) -> dict[str, Any]:
        """Answer a business question with three-level context and source citations."""
        return await gateway.ask(network_id, question)

    @server.tool()
    async def request_action(
        network_id: str,
        action_type_id: str,
        object_type_id: str,
        instance_id: str,
    ) -> dict[str, Any]:
        """Request an allowlisted action; risk policy may return pending_confirmation."""
        return await gateway.execute_action(network_id, action_type_id, object_type_id, instance_id)

    return server


mcp = build_mcp_server()


def run() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
