import json

import httpx
import pytest

from minibkn.adapters.llm import OpenAICompatibleSchemaEnhancer


@pytest.mark.asyncio
async def test_openai_compatible_schema_enrichment_is_constrained() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0
        assert "Never change ids" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "object_descriptions": {"material": "A managed inventory item"},
                                    "relation_descriptions": {},
                                }
                            )
                        }
                    }
                ]
            },
        )

    enhancer = OpenAICompatibleSchemaEnhancer(
        "https://example.test/v1",
        "test-key",
        "test-model",
        httpx.MockTransport(handler),
    )
    result = await enhancer.enhance({"objects": [{"id": "material"}]})
    assert result["object_descriptions"]["material"] == "A managed inventory item"
