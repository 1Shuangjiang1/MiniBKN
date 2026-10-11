"""Run a reproducible LightRAG ingestion, retrieval, routing, and hybrid smoke evaluation."""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from minibkn.adapters.document_knowledge import LightRAGDocumentKnowledge
from minibkn.api.errors import MiniBKNError
from minibkn.config import Settings
from minibkn.main import create_app

ROOT = Path(__file__).resolve().parents[1]
CRM = ROOT / "examples" / "crm"
FIXTURES = ROOT / "evals" / "fixtures" / "documents" / "crm_public"


async def _wait_for_job(
    adapter: LightRAGDocumentKnowledge, track_id: str, max_wait_seconds: float
) -> dict[str, Any]:
    deadline = time.monotonic() + max_wait_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status = await adapter.job_status("crm", "public", track_id)
        last = status.model_dump(mode="json")
        if status.status.lower() in {"completed", "complete", "processed", "success", "failed"}:
            return last
        await asyncio.sleep(2)
    return {**last, "timed_out": True}


async def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    api_key = args.api_key_file.read_text(encoding="utf-8-sig").strip()
    adapter = LightRAGDocumentKnowledge(
        args.endpoint_map, api_key, query_mode="mix", timeout=args.request_timeout
    )
    status = await adapter.status()
    ingestions = []
    started = time.perf_counter()
    for path in sorted(FIXTURES.glob("*.md")):
        try:
            result = await adapter.ingest_text(
                "crm", "public", path.name, path.read_text(encoding="utf-8")
            )
        except MiniBKNError as exc:
            if exc.error_code != "DOCUMENT_ALREADY_EXISTS":
                raise
            ingestions.append({"file": path.name, "status": "already_present"})
            continue
        job = await _wait_for_job(adapter, result.track_id, args.index_timeout)
        ingestions.append(
            {"file": path.name, "submission": result.model_dump(mode="json"), "job": job}
        )

    retrieval_cases = [
        ("销售折扣超过10%需要谁审批？", "销售经理"),
        ("VIP客户工单首次响应时限是多少？", "2 小时"),
        ("离职员工访问凭证多久停用？", "4 小时"),
    ]
    retrieval_rows = []
    for question, expected in retrieval_cases:
        evidence = await adapter.query("crm", question, 8, {"public"})
        combined = "\n".join(item.content for item in evidence)
        retrieval_rows.append(
            {
                "question": question,
                "expected": expected,
                "passed": expected.replace(" ", "") in combined.replace(" ", ""),
                "evidence_count": len(evidence),
                "citations": [item.citation for item in evidence],
            }
        )

    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{args.database.as_posix()}",
            data_dir=args.database.parent,
        ),
        document_knowledge=adapter,
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/api/v1/networks/import", json={"path": str(CRM / "bkn")})
            await client.post(
                "/api/v1/sources",
                json={"id": "crm_files", "name": "CRM", "kind": "csv", "path": str(CRM / "data")},
            )
            await client.post("/api/v1/sources/crm_files/discover")
            await client.post("/api/v1/networks/crm/builds")
            document = await client.post(
                "/api/v1/networks/crm/ask-routed",
                json={"question": "销售折扣审批制度是什么？", "route": "auto"},
            )
            structured = await client.post(
                "/api/v1/networks/crm/ask-routed",
                json={"question": "客户订单有哪些？", "route": "auto"},
            )
            hybrid = await client.post(
                "/api/v1/networks/crm/ask-routed",
                json={"question": "客户订单与折扣审批制度", "route": "hybrid"},
            )
    document_payload = document.json()
    structured_payload = structured.json()
    hybrid_payload = hybrid.json()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": status.model_dump(mode="json"),
        "fixture_count": len(ingestions),
        "ingestions": ingestions,
        "retrieval": {
            "passed": sum(item["passed"] for item in retrieval_rows),
            "total": len(retrieval_rows),
            "cases": retrieval_rows,
        },
        "routing": {
            "auto_document": document.status_code == 200
            and document_payload.get("executed_routes") == ["document"],
            "auto_structured": structured.status_code == 200
            and structured_payload.get("executed_routes") == ["structured"],
            "hybrid_both": hybrid.status_code == 200
            and hybrid_payload.get("executed_routes") == ["structured", "document"],
            "hybrid_document_evidence": sum(
                item.get("kind") == "document" for item in hybrid_payload.get("evidence", [])
            ),
            "hybrid_structured_evidence": sum(
                item.get("kind") != "document" for item in hybrid_payload.get("evidence", [])
            ),
            "hybrid_citations": hybrid_payload.get("citations", []),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoint-map", type=Path, default=ROOT / "evals/config/lightrag-local.json"
    )
    parser.add_argument("--api-key-file", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=ROOT / "data/lightrag/evaluation.sqlite")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "evals/results/lightrag/integration.json"
    )
    parser.add_argument("--index-timeout", type=float, default=600)
    parser.add_argument("--request-timeout", type=float, default=300)
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(evaluate(args))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
