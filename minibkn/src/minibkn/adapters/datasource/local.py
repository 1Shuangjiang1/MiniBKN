"""CSV directory and SQLite file adapters used by the local MVP."""

import csv
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from minibkn.api.errors import MiniBKNError
from minibkn.application.data_profiling import profile_resources
from minibkn.domain.models import DataSource, Resource, ResourceField


class CsvDataSourceAdapter:
    def discover(self, source: DataSource) -> list[Resource]:
        root = Path(source.path).resolve()
        files = sorted(root.glob("*.csv")) if root.is_dir() else [root]
        if not files or any(not path.is_file() for path in files):
            raise _invalid_source(
                source.path, "CSV path must be a file or a directory with CSV files"
            )
        resources = [self._resource(source.id, path) for path in files]
        rows = {resource.id: self.read_rows(resource) for resource in resources}
        return profile_resources(resources, rows)

    def read_rows(self, resource: Resource) -> list[dict[str, Any]]:
        path = Path(resource.locator)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    def _resource(self, source_id: str, path: Path) -> Resource:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        field_names = list(rows[0]) if rows else self._headers(path)
        primary_keys = _initial_primary_keys(path.stem, field_names, rows)
        fields = [
            ResourceField(
                name=name,
                value_type=_infer_type([row.get(name) for row in rows]),
                nullable=any(not row.get(name) for row in rows),
                primary_key=name in primary_keys,
            )
            for name in field_names
        ]
        return Resource(
            id=f"{path.stem}_csv",
            source_id=source_id,
            name=path.name,
            locator=str(path.resolve()),
            fields=fields,
            row_count=len(rows),
        )

    @staticmethod
    def _headers(path: Path) -> list[str]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return next(csv.reader(handle), [])


class SQLiteDataSourceAdapter:
    def discover(self, source: DataSource) -> list[Resource]:
        path = Path(source.path).resolve()
        if not path.is_file():
            raise _invalid_source(source.path, "SQLite path must point to an existing file")
        with sqlite3.connect(path) as connection:
            table_names = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            resources = []
            rows_by_resource: dict[str, list[dict[str, Any]]] = {}
            for table_name in table_names:
                escaped = table_name.replace('"', '""')
                columns = list(connection.execute(f'PRAGMA table_info("{escaped}")'))
                count = connection.execute(f'SELECT COUNT(*) FROM "{escaped}"').fetchone()[0]
                resources.append(
                    Resource(
                        id=table_name,
                        source_id=source.id,
                        name=table_name,
                        locator=f"{path}::{table_name}",
                        fields=[
                            ResourceField(
                                name=column[1],
                                value_type=_sqlite_type(column[2]),
                                nullable=not bool(column[3]),
                                primary_key=bool(column[5]),
                            )
                            for column in columns
                        ],
                        row_count=count,
                    )
                )
                connection.row_factory = sqlite3.Row
                rows_by_resource[table_name] = [
                    dict(row)
                    for row in connection.execute(f'SELECT * FROM "{escaped}" LIMIT 10000')
                ]
        return profile_resources(resources, rows_by_resource)

    def read_rows(self, resource: Resource) -> list[dict[str, Any]]:
        database_path, table_name = resource.locator.rsplit("::", 1)
        escaped = table_name.replace('"', '""')
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(f'SELECT * FROM "{escaped}"')]


def _infer_type(values: list[str | None]) -> str:
    non_empty = [value.strip() for value in values if value and value.strip()]
    if non_empty and all(_is_int(value) for value in non_empty):
        return "integer"
    if non_empty and all(_is_float(value) for value in non_empty):
        return "number"
    if non_empty and all(value.lower() in {"true", "false"} for value in non_empty):
        return "boolean"
    if non_empty and all(_is_datetime(value) for value in non_empty):
        return "datetime"
    if non_empty and all(_is_date(value) for value in non_empty):
        return "date"
    if non_empty and all(_is_json(value) for value in non_empty):
        return "json"
    return "string"


def _is_int(value: str) -> bool:
    try:
        int(value)
    except ValueError:
        return False
    return True


def _is_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _is_datetime(value: str) -> bool:
    if "T" not in value and " " not in value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_json(value: str) -> bool:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, (dict, list))


def _looks_like_primary_key(name: str, rows: list[dict[str, str]]) -> bool:
    values = [row.get(name) for row in rows]
    return (
        bool(rows)
        and (name.lower() in {"id", "sku"} or name.lower().endswith("_id"))
        and None not in values
        and len(set(values)) == len(values)
    )


def _initial_primary_keys(
    resource_name: str, field_names: list[str], rows: list[dict[str, str]]
) -> set[str]:
    """Choose at most one declared CSV key; leave composite discovery to the profiler."""
    candidates = [name for name in field_names if _looks_like_primary_key(name, rows)]
    if not candidates:
        return set()
    singular = resource_name.removesuffix("s")
    last_word = singular.rsplit("_", 1)[-1]
    for expected in (f"{singular}_id", f"{last_word}_id", "id", "sku"):
        if expected in candidates:
            return {expected}
    first_field = field_names[0] if field_names else ""
    return {first_field} if first_field in candidates else set()


def _sqlite_type(value: str) -> str:
    normalized = value.upper()
    if "INT" in normalized:
        return "integer"
    if any(token in normalized for token in ("REAL", "FLOA", "DOUB", "NUM", "DEC")):
        return "number"
    if "BOOL" in normalized:
        return "boolean"
    if "DATETIME" in normalized or "TIMESTAMP" in normalized:
        return "datetime"
    if "DATE" in normalized:
        return "date"
    if "JSON" in normalized:
        return "json"
    return "string"


def _invalid_source(path: str, message: str) -> MiniBKNError:
    return MiniBKNError(
        error_code="INVALID_DATA_SOURCE",
        message=message,
        details=[{"path": path, "message": message}],
    )
