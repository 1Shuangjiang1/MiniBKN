"""Constrained OpenAI-compatible enrichment for deterministic Schema drafts."""

import json
from typing import Any

import httpx


class OpenAICompatibleSchemaEnhancer:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._transport = transport

    async def enhance(self, draft: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "You assist a human who is drafting a business knowledge network. "
            "Never change ids, fields, primary keys, or mappings supplied by the system. "
            "Return strict JSON with "
            "object_descriptions and relation_descriptions maps. You may also return "
            "action_suggestions and risk_suggestions arrays, but every action must be disabled, "
            "require approval, bind to an existing object id, and use the unconfigured "
            "tool binding. Every risk must use only the documented safe expression tree "
            "and policy confirm or deny. "
            "Suggestions are drafts requiring human review. Input:\n"
            + json.dumps(draft, ensure_ascii=False)
        )
        async with httpx.AsyncClient(timeout=60, transport=self._transport) as client:
            response = await client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        value = json.loads(content)
        return value if isinstance(value, dict) else {}
