"""Route questions across structured and future document knowledge sources."""

import re

from minibkn.api.errors import MiniBKNError
from minibkn.application.answer_generator import EvidenceAnswerGenerator
from minibkn.application.retrieval_service import RetrievalService
from minibkn.domain.access_control import current_principal
from minibkn.domain.document_knowledge import (
    DocumentIngestResult,
    DocumentJobStatus,
    DocumentKnowledgeStatus,
    KnowledgeRoute,
    RoutedAskResult,
)
from minibkn.domain.evidence import EvidenceItem
from minibkn.ports.document_knowledge import DocumentKnowledgePort


class KnowledgeRouterService:
    def __init__(
        self,
        structured: RetrievalService,
        documents: DocumentKnowledgePort,
        degrade_when_disabled: bool = True,
    ) -> None:
        self._structured = structured
        self._documents = documents
        self._degrade = degrade_when_disabled
        self._answers = EvidenceAnswerGenerator()

    async def status(self) -> DocumentKnowledgeStatus:
        status = await self._documents.status()
        principal = current_principal()
        if principal.is_admin or "*" in principal.document_collections:
            return status
        details = {
            key: value
            for key, value in status.details.items()
            if principal.allows_collection(key.rsplit("/", 1)[-1])
        }
        return status.model_copy(update={"details": details})

    async def ingest_text(
        self, network_id: str, collection: str, title: str, text: str
    ) -> DocumentIngestResult:
        principal = current_principal()
        if not principal.allows_collection(collection):
            raise MiniBKNError(
                "FORBIDDEN", f"document collection '{collection}' is not permitted", 403
            )
        return await self._documents.ingest_text(network_id, collection, title, text)

    async def job_status(
        self, network_id: str, collection: str, track_id: str
    ) -> DocumentJobStatus:
        principal = current_principal()
        if not principal.allows_collection(collection):
            raise MiniBKNError(
                "FORBIDDEN", f"document collection '{collection}' is not permitted", 403
            )
        return await self._documents.job_status(network_id, collection, track_id)

    async def ask(
        self, network_id: str, question: str, requested: KnowledgeRoute
    ) -> RoutedAskResult:
        route = self._select(question, requested)
        if route == KnowledgeRoute.STRUCTURED:
            structured = await self._structured.ask(network_id, question)
            return RoutedAskResult(
                question=question,
                answer=structured.answer,
                requested_route=requested,
                executed_routes=[KnowledgeRoute.STRUCTURED],
                citations=structured.citations,
                evidence=structured.evidence,
            )
        if route == KnowledgeRoute.DOCUMENT:
            try:
                evidence = await self._documents.query(
                    network_id,
                    question,
                    12,
                    set(current_principal().document_collections),
                )
            except MiniBKNError:
                if requested == KnowledgeRoute.DOCUMENT or not self._degrade:
                    raise
                return await self._degraded_structured(network_id, question, requested)
            return self._result(question, requested, [KnowledgeRoute.DOCUMENT], evidence)

        structured = await self._structured.ask(network_id, question)
        warnings: list[str] = []
        executed = [KnowledgeRoute.STRUCTURED]
        evidence = list(structured.evidence)
        try:
            evidence.extend(
                await self._documents.query(
                    network_id,
                    question,
                    12,
                    set(current_principal().document_collections),
                )
            )
            executed.append(KnowledgeRoute.DOCUMENT)
        except MiniBKNError:
            if not self._degrade:
                raise
            warnings.append("Document knowledge is disabled; returned structured evidence only")
        result = self._result(question, requested, executed, _deduplicate(evidence))
        return result.model_copy(update={"warnings": warnings})

    @staticmethod
    def _select(question: str, requested: KnowledgeRoute) -> KnowledgeRoute:
        if requested != KnowledgeRoute.AUTO:
            return requested
        if re.search(r"文档|制度|合同|手册|条款|政策|document|policy|manual", question, re.I):
            return KnowledgeRoute.DOCUMENT
        return KnowledgeRoute.STRUCTURED

    async def _degraded_structured(
        self, network_id: str, question: str, requested: KnowledgeRoute
    ) -> RoutedAskResult:
        result = await self._structured.ask(network_id, question)
        return RoutedAskResult(
            question=question,
            answer=result.answer,
            requested_route=requested,
            executed_routes=[KnowledgeRoute.STRUCTURED],
            citations=result.citations,
            evidence=result.evidence,
            warnings=["Document knowledge is disabled; route fell back to structured evidence"],
        )

    def _result(
        self,
        question: str,
        requested: KnowledgeRoute,
        routes: list[KnowledgeRoute],
        evidence: list[EvidenceItem],
    ) -> RoutedAskResult:
        return RoutedAskResult(
            question=question,
            answer=self._answers.generate(evidence),
            requested_route=requested,
            executed_routes=routes,
            citations=list(dict.fromkeys(item.citation for item in evidence)),
            evidence=evidence,
        )


def _deduplicate(items: list[EvidenceItem]) -> list[EvidenceItem]:
    result: list[EvidenceItem] = []
    seen: set[str] = set()
    for item in items:
        if item.id not in seen:
            seen.add(item.id)
            result.append(item)
    return result
