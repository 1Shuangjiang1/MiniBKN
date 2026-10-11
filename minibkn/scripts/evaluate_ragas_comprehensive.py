"""Run full ID metrics and stratified LLM Faithfulness over a CRM result."""

import argparse
import asyncio
import json
import statistics
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
from openai import AsyncOpenAI
from ragas import SingleTurnSample
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall

from minibkn.config import Settings
from minibkn.main import create_app

ROOT = Path(__file__).resolve().parents[1]


async def _id_metrics(source: dict[str, Any]) -> dict[str, dict[str, float]]:
    precision = IDBasedContextPrecision()
    recall = IDBasedContextRecall()
    result: dict[str, dict[str, float]] = {}
    for mode in ("bm25", "vector", "hybrid"):
        precision_scores = []
        recall_scores = []
        for case in source["cases"]:
            sample = SingleTurnSample(
                retrieved_context_ids=case["rankings"][mode],
                reference_context_ids=case["expected_document_ids"],
            )
            precision_scores.append(float(await precision.single_turn_ascore(sample)))
            recall_scores.append(float(await recall.single_turn_ascore(sample)))
        result[mode] = {
            "context_precision_at_5": round(statistics.mean(precision_scores), 4),
            "context_recall_at_5": round(statistics.mean(recall_scores), 4),
        }
    return result


def _stratified_cases(cases: list[dict[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    categories: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        categories.setdefault(case["category"], []).append(case)
    selected: list[dict[str, Any]] = []
    base = sample_size // len(categories)
    remainder = sample_size % len(categories)
    for index, category in enumerate(sorted(categories)):
        items = categories[category]
        count = base + int(index < remainder)
        if count <= 0:
            continue
        step = max(1, len(items) // count)
        selected.extend(items[offset] for offset in range(0, len(items), step)[:count])
    return selected[:sample_size]


async def _collect_answers(
    source: dict[str, Any], args: argparse.Namespace, cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    embedding_version = source["environment"]["embedding_version"]
    provider = "siliconflow" if embedding_version.startswith("siliconflow:") else "token_hashing"
    model = "BAAI/bge-m3"
    dimensions = 128
    if provider == "siliconflow":
        _, model, dimensions_text = embedding_version.split(":", 2)
        dimensions = int(dimensions_text)
    embedding_key = (
        args.embedding_key_file.read_text(encoding="utf-8-sig").strip()
        if args.embedding_key_file
        else ""
    )
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{args.database.as_posix()}",
            data_dir=ROOT / "data",
            embedding_provider=provider,
            embedding_api_key=embedding_key,
            embedding_model=model,
            embedding_dimensions=dimensions,
            embedding_failover_enabled=False,
            embedding_cache_entries=20000,
        )
    )
    answers = []
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://ragas",
            timeout=180,
        ) as client:
            for case in cases:
                started = perf_counter()
                response = await client.post(
                    "/api/v1/networks/crm_benchmark/ask",
                    json={"question": case["question"]},
                )
                response.raise_for_status()
                payload = response.json()
                all_contexts = [item["content"] for item in payload["evidence"] if item["content"]]
                answers.append(
                    {
                        "id": case["id"],
                        "category": case["category"],
                        "question": case["question"],
                        "answer": payload["answer"],
                        # Ragas judges the evidence that is actually placed in an LLM
                        # context window.  Aggregations can expose thousands of rows,
                        # so keep a deterministic, bounded window and record truncation.
                        "contexts": all_contexts[: args.max_contexts],
                        "evidence_count": len(all_contexts),
                        "evidence_truncated": len(all_contexts) > args.max_contexts,
                        "citations": payload["citations"][: args.max_contexts],
                        "ask_latency_ms": round((perf_counter() - started) * 1000, 2),
                    }
                )
    return answers


async def _faithfulness(
    answers: list[dict[str, Any]], deepseek_key: str, concurrency: int
) -> tuple[list[dict[str, Any]], int]:
    client = AsyncOpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com/v1")
    llm = llm_factory(
        "deepseek-chat",
        client=client,
        temperature=0,
        max_tokens=4096,
    )
    semaphore = asyncio.Semaphore(concurrency)

    async def score(item: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            started = perf_counter()
            try:
                metric = Faithfulness(llm=llm)
                result = await metric.ascore(
                    user_input=item["question"],
                    response=item["answer"],
                    retrieved_contexts=item["contexts"],
                )
                value = float(result.value)
                return {
                    **item,
                    "faithfulness": round(value, 4),
                    "judge_latency_ms": round((perf_counter() - started) * 1000, 2),
                }
            except Exception as exc:  # noqa: BLE001 - evaluation records judge failures
                return {
                    **item,
                    "faithfulness": None,
                    "judge_latency_ms": round((perf_counter() - started) * 1000, 2),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }

    try:
        rows = await asyncio.gather(*(score(item) for item in answers))
    finally:
        await client.close()
    return rows, sum(item["faithfulness"] is None for item in rows)


async def main(args: argparse.Namespace) -> None:
    source: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    id_metrics = await _id_metrics(source)
    sampled = _stratified_cases(source["cases"], args.faithfulness_sample_size)
    answers = await _collect_answers(source, args, sampled)
    deepseek_key = args.deepseek_key_file.read_text(encoding="utf-8-sig").strip()
    rows, failures = await _faithfulness(answers, deepseek_key, args.concurrency)
    scores = [item["faithfulness"] for item in rows if item["faithfulness"] is not None]
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_result": str(args.input),
        "source_run_id": source["run_id"],
        "embedding_version": source["environment"]["embedding_version"],
        "id_metrics": id_metrics,
        "faithfulness": {
            "metric": "Ragas Faithfulness with DeepSeek deepseek-chat judge",
            "sampling": "deterministic stratified sample by CRM question category",
            "sample_size": len(rows),
            "successful_cases": len(scores),
            "failed_cases": failures,
            "mean": round(statistics.mean(scores), 4) if scores else None,
            "minimum": round(min(scores), 4) if scores else None,
            "cases": rows,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "id_metrics": id_metrics,
                "faithfulness": {
                    key: result["faithfulness"][key]
                    for key in (
                        "sample_size",
                        "successful_cases",
                        "failed_cases",
                        "mean",
                        "minimum",
                    )
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--deepseek-key-file", type=Path, required=True)
    parser.add_argument("--embedding-key-file", type=Path)
    parser.add_argument("--faithfulness-sample-size", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--max-contexts", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(parser.parse_args()))
