"""Add Ragas IDBasedContextPrecision to the latest CRM benchmark report."""

import asyncio
import json
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ragas import SingleTurnSample

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from ragas.metrics import IDBasedContextPrecision

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"


async def main() -> None:
    latest_path = RESULTS / "latest.json"
    if not latest_path.is_file():
        raise RuntimeError("Run scripts/evaluate_crm.py before the Ragas evaluation")
    source: dict[str, Any] = json.loads(latest_path.read_text(encoding="utf-8"))
    scorer = IDBasedContextPrecision()
    metrics: dict[str, Any] = {}
    for mode in ("bm25", "vector", "hybrid"):
        scores = []
        for case in source["cases"]:
            sample = SingleTurnSample(
                retrieved_context_ids=case["rankings"][mode],
                reference_context_ids=case["expected_document_ids"],
            )
            scores.append(float(await scorer.single_turn_ascore(sample)))
        metrics[mode] = round(sum(scores) / len(scores), 4)
    source["ragas"] = {
        "status": "partial_complete",
        "metric": "Ragas IDBasedContextPrecision over retrieved top-5 document ids",
        "id_based_context_precision_at_5": metrics,
        "faithfulness": None,
        "faithfulness_note": "not run: evaluator LLM API key is not configured",
    }
    latest_path.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    output = RESULTS / f"crm-ragas-{timestamp}.json"
    output.write_text(
        json.dumps(
            {
                "source_run_id": source["run_id"],
                "created_at": datetime.now(UTC).isoformat(),
                "ragas": source["ragas"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"result": str(output), "ragas": source["ragas"]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
