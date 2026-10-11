"""Replay a frozen retrieval result against current code and compare every top-k ranking."""

import argparse
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


async def main(args: argparse.Namespace) -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    source: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    _, model, dimensions_text = source["environment"]["embedding_version"].split(":", 2)
    api_key = args.embedding_key_file.read_text(encoding="utf-8-sig").strip()
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{args.database.as_posix()}",
            data_dir=args.database.parent,
            embedding_provider="siliconflow",
            embedding_api_key=api_key,
            embedding_model=model,
            embedding_dimensions=int(dimensions_text),
            embedding_failover_enabled=False,
            embedding_cache_entries=20000,
        )
    )
    matches = {mode: 0 for mode in ("bm25", "vector", "hybrid")}
    mismatches: dict[str, list[dict[str, Any]]] = {mode: [] for mode in matches}
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://replay", timeout=180
        ) as client:
            for index, case in enumerate(source["cases"], 1):
                for mode in matches:
                    response = await client.post(
                        f"/api/v1/networks/{args.network_id}/search",
                        json={"query": case["question"], "mode": mode, "limit": 5},
                    )
                    response.raise_for_status()
                    actual = [item["document"]["id"] for item in response.json()]
                    expected = case["rankings"][mode]
                    if actual == expected:
                        matches[mode] += 1
                    else:
                        mismatches[mode].append(
                            {"id": case["id"], "expected": expected, "actual": actual}
                        )
                if index % 25 == 0:
                    print(f"replayed {index}/{len(source['cases'])}", flush=True)
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_result": str(args.input),
        "cases": len(source["cases"]),
        "embedding_version": source["environment"]["embedding_version"],
        "exact_top5_matches": matches,
        "mismatch_counts": {mode: len(items) for mode, items in mismatches.items()},
        "mismatches": mismatches,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps({key: result[key] for key in ("cases", "exact_top5_matches", "mismatch_counts")})
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--embedding-key-file", type=Path, required=True)
    parser.add_argument("--network-id", default="crm_benchmark")
    parser.add_argument("--output", type=Path, required=True)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(parser.parse_args()))
