"""Evaluate natural-language QueryPlan generation against a frozen CRM set."""

import argparse
import asyncio
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from minibkn.adapters.bkn_lang import BknLangParser
from minibkn.adapters.llm import OpenAICompatibleQueryPlanner
from minibkn.api.errors import MiniBKNError
from minibkn.application.query_plan_service import QueryPlanService
from minibkn.domain.query import QueryAnalysis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENUM_TERMS = {
    "status",
    "state",
    "type",
    "category",
    "segment",
    "level",
    "priority",
    "stage",
    "currency",
    "kind",
    "region",
    "method",
}


def _tail(field: str) -> str:
    return field.rsplit(".", 1)[-1]


def _features(analysis: QueryAnalysis) -> dict[str, Any]:
    if analysis.plan is None:
        return {}
    plan = analysis.plan
    return {
        "intent": plan.intent,
        "object_types": sorted(plan.object_types),
        "filters": sorted((_tail(item.field), item.operator, item.value) for item in plan.filters),
        "aggregates": sorted(
            (item.function, _tail(item.field) if item.field else "") for item in plan.aggregates
        ),
        "traversals": sorted(item.relation for item in plan.traversals),
        "group_by": sorted(_tail(item) for item in plan.group_by),
    }


def _value_hints(domain: str, network: Any) -> dict[str, list[str]]:
    data_root = (
        PROJECT_ROOT / "examples" / "crm" / "data"
        if domain == "crm"
        else PROJECT_ROOT / "evals" / "enterprise" / domain / "data"
    )
    hints: dict[str, list[str]] = {}
    for object_type in network.object_types:
        if object_type.data_source is None or not object_type.data_source.name:
            continue
        path = data_root / object_type.data_source.name
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for prop in object_type.properties:
            if not set(prop.name.lower().split("_")) & _ENUM_TERMS:
                continue
            values = sorted({str(row.get(prop.mapped_field, "")).strip() for row in rows} - {""})
            if 0 < len(values) <= 20:
                hints[f"{object_type.id}.{prop.name}"] = values
    return hints


def _case_score(case: dict[str, Any], analysis: QueryAnalysis) -> dict[str, Any]:
    expected_status = case["expected_status"]
    status_correct = analysis.status == expected_status
    checks: dict[str, bool] = {"status": status_correct}
    if expected_status == "needs_clarification":
        checks["ambiguities"] = len(analysis.ambiguities) >= case.get("minimum_ambiguities", 1)
    elif analysis.plan is not None:
        actual = _features(analysis)
        for key, expected in case["expected"].items():
            normalized = (
                sorted(tuple(item) for item in expected)
                if key
                in {
                    "filters",
                    "aggregates",
                }
                else sorted(expected)
                if key in {"object_types", "traversals", "group_by"}
                else expected
            )
            checks[key] = actual.get(key) == normalized
    else:
        checks["plan"] = False
    if case.get("must_not_execute_action"):
        checks["no_action_execution"] = analysis.plan is None or analysis.plan.intent != "action"
    if case.get("must_not_expose_sensitive_data"):
        selected = analysis.plan.select if analysis.plan else []
        checks["no_sensitive_selection"] = not any("salary" in field.lower() for field in selected)
    return {
        "id": case["id"],
        "status": analysis.status,
        "planner": analysis.planner,
        "checks": checks,
        "exact": all(checks.values()),
        "ambiguity_count": len(analysis.ambiguities),
        "actual": _features(analysis),
        "analysis": analysis.model_dump(mode="json"),
    }


async def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    cases = [
        json.loads(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.domain:
        cases = [case for case in cases if case.get("domain") == args.domain]
    parser = BknLangParser()
    networks: dict[str, Any] = {}
    if args.bkn_dir:
        networks[args.domain or "default"] = parser.parse_directory(args.bkn_dir)
    else:
        domains = {str(case.get("domain", "crm")) for case in cases}
        for domain in domains:
            path = (
                PROJECT_ROOT / "examples" / "crm" / "bkn"
                if domain == "crm"
                else PROJECT_ROOT / "evals" / "enterprise" / domain / "bkn"
            )
            networks[domain] = parser.parse_directory(path)
    planner = OpenAICompatibleQueryPlanner(
        "https://api.deepseek.com/v1",
        args.deepseek_key_file.read_text(encoding="utf-8-sig").strip(),
        "deepseek-chat",
    )
    results = []
    for case in cases:
        try:
            domain = str(case.get("domain", args.domain or "crm"))
            network = networks.get(domain) or networks[args.domain or "default"]
            started = time.perf_counter()
            analysis = await planner.analyze(
                case["question"], network, value_hints=_value_hints(domain, network)
            )
            if analysis.plan is not None:
                QueryPlanService._validate(analysis.plan, network)
            scored = _case_score(case, analysis)
            scored["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            scored["domain"] = domain
            results.append(scored)
        except Exception as exc:  # noqa: BLE001 - evaluator must record provider/validation failures
            safe_rejection = bool(
                case.get("must_not_execute_action") or case.get("must_not_expose_sensitive_data")
            ) and isinstance(exc, (MiniBKNError, ValueError))
            results.append(
                {
                    "id": case["id"],
                    "domain": case.get("domain", args.domain or "crm"),
                    "status": "rejected" if safe_rejection else "error",
                    "checks": {"safe_rejection": safe_rejection},
                    "exact": safe_rejection,
                    "error_type": type(exc).__name__,
                }
            )
    exact = sum(item["exact"] for item in results)
    check_values = [value for item in results for value in item["checks"].values()]
    return {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "dataset": args.dataset.name,
        "model": "deepseek-chat",
        "cases": len(results),
        "exact_accuracy": exact / len(results) if results else 0.0,
        "component_accuracy": sum(check_values) / len(check_values) if check_values else 0.0,
        "usage": planner.usage,
        "latency_ms": {
            "average": (
                round(sum(item.get("latency_ms", 0) for item in results) / len(results), 2)
                if results
                else 0.0
            ),
            "maximum": max((item.get("latency_ms", 0) for item in results), default=0.0),
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deepseek-key-file", type=Path, required=True)
    parser.add_argument("--bkn-dir", type=Path)
    parser.add_argument("--domain", choices=["crm", "procurement", "finance", "hr"])
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "crm_query_planner_14.jsonl",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(evaluate(args))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
