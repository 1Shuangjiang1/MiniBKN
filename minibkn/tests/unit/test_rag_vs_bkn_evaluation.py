from minibkn.domain.evidence import EvidenceItem, EvidenceKind
from minibkn.domain.query import QueryExecutionResult, QueryPlan
from scripts.evaluate_rag_vs_bkn import _exact_execution, _reference, _stratified_cases


def test_stratified_cases_selects_only_query_plan_cases() -> None:
    cases = [
        {"id": "a1", "category": "lookup", "query_plan": {"intent": "lookup"}},
        {"id": "a2", "category": "lookup"},
        {"id": "b1", "category": "aggregate", "query_plan": {"intent": "aggregate"}},
        {"id": "b2", "category": "aggregate", "query_plan": {"intent": "aggregate"}},
    ]

    selected = _stratified_cases(cases, 2)

    assert len(selected) == 2
    assert {item["category"] for item in selected} == {"lookup", "aggregate"}
    assert all(item.get("query_plan") for item in selected)


def test_reference_and_exactness_use_frozen_expected_results() -> None:
    execution = QueryExecutionResult(
        plan=QueryPlan(intent="aggregate", aggregates=[{"function": "count", "alias": "count"}]),
        rows=[{"count": 12}],
        evidence=[
            EvidenceItem(
                id="computed:0",
                network_id="crm",
                kind=EvidenceKind.COMPUTED,
                title="count",
                content="{'count': 12}",
                citation="computed://0",
            )
        ],
    )
    case = {"question": "符合条件的订单有多少", "expected_rows": [{"count": 12}]}

    assert _exact_execution(case, execution)
    assert "记录数量为 12" in _reference(case, execution)
