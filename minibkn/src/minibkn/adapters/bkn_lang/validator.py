"""Cross-document validation for a parsed knowledge network."""

from collections.abc import Iterable

from minibkn.domain.errors import BknValidationError, ValidationIssue
from minibkn.domain.models import KnowledgeNetwork
from minibkn.domain.policy import PolicyEvaluationError, PolicyEvaluator


def validate_network(network: KnowledgeNetwork) -> None:
    issues: list[ValidationIssue] = []
    if not network.object_types:
        issues.append(ValidationIssue(network.source_path, "at least one object_type is required"))

    _check_duplicates(
        ((item.id, item.source_path) for item in network.object_types), "object_type", issues
    )
    _check_duplicates(
        ((item.id, item.source_path) for item in network.relation_types),
        "relation_type",
        issues,
    )
    _check_duplicates(
        ((item.id, item.source_path) for item in network.action_types), "action_type", issues
    )
    _check_duplicates(
        ((item.id, item.source_path) for item in network.risk_types), "risk_type", issues
    )

    objects = {item.id: item for item in network.object_types}
    actions = {item.id: item for item in network.action_types}

    for object_type in network.object_types:
        property_names = [item.name for item in object_type.properties]
        duplicates = {name for name in property_names if property_names.count(name) > 1}
        for duplicate in sorted(duplicates):
            issues.append(
                ValidationIssue(object_type.source_path, f"duplicate property '{duplicate}'")
            )
        known_properties = set(property_names)
        for primary_key in object_type.primary_keys:
            if primary_key not in known_properties:
                issues.append(
                    ValidationIssue(
                        object_type.source_path,
                        f"primary key '{primary_key}' is not a declared property",
                    )
                )
        if not object_type.primary_keys:
            issues.append(ValidationIssue(object_type.source_path, "a primary key is required"))
        if object_type.display_key and object_type.display_key not in known_properties:
            issues.append(
                ValidationIssue(
                    object_type.source_path,
                    f"display key '{object_type.display_key}' is not a declared property",
                )
            )

    for relation in network.relation_types:
        source = objects.get(relation.endpoint.source_object_type)
        target = objects.get(relation.endpoint.target_object_type)
        if source is None:
            issues.append(
                ValidationIssue(
                    relation.source_path,
                    f"unknown source object_type '{relation.endpoint.source_object_type}'",
                )
            )
        if target is None:
            issues.append(
                ValidationIssue(
                    relation.source_path,
                    f"unknown target object_type '{relation.endpoint.target_object_type}'",
                )
            )
        source_properties = {item.name for item in source.properties} if source else set()
        target_properties = {item.name for item in target.properties} if target else set()
        for mapping in relation.mappings:
            if source and mapping.source_property not in source_properties:
                issues.append(
                    ValidationIssue(
                        relation.source_path,
                        f"unknown source property '{mapping.source_property}'",
                    )
                )
            if target and mapping.target_property not in target_properties:
                issues.append(
                    ValidationIssue(
                        relation.source_path,
                        f"unknown target property '{mapping.target_property}'",
                    )
                )

    for action in network.action_types:
        bound_object = objects.get(action.bound_object_type)
        if bound_object is None:
            issues.append(
                ValidationIssue(
                    action.source_path,
                    f"unknown bound object_type '{action.bound_object_type}'",
                )
            )
            continue
        properties = {item.name for item in bound_object.properties}
        for parameter in action.parameters:
            if parameter.source == "property" and parameter.binding not in properties:
                issues.append(
                    ValidationIssue(
                        action.source_path,
                        f"parameter '{parameter.parameter}' references unknown property "
                        f"'{parameter.binding}'",
                    )
                )

    for risk in network.risk_types:
        if risk.policy not in {"allow", "confirm", "deny"}:
            issues.append(
                ValidationIssue(
                    risk.source_path,
                    f"risk policy '{risk.policy}' must be allow, confirm, or deny",
                )
            )
        for action_id in risk.applies_to_actions:
            if action_id not in actions:
                issues.append(
                    ValidationIssue(
                        risk.source_path,
                        f"risk references unknown action_type '{action_id}'",
                    )
                )
        try:
            references = PolicyEvaluator().references(risk.condition)
        except PolicyEvaluationError as exc:
            issues.append(ValidationIssue(risk.source_path, f"invalid risk condition: {exc}"))
            references = set()
        for action_id in risk.applies_to_actions:
            risk_action = actions.get(action_id)
            if risk_action is None:
                continue
            bound = objects.get(risk_action.bound_object_type)
            object_fields = {item.name for item in bound.properties} if bound else set()
            action_fields = {item.parameter for item in risk_action.parameters}
            for reference in references:
                scope, field = reference.split(".", 1)
                if scope == "object" and field not in object_fields:
                    issues.append(
                        ValidationIssue(
                            risk.source_path, f"risk references unknown object field '{field}'"
                        )
                    )
                if scope == "action" and field not in action_fields:
                    issues.append(
                        ValidationIssue(
                            risk.source_path, f"risk references unknown action field '{field}'"
                        )
                    )

    if issues:
        raise BknValidationError("BKN validation failed", issues)


def _check_duplicates(
    values: Iterable[tuple[str, str]], kind: str, issues: list[ValidationIssue]
) -> None:
    seen: set[str] = set()
    for value, source_path in values:
        if value in seen:
            issues.append(ValidationIssue(source_path, f"duplicate {kind} id '{value}'"))
        seen.add(value)
