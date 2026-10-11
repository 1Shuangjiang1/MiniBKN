"""Generic field profiling and explainable primary/foreign key discovery."""

from itertools import combinations
from typing import Any

from minibkn.domain.models import KeyCandidate, Resource, ResourceField

_ID_NAMES = {"id", "key", "code", "sku", "uuid"}


def profile_resources(
    resources: list[Resource], rows_by_resource: dict[str, list[dict[str, Any]]]
) -> list[Resource]:
    profiled = [
        _profile_resource(resource, rows_by_resource.get(resource.id, [])) for resource in resources
    ]
    result = []
    for resource in profiled:
        foreign = _foreign_candidates(resource, profiled, rows_by_resource)
        result.append(resource.model_copy(update={"foreign_key_candidates": foreign}))
    return result


def _profile_resource(resource: Resource, rows: list[dict[str, Any]]) -> Resource:
    declared_primary = [field.name for field in resource.fields if field.primary_key]
    fields = [_profile_field(field, rows) for field in resource.fields]
    primary = _primary_candidates(resource.id, fields, rows)
    if declared_primary:
        primary = [
            KeyCandidate(
                kind="primary",
                fields=declared_primary,
                confidence=1.0,
                reasons=["数据源显式声明主键"],
                recommended=True,
            ),
            *[item for item in primary if item.fields != declared_primary],
        ]
    recommended_fields = set(primary[0].fields) if primary and primary[0].recommended else set()
    fields = [
        field.model_copy(update={"primary_key": field.name in recommended_fields})
        for field in fields
    ]
    return resource.model_copy(
        update={
            "fields": fields,
            "row_count": len(rows) if rows else resource.row_count,
            "primary_key_candidates": primary,
        }
    )


def _profile_field(field: ResourceField, rows: list[dict[str, Any]]) -> ResourceField:
    values = [row.get(field.name) for row in rows]
    non_empty = [value for value in values if value is not None and str(value).strip()]
    distinct = {_stable(value) for value in non_empty}
    total = len(values)
    return field.model_copy(
        update={
            "non_null_count": len(non_empty),
            "distinct_count": len(distinct),
            "null_ratio": (total - len(non_empty)) / total if total else 0.0,
            "uniqueness_ratio": len(distinct) / len(non_empty) if non_empty else 0.0,
        }
    )


def _primary_candidates(
    resource_id: str, fields: list[ResourceField], rows: list[dict[str, Any]]
) -> list[KeyCandidate]:
    candidates = []
    for field in fields:
        if not rows or field.non_null_count != len(rows) or field.uniqueness_ratio < 1.0:
            continue
        name_signal = _id_signal(field.name, resource_id)
        confidence = min(1.0, 0.75 + name_signal + (0.05 if len(rows) >= 3 else 0.0))
        reasons = ["所有非空值唯一", "字段无空值"]
        if name_signal:
            reasons.append("字段名具有标识符语义")
        candidates.append(
            KeyCandidate(
                kind="primary",
                fields=[field.name],
                confidence=confidence,
                reasons=reasons,
                recommended=confidence >= 0.9,
            )
        )
    promising = [field for field in fields if field.null_ratio == 0.0][:12]
    if not any(item.recommended for item in candidates):
        for left, right in combinations(promising, 2):
            values = {(_stable(row.get(left.name)), _stable(row.get(right.name))) for row in rows}
            if rows and len(values) == len(rows):
                confidence = min(
                    0.95,
                    0.82
                    + _id_signal(left.name, resource_id) / 2
                    + _id_signal(right.name, resource_id) / 2,
                )
                candidates.append(
                    KeyCandidate(
                        kind="primary",
                        fields=[left.name, right.name],
                        confidence=confidence,
                        reasons=["字段组合无空值且联合唯一", "单字段候选不足以可靠标识记录"],
                        recommended=confidence >= 0.88,
                    )
                )
    return sorted(candidates, key=lambda item: (-item.confidence, len(item.fields), item.fields))[
        :10
    ]


