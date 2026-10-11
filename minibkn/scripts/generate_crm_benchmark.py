"""Generate a deterministic, business-shaped CRM benchmark and frozen questions."""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "evals" / "crm" / "data"
DATASET_DIR = ROOT / "evals" / "datasets"
SEED = 20260816


def _write_csv(name: str, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate() -> dict[str, int]:
    random.seed(SEED)
    reps = [
        {
            "rep_id": f"REP-{index:03d}",
            "name": f"Sales Rep {index:02d}",
            "region": ["east", "west", "north", "south"][index % 4],
        }
        for index in range(1, 21)
    ]
    customers = []
    for index in range(1, 501):
        customers.append(
            {
                "customer_id": f"CUST-{index:04d}",
                "name": f"Enterprise Customer {index:04d}",
                "tier": ["standard", "growth", "vip"][index % 3],
                "region": ["east", "west", "north", "south"][index % 4],
                "rep_id": reps[index % len(reps)]["rep_id"],
                "credit_limit": f"{10000 + (index % 20) * 5000:.2f}",
            }
        )
    products = [
        {
            "product_id": f"PROD-{index:04d}",
            "name": f"Business Product {index:03d}",
            "category": ["software", "hardware", "service", "subscription"][index % 4],
            "list_price": f"{50 + (index % 30) * 25:.2f}",
        }
        for index in range(1, 121)
    ]
    orders = []
    start = date(2025, 1, 1)
    statuses = ["paid", "paid", "shipped", "pending", "cancelled"]
    for index in range(1, 2501):
        amount = 400 + ((index * 137) % 30000)
        orders.append(
            {
                "order_id": f"ORD-{index:05d}",
                "customer_id": customers[(index * 17) % len(customers)]["customer_id"],
                "amount": f"{amount:.2f}",
                "status": statuses[index % len(statuses)],
                "created_at": str(start + timedelta(days=index % 540)),
            }
        )
    order_items = []
    for index in range(1, 6001):
        order = orders[(index * 11) % len(orders)]
        product = products[(index * 7) % len(products)]
        quantity = 1 + index % 8
        unit_price = float(product["list_price"])
        order_items.append(
            {
                "item_id": f"ITEM-{index:06d}",
                "order_id": order["order_id"],
                "product_id": product["product_id"],
                "quantity": quantity,
                "unit_price": f"{unit_price:.2f}",
            }
        )
    _write_csv("sales_reps.csv", ["rep_id", "name", "region"], reps)
    _write_csv(
        "customers.csv",
        ["customer_id", "name", "tier", "region", "rep_id", "credit_limit"],
        customers,
    )
    _write_csv("products.csv", ["product_id", "name", "category", "list_price"], products)
    _write_csv("orders.csv", ["order_id", "customer_id", "amount", "status", "created_at"], orders)
    _write_csv(
        "order_items.csv",
        ["item_id", "order_id", "product_id", "quantity", "unit_price"],
        order_items,
    )
    _write_questions(customers, orders)
    _write_actions(orders)
    return {
        "customers": len(customers),
        "orders": len(orders),
        "order_items": len(order_items),
        "products": len(products),
        "sales_reps": len(reps),
        "questions": 200,
        "action_cases": 30,
    }


def _write_questions(customers: list[dict[str, Any]], orders: list[dict[str, Any]]) -> None:
    cases: list[dict[str, Any]] = []
    for index in range(40):
        customer = customers[index * 7]
        cases.append(
            {
                "id": f"crm-{len(cases) + 1:03d}",
                "category": "single_entity",
                "question": f"查询客户 {customer['customer_id']} {customer['name']} 的资料",
                "expected_document_ids": [f"instance:customer:{customer['customer_id']}"],
            }
        )
    for index in range(30):
        order = orders[index * 13]
        cases.append(
            {
                "id": f"crm-{len(cases) + 1:03d}",
                "category": "single_entity",
                "question": f"订单 {order['order_id']} 的金额和状态是什么",
                "expected_document_ids": [f"instance:order:{order['order_id']}"],
            }
        )
    for index in range(70):
        order = orders[index * 19]
        cases.append(
            {
                "id": f"crm-{len(cases) + 1:03d}",
                "category": "multi_hop",
                "question": f"订单 {order['order_id']} 是哪个客户下的，请给出双方信息",
                "expected_document_ids": [
                    f"instance:order:{order['order_id']}",
                    f"instance:customer:{order['customer_id']}",
                ],
                "query_plan": {
                    "intent": "traverse",
                    "object_types": ["order"],
                    "filters": [
                        {"field": "order.order_id", "operator": "eq", "value": order["order_id"]}
                    ],
                    "traversals": [{"relation": "placed_by", "direction": "out", "max_hops": 1}],
                    "limit": 10,
                },
                "expected_instance_ids": [order["order_id"], order["customer_id"]],
            }
        )
    for index in range(20):
        threshold = 1000 + index * 750
        expected = sum(float(item["amount"]) >= threshold for item in orders)
        cases.append(
            _aggregate_case(
                cases,
                f"金额不低于 {threshold} 的订单有多少",
                "order",
                "order.amount",
                "gte",
                threshold,
                "count",
                "count",
                expected,
            )
        )
    for index in range(20):
        threshold = 500 + index * 500
        matched = [
            item
            for item in orders
            if item["status"] == "paid" and float(item["amount"]) >= threshold
        ]
        expected = round(sum(float(item["amount"]) for item in matched), 2)
        cases.append(
            _aggregate_case(
                cases,
                f"已支付且金额不低于 {threshold} 的订单总额",
                "order",
                "order.amount",
                "gte",
                threshold,
                "sum",
                "total_amount",
                expected,
                extra_filter={"field": "order.status", "operator": "eq", "value": "paid"},
            )
        )
    tiers = ["standard", "growth", "vip"]
    for index in range(20):
        tier = tiers[index % len(tiers)]
        expected = sum(item["tier"] == tier for item in customers)
        cases.append(
            _aggregate_case(
                cases,
                f"{tier} 等级客户有多少",
                "customer",
                "customer.tier",
                "eq",
                tier,
                "count",
                "count",
                expected,
                aggregate_field="",
            )
        )
    assert len(cases) == 200
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    with (DATASET_DIR / "crm_200.jsonl").open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")


def _aggregate_case(
    cases: list[dict[str, Any]],
    question: str,
    object_type: str,
    field: str,
    operator: str,
    value: Any,
    function: str,
    alias: str,
    expected: Any,
    extra_filter: dict[str, Any] | None = None,
    aggregate_field: str | None = None,
) -> dict[str, Any]:
    filters = [{"field": field, "operator": operator, "value": value}]
    if extra_filter:
        filters.append(extra_filter)
    return {
        "id": f"crm-{len(cases) + 1:03d}",
        "category": "filter_aggregate",
        "question": question,
        "expected_document_ids": [f"schema:object:{object_type}"],
        "query_plan": {
            "intent": "aggregate",
            "object_types": [object_type],
            "filters": filters,
            "aggregates": [
                {
                    "function": function,
                    "field": field if aggregate_field is None else aggregate_field,
                    "alias": alias,
                }
            ],
            "limit": 10,
        },
        "expected_rows": [{alias: expected}],
    }


def _write_actions(orders: list[dict[str, Any]]) -> None:
    groups = {
        "deny": [item for item in orders if item["status"] == "cancelled"][:10],
        "confirm": [
            item
            for item in orders
            if item["status"] != "cancelled" and float(item["amount"]) >= 10000
        ][:10],
        "allow": [
            item
            for item in orders
            if item["status"] != "cancelled" and float(item["amount"]) < 10000
        ][:10],
    }
    cases = [
        {
            "id": f"action-{index:03d}",
            "action_type_id": "approve_order",
            "object_type_id": "order",
            "instance_id": item["order_id"],
            "expected_decision": decision,
        }
        for index, (decision, item) in enumerate(
            ((decision, item) for decision, items in groups.items() for item in items), 1
        )
    ]
    with (DATASET_DIR / "crm_actions_30.jsonl").open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
