import json
from pathlib import Path

import httpx
import pytest

from minibkn.adapters.bkn_lang import BknLangParser
from minibkn.adapters.llm import OpenAICompatibleQueryPlanner
from minibkn.application.query_plan_service import QueryPlanService
from minibkn.domain.query import QueryIntent, QueryPlan

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_openai_compatible_planner_returns_validated_query_plan() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer secret"
        assert payload["response_format"] == {"type": "json_object"}
        assert "Never output SQL" in payload["messages"][0]["content"]
        plan = {
            "intent": "aggregate",
            "object_types": ["order"],
            "filters": [{"field": "order.status", "operator": "eq", "value": "paid"}],
            "aggregates": [{"function": "sum", "field": "order.amount", "alias": "revenue"}],
            "group_by": ["order.customer_id"],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan)}}]})

    network = BknLangParser().parse_directory(PROJECT_ROOT / "examples" / "crm" / "bkn")
    planner = OpenAICompatibleQueryPlanner(
        "https://llm.example/v1",
        "secret",
        "planner-model",
        transport=httpx.MockTransport(handler),
    )

    plan = await planner.plan("统计已付款客户收入", network)

    assert plan.intent == QueryIntent.AGGREGATE
    assert plan.aggregates[0].alias == "revenue"


@pytest.mark.asyncio
async def test_planner_rejects_extra_or_executable_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        plan = {"intent": "search", "raw_sql": "select * from orders"}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan)}}]})

    network = BknLangParser().parse_directory(PROJECT_ROOT / "examples" / "crm" / "bkn")
    planner = OpenAICompatibleQueryPlanner(
        "https://llm.example/v1",
        "secret",
        "planner-model",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValueError):
        await planner.plan("执行任意查询", network)


@pytest.mark.asyncio
async def test_openai_compatible_analyzer_returns_rewrite_and_clarification() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        result = {
            "original_question": "ignored",
            "rewritten_question": "查询近一段时间的大客户",
            "keywords": ["客户", "订单金额"],
            "synonym_expansions": {"customer": ["客户"]},
            "sub_questions": ["查询大客户"],
            "assumptions": [],
            "ambiguities": [
                {
                    "id": "time_range",
                    "reason": "时间范围不明确",
                    "question": "最近是多久？",
                    "options": ["近7天", "近30天"],
                }
            ],
            "clarification_answers": {},
            "status": "needs_clarification",
            "planner": "llm",
            "plan": None,
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(result)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    network = BknLangParser().parse_directory(PROJECT_ROOT / "examples" / "crm" / "bkn")
    planner = OpenAICompatibleQueryPlanner(
        "https://llm.example/v1",
        "secret",
        "planner-model",
        transport=httpx.MockTransport(handler),
    )

    analysis = await planner.analyze("最近的大客户怎么样", network)

    assert analysis.status == "needs_clarification"
    assert analysis.ambiguities[0].id == "time_range"
    assert analysis.original_question == "最近的大客户怎么样"
    assert planner.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def test_query_plan_rejects_unknown_categorical_filter_value_before_execution() -> None:
    plan = QueryPlan.model_validate(
        {
            "intent": "aggregate",
            "object_types": ["order"],
            "filters": [{"field": "status", "operator": "eq", "value": "已付款"}],
            "aggregates": [{"function": "sum", "field": "amount", "alias": "total"}],
        }
    )

    ambiguities = QueryPlanService._invalid_filter_values(
        plan, {"order.status": ["cancelled", "paid", "pending"]}
    )

    assert len(ambiguities) == 1
    assert ambiguities[0].id == "filter_value:status"
    assert ambiguities[0].options == ["cancelled", "paid", "pending"]
