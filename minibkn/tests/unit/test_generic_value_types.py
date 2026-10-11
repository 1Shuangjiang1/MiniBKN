import pytest

from minibkn.application.graph_service import _convert_value


@pytest.mark.parametrize(
    ("value", "value_type", "expected"),
    [
        ("128000.50", "decimal", "128000.50"),
        ("2026-08-16", "date", "2026-08-16"),
        ("2026-08-16T08:30:00Z", "datetime", "2026-08-16T08:30:00+00:00"),
        ('{"priority": "high"}', "json", {"priority": "high"}),
    ],
)
def test_business_values_are_normalized_to_json_compatible_types(
    value: str, value_type: str, expected: object
) -> None:
    assert _convert_value(value, value_type) == expected


def test_invalid_decimal_is_rejected_instead_of_silently_coerced() -> None:
    with pytest.raises(ValueError, match="invalid decimal"):
        _convert_value("not-a-number", "decimal")
