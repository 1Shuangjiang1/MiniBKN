# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Transactional orchestration for incremental graph and index builds."""

from datetime import UTC, datetime
from uuid import uuid4

from minibkn.api.errors import ResourceNotFoundError
from minibkn.application.graph_service import KnowledgeGraphService
from minibkn.application.retrieval_service import RetrievalService
from minibkn.domain.build import BuildJob, BuildJobStatus
from minibkn.ports.repository import KnowledgeGraphRepository, KnowledgeNetworkRepository


class IncrementalBuildService:
    def __init__(
        self,
        networks: KnowledgeNetworkRepository,
        repository: KnowledgeGraphRepository,
        graph: KnowledgeGraphService,
        retrieval: RetrievalService,
    ) -> None:
        self._networks = networks
        self._repository = repository
        self._graph = graph
        self._retrieval = retrieval

    async def run(self, network_id: str) -> BuildJob:
        network = await self._networks.get(network_id)
        if network is None:
            raise ResourceNotFoundError("knowledge network", network_id)
        now = datetime.now(UTC)
        job = BuildJob(
            id=f"build-{uuid4().hex}",
            network_id=network_id,
            target_version=network.version,
            created_at=now,
            updated_at=now,
        )
        await self._repository.save_build_job(job)
        old_objects = await self._repository.list_objects(network_id)
        old_relations = await self._repository.list_relations(network_id)
        old_documents = await self._repository.list_search_documents(network_id)
        old_manifest = await self._repository.get_search_manifest(network_id)
        try:
            job = await self._status(job, BuildJobStatus.MATERIALIZING)
            (
                changes,
                relation_inserted,
                relation_deleted,
            ) = await self._graph.materialize_incremental(network_id)
            job = job.model_copy(
                update={
                    "change_set": changes,
                    "relation_inserted": relation_inserted,
                    "relation_deleted": relation_deleted,
                    "status": BuildJobStatus.INDEXING,
                    "updated_at": datetime.now(UTC),
                }
            )
            await self._repository.save_build_job(job)
            index = await self._retrieval.build_index_incremental(network_id)
            job = job.model_copy(
                update={
                    "index_inserted": int(index["inserted"]),
                    "index_updated": int(index["updated"]),
                    "index_deleted": int(index["deleted"]),
                    "embedded_documents": int(index["embedded"]),
                    "status": BuildJobStatus.VALIDATING,
                    "updated_at": datetime.now(UTC),
                }
            )
            await self._repository.save_build_job(job)
            final_objects = await self._repository.list_objects(network_id)
            final_manifest = await self._repository.get_search_manifest(network_id)
            if final_manifest is None or final_manifest.document_count < len(final_objects):
                raise RuntimeError("incremental build validation failed")
            job = await self._status(job, BuildJobStatus.PUBLISHED)
            return job
        except Exception as exc:
            await self._repository.replace_graph(network_id, old_objects, old_relations)
            await self._repository.replace_search_documents(network_id, old_documents)
            if old_manifest is None:
                await self._repository.delete_search_manifest(network_id)
            else:
                await self._repository.save_search_manifest(old_manifest)
            failed = job.model_copy(
                update={
                    "status": BuildJobStatus.FAILED,
                    "error": str(exc),
                    "updated_at": datetime.now(UTC),
                }
            )
            await self._repository.save_build_job(failed)
            return failed

    async def get(self, build_id: str) -> BuildJob:
        job = await self._repository.get_build_job(build_id)
        if job is None:
            raise ResourceNotFoundError("build job", build_id)
        return job

    async def _status(self, job: BuildJob, status: BuildJobStatus) -> BuildJob:
        updated = job.model_copy(update={"status": status, "updated_at": datetime.now(UTC)})
        await self._repository.save_build_job(updated)
        return updated
