import hashlib
import json
from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRM = PROJECT_ROOT / "examples" / "crm"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.mark.asyncio
async def test_rbac_filters_files_and_denies_modeling_and_actions(tmp_path: Path) -> None:
    policy = tmp_path / "access.json"
    policy.write_text(
        json.dumps(
            {
                "roles": {
                    "customer_reader": {
                        "permissions": ["read"],
                        "networks": ["crm"],
                        "resources": ["customers_csv"],
                        "document_collections": ["public"],
                        "actions": [],
                    }
                },
                "principals": [
                    {
                        "id": "alice",
                        "roles": ["customer_reader"],
                        "api_key_sha256": _digest("alice-key"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "data",
            api_key="admin-key",
            authorization_enabled=True,
            authorization_policy_file=policy,
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            admin = {"x-api-key": "admin-key"}
            alice = {"x-api-key": "alice-key"}
            assert (
                await client.post(
                    "/api/v1/networks/import", headers=admin, json={"path": str(CRM / "bkn")}
                )
            ).status_code == 201
            assert (
                await client.post(
                    "/api/v1/sources",
                    headers=admin,
                    json={
                        "id": "crm_files",
                        "name": "CRM",
                        "kind": "csv",
                        "path": str(CRM / "data"),
                    },
                )
            ).status_code == 201
            await client.post("/api/v1/sources/crm_files/discover", headers=admin)
            await client.post("/api/v1/networks/crm/builds", headers=admin)

            assert (await client.get("/api/v1/networks")).status_code == 401
            assert (await client.get("/api/v1/networks", headers=alice)).status_code == 200
            customers = await client.get(
                "/api/v1/networks/crm/object-types/customer/instances", headers=alice
            )
            orders = await client.get(
                "/api/v1/networks/crm/object-types/order/instances", headers=alice
            )
            assert customers.status_code == 200 and customers.json()
            assert orders.status_code == 200 and orders.json() == []

            searched = await client.post(
                "/api/v1/networks/crm/search",
                headers=alice,
                json={"query": "订单 ORD-1001", "limit": 20},
            )
            assert searched.status_code == 200
            assert not any(
                hit["document"]["citation"].startswith("resource://orders_csv")
                for hit in searched.json()
            )

            denied_model = await client.post("/api/v1/networks/crm/index", headers=alice)
            denied_action = await client.post(
                "/api/v1/networks/crm/actions/create_followup_task/execute",
                headers=alice,
                json={"object_type_id": "customer", "instance_id": "C001"},
            )
            assert denied_model.status_code == 403
            assert denied_action.status_code == 403

            schema = await client.get("/api/v1/networks/crm/schema", headers=alice)
            assert {item["id"] for item in schema.json()["object_types"]} == {"customer"}


@pytest.mark.asyncio
async def test_invalid_policy_fails_closed(tmp_path: Path) -> None:
    policy = tmp_path / "bad.json"
    policy.write_text(
        json.dumps({"roles": {}, "principals": [{"id": "bad", "api_key_sha256": "secret"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SHA-256"):
        create_app(
            Settings(
                database_url=f"sqlite+aiosqlite:///{(tmp_path / 'db.sqlite').as_posix()}",
                data_dir=tmp_path,
                authorization_enabled=True,
                authorization_policy_file=policy,
            )
        )
