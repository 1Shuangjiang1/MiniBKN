"""Generate a fresh 60-case cross-domain QueryPlan holdout set."""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evals" / "datasets" / "enterprise_query_planner_holdout_60.jsonl"


def _case(
    case_id: str,
    domain: str,
    question: str,
    expected: dict[str, Any] | None = None,
    ambiguities: int = 0,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": case_id,
        "domain": domain,
        "split": "holdout",
        "question": question,
        "expected_status": "needs_clarification" if ambiguities else "ready",
    }
    if ambiguities:
        row["minimum_ambiguities"] = ambiguities
    else:
        row["expected"] = expected or {}
    return row


def _e(
    intent: str,
    object_type: str,
    filters: list[list[Any]] | None = None,
    aggregates: list[list[str]] | None = None,
    traversals: list[str] | None = None,
    group_by: list[str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"intent": intent, "object_types": [object_type]}
    if filters is not None:
        result["filters"] = filters
    if aggregates is not None:
        result["aggregates"] = aggregates
    if traversals is not None:
        result["traversals"] = traversals
    if group_by is not None:
        result["group_by"] = group_by
    return result


def generate() -> list[dict[str, Any]]:
    rows = [
        _case(
            "proc-h-001",
            "procurement",
            "已批准采购单有多少笔",
            _e("aggregate", "purchase_order", [["status", "eq", "approved"]], [["count", ""]]),
        ),
        _case(
            "proc-h-002",
            "procurement",
            "已收货采购单的平均金额",
            _e("aggregate", "purchase_order", [["status", "eq", "received"]], [["avg", "amount"]]),
        ),
        _case(
            "proc-h-003",
            "procurement",
            "已取消采购单的金额总和",
            _e("aggregate", "purchase_order", [["status", "eq", "cancelled"]], [["sum", "amount"]]),
        ),
        _case(
            "proc-h-004",
            "procurement",
            "按状态统计采购单数量",
            _e("aggregate", "purchase_order", aggregates=[["count", ""]], group_by=["status"]),
        ),
        _case(
            "proc-h-005",
            "procurement",
            "采购单的最大金额是多少",
            _e("aggregate", "purchase_order", aggregates=[["max", "amount"]]),
        ),
        _case(
            "proc-h-006",
            "procurement",
            "列出华东地区的供应商",
            _e("lookup", "supplier", [["region", "eq", "华东"]]),
        ),
        _case(
            "proc-h-007",
            "procurement",
            "查找物流类供应商",
            _e("lookup", "supplier", [["category", "eq", "物流"]]),
        ),
        _case(
            "proc-h-008",
            "procurement",
            "有哪些中风险供应商",
            _e("lookup", "supplier", [["risk_level", "eq", "medium"]]),
        ),
        _case(
            "proc-h-009",
            "procurement",
            "待处理付款有多少笔",
            _e("aggregate", "payment", [["status", "eq", "pending"]], [["count", ""]]),
        ),
        _case(
            "proc-h-010",
            "procurement",
            "已付款记录的金额总和",
            _e("aggregate", "payment", [["status", "eq", "paid"]], [["sum", "amount"]]),
        ),
        _case(
            "proc-h-011",
            "procurement",
            "列出数量超过20的采购明细",
            _e("lookup", "purchase_item", [["quantity", "gt", 20]]),
        ),
        _case(
            "proc-h-012",
            "procurement",
            "查询采购单 PO-00123",
            _e("lookup", "purchase_order", [["po_id", "eq", "PO-00123"]]),
        ),
        _case(
            "proc-h-013",
            "procurement",
            "供应商 SUP-042 的资料",
            _e("lookup", "supplier", [["supplier_id", "eq", "SUP-042"]]),
        ),
        _case(
            "proc-h-014",
            "procurement",
            "查询付款 PAY-00111",
            _e("lookup", "payment", [["payment_id", "eq", "PAY-00111"]]),
        ),
        _case(
            "proc-h-015",
            "procurement",
            "PO-00201 对应哪家供应商",
            _e(
                "traverse",
                "purchase_order",
                [["po_id", "eq", "PO-00201"]],
                traversals=["ordered_from"],
            ),
        ),
        _case(
            "proc-h-016",
            "procurement",
            "PO-00202 由哪个采购员负责",
            _e(
                "traverse",
                "purchase_order",
                [["po_id", "eq", "PO-00202"]],
                traversals=["handled_by"],
            ),
        ),
        _case(
            "proc-h-017",
            "procurement",
            "PAY-00129 是哪张采购单的付款",
            _e(
                "traverse",
                "payment",
                [["payment_id", "eq", "PAY-00129"]],
                traversals=["payment_for_order"],
            ),
        ),
        _case("proc-h-018", "procurement", "最近的大额采购单有哪些", ambiguities=2),
        _case("proc-h-019", "procurement", "看看它的付款情况", ambiguities=1),
        _case("proc-h-020", "procurement", "最好的供应商是哪家", ambiguities=1),
        _case(
            "fin-h-001",
            "finance",
            "未结清发票有多少张",
            _e("aggregate", "invoice", [["status", "eq", "open"]], [["count", ""]]),
        ),
        _case(
            "fin-h-002",
            "finance",
            "已付清发票的平均金额",
            _e("aggregate", "invoice", [["status", "eq", "paid"]], [["avg", "amount"]]),
        ),
        _case(
            "fin-h-003",
            "finance",
            "部分付款发票的总金额",
            _e("aggregate", "invoice", [["status", "eq", "partial"]], [["sum", "amount"]]),
        ),
        _case(
            "fin-h-004",
            "finance",
            "按状态汇总发票数量",
            _e("aggregate", "invoice", aggregates=[["count", ""]], group_by=["status"]),
        ),
        _case(
            "fin-h-005",
            "finance",
            "最小的发票金额是多少",
            _e("aggregate", "invoice", aggregates=[["min", "amount"]]),
        ),
        _case(
            "fin-h-006",
            "finance",
            "列出东部地区的客户",
            _e("lookup", "client", [["region", "eq", "east"]]),
        ),
        _case(
            "fin-h-007",
            "finance",
            "企业级客户有哪些",
            _e("lookup", "client", [["segment", "eq", "enterprise"]]),
        ),
        _case(
            "fin-h-008",
            "finance",
            "银行方式的收款有多少笔",
            _e("aggregate", "receipt", [["method", "eq", "bank"]], [["count", ""]]),
        ),
        _case(
            "fin-h-009",
            "finance",
            "转账收款的总金额",
            _e("aggregate", "receipt", [["method", "eq", "transfer"]], [["sum", "amount"]]),
        ),
        _case(
            "fin-h-010",
            "finance",
            "列出已批准的差旅报销",
            _e("lookup", "expense", [["status", "eq", "approved"], ["category", "eq", "travel"]]),
        ),
        _case(
            "fin-h-011",
            "finance",
            "查询发票 INV-00217",
            _e("lookup", "invoice", [["invoice_id", "eq", "INV-00217"]]),
        ),
        _case(
            "fin-h-012",
            "finance",
            "客户 CLI-0042 的资料",
            _e("lookup", "client", [["client_id", "eq", "CLI-0042"]]),
        ),
        _case(
            "fin-h-013",
            "finance",
            "查询收款 REC-00176",
            _e("lookup", "receipt", [["receipt_id", "eq", "REC-00176"]]),
        ),
        _case(
            "fin-h-014",
            "finance",
            "INV-00311 属于哪位客户",
            _e(
                "traverse", "invoice", [["invoice_id", "eq", "INV-00311"]], traversals=["billed_to"]
            ),
        ),
        _case(
            "fin-h-015",
            "finance",
            "REC-00203 对应哪张发票",
            _e(
                "traverse",
                "receipt",
                [["receipt_id", "eq", "REC-00203"]],
                traversals=["receipt_for_invoice"],
            ),
        ),
        _case(
            "fin-h-016",
            "finance",
            "EXP-00155 属于哪个部门",
            _e(
                "traverse",
                "expense",
                [["expense_id", "eq", "EXP-00155"]],
                traversals=["expense_department"],
            ),
        ),
        _case("fin-h-017", "finance", "最近的高额报销有哪些", ambiguities=2),
        _case("fin-h-018", "finance", "它还欠多少钱", ambiguities=1),
        _case("fin-h-019", "finance", "最重要的客户是谁", ambiguities=1),
        _case("fin-h-020", "finance", "近期的发票情况", ambiguities=1),
        _case(
            "hr-h-001",
            "hr",
            "离职员工有多少人",
            _e("aggregate", "employee", [["status", "eq", "terminated"]], [["count", ""]]),
        ),
        _case(
            "hr-h-002",
            "hr",
            "已提交请假有多少条",
            _e("aggregate", "leave_request", [["status", "eq", "submitted"]], [["count", ""]]),
        ),
        _case(
            "hr-h-003",
            "hr",
            "病假的平均天数",
            _e("aggregate", "leave_request", [["leave_type", "eq", "sick"]], [["avg", "days"]]),
        ),
        _case(
            "hr-h-004",
            "hr",
            "按状态统计员工人数",
            _e("aggregate", "employee", aggregates=[["count", ""]], group_by=["status"]),
        ),
        _case(
            "hr-h-005",
            "hr",
            "请假申请的最大天数",
            _e("aggregate", "leave_request", aggregates=[["max", "days"]]),
        ),
        _case(
            "hr-h-006",
            "hr",
            "列出状态为休假的员工",
            _e("lookup", "employee", [["status", "eq", "leave"]]),
        ),
        _case(
            "hr-h-007",
            "hr",
            "已拒绝的请假申请有哪些",
            _e("lookup", "leave_request", [["status", "eq", "rejected"]]),
        ),
        _case(
            "hr-h-008",
            "hr",
            "三天以内的个人假申请",
            _e("lookup", "leave_request", [["days", "lte", 3], ["leave_type", "eq", "personal"]]),
        ),
        _case(
            "hr-h-009",
            "hr",
            "计划中的调岗有多少个",
            _e("aggregate", "job_change", [["status", "eq", "planned"]], [["count", ""]]),
        ),
        _case(
            "hr-h-010",
            "hr",
            "年假申请总共有多少条",
            _e("aggregate", "leave_request", [["leave_type", "eq", "annual"]], [["count", ""]]),
        ),
        _case(
            "hr-h-011",
            "hr",
            "查询员工 EMP-0128",
            _e("lookup", "employee", [["employee_id", "eq", "EMP-0128"]]),
        ),
        _case(
            "hr-h-012",
            "hr",
            "查询部门 DEP-014",
            _e("lookup", "department", [["dept_id", "eq", "DEP-014"]]),
        ),
        _case(
            "hr-h-013",
            "hr",
            "查询请假 LEV-00321",
            _e("lookup", "leave_request", [["leave_id", "eq", "LEV-00321"]]),
        ),
        _case(
            "hr-h-014",
            "hr",
            "EMP-0207 属于哪个部门",
            _e(
                "traverse",
                "employee",
                [["employee_id", "eq", "EMP-0207"]],
                traversals=["employee_department"],
            ),
        ),
        _case(
            "hr-h-015",
            "hr",
            "LEV-00409 是谁的请假",
            _e(
                "traverse",
                "leave_request",
                [["leave_id", "eq", "LEV-00409"]],
                traversals=["leave_employee"],
            ),
        ),
        _case(
            "hr-h-016",
            "hr",
            "CHG-00177 是哪位员工的调岗",
            _e(
                "traverse",
                "job_change",
                [["change_id", "eq", "CHG-00177"]],
                traversals=["change_employee"],
            ),
        ),
        _case("hr-h-017", "hr", "最近的调岗有哪些", ambiguities=1),
        _case("hr-h-018", "hr", "看看他的请假记录", ambiguities=1),
        _case("hr-h-019", "hr", "表现最好的员工是谁", ambiguities=1),
        _case("hr-h-020", "hr", "近期长假申请有哪些", ambiguities=2),
    ]
    assert len(rows) == 60
    assert len({row["id"] for row in rows}) == 60
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


if __name__ == "__main__":
    print(json.dumps({"output": str(OUTPUT), "cases": len(generate())}, ensure_ascii=False))
