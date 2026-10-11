"""Run the frozen CRM retrieval, QueryPlan, and action benchmark end to end."""

import argparse
import asyncio
import json
import logging
import platform
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from minibkn.adapters.search.hybrid import tokenize
from minibkn.config import Settings
from minibkn.main import create_app

ROOT = Path(__file__).resolve().parents[1]
CRM = ROOT / "evals" / "crm"
DATASET = ROOT / "evals" / "datasets" / "crm_200.jsonl"
ACTIONS = ROOT / "evals" / "datasets" / "crm_actions_30.jsonl"
RESULTS = ROOT / "evals" / "results"


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


async def _prepare(client: httpx.AsyncClient) -> dict[str, Any]:
    for path, payload in (
        ("/api/v1/networks/import", {"path": str(CRM / "bkn")}),
        (
            "/api/v1/sources",
            {
                "id": "crm_benchmark_files",
                "name": "Frozen CRM benchmark",
                "kind": "csv",
                "path": str(CRM / "data"),
            },
        ),
    ):
        response = await client.post(path, json=payload)
        response.raise_for_status()
    response = await client.post("/api/v1/sources/crm_benchmark_files/discover")
    response.raise_for_status()
    build = await client.post("/api/v1/networks/crm_benchmark/builds")
    build.raise_for_status()
    return build.json()


def _retrieval_metrics(
    cases: list[dict[str, Any]],
    rankings: list[list[str]],
    latencies: list[float],
    tokens: list[int],
) -> dict[str, Any]:
    hits_1 = hits_5 = 0
    reciprocal = precision = recall = 0.0
    for case, ranking in zip(cases, rankings, strict=True):
        expected = set(case["expected_document_ids"])
        relevant_ranks = [index + 1 for index, item in enumerate(ranking) if item in expected]
        hits_1 += int(bool(ranking) and ranking[0] in expected)
        hits_5 += int(bool(relevant_ranks))
        reciprocal += 1 / min(relevant_ranks) if relevant_ranks else 0
        precision += len(expected.intersection(ranking)) / max(len(ranking), 1)
        recall += len(expected.intersection(ranking)) / len(expected)
    total = len(cases)
    return {
        "cases": total,
        "hit_rate_at_1": round(hits_1 / total, 4),
        "hit_rate_at_5": round(hits_5 / total, 4),
        "mean_reciprocal_rank": round(reciprocal / total, 4),
        "labeled_context_precision_at_5": round(precision / total, 4),
        "labeled_context_recall_at_5": round(recall / total, 4),
        "latency_ms_p50": round(statistics.median(latencies), 2),
        "latency_ms_p95": round(sorted(latencies)[int(total * 0.95) - 1], 2),
        "average_context_tokens_at_5": round(sum(tokens) / total, 2),
    }


def _rows_match(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> bool:
    if len(expected) != len(actual):
        return False
    for expected_row, actual_row in zip(expected, actual, strict=True):
        for key, value in expected_row.items():
            actual_value = actual_row.get(key)
            if isinstance(value, float):
                if actual_value is None or abs(float(actual_value) - value) > 0.01:
                    return False
            elif actual_value != value:
                return False
    return True


async def _evaluate_query_plans(
    client: httpx.AsyncClient, cases: list[dict[str, Any]]
) -> dict[str, Any]:
    eligible = [case for case in cases if "query_plan" in case]
    correct = 0
    latencies = []
    for case in eligible:
        started = perf_counter()
        response = await client.post(
            "/api/v1/networks/crm_benchmark/query-plans/execute",
            json={"plan": case["query_plan"]},
        )
        latencies.append((perf_counter() - started) * 1000)
        response.raise_for_status()
        rows = response.json()["rows"]
        if "expected_rows" in case:
            correct += int(_rows_match(case["expected_rows"], rows))
        else:
            actual_ids = {row["_instance_id"] for row in rows}
            correct += int(set(case["expected_instance_ids"]).issubset(actual_ids))
    return {
        "cases": len(eligible),
        "exact_execution_accuracy": round(correct / len(eligible), 4),
        "latency_ms_p50": round(statistics.median(latencies), 2),
        "latency_ms_p95": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 2),
        "planner": "frozen validated QueryPlan; does not claim LLM intent accuracy",
    }


async def _evaluate_actions(client: httpx.AsyncClient) -> dict[str, Any]:
    cases = _load(ACTIONS)
    correct = 0
    decisions: dict[str, int] = {"allow": 0, "confirm": 0, "deny": 0}
    for case in cases:
        response = await client.post(
            "/api/v1/networks/crm_benchmark/actions/approve_order/risks/simulate",
            json={
                "object_type_id": case["object_type_id"],
                "instance_id": case["instance_id"],
                "parameters": {},
            },
        )
        response.raise_for_status()
        decision = response.json()["decision"]
        decisions[decision] += 1
        correct += int(decision == case["expected_decision"])
    return {
        "cases": len(cases),
        "decision_accuracy": round(correct / len(cases), 4),
        "decision_distribution": decisions,
        "side_effects": 0,
    }


