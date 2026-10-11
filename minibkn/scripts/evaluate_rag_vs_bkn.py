"""Compare traditional retrieval-only RAG with QueryPlan-guided MiniBKN.

The two systems use the same questions, DeepSeek answer model, prompt template, and Ragas
judges. API keys are read from files and are never serialized into the output.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import AsyncOpenAI

from minibkn.config import Settings
from minibkn.domain.models import SearchMode
from minibkn.domain.query import QueryExecutionResult, QueryPlan
from minibkn.main import create_app

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT = (
    "你是企业数据问答助手。只能依据给定证据回答；证据不足时明确说明。"
    "优先直接回答问题，不要补充证据中不存在的事实。"
)


def _stratified_cases(cases: list[dict[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    eligible = [case for case in cases if case.get("query_plan")]
    categories: dict[str, list[dict[str, Any]]] = {}
    for case in eligible:
        categories.setdefault(case["category"], []).append(case)
    if not categories:
        raise ValueError("evaluation dataset contains no cases with a frozen query_plan")
    selected: list[dict[str, Any]] = []
    base, remainder = divmod(sample_size, len(categories))
    for index, category in enumerate(sorted(categories)):
        items = categories[category]
        count = min(len(items), base + int(index < remainder))
        if not count:
            continue
        step = len(items) / count
        selected.extend(items[min(int(offset * step), len(items) - 1)] for offset in range(count))
    return selected[:sample_size]


def _reference(case: dict[str, Any], execution: QueryExecutionResult | None = None) -> str:
    if case.get("expected_rows") is not None:
        statements = []
        labels = {
            "count": "符合条件的记录数量",
            "total_amount": "符合条件的金额总和",
            "average_amount": "符合条件的平均金额",
        }
        for row in case["expected_rows"]:
            statements.extend(f"{labels.get(key, key)}为 {value}" for key, value in row.items())
        return f"对于问题“{case['question']}”，正确答案是：{'；'.join(statements)}。"
    if execution is None:
        raise ValueError("instance reference requires a QueryExecutionResult")
    expected_ids = set(case.get("expected_instance_ids", []))
    evidence = [
        item.content
        for item in execution.evidence
        if item.entity_id in expected_ids and item.content
    ]
    return (
        "正确结果应包含业务对象 "
        + "、".join(sorted(expected_ids))
        + ("；对应事实：" + "；".join(evidence) if evidence else "")
    )


def _exact_execution(case: dict[str, Any], execution: QueryExecutionResult) -> bool:
    if case.get("expected_rows") is not None:
        return execution.rows == case["expected_rows"]
    expected_ids = set(case.get("expected_instance_ids", []))
    actual_ids = {item.entity_id for item in execution.evidence if item.entity_id}
    return expected_ids <= actual_ids


def _prompt(question: str, contexts: list[str]) -> str:
    numbered = "\n".join(f"[{index}] {text}" for index, text in enumerate(contexts, 1))
    return f"问题：{question}\n\n证据：\n{numbered}\n\n请给出答案。"


async def _generate_answer(
    client: AsyncOpenAI,
    model: str,
    question: str,
    contexts: list[str],
) -> dict[str, Any]:
    started = perf_counter()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(question, contexts)},
        ],
        temperature=0,
        max_tokens=800,
    )
    usage = response.usage
    return {
        "answer": response.choices[0].message.content or "",
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "latency_ms": round((perf_counter() - started) * 1000, 2),
    }


async def _collect_cases(
    source: dict[str, Any],
    args: argparse.Namespace,
    deepseek_key: str,
    embedding_key: str,
) -> list[dict[str, Any]]:
    from openai import AsyncOpenAI

    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{args.database.as_posix()}",
            data_dir=ROOT / "data",
            embedding_provider="siliconflow",
            embedding_api_key=embedding_key,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            embedding_failover_enabled=False,
            embedding_cache_entries=20000,
        )
    )
    answer_client = AsyncOpenAI(
        api_key=deepseek_key,
        base_url=args.llm_base_url,
        max_retries=3,
        timeout=120,
    )
    semaphore = asyncio.Semaphore(args.concurrency)
    cases = _stratified_cases(source["cases"], args.sample_size)
    rows: list[dict[str, Any]] = []
    try:
        async with app.router.lifespan_context(app):
            retrieval = app.state.retrieval_service
            planner = app.state.query_plan_service

            async def collect(case: dict[str, Any]) -> dict[str, Any]:
                async with semaphore:
                    hits = await retrieval.search(
                        args.network_id,
                        case["question"],
                        args.max_contexts,
                        SearchMode.HYBRID,
                    )
                    baseline_contexts = [hit.document.content for hit in hits]
                    plan = QueryPlan.model_validate(case["query_plan"])
                    execution = await planner.execute(args.network_id, plan)
                    bkn_contexts = [item.content for item in execution.evidence if item.content][
                        : args.max_contexts
                    ]
                    baseline_answer = await _generate_answer(
                        answer_client,
                        args.answer_model,
                        case["question"],
                        baseline_contexts,
                    )
                    bkn_answer = await _generate_answer(
                        answer_client, args.answer_model, case["question"], bkn_contexts
                    )
                    expected_documents = set(case.get("expected_document_ids", []))
                    baseline_documents = {hit.document.id for hit in hits}
                    return {
                        "id": case["id"],
                        "category": case["category"],
                        "question": case["question"],
                        "reference": _reference(case, execution),
                        "expected_document_ids": sorted(expected_documents),
                        "structured_execution_exact": _exact_execution(case, execution),
                        "systems": {
                            "traditional_rag": {
                                "contexts": baseline_contexts,
                                "retrieval_reference_coverage": round(
                                    len(expected_documents & baseline_documents)
                                    / max(1, len(expected_documents)),
                                    4,
                                ),
                                **baseline_answer,
                            },
                            "minibkn_queryplan": {
                                "contexts": bkn_contexts,
                                "retrieval_reference_coverage": 1.0
                                if _exact_execution(case, execution)
                                else 0.0,
                                **bkn_answer,
                            },
                        },
                    }

            rows = await asyncio.gather(*(collect(case) for case in cases))
    finally:
        await answer_client.close()
    return rows


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


async def _score_ragas(
    rows: list[dict[str, Any]],
    args: argparse.Namespace,
    deepseek_key: str,
    embedding_key: str,
) -> dict[str, Any]:
    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithReference,
        ContextRecall,
        FactualCorrectness,
        Faithfulness,
        NoiseSensitivity,
    )

    judge_client = AsyncOpenAI(
        api_key=deepseek_key,
        base_url=args.llm_base_url,
        max_retries=3,
        timeout=180,
    )
    embedding_client = AsyncOpenAI(
        api_key=embedding_key,
        base_url=args.embedding_base_url,
        max_retries=3,
        timeout=120,
    )
    llm = llm_factory(
        args.judge_model,
        client=judge_client,
        temperature=0,
        max_tokens=4096,
    )
    embeddings = embedding_factory(
        "openai",
        model=args.embedding_model,
        client=embedding_client,
    )
    metric_factories: dict[
        str,
        tuple[
            Callable[[], Any],
            Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        ],
    ] = {
        "faithfulness": (
            lambda: Faithfulness(llm=llm),
            lambda row, system: {
                "user_input": row["question"],
                "response": system["answer"],
                "retrieved_contexts": system["contexts"],
            },
        ),
        "factual_correctness": (
            lambda: FactualCorrectness(llm=llm, mode="f1"),
            lambda row, system: {
                "response": system["answer"],
                "reference": row["reference"],
            },
        ),
        "answer_relevancy": (
            lambda: AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=3),
            lambda row, system: {
                "user_input": row["question"],
                "response": system["answer"],
            },
        ),
        "context_precision": (
            lambda: ContextPrecisionWithReference(llm=llm),
            lambda row, system: {
                "user_input": row["question"],
                "reference": row["reference"],
                "retrieved_contexts": system["contexts"],
            },
        ),
        "context_recall": (
            lambda: ContextRecall(llm=llm),
            lambda row, system: {
                "user_input": row["question"],
                "reference": row["reference"],
                "retrieved_contexts": system["contexts"],
            },
        ),
        "noise_sensitivity": (
            lambda: NoiseSensitivity(llm=llm, mode="irrelevant"),
            lambda row, system: {
                "user_input": row["question"],
                "response": system["answer"],
                "reference": row["reference"],
                "retrieved_contexts": system["contexts"],
            },
        ),
    }
    semaphore = asyncio.Semaphore(args.judge_concurrency)

    async def score_one(
        row: dict[str, Any], system_name: str, metric_name: str
    ) -> tuple[str, str, str, float | None, str]:
        system = row["systems"][system_name]
        factory, arguments = metric_factories[metric_name]
        async with semaphore:
            try:
                result = await factory().ascore(**arguments(row, system))
                return (
                    row["id"],
                    system_name,
                    metric_name,
                    round(float(result.value), 4),
                    "",
                )
            except Exception as exc:  # noqa: BLE001 - failures are part of the evaluation output
                return row["id"], system_name, metric_name, None, type(exc).__name__

    selected_metrics = list(metric_factories) if args.metrics == "all" else args.metrics.split(",")
    jobs: list[Awaitable[tuple[str, str, str, float | None, str]]] = []
    for row in rows:
        for system_name in row["systems"]:
            for metric_name in selected_metrics:
                if metric_name not in metric_factories:
                    raise ValueError(f"unknown metric: {metric_name}")
                jobs.append(score_one(row, system_name, metric_name))
    try:
        scored = await asyncio.gather(*jobs)
    finally:
        await judge_client.close()
        await embedding_client.close()
    row_map = {row["id"]: row for row in rows}
    for case_id, system_name, metric_name, value, error in scored:
        metric_result: dict[str, Any] = {"value": value}
        if error:
            metric_result["error_type"] = error
        row_map[case_id]["systems"][system_name].setdefault("ragas", {})[metric_name] = (
            metric_result
        )
    summary: dict[str, Any] = {}
    for system_name in ("traditional_rag", "minibkn_queryplan"):
        metrics: dict[str, Any] = {}
        for metric_name in selected_metrics:
            values = [
                row["systems"][system_name]["ragas"][metric_name]["value"]
                for row in rows
                if row["systems"][system_name]["ragas"][metric_name]["value"] is not None
            ]
            metrics[metric_name] = {
                "mean": _mean(values),
                "successful_cases": len(values),
                "failed_cases": len(rows) - len(values),
            }
        summary[system_name] = metrics
    return summary


def _system_summary(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    systems = [row["systems"][name] for row in rows]
    return {
        "average_prompt_tokens": _mean([float(item["prompt_tokens"]) for item in systems]),
        "average_completion_tokens": _mean([float(item["completion_tokens"]) for item in systems]),
        "average_total_tokens": _mean([float(item["total_tokens"]) for item in systems]),
        "total_prompt_tokens": sum(item["prompt_tokens"] for item in systems),
        "total_completion_tokens": sum(item["completion_tokens"] for item in systems),
        "total_tokens": sum(item["total_tokens"] for item in systems),
        "average_retrieval_reference_coverage": _mean(
            [float(item["retrieval_reference_coverage"]) for item in systems]
        ),
    }


async def main(args: argparse.Namespace) -> None:
    source: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    dataset = [
        json.loads(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases_by_id = {case["id"]: case for case in dataset}
    source["cases"] = [{**case, **cases_by_id.get(case["id"], {})} for case in source["cases"]]
    deepseek_key = args.deepseek_key_file.read_text(encoding="utf-8-sig").strip()
    embedding_key = args.embedding_key_file.read_text(encoding="utf-8-sig").strip()
    if args.reuse_cases:
        reused = json.loads(args.reuse_cases.read_text(encoding="utf-8"))
        rows = reused["cases"]
        for row in rows:
            case = cases_by_id[row["id"]]
            if case.get("expected_rows") is not None:
                row["reference"] = _reference(case)
    else:
        rows = await _collect_cases(source, args, deepseek_key, embedding_key)
    ragas_summary = (
        {}
        if args.metrics == "none"
        else await _score_ragas(rows, args, deepseek_key, embedding_key)
    )
    baseline = _system_summary(rows, "traditional_rag")
    minibkn = _system_summary(rows, "minibkn_queryplan")
    prompt_reduction = (
        1 - minibkn["average_prompt_tokens"] / baseline["average_prompt_tokens"]
        if baseline["average_prompt_tokens"]
        else 0.0
    )
    total_reduction = (
        1 - minibkn["average_total_tokens"] / baseline["average_total_tokens"]
        if baseline["average_total_tokens"]
        else 0.0
    )
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "comparison": {
            "baseline": "traditional hybrid RAG: top-20 retrieval without QueryPlan",
            "candidate": "MiniBKN: frozen validated QueryPlan plus deterministic execution",
            "answer_model": args.answer_model,
            "judge_model": args.judge_model,
            "embedding_model": args.embedding_model,
            "same_prompt_and_answer_model": True,
        },
        "sample": {
            "size": len(rows),
            "categories": {
                category: sum(row["category"] == category for row in rows)
                for category in sorted({row["category"] for row in rows})
            },
            "structured_execution_exact": sum(
                bool(row["structured_execution_exact"]) for row in rows
            )
            / max(1, len(rows)),
        },
        "token_usage": {
            "traditional_rag": baseline,
            "minibkn_queryplan": minibkn,
            "prompt_token_reduction": round(prompt_reduction, 4),
            "total_token_reduction": round(total_reduction, 4),
            "measurement": "provider-reported DeepSeek API usage",
        },
        "ragas": ragas_summary,
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sample": result["sample"],
                "token_usage": result["token_usage"],
                "ragas": result["ragas"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "evals" / "datasets" / "crm_200.jsonl"
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--deepseek-key-file", type=Path, required=True)
    parser.add_argument("--embedding-key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-cases", type=Path)
    parser.add_argument("--network-id", default="crm_benchmark")
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--max-contexts", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--judge-concurrency", type=int, default=3)
    parser.add_argument("--answer-model", default="deepseek-chat")
    parser.add_argument("--judge-model", default="deepseek-chat")
    parser.add_argument("--llm-base-url", default="https://api.deepseek.com/v1")
    parser.add_argument("--embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--embedding-dimensions", type=int, default=1024)
    parser.add_argument("--embedding-base-url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--metrics", default="all")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(parser.parse_args()))
