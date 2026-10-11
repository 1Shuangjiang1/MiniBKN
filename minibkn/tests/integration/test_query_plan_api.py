from pathlib import Path

import httpx
import pytest

from minibkn.application.query_plan_service import QueryPlanService
from minibkn.config import Settings
from minibkn.main import create_app

ROOT = Path(__file__).resolve().parents[2] / "examples"


async def _load(client: httpx.AsyncClient, name: str) -> None:
    example = ROOT / name
    assert (
        await client.post("/api/v1/networks/import", json={"path": str(example / "bkn")})
    ).status_code == 201
    source_id = f"{name}_files"
    assert (
        await client.post(
            "/api/v1/sources",
            json={"id": source_id, "name": name, "kind": "csv", "path": str(example / "data")},
        )
    ).status_code == 201
    assert (await client.post(f"/api/v1/sources/{source_id}/discover")).status_code == 200
    assert (await client.post(f"/api/v1/networks/{name}/materialize")).status_code == 200


@pytest.mark.asyncio
async def test_query_plan_executes_field_comparison_and_crm_aggregation(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "data",
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _load(client, "supply_chain")
            compared = await client.post(
                "/api/v1/networks/supply_chain/query-plans/execute",
                json={
                    "plan": {
                        "intent": "lookup",
                        "object_types": ["material"],
                        "filters": [
                            {
                                "field": "material.current_stock",
                                "operator": "lt",
                                "value_field": "material.safety_stock",
                            }
                        ],
                        "select": ["material.sku", "material.current_stock"],
                    }
                },
            )
            assert compared.status_code == 200, compared.text
            assert {row["material.sku"] for row in compared.json()["rows"]} == {
                "MAT-001",
                "MAT-003",
            }

            await _load(client, "crm")
            aggregated = await client.post(
                "/api/v1/networks/crm/query-plans/execute",
                json={
                    "plan": {
                        "intent": "aggregate",
                        "object_types": ["order"],
                        "filters": [{"field": "order.status", "operator": "eq", "value": "paid"}],
                        "aggregates": [
                            {"function": "sum", "field": "order.amount", "alias": "revenue"}
                        ],
                        "group_by": ["order.customer_id"],
                        "order_by": [{"field": "revenue", "direction": "desc"}],
                    }
                },
            )
            assert aggregated.status_code == 200, aggregated.text
            assert aggregated.json()["rows"] == [
                {"order.customer_id": "CUST-001", "revenue": 128000.5},
                {"order.customer_id": "CUST-002", "revenue": 8600.0},
            ]
            assert any(item["kind"] == "computed" for item in aggregated.json()["evidence"])
            assert aggregated.json()["evidence"][0]["kind"] == "computed"
            assert "结构化查询计划" in aggregated.json()["evidence"][0]["content"]

            traversed = await client.post(
                "/api/v1/networks/crm/query-plans/execute",
                json={
                    "plan": {
                        "intent": "traverse",
                        "object_types": ["order"],
                        "filters": [
                            {"field": "order.order_id", "operator": "eq", "value": "ORD-001"}
                        ],
                        "traversals": [{"relation": "placed_by", "direction": "out"}],
                    }
                },
            )
            assert traversed.status_code == 200, traversed.text
            evidence_ids = {item["entity_id"] for item in traversed.json()["evidence"]}
            assert {"ORD-001", "CUST-001"} <= evidence_ids
            assert any(item["kind"] == "relation" for item in traversed.json()["evidence"])


@pytest.mark.asyncio
async def test_query_plan_rejects_unknown_schema_fields(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "data",
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _load(client, "crm")
            response = await client.post(
                "/api/v1/networks/crm/query-plans/execute",
                json={
                    "plan": {
                        "intent": "lookup",
                        "object_types": ["customer"],
                        "filters": [{"field": "customer.password", "operator": "eq", "value": "x"}],
                    }
                },
            )
            assert response.status_code == 422
            assert response.json()["error_code"] == "INVALID_QUERY_PLAN"

            await _load(client, "supply_chain")
            bulk_action = await client.post(
                "/api/v1/networks/supply_chain/query-plans/execute",
                json={
                    "plan": {
                        "intent": "action",
                        "object_types": ["material"],
                        "action_request": {
                            "action_type_id": "create_replenishment_alert",
                            "object_type_id": "material",
                            "instance_id": "",
                        },
                    }
                },
            )
            assert bulk_action.status_code == 422
            assert bulk_action.json()["error_code"] == "INVALID_QUERY_PLAN"

            explicit_action = await client.post(
                "/api/v1/networks/supply_chain/query-plans/execute",
                json={
                    "plan": {
                        "intent": "action",
                        "object_types": ["material"],
                        "action_request": {
                            "action_type_id": "create_replenishment_alert",
                            "object_type_id": "material",
                            "instance_id": "MAT-001",
                        },
                    }
                },
            )
            assert explicit_action.status_code == 422
            assert explicit_action.json()["error_code"] == "ACTION_REQUIRES_ACTION_ENDPOINT"


@pytest.mark.asyncio
async def test_query_analysis_rewrites_splits_and_requests_clarification(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "data",
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _load(client, "crm")
            ambiguous = await client.post(
                "/api/v1/networks/crm/query-plans/analyze",
                json={"question": "最近的大客户怎么样，同时看看订单"},
            )
            assert ambiguous.status_code == 200, ambiguous.text
            result = ambiguous.json()
            assert result["status"] == "needs_clarification"
            assert {item["id"] for item in result["ambiguities"]} == {
                "time_range",
                "size_metric",
            }
            assert len(result["sub_questions"]) == 2
            assert {"customer", "客户", "顾客"} <= set(result["synonym_expansions"]["customer"])

            clarified = await client.post(
                "/api/v1/networks/crm/query-plans/analyze",
                json={
                    "question": "最近的大客户怎么样，同时看看订单",
                    "clarification_answers": {
                        "time_range": "近30天",
                        "size_metric": "累计订单金额",
                    },
                },
            )
            assert clarified.status_code == 200, clarified.text
            clarified_result = clarified.json()
            assert clarified_result["status"] == "ready"
            assert clarified_result["plan"] is not None
            assert "补充条件" in clarified_result["rewritten_question"]

            preview = await client.post(
                "/api/v1/networks/crm/query-plans/preview",
                json={"question": "最近的大客户怎么样"},
            )
            assert preview.status_code == 409
            assert preview.json()["error_code"] == "QUERY_CLARIFICATION_REQUIRED"


@pytest.mark.asyncio
async def test_intelligent_ask_stops_for_clarification_then_executes(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "data",
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _load(client, "crm")
            await client.post("/api/v1/networks/crm/index")

            ambiguous = await client.post(
                "/api/v1/networks/crm/ask-intelligent",
                json={"question": "最近的大客户怎么样"},
            )
            assert ambiguous.status_code == 200, ambiguous.text
            payload = ambiguous.json()
            assert payload["status"] == "needs_clarification"
            assert payload["answer"] == ""
            assert payload["execution"] is None
            assert payload["retrieval"] is None
            assert {item["id"] for item in payload["analysis"]["ambiguities"]} == {
                "time_range",
                "size_metric",
            }

            clarified = await client.post(
                "/api/v1/networks/crm/ask-intelligent",
                json={
                    "question": "最近的大客户怎么样",
                    "clarification_answers": {
                        "time_range": "近30天",
                        "size_metric": "累计订单金额",
                    },
                },
            )
            assert clarified.status_code == 200, clarified.text
            resolved = clarified.json()
            assert resolved["status"] == "ready"
            assert resolved["analysis"]["rewritten_question"]
            assert resolved["retrieval"] is not None
            assert resolved["answer"]


def test_query_analysis_expansions_feed_retrieval_query() -> None:
    from minibkn.domain.query import QueryAnalysis

    analysis = QueryAnalysis.model_validate(
        {
            "original_question": "查客户订单",
            "rewritten_question": "查询客户及其订单",
            "keywords": ["客户", "订单"],
            "synonym_expansions": {
                "customer": ["客户", "顾客"],
                "order": ["订单", "交易单"],
            },
            "sub_questions": ["查询客户", "查询订单"],
            "status": "ready",
            "planner": "rule",
            "plan": {"intent": "search"},
        }
    )

    query = QueryPlanService._retrieval_query(analysis)

    assert "查询客户及其订单" in query
    assert "顾客" in query
    assert "交易单" in query
    assert len(query.split()) == len(set(query.split()))
