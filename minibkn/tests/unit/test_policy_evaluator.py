import pytest

from minibkn.domain.policy import PolicyEvaluationError, PolicyEvaluator


def test_policy_dsl_evaluates_nested_business_expression() -> None:
    expression = {
        "and": [
            {"gt": [{"ref": "action.discount_rate"}, 0.2]},
            {"neq": [{"ref": "subject.role"}, "sales_manager"]},
        ]
    }
    context = {
        "object": {},
        "action": {"discount_rate": 0.25},
        "subject": {"role": "sales_rep"},
    }

    assert PolicyEvaluator().evaluate(expression, context) is True


def test_policy_dsl_supports_safe_arithmetic_without_eval() -> None:
    expression = {
        "gte": [
            {
                "mul": [
                    {"max": [0, {"sub": [{"ref": "object.target"}, {"ref": "object.current"}]}]},
                    {"ref": "object.price"},
                ]
            },
            500,
        ]
    }
    assert PolicyEvaluator().evaluate(
        expression,
        {"object": {"target": 30, "current": 8, "price": 42.5}, "action": {}, "subject": {}},
    )


@pytest.mark.parametrize(
    "expression",
    [
        {"python": "__import__('os').system('whoami')"},
        {"div": [1, 0]},
        {"ref": "subject.missing"},
        {"eq": [1, 1], "or": [True]},
    ],
)
def test_policy_dsl_rejects_unsafe_or_invalid_expressions(expression: object) -> None:
    with pytest.raises(PolicyEvaluationError):
        PolicyEvaluator().evaluate(expression, {"object": {}, "action": {}, "subject": {}})
