from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRM_DATA = PROJECT_ROOT / "examples" / "crm" / "data"


@pytest.mark.asyncio
async def test_modeling_proposals_require_review_before_human_publication(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'minibkn.db').as_posix()}",
            data_dir=tmp_path / "runtime",
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            source = await client.post(
                "/api/v1/sources",
                json={
                    "id": "crm_modeling_source",
                    "name": "CRM modeling source",
                    "kind": "csv",
                    "path": str(CRM_DATA),
                },
            )
            assert source.status_code == 201
            assert (
                await client.post("/api/v1/sources/crm_modeling_source/discover")
            ).status_code == 200

            created = await client.post(
                "/api/v1/modeling-sessions",
                json={
                    "source_id": "crm_modeling_source",
                    "network_id": "crm_reviewed",
                    "name": "Reviewed CRM",
                    "instruction": "客户订单需要创建审批动作，并默认要求人工确认",
                },
            )
            assert created.status_code == 201, created.text
            session = created.json()
            assert session["status"] == "in_review"
            assert {item["kind"] for item in session["proposals"]} >= {
                "object_type",
                "property",
                "primary_key",
                "relation",
                "action",
                "risk",
            }

            blocked = await client.post(
                f"/api/v1/modeling-sessions/{session['id']}/publish",
                json={"published_by": "product-owner"},
            )
            assert blocked.status_code == 409
            assert blocked.json()["error_code"] == "MODELING_REVIEW_INCOMPLETE"

            action = next(item for item in session["proposals"] if item["kind"] == "action")
            unsafe_payload = {**action["payload"], "enabled": True}
            unsafe = await client.patch(
                f"/api/v1/modeling-sessions/{session['id']}/proposals/{action['id']}",
                json={
                    "status": "modified",
                    "reviewed_by": "reviewer",
                    "payload": unsafe_payload,
                },
            )
            assert unsafe.status_code == 400
            assert unsafe.json()["error_code"] == "INVALID_MODELING_PROPOSAL"

            for proposal in session["proposals"]:
                reviewed = await client.patch(
                    f"/api/v1/modeling-sessions/{session['id']}/proposals/{proposal['id']}",
                    json={"status": "accepted", "reviewed_by": "reviewer"},
                )
                assert reviewed.status_code == 200, reviewed.text
            assert reviewed.json()["status"] == "ready"

            published = await client.post(
                f"/api/v1/modeling-sessions/{session['id']}/publish",
                json={"published_by": "product-owner"},
            )
            assert published.status_code == 200, published.text
            network = published.json()
            assert network["lifecycle_status"] == "published"
            assert {item["id"] for item in network["object_types"]} == {
                "customer",
                "order",
            }
            assert network["action_types"][0]["enabled"] is False
            assert network["action_types"][0]["requires_approval"] is True
            assert network["risk_types"][0]["policy"] == "confirm"

            saved_session = await client.get(f"/api/v1/modeling-sessions/{session['id']}")
            assert saved_session.status_code == 200
            assert saved_session.json()["status"] == "published"
            assert saved_session.json()["published_network_version"] == 1

            built = await client.post("/api/v1/networks/crm_reviewed/builds")
            assert built.status_code == 200
            assert built.json()["status"] == "published"
