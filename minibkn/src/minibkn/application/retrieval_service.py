"""Index building, hybrid retrieval, and three-level context assembly."""

import asyncio

from minibkn.adapters.search import HybridRetriever
from minibkn.api.errors import MiniBKNError, ResourceNotFoundError
from minibkn.application.answer_generator import EvidenceAnswerGenerator
from minibkn.domain.access_control import current_principal
from minibkn.domain.evidence import EvidenceItem, EvidenceKind
from minibkn.domain.models import (
    AskResult,
    ContextBundle,
    KnowledgeNetwork,
    ObjectInstance,
    SearchDocument,
    SearchHit,
    SearchIndexManifest,
    SearchLevel,
    SearchMode,
    Subgraph,
)
from minibkn.ports.repository import KnowledgeGraphRepository, KnowledgeNetworkRepository


class RetrievalService:
    def __init__(
        self,
        networks: KnowledgeNetworkRepository,
        graph: KnowledgeGraphRepository,
        retriever: HybridRetriever | None = None,
        answer_generator: EvidenceAnswerGenerator | None = None,
    ) -> None:
        self._networks = networks
        self._graph = graph
        self._retriever = retriever or HybridRetriever()
        self._answer_generator = answer_generator or EvidenceAnswerGenerator()
        self._document_cache: dict[str, tuple[str, list[SearchDocument]]] = {}

    async def build_index(self, network_id: str) -> dict[str, int | str]:
        network = await self._get_network(network_id)
        instances = await self._graph.list_objects(network_id)
        documents = self._schema_documents(network)
        documents.extend(self._instance_documents(instances))
        documents.extend(self._action_documents(network))
        vectors = await asyncio.to_thread(
            self._retriever.embedder.embed_many, [item.content for item in documents]
        )
        documents = [
            document.model_copy(update={"vector": vector})
            for document, vector in zip(documents, vectors, strict=True)
        ]
        await self._graph.replace_search_documents(network_id, documents)
        manifest = SearchIndexManifest(
            network_id=network_id,
            embedding_version=self._retriever.embedder.version,
            dimensions=self._retriever.embedder.dimensions,
            document_count=len(documents),
        )
        await self._graph.save_search_manifest(manifest)
        self._document_cache[network_id] = (self._manifest_key(manifest), documents)
        return {
            "total": len(documents),
            "schema": sum(item.level == SearchLevel.SCHEMA for item in documents),
            "instance": sum(item.level == SearchLevel.INSTANCE for item in documents),
            "action": sum(item.level == SearchLevel.ACTION for item in documents),
            "embedding_version": manifest.embedding_version,
            "embedding_dimensions": manifest.dimensions,
        }

    async def build_index_incremental(self, network_id: str) -> dict[str, int | str]:
        network = await self._get_network(network_id)
        instances = await self._graph.list_objects(network_id)
        desired = self._schema_documents(network)
        desired.extend(self._instance_documents(instances))
        desired.extend(self._action_documents(network))
        existing = await self._graph.list_search_documents(network_id)
        manifest = await self._graph.get_search_manifest(network_id)
        existing_map = {item.id: item for item in existing}
        desired_map = {item.id: item for item in desired}
        inserted_ids = sorted(set(desired_map) - set(existing_map))
        deleted_ids = sorted(set(existing_map) - set(desired_map))
        version_changed = (
            manifest is None or manifest.embedding_version != self._retriever.embedder.version
        )
        updated_ids = sorted(
            item_id
            for item_id in set(existing_map) & set(desired_map)
            if version_changed
            or self._document_changed(existing_map[item_id], desired_map[item_id])
        )
        changed_ids = inserted_ids + updated_ids
        if changed_ids:
            vectors = await asyncio.to_thread(
                self._retriever.embedder.embed_many,
                [desired_map[item_id].content for item_id in changed_ids],
            )
            upserts = [
                desired_map[item_id].model_copy(update={"vector": vector})
                for item_id, vector in zip(changed_ids, vectors, strict=True)
            ]
        else:
            upserts = []
        await self._graph.apply_search_document_changes(upserts, deleted_ids)
        new_manifest = SearchIndexManifest(
            network_id=network_id,
            embedding_version=self._retriever.embedder.version,
            dimensions=self._retriever.embedder.dimensions,
            document_count=len(desired),
        )
        await self._graph.save_search_manifest(new_manifest)
        upserts_by_id = {item.id: item for item in upserts}
        cached_documents = [
            upserts_by_id[item_id] if item_id in upserts_by_id else existing_map[item_id]
            for item_id in desired_map
            if item_id in upserts_by_id or item_id in existing_map
        ]
        self._document_cache[network_id] = (
            self._manifest_key(new_manifest),
            cached_documents,
        )
        return {
            "inserted": len(inserted_ids),
            "updated": len(updated_ids),
            "deleted": len(deleted_ids),
            "embedded": len(changed_ids),
            "total": len(desired),
            "embedding_version": new_manifest.embedding_version,
        }

    async def search(
        self,
        network_id: str,
        query: str,
        limit: int = 10,
        mode: SearchMode = SearchMode.HYBRID,
    ) -> list[SearchHit]:
        await self._get_network(network_id)
        manifest = await self._graph.get_search_manifest(network_id)
        if manifest is None:
            raise MiniBKNError(
                error_code="INDEX_NOT_BUILT",
                message=f"search index for network '{network_id}' has not been built",
                status_code=409,
            )
        if manifest.embedding_version != self._retriever.embedder.version:
            raise MiniBKNError(
                error_code="INDEX_VERSION_MISMATCH",
                message="search index embedding version changed; rebuild the index",
                status_code=409,
            )
        corpus_key = self._manifest_key(manifest)
        cached = self._document_cache.get(network_id)
        if cached is None or cached[0] != corpus_key:
            documents = await self._graph.list_search_documents(network_id)
            self._document_cache[network_id] = (corpus_key, documents)
        else:
            documents = cached[1]
        documents = self._authorized_documents(documents)
        if not documents:
            raise MiniBKNError(
                error_code="INDEX_NOT_BUILT",
                message=f"search index for network '{network_id}' has not been built",
                status_code=409,
            )
        # Embedding clients and the pure-Python rankers are synchronous.  Running
        # them on the event loop serialized concurrent HTTP requests, so isolate
        # the blocking work in the application's worker thread pool.
        hits = await asyncio.to_thread(
            self._retriever.search, query, documents, limit, mode, corpus_key
        )
        if manifest.embedding_version != self._retriever.embedder.version:
            raise MiniBKNError(
                error_code="INDEX_VERSION_MISMATCH",
                message="embedding provider failed over; rebuild the index before searching",
                status_code=409,
            )
        return hits

    @staticmethod
    def _manifest_key(manifest: SearchIndexManifest) -> str:
        updated_at = manifest.updated_at.replace(tzinfo=None).isoformat(timespec="microseconds")
        return (
            f"{manifest.network_id}:{manifest.embedding_version}:"
            f"{updated_at}:{manifest.document_count}"
        )

    async def ask(self, network_id: str, question: str) -> AskResult:
        hits = await self.search(network_id, question, 20)
        schema = [hit for hit in hits if hit.document.level == SearchLevel.SCHEMA][:5]
        instances = [hit for hit in hits if hit.document.level == SearchLevel.INSTANCE][:8]
        actions = [hit for hit in hits if hit.document.level == SearchLevel.ACTION][:5]
        subgraph = await self._context_subgraph(network_id, instances)
        evidence = self._evidence_items(network_id, schema, instances, subgraph, actions)
        answer = self._answer_generator.generate(evidence)
        citations = list(dict.fromkeys(item.citation for item in evidence))
        return AskResult(
            question=question,
            answer=answer,
            context=ContextBundle(
                schema_hits=schema,
                instances=instances,
                subgraph=subgraph,
                actions=actions,
            ),
            citations=citations,
            evidence=evidence,
        )

    async def _get_network(self, network_id: str) -> KnowledgeNetwork:
        network = await self._networks.get(network_id)
        if network is None:
            raise ResourceNotFoundError("knowledge network", network_id)
        return network

    async def _context_subgraph(self, network_id: str, hits: list[SearchHit]) -> Subgraph:
        principal = current_principal()
        all_objects = [
            item
            for item in await self._graph.list_objects(network_id)
            if principal.allows_resource(item.resource_id)
        ]
        all_relations = await self._graph.list_relations(network_id)
        selected = {(hit.document.entity_type, hit.document.entity_id) for hit in hits}
        for edge in all_relations:
            source = (edge.source_object_type_id, edge.source_instance_id)
            target = (edge.target_object_type_id, edge.target_instance_id)
            if source in selected or target in selected:
                selected.update((source, target))
        return Subgraph(
            nodes=[
                item for item in all_objects if (item.object_type_id, item.instance_id) in selected
            ],
            edges=[
                edge
                for edge in all_relations
                if (edge.source_object_type_id, edge.source_instance_id) in selected
                and (edge.target_object_type_id, edge.target_instance_id) in selected
            ],
        )

    @staticmethod
    def _authorized_documents(documents: list[SearchDocument]) -> list[SearchDocument]:
        principal = current_principal()
        result = []
        for document in documents:
            if not document.citation.startswith("resource://"):
                result.append(document)
                continue
            resource_id = document.citation.removeprefix("resource://").split("#", 1)[0]
            if principal.allows_resource(resource_id):
                result.append(document)
        return result

    def _schema_documents(self, network: KnowledgeNetwork) -> list[SearchDocument]:
        documents = []
        for item in network.object_types:
            properties = " ".join(
                f"{prop.name} {prop.display_name} {prop.description}" for prop in item.properties
            )
            documents.append(
                self._document(
                    f"schema:object:{item.id}",
                    network.id,
                    SearchLevel.SCHEMA,
                    "object_type",
                    item.id,
                    item.name,
                    f"{item.name} {item.description} {properties}",
                    f"bkn://{item.source_path}",
                )
            )
        for relation_type in network.relation_types:
            documents.append(
                self._document(
                    f"schema:relation:{relation_type.id}",
                    network.id,
                    SearchLevel.SCHEMA,
                    "relation_type",
                    relation_type.id,
                    relation_type.name,
                    f"{relation_type.name} {relation_type.description} "
                    f"{relation_type.endpoint.source_object_type} "
                    f"{relation_type.endpoint.target_object_type}",
                    f"bkn://{relation_type.source_path}",
                )
            )
        return documents

    def _instance_documents(self, instances: list[ObjectInstance]) -> list[SearchDocument]:
        return [
            self._document(
                f"instance:{item.object_type_id}:{item.instance_id}",
                item.network_id,
                SearchLevel.INSTANCE,
                item.object_type_id,
                item.instance_id,
                item.display_name,
                f"{item.object_type_id} {item.display_name} "
                + " ".join(f"{key} {value}" for key, value in item.properties.items()),
                f"resource://{item.resource_id}#row={item.row_number}",
            )
            for item in instances
        ]

    def _action_documents(self, network: KnowledgeNetwork) -> list[SearchDocument]:
        return [
            self._document(
                f"action:{item.id}",
                network.id,
                SearchLevel.ACTION,
                "action_type",
                item.id,
                item.name,
                f"{item.name} {item.description} {item.bound_object_type}",
                f"bkn://{item.source_path}",
            )
            for item in network.action_types
            if item.enabled
        ]

    def _document(
        self,
        document_id: str,
        network_id: str,
        level: SearchLevel,
        entity_type: str,
        entity_id: str,
        title: str,
        content: str,
        citation: str,
    ) -> SearchDocument:
        return SearchDocument(
            id=document_id,
            network_id=network_id,
            level=level,
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            content=content,
            citation=citation,
        )

    @staticmethod
    def _document_changed(current: SearchDocument, desired: SearchDocument) -> bool:
        return any(
            (
                current.level != desired.level,
                current.entity_type != desired.entity_type,
                current.entity_id != desired.entity_id,
                current.title != desired.title,
                current.content != desired.content,
                current.citation != desired.citation,
            )
        )

    @staticmethod
    def _evidence_items(
        network_id: str,
        schema: list[SearchHit],
        instances: list[SearchHit],
        subgraph: Subgraph,
        actions: list[SearchHit],
    ) -> list[EvidenceItem]:
        result = [
            EvidenceItem(
                id=hit.document.id,
                network_id=network_id,
                kind=(
                    EvidenceKind.SCHEMA
                    if hit.document.level == SearchLevel.SCHEMA
                    else EvidenceKind.ACTION
                ),
                title=hit.document.title,
                content=hit.document.content,
                citation=hit.document.citation,
                entity_type=hit.document.entity_type,
                entity_id=hit.document.entity_id,
                score=hit.score,
            )
            for hit in schema + actions
        ]
        scores = {
            (hit.document.entity_type, hit.document.entity_id): hit.score for hit in instances
        }
        result.extend(
            EvidenceItem(
                id=f"instance:{item.object_type_id}:{item.instance_id}",
                network_id=network_id,
                kind=EvidenceKind.INSTANCE,
                title=item.display_name,
                content=" ".join(f"{key} {value}" for key, value in item.properties.items()),
                citation=f"resource://{item.resource_id}#row={item.row_number}",
                entity_type=item.object_type_id,
                entity_id=item.instance_id,
                score=scores.get((item.object_type_id, item.instance_id)),
                attributes={"properties": item.properties},
            )
            for item in subgraph.nodes
        )
        result.extend(
            EvidenceItem(
                id=(
                    f"relation:{edge.relation_type_id}:{edge.source_instance_id}:"
                    f"{edge.target_instance_id}"
                ),
                network_id=network_id,
                kind=EvidenceKind.RELATION,
                title=edge.relation_type_id,
                content=(
                    f"{edge.source_object_type_id}/{edge.source_instance_id} "
                    f"-[{edge.relation_type_id}]-> "
                    f"{edge.target_object_type_id}/{edge.target_instance_id}"
                ),
                citation=f"bkn://relation/{edge.relation_type_id}",
                entity_type="relation_type",
                entity_id=edge.relation_type_id,
            )
            for edge in subgraph.edges
        )
        return list({item.id: item for item in result}.values())
