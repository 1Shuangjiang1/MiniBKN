"""A reproducible 200-query synthetic benchmark for the supply-chain example."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    query: str
    expected_document_id: str


def build_200_case_dataset() -> list[EvaluationCase]:
    entities = {
        "instance:material:MAT-001": [
            "MAT-001",
            "Temperature Sensor",
            "temperature sensor stock",
            "温度传感器库存",
            "安全库存 MAT-001",
            "who supplies MAT-001",
            "Temperature Sensor supplier",
            "缺货的温度传感器",
        ],
        "instance:material:MAT-002": [
            "MAT-002",
            "Smart Gateway",
            "smart gateway stock",
            "智能网关库存",
            "安全库存 MAT-002",
            "who supplies MAT-002",
            "Smart Gateway supplier",
            "智能网关供应信息",
        ],
        "instance:material:MAT-003": [
            "MAT-003",
            "Relay Module",
            "relay module stock",
            "继电器模块库存",
            "安全库存 MAT-003",
            "who supplies MAT-003",
            "Relay Module supplier",
            "缺货的继电器模块",
        ],
        "instance:supplier:SUP-001": [
            "SUP-001",
            "Precision Components",
            "precision components supplier",
            "精密组件供应商",
            "SUP-001 contact",
            "expedite SUP-001",
            "supply@example.com",
            "供应商 Precision Components",
        ],
        "instance:supplier:SUP-002": [
            "SUP-002",
            "Connected Devices",
            "connected devices supplier",
            "联网设备供应商",
            "SUP-002 contact",
            "expedite SUP-002",
            "orders@example.com",
            "供应商 Connected Devices",
        ],
    }
    wrappers = [
        "{}",
        "请查询 {}",
        "帮我找到 {} 的业务记录",
        "business lookup: {}",
        "show details and relationships for {}",
    ]
    cases: list[EvaluationCase] = []
    for document_id, queries in entities.items():
        for wrapper in wrappers:
            for query in queries:
                cases.append(
                    EvaluationCase(
                        id=f"case-{len(cases) + 1:03d}",
                        query=wrapper.format(query),
                        expected_document_id=document_id,
                    )
                )
    return cases


def score_rankings(
    cases: list[EvaluationCase], rankings: list[list[str]]
) -> dict[str, float | int]:
    if len(cases) != len(rankings):
        raise ValueError("cases and rankings must have the same length")
    reciprocal_ranks = []
    hit_at_1 = 0
    hit_at_3 = 0
    for case, ranked_ids in zip(cases, rankings, strict=True):
        try:
            rank = ranked_ids.index(case.expected_document_id) + 1
        except ValueError:
            rank = 0
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        hit_at_1 += int(rank == 1)
        hit_at_3 += int(0 < rank <= 3)
    total = len(cases) or 1
    return {
        "cases": len(cases),
        "hit_rate_at_1": round(hit_at_1 / total, 4),
        "hit_rate_at_3": round(hit_at_3 / total, 4),
        "mean_reciprocal_rank": round(sum(reciprocal_ranks) / total, 4),
        "context_precision_proxy": round(sum(reciprocal_ranks) / total, 4),
    }
