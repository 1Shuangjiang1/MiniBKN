# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""OpenAI-compatible constrained QueryPlan generation."""

import json
from typing import Any

import httpx

from minibkn.domain.models import KnowledgeNetwork
from minibkn.domain.query import QueryAnalysis, QueryPlan


class OpenAICompatibleQueryPlanner:
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
        self._usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    @property
    def usage(self) -> dict[str, int]:
        return dict(self._usage)

    async def plan(self, question: str, network: KnowledgeNetwork) -> QueryPlan:
        analysis = await self.analyze(question, network)
        if analysis.plan is None:
            raise ValueError("query requires clarification before planning")
        return analysis.plan

    async def analyze(
        self,
        question: str,
        network: KnowledgeNetwork,
        clarification_answers: dict[str, str] | None = None,
        value_hints: dict[str, list[str]] | None = None,
    ) -> QueryAnalysis:
        schema = {
            "objects": [
                {
                    "id": item.id,
                    "name": item.name,
                    "properties": [prop.name for prop in item.properties],
                }
                for item in network.object_types
            ],
            "relations": [
                {
                    "id": item.id,
                    "source": item.endpoint.source_object_type,
                    "target": item.endpoint.target_object_type,
                }
                for item in network.relation_types
            ],
            "actions": [item.id for item in network.action_types if item.enabled],
        }
        answers = clarification_answers or {}
        contract = QueryAnalysis.model_json_schema()
        prompt = (
            "Analyze the business question and return exactly one JSON object, without prose. "
            "First normalize and rewrite the question, extract useful keywords and schema-aware "
            "synonyms, and split genuinely independent goals into sub_questions. Detect only "
            "material ambiguities that change filters, metrics, time ranges, entities, relations, "
            "or requested actions. Do not ask a question when a safe exact interpretation exists. "
            "If material ambiguity remains, set status=needs_clarification, provide one or more "
            "ambiguities with stable id/reason/question/options, and set plan=null. If answers "
            "resolve all ambiguity, set status=ready and generate a QueryPlan in plan. "
            "Use only supplied object, relation, action ids and fields. Never output SQL, code, "
            "prose outside JSON, or unknown fields. QueryPlan operators are eq, neq, gt, gte, lt, "
            "lte, in, not_in, like, exist, not_exist; field comparison uses value_field. "
            "QueryPlan intent rules are strict: use aggregate whenever aggregates is non-empty; "
            "otherwise use traverse whenever traversals is non-empty; use action only with an "
            "action_request; use lookup for exact structured filters or listing known object "
            "types; reserve search for relevance-style discovery without structured criteria. "
            "For traversal, object_types contains ONLY the starting object types, never target "
            "types reached by the relation. For count, field MUST be an empty string because the "
            "executor counts rows. Relative terms such as recent/latest require clarification "
            "unless an exact time range is present in the question or clarification answers. "
            "For eq/in filters on fields listed in Allowed field values, use only the exact "
            "stored value from that list; translate the user's wording to that stored value. "
            "The top-level JSON fields must be original_question, rewritten_question, keywords, "
            "synonym_expansions, sub_questions, assumptions, ambiguities, clarification_answers, "
            "status, planner, plan. Set planner=llm. Each ambiguity has id, reason, question, "
            "options. Schema:\n"
            + json.dumps(schema, ensure_ascii=False)
            + "\nThe response MUST validate against this JSON Schema:\n"
            + json.dumps(contract, ensure_ascii=False)
            + "\nAllowed low-cardinality field values:\n"
            + json.dumps(value_hints or {}, ensure_ascii=False)
            + "\nOriginal question:\n"
            + question
            + "\nClarification answers:\n"
            + json.dumps(answers, ensure_ascii=False)
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
        payload: dict[str, Any] = response.json()
        usage = payload.get("usage", {})
        for key in self._usage:
            value = usage.get(key, 0)
            if isinstance(value, int):
                self._usage[key] += value
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if "intent" in parsed:
            return QueryAnalysis(
                original_question=question,
                rewritten_question=question,
                keywords=[],
                sub_questions=[question],
                clarification_answers=answers,
                status="ready",
                planner="llm",
                plan=QueryPlan.model_validate(parsed),
            )
        parsed["original_question"] = question
        parsed["clarification_answers"] = answers
        parsed["planner"] = "llm"
        return QueryAnalysis.model_validate(parsed)
