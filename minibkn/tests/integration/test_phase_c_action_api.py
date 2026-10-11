from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = PROJECT_ROOT / "examples" / "supply_chain"


async def _prepare(client: httpx.AsyncClient) -> None:
    imported = await client.post("/api/v1/networks/import", json={"path": str(EXAMPLE / "bkn")})
    assert imported.status_code == 201, imported.text
    registered = await client.post(
        "/api/v1/sources",
        json={
            "id": "supply_chain_files",
            "name": "Supply chain CSV files",
            "kind": "csv",
            "path": str(EXAMPLE / "data"),
        },
    )
    assert registered.status_code == 201, registered.text
    discovered = await client.post("/api/v1/sources/supply_chain_files/discover")
    assert discovered.status_code == 200, discovered.text
    materialized = await client.post("/api/v1/networks/supply_chain/materialize")
    assert materialized.status_code == 200, materialized.text


@pytest.mark.asyncio
async def test_risk_confirmation_tool_execution_and_trace(tmp_path: Path) -> None:
    database_path = (tmp_path / "minibkn.db").as_posix()
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            data_dir=tmp_path / "data",
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await _prepare(client)

            simulated = await client.post(
                "/api/v1/networks/supply_chain/actions/create_replenishment_alert/risks/simulate",
                json={"object_type_id": "material", "instance_id": "MAT-001"},
            )
            assert simulated.status_code == 200, simulated.text
            assert simulated.json()["decision"] == "confirm"
            assert simulated.json()["risk_decisions"][0]["matched"] is True

            high_value = await client.post(
                "/api/v1/networks/supply_chain/actions/create_replenishment_alert/execute",
                json={"object_type_id": "material", "instance_id": "MAT-001"},
                headers={"x-trace-id": "trace-phase-c-high-value"},
            )
            assert high_value.status_code == 200, high_value.text
            execution = high_value.json()
            assert execution["status"] == "pending_confirmation"
            assert execution["parameters"] == {
                "sku": "MAT-001",
                "current_stock": 8,
                "safety_stock": 30,
            }
            assert execution["risk_decisions"][0]["matched"] is True
            execution_id = execution["id"]

            before_confirmation = await client.get("/api/v1/traces/trace-phase-c-high-value")
            assert [item["event_type"] for item in before_confirmation.json()] == [
                "action.requested",
                "risk.evaluated",
                "action.awaiting_confirmation",
            ]

            confirmed = await client.post(
                f"/api/v1/action-executions/{execution_id}/confirm",
                json={"approved": True},
            )
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["status"] == "succeeded"
            assert confirmed.json()["result"]["status"] == "created"
            assert confirmed.json()["result"]["input"]["sku"] == "MAT-001"

            duplicate = await client.post(
                f"/api/v1/action-executions/{execution_id}/confirm",
                json={"approved": True},
            )
            assert duplicate.status_code == 409
            assert duplicate.json()["error_code"] == "INVALID_EXECUTION_STATE"

            trace = await client.get("/api/v1/traces/trace-phase-c-high-value")
            event_types = [item["event_type"] for item in trace.json()]
            assert event_types[-3:] == [
                "action.confirmation_approved",
                "tool.started",
                "tool.succeeded",
            ]

            low_value = await client.post(
                "/api/v1/networks/supply_chain/actions/create_replenishment_alert/execute",
                json={
                    "object_type_id": "material",
                    "instance_id": "MAT-003",
                    "idempotency_key": "replenish-MAT-003-v1",
                },
            )
            assert low_value.status_code == 200, low_value.text
            assert low_value.json()["status"] == "succeeded"
            assert low_value.json()["risk_decisions"][0]["matched"] is False

            repeated = await client.post(
                "/api/v1/networks/supply_chain/actions/create_replenishment_alert/execute",
                json={
                    "object_type_id": "material",
                    "instance_id": "MAT-003",
                    "idempotency_key": "replenish-MAT-003-v1",
                },
            )
            assert repeated.status_code == 200
            assert repeated.json()["id"] == low_value.json()["id"]


@pytest.mark.asyncio
async def test_rejected_confirmation_never_calls_tool(tmp_path: Path) -> None:
    database_path = (tmp_path / "minibkn.db").as_posix()
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path}",
            data_dir=tmp_path / "data",
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await _prepare(client)
            created = await client.post(
                "/api/v1/networks/supply_chain/actions/create_replenishment_alert/execute",
                json={"object_type_id": "material", "instance_id": "MAT-001"},
            )
            execution_id = created.json()["id"]
            rejected = await client.post(
                f"/api/v1/action-executions/{execution_id}/confirm",
                json={"approved": False},
            )
            assert rejected.status_code == 200
            assert rejected.json()["status"] == "denied"
            assert rejected.json()["result"] == {}
