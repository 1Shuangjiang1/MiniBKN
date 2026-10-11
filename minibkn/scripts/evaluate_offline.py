"""Build the demo graph and compare vector, BM25, and RRF hybrid retrieval on 200 cases."""

import asyncio
import json
import logging
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from minibkn.config import Settings
from minibkn.evaluation import build_200_case_dataset, score_rankings
from minibkn.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT_ROOT / "examples" / "supply_chain"


async def _prepare(client: httpx.AsyncClient) -> None:
    calls = [
        ("/api/v1/networks/import", {"path": str(EXAMPLE / "bkn")}),
        (
            "/api/v1/sources",
            {
                "id": "evaluation_files",
                "name": "Evaluation CSV files",
                "kind": "csv",
                "path": str(EXAMPLE / "data"),
            },
        ),
    ]
    for path, payload in calls:
        response = await client.post(path, json=payload)
        response.raise_for_status()
    for path in (
        "/api/v1/sources/evaluation_files/discover",
        "/api/v1/networks/supply_chain/materialize",
        "/api/v1/networks/supply_chain/index",
    ):
        response = await client.post(path)
        response.raise_for_status()


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    database_path = PROJECT_ROOT / "data" / f"evaluation-{timestamp}.db"
    result_path = PROJECT_ROOT / "evals" / "results" / f"offline-{timestamp}.json"
    dataset_path = PROJECT_ROOT / "evals" / "datasets" / "supply_chain_200.jsonl"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    cases = build_200_case_dataset()
    with dataset_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(asdict(case), ensure_ascii=False) + "\n")

    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
            data_dir=PROJECT_ROOT / "data",
        )
    )
    transport = httpx.ASGITransport(app=app)
    metrics: dict[str, Any] = {}
    rankings_by_mode: dict[str, list[list[str]]] = {}
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://eval") as client:
            await _prepare(client)
            for mode in ("vector", "bm25", "hybrid"):
                rankings = []
                context_sizes = []
                for case in cases:
                    response = await client.post(
                        "/api/v1/networks/supply_chain/search",
                        json={"query": case.query, "limit": 5, "mode": mode},
                    )
                    response.raise_for_status()
                    hits = response.json()
                    rankings.append([item["document"]["id"] for item in hits])
                    context_sizes.append(sum(len(item["document"]["content"]) for item in hits))
                mode_metrics = score_rankings(cases, rankings)
                rankings_by_mode[mode] = rankings
                mode_metrics["average_context_characters_at_5"] = round(
                    sum(context_sizes) / len(context_sizes), 2
                )
                metrics[mode] = mode_metrics
    result = {
        "dataset": str(dataset_path),
        "dataset_kind": "deterministic synthetic supply-chain retrieval benchmark",
        "metrics_note": (
            "context_precision_proxy equals reciprocal rank for one labeled relevant document; "
            "it is not an LLM-judged Ragas score"
        ),
        "metrics": metrics,
        "cases": [
            {
                "id": case.id,
                "query": case.query,
                "expected_document_id": case.expected_document_id,
                "rankings": {mode: rankings_by_mode[mode][index] for mode in rankings_by_mode},
            }
            for index, case in enumerate(cases)
        ],
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "result": str(result_path),
                "dataset": str(dataset_path),
                "dataset_kind": result["dataset_kind"],
                "metrics_note": result["metrics_note"],
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