async def main(args: argparse.Namespace) -> None:
    cases = _load(DATASET)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    database = ROOT / "data" / f"crm-evaluation-{timestamp}.db"
    embedding_key = (
        args.embedding_key_file.read_text(encoding="utf-8-sig").strip()
        if args.embedding_key_file
        else ""
    )
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database.as_posix()}",
        data_dir=ROOT / "data",
        embedding_provider=args.embedding_provider,
        embedding_api_key=embedding_key,
        embedding_model=args.embedding_model,
        embedding_dimensions=args.embedding_dimensions,
        embedding_batch_size=args.embedding_batch_size,
        embedding_failover_enabled=False,
        embedding_cache_entries=20000,
    )
    app = create_app(settings)
    rankings_by_mode: dict[str, list[list[str]]] = {}
    metrics: dict[str, Any] = {}
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://evaluation",
            timeout=180,
        ) as client:
            build = await _prepare(client)
            for mode in ("bm25", "vector", "hybrid"):
                rankings: list[list[str]] = []
                latencies: list[float] = []
                context_tokens: list[int] = []
                for case in cases:
                    started = perf_counter()
                    response = await client.post(
                        "/api/v1/networks/crm_benchmark/search",
                        json={"query": case["question"], "limit": 5, "mode": mode},
                    )
                    latencies.append((perf_counter() - started) * 1000)
                    response.raise_for_status()
                    hits = response.json()
                    rankings.append([item["document"]["id"] for item in hits])
                    context_tokens.append(
                        sum(len(tokenize(item["document"]["content"])) for item in hits)
                    )
                rankings_by_mode[mode] = rankings
                metrics[mode] = _retrieval_metrics(cases, rankings, latencies, context_tokens)
            query_plan = await _evaluate_query_plans(client, cases)
            actions = await _evaluate_actions(client)
    result = {
        "report_version": "1.0",
        "run_id": timestamp,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "name": "crm_200",
            "seed": 20260816,
            "kind": "deterministic realistic synthetic CRM",
            "questions": 200,
            "categories": {"single_entity": 70, "multi_hop": 70, "filter_aggregate": 60},
            "records": {
                "customers": 500,
                "orders": 2500,
                "order_items": 6000,
                "products": 120,
                "sales_reps": 20,
            },
        },
        "build": {
            "status": build["status"],
            "inserted_objects": len(build["change_set"]["inserted"]),
            "inserted_relations": build["relation_inserted"],
            "embedded_documents": build["embedded_documents"],
        },
        "retrieval": metrics,
        "query_plan": query_plan,
        "actions": actions,
        "ragas": {
            "status": "pending",
            "id_based_context_precision": None,
            "faithfulness": None,
            "faithfulness_note": "not run: evaluator LLM API key is not configured",
        },
        "token_accounting": {
            "method": "MiniBKN tokenizer count over retrieved top-5 context",
            "llm_input_tokens": 0,
            "llm_output_tokens": 0,
            "note": "extractive benchmark invokes no answer LLM",
        },
        "baselines": {
            "B0": "BM25 lexical retrieval",
            "B1": (
                "token-hashing vector orchestration baseline (not a semantic model)"
                if args.embedding_provider == "token_hashing"
                else f"semantic vector retrieval with {args.embedding_model}"
            ),
            "B2": f"BM25 + {args.embedding_provider} vector + RRF",
            "B3": "reranker not implemented; no result claimed",
            "B4": "validated QueryPlan executor on 130 traversal/aggregate cases",
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "embedding_version": (
                f"token_hashing:v1:{args.embedding_dimensions}"
                if args.embedding_provider == "token_hashing"
                else f"siliconflow:{args.embedding_model}:{args.embedding_dimensions}"
            ),
        },
        "cases": [
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "expected_document_ids": case["expected_document_ids"],
                "rankings": {mode: rankings_by_mode[mode][index] for mode in rankings_by_mode},
            }
            for index, case in enumerate(cases)
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"crm-{args.embedding_provider}-{timestamp}.json"
    text = json.dumps(result, ensure_ascii=False, indent=2)
    output.write_text(text, encoding="utf-8")
    (args.output_dir / f"latest-{args.embedding_provider}.json").write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "result": str(output),
                **{key: result[key] for key in ("retrieval", "query_plan", "actions", "ragas")},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--embedding-provider", choices=["token_hashing", "siliconflow"], default="token_hashing"
    )
    parser.add_argument("--embedding-key-file", type=Path)
    parser.add_argument("--embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--embedding-dimensions", type=int, default=1024)
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    parser.add_argument("--output-dir", type=Path, default=RESULTS / "comprehensive" / "retrieval")
    asyncio.run(main(parser.parse_args()))
