"""Run an opt-in end-to-end CRM demo with real LLM and embedding providers."""

import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from minibkn.config import Settings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def verify(args: argparse.Namespace) -> dict[str, object]:
    example = PROJECT_ROOT / "examples" / "crm"
    with TemporaryDirectory(prefix="minibkn-ai-demo-") as temporary:
        temp = Path(temporary)
        app = create_app(
            Settings(
                _env_file=None,
                database_url=f"sqlite+aiosqlite:///{(temp / 'demo.db').as_posix()}",
                data_dir=temp / "data",
                llm_provider="openai_compatible",
                llm_api_key_file=args.deepseek_key_file,
                llm_base_url="https://api.deepseek.com/v1",
                llm_model="deepseek-chat",
                embedding_provider="siliconflow",
                embedding_api_key_file=args.siliconflow_key_file,
                embedding_model="BAAI/bge-m3",
                embedding_dimensions=1024,
            )
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://demo"
            ) as client:
                imported = await client.post(
                    "/api/v1/networks/import", json={"path": str(example / "bkn")}
                )
                imported.raise_for_status()
                source = await client.post(
                    "/api/v1/sources",
                    json={
                        "id": "crm_demo_files",
                        "name": "CRM demo",
                        "kind": "csv",
                        "path": str(example / "data"),
                    },
                )
                source.raise_for_status()
                discovered = await client.post("/api/v1/sources/crm_demo_files/discover")
                discovered.raise_for_status()
                materialized = await client.post("/api/v1/networks/crm/materialize")
                materialized.raise_for_status()
                indexed = await client.post("/api/v1/networks/crm/index")
                indexed.raise_for_status()
                analysis = await client.post(
                    "/api/v1/networks/crm/query-plans/analyze",
                    json={"question": "统计已付款订单的总金额"},
                )
                analysis.raise_for_status()
                plan = analysis.json()["plan"]
                executed = await client.post(
                    "/api/v1/networks/crm/query-plans/execute", json={"plan": plan}
                )
                executed.raise_for_status()
                ambiguous = await client.post(
                    "/api/v1/networks/crm/query-plans/analyze",
                    json={"question": "最近的大客户怎么样"},
                )
                ambiguous.raise_for_status()
                ambiguity_payload = ambiguous.json()
                clarification_answers = {
                    item["id"]: (item["options"][0] if item["options"] else "采用常用业务口径")
                    for item in ambiguity_payload["ambiguities"]
                }
                clarified = await client.post(
                    "/api/v1/networks/crm/query-plans/analyze",
                    json={
                        "question": "最近的大客户怎么样",
                        "clarification_answers": clarification_answers,
                    },
                )
                clarified.raise_for_status()
                searched = await client.post(
                    "/api/v1/networks/crm/search",
                    json={"query": "上海企业客户", "mode": "hybrid", "limit": 3},
                )
                searched.raise_for_status()
                return {
                    "materialized": materialized.json(),
                    "index": indexed.json(),
                    "query": {
                        "status": analysis.json()["status"],
                        "planner": analysis.json()["planner"],
                        "intent": plan["intent"],
                        "rows": executed.json()["rows"],
                    },
                    "clarification": {
                        "status": ambiguity_payload["status"],
                        "ids": [item["id"] for item in ambiguity_payload["ambiguities"]],
                        "resolved_status": clarified.json()["status"],
                        "resolved_plan_available": clarified.json()["plan"] is not None,
                    },
                    "search": {
                        "top_entity_id": searched.json()[0]["document"]["entity_id"],
                        "returned": len(searched.json()),
                    },
                }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deepseek-key-file", type=Path, required=True)
    parser.add_argument("--siliconflow-key-file", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(verify(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
