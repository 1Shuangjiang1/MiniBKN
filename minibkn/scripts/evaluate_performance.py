"""Measure cold, sequential, and concurrent search behavior on a built network."""

import argparse
import asyncio
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from minibkn.config import Settings
from minibkn.main import create_app


def _percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percent)))
    return round(ordered[index], 2)


def _summary(
    latencies: list[float], elapsed: float, errors: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "requests": len(latencies) + len(errors),
        "successful": len(latencies),
        "failed": len(errors),
        "p50_ms": _percentile(latencies, 0.5) if latencies else None,
        "p95_ms": _percentile(latencies, 0.95) if latencies else None,
        "mean_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "throughput_rps": round(len(latencies) / elapsed, 2) if elapsed else None,
        "wall_time_ms": round(elapsed * 1000, 2),
        "errors": errors,
    }


async def _request(
    client: httpx.AsyncClient, network_id: str, question: str, mode: str
) -> tuple[float | None, dict[str, Any] | None]:
    started = perf_counter()
    try:
        response = await client.post(
            f"/api/v1/networks/{network_id}/search",
            json={"query": question, "mode": mode, "limit": 5},
        )
        elapsed = (perf_counter() - started) * 1000
        if response.status_code != 200:
            return None, {"status": response.status_code, "body": response.text[:300]}
        return elapsed, None
    except Exception as exc:  # noqa: BLE001 - benchmark records request failures
        return None, {"type": type(exc).__name__, "message": str(exc)}


async def _run_group(
    client: httpx.AsyncClient,
    network_id: str,
    questions: list[str],
    mode: str,
    concurrent: bool,
) -> dict[str, Any]:
    started = perf_counter()
    if concurrent:
        rows = await asyncio.gather(
            *(_request(client, network_id, question, mode) for question in questions)
        )
    else:
        rows = []
        for question in questions:
            rows.append(await _request(client, network_id, question, mode))
    elapsed = perf_counter() - started
    latencies = [latency for latency, _ in rows if latency is not None]
    errors = [error for _, error in rows if error is not None]
    return _summary(latencies, elapsed, errors)


async def main(args: argparse.Namespace) -> None:
    source = json.loads(args.input.read_text(encoding="utf-8"))
    questions = [case["question"] for case in source["cases"]]
    if len(questions) < 1 + args.sequential_requests + args.concurrent_requests:
        raise ValueError("retrieval result does not contain enough distinct questions")
    embedding_key = args.embedding_key_file.read_text(encoding="utf-8-sig").strip()
    embedding_version = source["environment"]["embedding_version"]
    _, model, dimensions_text = embedding_version.split(":", 2)
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{args.database.as_posix()}",
            data_dir=args.database.parent,
            embedding_provider="siliconflow",
            embedding_api_key=embedding_key,
            embedding_model=model,
            embedding_dimensions=int(dimensions_text),
            embedding_failover_enabled=False,
            embedding_cache_entries=20000,
        )
    )
    result: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "database": str(args.database),
        "network_id": args.network_id,
        "embedding_version": embedding_version,
        "methodology": {
            "client": "in-process ASGI HTTP",
            "distinct_questions": True,
            "concurrency": args.concurrent_requests,
            "note": "Measures one application process and includes remote query embedding.",
        },
        "modes": {},
    }
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://performance", timeout=180
        ) as client:
            offset = 0
            for mode in ("bm25", "hybrid"):
                cold_latency, cold_error = await _request(
                    client, args.network_id, questions[offset], mode
                )
                offset += 1
                sequential = questions[offset : offset + args.sequential_requests]
                offset += args.sequential_requests
                concurrent = questions[offset : offset + args.concurrent_requests]
                offset += args.concurrent_requests
                result["modes"][mode] = {
                    "cold_first_request_ms": round(cold_latency, 2) if cold_latency else None,
                    "cold_error": cold_error,
                    "warm_sequential": await _run_group(
                        client, args.network_id, sequential, mode, False
                    ),
                    "warm_concurrent": await _run_group(
                        client, args.network_id, concurrent, mode, True
                    ),
                }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "modes": result["modes"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--embedding-key-file", type=Path, required=True)
    parser.add_argument("--network-id", default="crm_benchmark")
    parser.add_argument("--sequential-requests", type=int, default=20)
    parser.add_argument("--concurrent-requests", type=int, default=50)
    parser.add_argument("--output", type=Path, required=True)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(parser.parse_args()))
