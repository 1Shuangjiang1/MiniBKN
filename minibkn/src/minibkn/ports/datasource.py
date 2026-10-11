"""Ports for discovering and reading structured local data."""

from typing import Any, Protocol

from minibkn.domain.models import DataSource, Resource


class DataSourceAdapter(Protocol):
    def discover(self, source: DataSource) -> list[Resource]: ...

    def read_rows(self, resource: Resource) -> list[dict[str, Any]]: ...
