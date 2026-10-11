# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Small allowlisted expression evaluator for BKN risk policies."""

from typing import Any


class PolicyEvaluationError(ValueError):
    pass


class PolicyEvaluator:
    def __init__(self, max_depth: int = 20, max_nodes: int = 200) -> None:
        self._max_depth = max_depth
        self._max_nodes = max_nodes

    def evaluate(self, expression: Any, context: dict[str, Any]) -> bool:
        counter = [0]
        return bool(self._eval(expression, context, 0, counter))

    def validate(self, expression: Any) -> None:
        self._validate(expression, 0, [0])

    def references(self, expression: Any) -> set[str]:
        self.validate(expression)
        result: set[str] = set()

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                if set(value) == {"ref"} and isinstance(value["ref"], str):
                    result.add(value["ref"])
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        collect(expression)
        return result

    def _validate(self, expression: Any, depth: int, counter: list[int]) -> None:
        counter[0] += 1
        if counter[0] > self._max_nodes or depth > self._max_depth:
            raise PolicyEvaluationError("policy expression exceeds complexity limit")
        if expression is None or isinstance(expression, (str, int, float, bool)):
            return
        if isinstance(expression, list):
            for item in expression:
                self._validate(item, depth + 1, counter)
            return
        if not isinstance(expression, dict) or len(expression) != 1:
            raise PolicyEvaluationError("each policy expression must contain exactly one operator")
        operator, raw = next(iter(expression.items()))
        allowed = {
            "ref",
            "and",
            "or",
            "not",
            "eq",
            "neq",
            "gt",
            "gte",
            "lt",
            "lte",
            "in",
            "add",
            "sub",
            "mul",
            "div",
            "max",
            "min",
            "abs",
        }
        if operator not in allowed:
            raise PolicyEvaluationError(f"unsupported policy operator: {operator}")
        if operator == "ref":
            if not isinstance(raw, str) or "." not in raw:
                raise PolicyEvaluationError("ref must use scope.field format")
            if raw.split(".", 1)[0] not in {"object", "action", "subject"}:
                raise PolicyEvaluationError(f"unsupported policy reference scope: {raw}")
            return
        operands = self._list(raw)
        exact = {
            "not": 1,
            "abs": 1,
            "eq": 2,
            "neq": 2,
            "gt": 2,
            "gte": 2,
            "lt": 2,
            "lte": 2,
            "in": 2,
        }
        if operator in exact:
            self._arity(operator, operands, exact[operator])
        if operator in {"add", "sub", "mul", "div", "max", "min"} and len(operands) < 2:
            raise PolicyEvaluationError(f"{operator} requires at least two operands")
        for item in operands:
            self._validate(item, depth + 1, counter)

    def _eval(
        self, expression: Any, context: dict[str, Any], depth: int, counter: list[int]
    ) -> Any:
        counter[0] += 1
        if counter[0] > self._max_nodes or depth > self._max_depth:
            raise PolicyEvaluationError("policy expression exceeds complexity limit")
        if expression is None or isinstance(expression, (str, int, float, bool)):
            return expression
        if isinstance(expression, list):
            return [self._eval(item, context, depth + 1, counter) for item in expression]
        if not isinstance(expression, dict) or len(expression) != 1:
            raise PolicyEvaluationError("each policy expression must contain exactly one operator")
        operator, raw = next(iter(expression.items()))
        if operator == "ref":
            return self._resolve_ref(raw, context)
        if operator == "and":
            return all(
                bool(self._eval(item, context, depth + 1, counter)) for item in self._list(raw)
            )
        if operator == "or":
            return any(
                bool(self._eval(item, context, depth + 1, counter)) for item in self._list(raw)
            )
        if operator == "not":
            return not bool(self._eval(raw, context, depth + 1, counter))
        values = [self._eval(item, context, depth + 1, counter) for item in self._list(raw)]
        if operator in {"eq", "neq", "gt", "gte", "lt", "lte", "in"}:
            self._arity(operator, values, 2)
            return self._compare(operator, values[0], values[1])
        if operator in {"add", "sub", "mul", "div", "max", "min"}:
            if len(values) < 2:
                raise PolicyEvaluationError(f"{operator} requires at least two operands")
            return self._arithmetic(operator, values)
        if operator == "abs":
            self._arity(operator, values, 1)
            return abs(self._number(values[0]))
        raise PolicyEvaluationError(f"unsupported policy operator: {operator}")

    @staticmethod
    def _resolve_ref(raw: Any, context: dict[str, Any]) -> Any:
        if not isinstance(raw, str) or "." not in raw:
            raise PolicyEvaluationError("ref must use scope.field format")
        scope, field = raw.split(".", 1)
        values = context.get(scope)
        if not isinstance(values, dict) or field not in values:
            raise PolicyEvaluationError(f"policy reference is unavailable: {raw}")
        return values[field]

    @staticmethod
    def _list(raw: Any) -> list[Any]:
        return raw if isinstance(raw, list) else [raw]

    @staticmethod
    def _arity(operator: str, values: list[Any], expected: int) -> None:
        if len(values) != expected:
            raise PolicyEvaluationError(f"{operator} requires {expected} operands")

    @staticmethod
    def _compare(operator: str, left: Any, right: Any) -> bool:
        if operator == "eq":
            return bool(left == right)
        if operator == "neq":
            return bool(left != right)
        if operator == "in":
            return left in right if isinstance(right, list) else False
        try:
            left_number, right_number = float(left), float(right)
        except (TypeError, ValueError):
            left_text, right_text = str(left), str(right)
            return {
                "gt": left_text > right_text,
                "gte": left_text >= right_text,
                "lt": left_text < right_text,
                "lte": left_text <= right_text,
            }[operator]
        return {
            "gt": left_number > right_number,
            "gte": left_number >= right_number,
            "lt": left_number < right_number,
            "lte": left_number <= right_number,
        }[operator]

    @classmethod
    def _arithmetic(cls, operator: str, values: list[Any]) -> float:
        numbers = [cls._number(value) for value in values]
        if operator == "add":
            return sum(numbers)
        if operator == "sub":
            return numbers[0] - sum(numbers[1:])
        if operator == "mul":
            result = 1.0
            for value in numbers:
                result *= value
            return result
        if operator == "div":
            result = numbers[0]
            for value in numbers[1:]:
                if value == 0:
                    raise PolicyEvaluationError("division by zero")
                result /= value
            return result
        return max(numbers) if operator == "max" else min(numbers)

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise PolicyEvaluationError(f"value is not numeric: {value}") from exc