def _foreign_candidates(
    source: Resource,
    resources: list[Resource],
    rows_by_resource: dict[str, list[dict[str, Any]]],
) -> list[KeyCandidate]:
    source_rows = rows_by_resource.get(source.id, [])
    candidates = []
    for target in resources:
        if target.id == source.id:
            continue
        target_rows = rows_by_resource.get(target.id, [])
        target_keys = [item for item in target.primary_key_candidates if item.recommended]
        for target_key in target_keys[:3]:
            if len(target_key.fields) == 1:
                for source_field in source.fields:
                    candidate = _single_foreign_candidate(
                        source_field, source_rows, target, target_key.fields[0], target_rows
                    )
                    if candidate is not None:
                        candidates.append(candidate)
            elif all(
                any(field.name == key for field in source.fields) for key in target_key.fields
            ):
                overlap = _tuple_overlap(
                    source_rows, target_rows, target_key.fields, target_key.fields
                )
                confidence = min(1.0, 0.75 * overlap + 0.2)
                if overlap >= 0.5:
                    candidates.append(
                        KeyCandidate(
                            kind="foreign",
                            fields=target_key.fields,
                            target_resource_id=target.id,
                            target_fields=target_key.fields,
                            confidence=confidence,
                            reasons=[f"组合值域覆盖率 {overlap:.0%}", "字段组合与目标主键一致"],
                            recommended=overlap >= 0.8 and confidence >= 0.8,
                        )
                    )
    unique = {
        (tuple(item.fields), item.target_resource_id, tuple(item.target_fields)): item
        for item in candidates
    }
    return sorted(unique.values(), key=lambda item: (-item.confidence, item.fields))[:20]


def _single_foreign_candidate(
    source_field: ResourceField,
    source_rows: list[dict[str, Any]],
    target: Resource,
    target_field_name: str,
    target_rows: list[dict[str, Any]],
) -> KeyCandidate | None:
    source_values = {
        _stable(row.get(source_field.name))
        for row in source_rows
        if row.get(source_field.name) not in (None, "")
    }
    target_values = {
        _stable(row.get(target_field_name))
        for row in target_rows
        if row.get(target_field_name) not in (None, "")
    }
    if not source_values or not target_values:
        return None
    overlap = len(source_values & target_values) / len(source_values)
    if overlap < 0.35:
        return None
    target_field = next(field for field in target.fields if field.name == target_field_name)
    name_score = _foreign_name_signal(source_field.name, target.id, target_field_name)
    type_score = 0.1 if source_field.value_type == target_field.value_type else 0.0
    confidence = min(1.0, 0.65 * overlap + name_score + type_score)
    reasons = [f"源值在目标主键中的覆盖率 {overlap:.0%}"]
    if name_score:
        reasons.append("字段名与目标对象或主键语义相符")
    if type_score:
        reasons.append("源字段与目标主键类型一致")
    return KeyCandidate(
        kind="foreign",
        fields=[source_field.name],
        target_resource_id=target.id,
        target_fields=[target_field_name],
        confidence=confidence,
        reasons=reasons,
        recommended=overlap >= 0.7 and confidence >= 0.8,
    )


def _tuple_overlap(
    source_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    source_fields: list[str],
    target_fields: list[str],
) -> float:
    source_values = {
        tuple(_stable(row.get(field)) for field in source_fields) for row in source_rows
    }
    target_values = {
        tuple(_stable(row.get(field)) for field in target_fields) for row in target_rows
    }
    return len(source_values & target_values) / len(source_values) if source_values else 0.0


def _id_signal(field_name: str, resource_id: str) -> float:
    field = field_name.lower()
    resource = resource_id.lower().removesuffix("_csv").rstrip("s")
    return (
        0.2
        if field in _ID_NAMES or field.endswith(("_id", "_code")) or field == f"{resource}_id"
        else 0.0
    )


def _foreign_name_signal(source_field: str, target_resource: str, target_field: str) -> float:
    source = source_field.lower()
    target = target_resource.lower().removesuffix("_csv").rstrip("s")
    if source == target_field.lower() or source == f"{target}_id":
        return 0.25
    return 0.1 if source.endswith("_id") else 0.0


def _stable(value: Any) -> str:
    return str(value).strip().casefold()
