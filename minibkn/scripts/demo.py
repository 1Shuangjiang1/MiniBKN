"""Run the complete MiniBKN workflow in-process and print an acceptance summary."""

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT_ROOT / "examples" / "supply_chain"


async def _request(
    client: httpx.AsyncClient, method: str, path: str, **kwargs: Any
) -> dict[str, Any]:
    response = await client.request(method, path, **kwargs)
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected an object response from {path}")
    return value


async def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    database_path = PROJECT_ROOT / "data" / f"demo-{timestamp}.db"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
        data_dir=PROJECT_ROOT / "data",
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://demo") as client:
            await _request(
                client, "POST", "/api/v1/networks/import", json={"path": str(EXAMPLE / "bkn")}
            )
            await _request(
                client,
                "POST",
                "/api/v1/sources",
                json={
                    "id": "supply_chain_files",
                    "name": "Supply chain CSV files",
                    "kind": "csv",
                    "path": str(EXAMPLE / "data"),
                },
            )
            source = await _request(client, "POST", "/api/v1/sources/supply_chain_files/discover")
            graph = await _request(client, "POST", "/api/v1/networks/supply_chain/materialize")
            index = await _request(client, "POST", "/api/v1/networks/supply_chain/index")
            answer = await _request(
                client,
                "POST",
                "/api/v1/networks/supply_chain/ask",
                json={"question": "哪些物料库存低于安全库存，它们由谁供应？"},
            )
            action = await _request(
                client,
                "POST",
                "/api/v1/networks/supply_chain/actions/create_replenishment_alert/execute",
                json={"object_type_id": "material", "instance_id": "MAT-001"},
                headers={"x-trace-id": f"trace-demo-{timestamp}"},
            )
            confirmed = await _request(
                client,
                "POST",
                f"/api/v1/action-executions/{action['id']}/confirm",
                json={"approved": True},
            )
            trace_response = await client.get(f"/api/v1/traces/{action['trace_id']}")
            trace_response.raise_for_status()
            trace = trace_response.json()

    summary = {
        "database": str(database_path),
        "resources": [item["id"] for item in source["resources"]],
        "graph": graph,
        "index": index,
        "answer": answer["answer"],
        "citations": answer["citations"],
        "action_before_confirmation": action["status"],
        "action_after_confirmation": confirmed["status"],
        "trace_events": [item["event_type"] for item in trace],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
