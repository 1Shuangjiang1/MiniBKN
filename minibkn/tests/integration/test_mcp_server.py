from typing import Any

import pytest
from mcp import Client

from minibkn.mcp_server import build_mcp_server


class FakeGateway:
    async def search(self, network_id: str, query: str, limit: int) -> list[dict[str, Any]]:
        return [{"network_id": network_id, "query": query, "limit": limit}]

    async def ask(self, network_id: str, question: str) -> dict[str, Any]:
        return {"network_id": network_id, "question": question, "citations": ["bkn://demo"]}

    async def execute_action(
        self,
        network_id: str,
        action_type_id: str,
        object_type_id: str,
        instance_id: str,
    ) -> dict[str, Any]:
        return {
            "network_id": network_id,
            "action_type_id": action_type_id,
            "object_type_id": object_type_id,
            "instance_id": instance_id,
            "status": "pending_confirmation",
        }


@pytest.mark.asyncio
async def test_native_mcp_tools_are_discoverable_and_callable() -> None:
    server = build_mcp_server(FakeGateway())
    async with Client(server) as client:
        tools = await client.list_tools()
        assert {item.name for item in tools.tools} == {
            "ask_knowledge",
            "request_action",
            "search_knowledge",
        }

        result = await client.call_tool(
            "ask_knowledge",
            {"network_id": "supply_chain", "question": "who supplies MAT-001?"},
        )
        assert result.structured_content == {
            "network_id": "supply_chain",
            "question": "who supplies MAT-001?",
            "citations": ["bkn://demo"],
        }
