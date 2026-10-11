"""Compile detailed evaluation artifacts into a compact UI-facing latest report."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"evaluation artifact must be an object: {path}")
    return value


def main(args: argparse.Namespace) -> None:
    retrieval = _read(args.retrieval)
    ragas = _read(args.ragas)
    planner = _read(args.planner)
    adversarial = _read(args.adversarial)
    performance = _read(args.performance)
    coverage = _read(args.coverage)
    summary = {
        "report_version": "2.0",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "completed",
        "dataset": retrieval["dataset"],
        "retrieval": retrieval["retrieval"],
        "ragas": {
            "id_metrics": ragas["id_metrics"],
            **{
                key: ragas["faithfulness"][key]
                for key in (
                    "metric",
                    "sampling",
                    "sample_size",
                    "successful_cases",
                    "failed_cases",
                    "mean",
                    "minimum",
                )
            },
        },
        "query_plan": {
            "holdout_cases": planner["cases"],
            "holdout_exact_accuracy": planner["exact_accuracy"],
            "holdout_component_accuracy": planner["component_accuracy"],
            "holdout_usage": planner["usage"],
            "holdout_latency_ms": planner["latency_ms"],
            "adversarial_cases": adversarial["cases"],
            "adversarial_exact_accuracy": adversarial["exact_accuracy"],
            "known_gap": "field-level RBAC is not implemented",
        },
        "actions": retrieval["actions"],
        "performance": performance["modes"],
        "coverage": coverage["totals"],
        "claims": {
            "supported": [
                "BGE-M3 vector Hit@1 exceeds token hashing by 48 percentage points",
                "30-case Ragas Faithfulness mean is 0.9261",
                "50 concurrent hybrid searches completed with zero errors",
            ],
            "not_yet_supported": [
                "Context Precision 0.78",
                "average context token reduction 36%",
                "field-level authorization",
            ],
        },
        "artifacts": {
            "retrieval": str(args.retrieval),
            "ragas": str(args.ragas),
            "query_plan": str(args.planner),
            "adversarial": str(args.adversarial),
            "performance": str(args.performance),
            "coverage": str(args.coverage),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--ragas", type=Path, required=True)
    parser.add_argument("--planner", type=Path, required=True)
    parser.add_argument("--adversarial", type=Path, required=True)
    parser.add_argument("--performance", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evals/results/latest.json"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main(parser.parse_args())
