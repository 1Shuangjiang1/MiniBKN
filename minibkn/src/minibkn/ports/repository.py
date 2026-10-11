"""Persistence ports for knowledge networks."""

from typing import Protocol

from minibkn.domain.build import BuildJob
from minibkn.domain.models import (
    ActionExecution,
    DataSource,
    KnowledgeNetwork,
    ObjectInstance,
    RelationInstance,
    SearchDocument,
    SearchIndexManifest,
    TraceEvent,
)


class KnowledgeNetworkRepository(Protocol):
    async def save(self, network: KnowledgeNetwork) -> KnowledgeNetwork:
        """Create or replace a complete knowledge network."""
        ...

    async def get(self, network_id: str) -> KnowledgeNetwork | None:
        """Return a knowledge network by id."""
        ...

    async def list_all(self) -> list[KnowledgeNetwork]:
        """Return all knowledge networks in stable order."""
        ...


class KnowledgeGraphRepository(Protocol):
    async def save_source(self, source: DataSource) -> DataSource: ...

    async def get_source(self, source_id: str) -> DataSource | None: ...

    async def list_sources(self) -> list[DataSource]: ...

    async def replace_graph(
        self,
        network_id: str,
        objects: list[ObjectInstance],
        relations: list[RelationInstance],
    ) -> None: ...

    async def list_objects(
        self, network_id: str, object_type_id: str | None = None
    ) -> list[ObjectInstance]: ...

    async def list_relations(self, network_id: str) -> list[RelationInstance]: ...

    async def replace_search_documents(
        self, network_id: str, documents: list[SearchDocument]
    ) -> None: ...

    async def list_search_documents(self, network_id: str) -> list[SearchDocument]: ...

    async def save_search_manifest(self, manifest: SearchIndexManifest) -> None: ...

    async def get_search_manifest(self, network_id: str) -> SearchIndexManifest | None: ...

    async def delete_search_manifest(self, network_id: str) -> None: ...

    async def apply_graph_changes(
        self,
        network_id: str,
        upsert_objects: list[ObjectInstance],
        delete_objects: list[tuple[str, str]],
        upsert_relations: list[RelationInstance],
        delete_relations: list[tuple[str, str, str]],
    ) -> None: ...

    async def apply_search_document_changes(
        self, upserts: list[SearchDocument], delete_ids: list[str]
    ) -> None: ...

    async def save_build_job(self, job: BuildJob) -> None: ...

    async def get_build_job(self, build_id: str) -> BuildJob | None: ...


class ExecutionRepository(Protocol):
    async def save_execution(self, execution: ActionExecution) -> ActionExecution: ...

    async def get_execution(self, execution_id: str) -> ActionExecution | None: ...

    async def find_execution_by_idempotency_key(
        self, network_id: str, action_type_id: str, idempotency_key: str
    ) -> ActionExecution | None: ...

    async def append_trace_event(self, event: TraceEvent) -> TraceEvent: ...

    async def list_trace_events(self, trace_id: str) -> list[TraceEvent]: ...
