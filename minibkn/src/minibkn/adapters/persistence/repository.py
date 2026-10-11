"""SQLite/SQLAlchemy implementation of the knowledge network repository."""

from __future__ import annotations

from sqlalchemy import and_, delete, select

from minibkn.adapters.persistence.database import Database
from minibkn.adapters.persistence.tables import (
    ActionExecutionRow,
    BknDocumentRow,
    BuildJobRow,
    DataSourceRow,
    KnowledgeNetworkRow,
    ModelingSessionRow,
    ObjectInstanceRow,
    RelationInstanceRow,
    SearchDocumentRow,
    SearchIndexManifestRow,
    TraceEventRow,
)
from minibkn.domain.build import BuildJob
from minibkn.domain.modeling import ModelingSession
from minibkn.domain.models import (
    ActionExecution,
    DataSource,
    DocumentType,
    KnowledgeNetwork,
    ObjectInstance,
    RelationInstance,
    SearchDocument,
    SearchIndexManifest,
    TraceEvent,
)


class SqlAlchemyKnowledgeNetworkRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def save(self, network: KnowledgeNetwork) -> KnowledgeNetwork:
        payload = network.model_dump(mode="json")
        async with self._database.session() as session:
            existing = await session.get(KnowledgeNetworkRow, network.id)
            if existing is None:
                existing = KnowledgeNetworkRow(
                    id=network.id,
                    name=network.name,
                    business_domain=network.business_domain,
                    version=network.version,
                    source_path=network.source_path,
                    payload=payload,
                    created_at=network.created_at,
                    updated_at=network.updated_at,
                )
                session.add(existing)
            else:
                existing.name = network.name
                existing.business_domain = network.business_domain
                existing.version = network.version
                existing.source_path = network.source_path
                existing.payload = payload
                existing.updated_at = network.updated_at
                await session.execute(
                    delete(BknDocumentRow).where(BknDocumentRow.network_id == network.id)
                )

            session.add_all(self._document_rows(network))
        return network

    async def get(self, network_id: str) -> KnowledgeNetwork | None:
        async with self._database.session() as session:
            row = await session.get(KnowledgeNetworkRow, network_id)
            return KnowledgeNetwork.model_validate(row.payload) if row else None

    async def list_all(self) -> list[KnowledgeNetwork]:
        async with self._database.session() as session:
            result = await session.scalars(
                select(KnowledgeNetworkRow).order_by(KnowledgeNetworkRow.id)
            )
            return [KnowledgeNetwork.model_validate(row.payload) for row in result]

    @staticmethod
    def _document_rows(network: KnowledgeNetwork) -> list[BknDocumentRow]:
        rows: list[BknDocumentRow] = []
        groups = (
            (DocumentType.OBJECT_TYPE, network.object_types),
            (DocumentType.RELATION_TYPE, network.relation_types),
            (DocumentType.ACTION_TYPE, network.action_types),
            (DocumentType.RISK_TYPE, network.risk_types),
        )
        for document_type, documents in groups:
            rows.extend(
                BknDocumentRow(
                    network_id=network.id,
                    document_type=document_type.value,
                    document_id=document.id,
                    name=document.name,
                    source_path=document.source_path,
                    payload=document.model_dump(mode="json"),
                )
                for document in documents
            )
        return rows


class SqlAlchemyKnowledgeGraphRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def save_source(self, source: DataSource) -> DataSource:
        payload = source.model_dump(mode="json")
        async with self._database.session() as session:
            row = await session.get(DataSourceRow, source.id)
            if row is None:
                session.add(
                    DataSourceRow(
                        id=source.id,
                        name=source.name,
                        kind=source.kind.value,
                        path=source.path,
                        payload=payload,
                        created_at=source.created_at,
                        updated_at=source.updated_at,
                    )
                )
            else:
                row.name = source.name
                row.kind = source.kind.value
                row.path = source.path
                row.payload = payload
                row.updated_at = source.updated_at
        return source

    async def get_source(self, source_id: str) -> DataSource | None:
        async with self._database.session() as session:
            row = await session.get(DataSourceRow, source_id)
            return DataSource.model_validate(row.payload) if row else None

    async def list_sources(self) -> list[DataSource]:
        async with self._database.session() as session:
            rows = await session.scalars(select(DataSourceRow).order_by(DataSourceRow.id))
            return [DataSource.model_validate(row.payload) for row in rows]

    async def replace_graph(
        self,
        network_id: str,
        objects: list[ObjectInstance],
        relations: list[RelationInstance],
    ) -> None:
        async with self._database.session() as session:
            await session.execute(
                delete(RelationInstanceRow).where(RelationInstanceRow.network_id == network_id)
            )
            await session.execute(
                delete(ObjectInstanceRow).where(ObjectInstanceRow.network_id == network_id)
            )
            session.add_all(
                ObjectInstanceRow(
                    network_id=item.network_id,
                    object_type_id=item.object_type_id,
                    instance_id=item.instance_id,
                    display_name=item.display_name,
                    resource_id=item.resource_id,
                    row_number=item.row_number,
                    properties=item.properties,
                )
                for item in objects
            )
            session.add_all(
                RelationInstanceRow(
                    network_id=item.network_id,
                    relation_type_id=item.relation_type_id,
                    source_object_type_id=item.source_object_type_id,
                    source_instance_id=item.source_instance_id,
                    target_object_type_id=item.target_object_type_id,
                    target_instance_id=item.target_instance_id,
                )
                for item in relations
            )

    async def list_objects(
        self, network_id: str, object_type_id: str | None = None
    ) -> list[ObjectInstance]:
        statement = select(ObjectInstanceRow).where(ObjectInstanceRow.network_id == network_id)
        if object_type_id is not None:
            statement = statement.where(ObjectInstanceRow.object_type_id == object_type_id)
        statement = statement.order_by(
            ObjectInstanceRow.object_type_id, ObjectInstanceRow.instance_id
        )
        async with self._database.session() as session:
            rows = await session.scalars(statement)
            return [self._object_model(row) for row in rows]

    async def list_relations(self, network_id: str) -> list[RelationInstance]:
        async with self._database.session() as session:
            rows = await session.scalars(
                select(RelationInstanceRow)
                .where(RelationInstanceRow.network_id == network_id)
                .order_by(RelationInstanceRow.relation_type_id, RelationInstanceRow.row_id)
            )
            return [self._relation_model(row) for row in rows]

    async def replace_search_documents(
        self, network_id: str, documents: list[SearchDocument]
    ) -> None:
        async with self._database.session() as session:
            await session.execute(
                delete(SearchDocumentRow).where(SearchDocumentRow.network_id == network_id)
            )
            session.add_all(
                SearchDocumentRow(**document.model_dump(mode="python")) for document in documents
            )

    async def list_search_documents(self, network_id: str) -> list[SearchDocument]:
        async with self._database.session() as session:
            rows = await session.scalars(
                select(SearchDocumentRow)
                .where(SearchDocumentRow.network_id == network_id)
                .order_by(SearchDocumentRow.id)
            )
            return [
                SearchDocument.model_validate(
                    {
                        "id": row.id,
                        "network_id": row.network_id,
                        "level": row.level,
                        "entity_type": row.entity_type,
                        "entity_id": row.entity_id,
                        "title": row.title,
                        "content": row.content,
                        "citation": row.citation,
                        "vector": row.vector,
                    }
                )
                for row in rows
            ]

    async def save_search_manifest(self, manifest: SearchIndexManifest) -> None:
        async with self._database.session() as session:
            row = await session.get(SearchIndexManifestRow, manifest.network_id)
            if row is None:
                session.add(SearchIndexManifestRow(**manifest.model_dump(mode="python")))
            else:
                row.embedding_version = manifest.embedding_version
                row.dimensions = manifest.dimensions
                row.document_count = manifest.document_count
                row.updated_at = manifest.updated_at

    async def get_search_manifest(self, network_id: str) -> SearchIndexManifest | None:
        async with self._database.session() as session:
            row = await session.get(SearchIndexManifestRow, network_id)
            if row is None:
                return None
            return SearchIndexManifest(
                network_id=row.network_id,
                embedding_version=row.embedding_version,
                dimensions=row.dimensions,
                document_count=row.document_count,
                updated_at=row.updated_at,
            )

    async def delete_search_manifest(self, network_id: str) -> None:
        async with self._database.session() as session:
            await session.execute(
                delete(SearchIndexManifestRow).where(
                    SearchIndexManifestRow.network_id == network_id
                )
            )

    async def apply_graph_changes(
        self,
        network_id: str,
        upsert_objects: list[ObjectInstance],
        delete_objects: list[tuple[str, str]],
        upsert_relations: list[RelationInstance],
        delete_relations: list[tuple[str, str, str]],
    ) -> None:
        async with self._database.session() as session:
            for object_type_id, instance_id in delete_objects:
                await session.execute(
                    delete(ObjectInstanceRow).where(
                        and_(
                            ObjectInstanceRow.network_id == network_id,
                            ObjectInstanceRow.object_type_id == object_type_id,
                            ObjectInstanceRow.instance_id == instance_id,
                        )
                    )
                )
            for item in upsert_objects:
                statement = select(ObjectInstanceRow).where(
                    and_(
                        ObjectInstanceRow.network_id == item.network_id,
                        ObjectInstanceRow.object_type_id == item.object_type_id,
                        ObjectInstanceRow.instance_id == item.instance_id,
                    )
                )
                row = await session.scalar(statement)
                if row is None:
                    session.add(
                        ObjectInstanceRow(
                            network_id=item.network_id,
                            object_type_id=item.object_type_id,
                            instance_id=item.instance_id,
                            display_name=item.display_name,
                            resource_id=item.resource_id,
                            row_number=item.row_number,
                            properties=item.properties,
                        )
                    )
                else:
                    row.display_name = item.display_name
                    row.resource_id = item.resource_id
                    row.row_number = item.row_number
                    row.properties = item.properties
            for relation_type_id, source_id, target_id in delete_relations:
                await session.execute(
                    delete(RelationInstanceRow).where(
                        and_(
                            RelationInstanceRow.network_id == network_id,
                            RelationInstanceRow.relation_type_id == relation_type_id,
                            RelationInstanceRow.source_instance_id == source_id,
                            RelationInstanceRow.target_instance_id == target_id,
                        )
                    )
                )
            for relation in upsert_relations:
                relation_statement = select(RelationInstanceRow).where(
                    and_(
                        RelationInstanceRow.network_id == relation.network_id,
                        RelationInstanceRow.relation_type_id == relation.relation_type_id,
                        RelationInstanceRow.source_instance_id == relation.source_instance_id,
                        RelationInstanceRow.target_instance_id == relation.target_instance_id,
                    )
                )
                if await session.scalar(relation_statement) is None:
                    session.add(
                        RelationInstanceRow(
                            network_id=relation.network_id,
                            relation_type_id=relation.relation_type_id,
                            source_object_type_id=relation.source_object_type_id,
                            source_instance_id=relation.source_instance_id,
                            target_object_type_id=relation.target_object_type_id,
                            target_instance_id=relation.target_instance_id,
                        )
                    )

    async def apply_search_document_changes(
        self, upserts: list[SearchDocument], delete_ids: list[str]
    ) -> None:
        async with self._database.session() as session:
            if delete_ids:
                await session.execute(
                    delete(SearchDocumentRow).where(SearchDocumentRow.id.in_(delete_ids))
                )
            for document in upserts:
                row = await session.get(SearchDocumentRow, document.id)
                payload = document.model_dump(mode="python")
                if row is None:
                    session.add(SearchDocumentRow(**payload))
                else:
                    for key, value in payload.items():
                        if key != "id":
                            setattr(row, key, value)

    async def save_build_job(self, job: BuildJob) -> None:
        async with self._database.session() as session:
            row = await session.get(BuildJobRow, job.id)
            if row is None:
                session.add(
                    BuildJobRow(
                        id=job.id,
                        network_id=job.network_id,
                        status=job.status.value,
                        payload=job.model_dump(mode="json"),
                        created_at=job.created_at,
                        updated_at=job.updated_at,
                    )
                )
            else:
                row.status = job.status.value
                row.payload = job.model_dump(mode="json")
                row.updated_at = job.updated_at

    async def get_build_job(self, build_id: str) -> BuildJob | None:
        async with self._database.session() as session:
            row = await session.get(BuildJobRow, build_id)
            return BuildJob.model_validate(row.payload) if row else None

    @staticmethod
    def _object_model(row: ObjectInstanceRow) -> ObjectInstance:
        return ObjectInstance(
            network_id=row.network_id,
            object_type_id=row.object_type_id,
            instance_id=row.instance_id,
            display_name=row.display_name,
            resource_id=row.resource_id,
            row_number=row.row_number,
            properties=row.properties,
        )

    @staticmethod
    def _relation_model(row: RelationInstanceRow) -> RelationInstance:
        return RelationInstance(
            network_id=row.network_id,
            relation_type_id=row.relation_type_id,
            source_object_type_id=row.source_object_type_id,
            source_instance_id=row.source_instance_id,
            target_object_type_id=row.target_object_type_id,
            target_instance_id=row.target_instance_id,
        )


class SqlAlchemyModelingRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def save_modeling_session(self, session: ModelingSession) -> ModelingSession:
        payload = session.model_dump(mode="json")
        async with self._database.session() as database_session:
            row = await database_session.get(ModelingSessionRow, session.id)
            if row is None:
                database_session.add(
                    ModelingSessionRow(
                        id=session.id,
                        source_id=session.source_id,
                        network_id=session.network_id,
                        status=session.status.value,
                        payload=payload,
                        created_at=session.created_at,
                        updated_at=session.updated_at,
                    )
                )
            else:
                row.status = session.status.value
                row.payload = payload
                row.updated_at = session.updated_at
        return session

    async def get_modeling_session(self, session_id: str) -> ModelingSession | None:
        async with self._database.session() as database_session:
            row = await database_session.get(ModelingSessionRow, session_id)
            return ModelingSession.model_validate(row.payload) if row else None

    async def list_modeling_sessions(self) -> list[ModelingSession]:
        async with self._database.session() as database_session:
            rows = await database_session.scalars(
                select(ModelingSessionRow).order_by(ModelingSessionRow.created_at)
            )
            return [ModelingSession.model_validate(row.payload) for row in rows]


class SqlAlchemyExecutionRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def save_execution(self, execution: ActionExecution) -> ActionExecution:
        payload = execution.model_dump(mode="json")
        async with self._database.session() as session:
            row = await session.get(ActionExecutionRow, execution.id)
            if row is None:
                session.add(
                    ActionExecutionRow(
                        id=execution.id,
                        network_id=execution.network_id,
                        action_type_id=execution.action_type_id,
                        object_type_id=execution.object_type_id,
                        instance_id=execution.instance_id,
                        status=execution.status.value,
                        payload=payload,
                        trace_id=execution.trace_id,
                        created_at=execution.created_at,
                        updated_at=execution.updated_at,
                    )
                )
            else:
                row.status = execution.status.value
                row.payload = payload
                row.updated_at = execution.updated_at
        return execution

    async def get_execution(self, execution_id: str) -> ActionExecution | None:
        async with self._database.session() as session:
            row = await session.get(ActionExecutionRow, execution_id)
            return ActionExecution.model_validate(row.payload) if row else None

    async def find_execution_by_idempotency_key(
        self, network_id: str, action_type_id: str, idempotency_key: str
    ) -> ActionExecution | None:
        async with self._database.session() as session:
            rows = await session.scalars(
                select(ActionExecutionRow)
                .where(ActionExecutionRow.network_id == network_id)
                .where(ActionExecutionRow.action_type_id == action_type_id)
                .order_by(ActionExecutionRow.created_at)
            )
            for row in rows:
                execution = ActionExecution.model_validate(row.payload)
                if execution.idempotency_key == idempotency_key:
                    return execution
        return None

    async def append_trace_event(self, event: TraceEvent) -> TraceEvent:
        async with self._database.session() as session:
            session.add(
                TraceEventRow(
                    id=event.id,
                    trace_id=event.trace_id,
                    event_type=event.event_type,
                    payload=event.payload,
                    created_at=event.created_at,
                )
            )
        return event

    async def list_trace_events(self, trace_id: str) -> list[TraceEvent]:
        async with self._database.session() as session:
            rows = await session.scalars(
                select(TraceEventRow)
                .where(TraceEventRow.trace_id == trace_id)
                .order_by(TraceEventRow.created_at, TraceEventRow.id)
            )
            return [
                TraceEvent(
                    id=row.id,
                    trace_id=row.trace_id,
                    event_type=row.event_type,
                    payload=row.payload,
                    created_at=row.created_at,
                )
                for row in rows
            ]
