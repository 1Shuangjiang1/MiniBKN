import sqlite3
from pathlib import Path

from minibkn.adapters.datasource import CsvDataSourceAdapter, SQLiteDataSourceAdapter
from minibkn.domain.models import DataSource, DataSourceKind


def test_sqlite_discovery_and_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "crm.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE customers (customer_id TEXT PRIMARY KEY, name TEXT, score INTEGER)"
        )
        connection.execute("INSERT INTO customers VALUES ('C-001', 'Acme', 95)")

    source = DataSource(
        id="crm_sqlite",
        name="CRM SQLite",
        kind=DataSourceKind.SQLITE,
        path=str(database_path),
    )
    adapter = SQLiteDataSourceAdapter()
    resources = adapter.discover(source)

    assert len(resources) == 1
    assert resources[0].id == "customers"
    assert resources[0].row_count == 1
    assert resources[0].fields[0].primary_key is True
    assert adapter.read_rows(resources[0]) == [
        {"customer_id": "C-001", "name": "Acme", "score": 95}
    ]


def test_csv_discovery_profiles_composite_keys_and_foreign_candidates(tmp_path: Path) -> None:
    (tmp_path / "regions.csv").write_text(
        "region,code,label\nA,1,same\nA,2,same\nB,1,same\nB,2,same\n",
        encoding="utf-8",
    )
    (tmp_path / "events.csv").write_text(
        "event_id,region,code\nE1,A,1\nE2,B,2\n",
        encoding="utf-8",
    )
    source = DataSource(
        id="composite_csv",
        name="Composite CSV",
        kind=DataSourceKind.CSV,
        path=str(tmp_path),
    )

    resources = CsvDataSourceAdapter().discover(source)

    by_id = {item.id: item for item in resources}
    regions = by_id["regions_csv"]
    assert regions.primary_key_candidates[0].fields == ["region", "code"]
    assert regions.primary_key_candidates[0].recommended is True
    event_relation = next(
        item
        for item in by_id["events_csv"].foreign_key_candidates
        if item.target_resource_id == "regions_csv" and item.fields == ["region", "code"]
    )
    assert event_relation.recommended is True
    event_id = next(field for field in by_id["events_csv"].fields if field.name == "event_id")
    assert event_id.distinct_count == 2
    assert event_id.uniqueness_ratio == 1.0
