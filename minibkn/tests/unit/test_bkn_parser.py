from pathlib import Path

import pytest

from minibkn.adapters.bkn_lang import BknLangParser
from minibkn.domain.errors import BknValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_BKN = PROJECT_ROOT / "examples" / "supply_chain" / "bkn"


def test_parse_supply_chain_network() -> None:
    network = BknLangParser().parse_directory(EXAMPLE_BKN)

    assert network.id == "supply_chain"
    assert network.business_domain == "procurement"
    assert [item.id for item in network.object_types] == ["material", "supplier"]
    assert [item.id for item in network.relation_types] == ["supplied_by"]
    assert [item.id for item in network.action_types] == ["create_replenishment_alert"]
    assert [item.id for item in network.risk_types] == ["high_value_replenishment"]

    material = network.object_types[0]
    assert material.primary_keys == ["sku"]
    assert material.display_key == "name"
    assert material.data_source is not None
    assert material.data_source.source_id == "materials_csv"

    action = network.action_types[0]
    assert action.bound_object_type == "material"
    assert action.trigger_condition["operation"] == "lt_field"
    assert action.tool.tool_id == "create_replenishment_alert"


def test_reject_relation_to_unknown_object_type(tmp_path: Path) -> None:
    (tmp_path / "network.bkn").write_text(
        """---
type: knowledge_network
id: invalid
name: Invalid Network
---

# Invalid Network
""",
        encoding="utf-8",
    )
    object_dir = tmp_path / "object_types"
    object_dir.mkdir()
    (object_dir / "material.bkn").write_text(
        """---
type: object_type
id: material
name: Material
---

## ObjectType: Material

### Data Properties

| Name | Display Name | Type | Description | Mapped Field |
| --- | --- | --- | --- | --- |
| sku | SKU | string | Code | sku |

### Keys

Primary Keys: sku
Display Key: sku
Incremental Key:
""",
        encoding="utf-8",
    )
    relation_dir = tmp_path / "relation_types"
    relation_dir.mkdir()
    (relation_dir / "broken.bkn").write_text(
        """---
type: relation_type
id: broken
name: Broken
---

## RelationType: Broken

### Endpoint

| Source | Target | Type |
| --- | --- | --- |
| material | missing_supplier | direct |

### Mapping Rules

| Source Property | Target Property |
| --- | --- |
| sku | supplier_id |
""",
        encoding="utf-8",
    )

    with pytest.raises(BknValidationError) as error:
        BknLangParser().parse_directory(tmp_path)

    messages = [issue.message for issue in error.value.issues]
    assert "unknown target object_type 'missing_supplier'" in messages
