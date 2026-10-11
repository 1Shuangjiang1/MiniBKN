# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Query planning port."""

from typing import Protocol

from minibkn.domain.models import KnowledgeNetwork
from minibkn.domain.query import QueryAnalysis, QueryPlan


class QueryPlanner(Protocol):
    async def plan(self, question: str, network: KnowledgeNetwork) -> QueryPlan: ...


class QueryAnalyzer(QueryPlanner, Protocol):
    async def analyze(
        self,
        question: str,
        network: KnowledgeNetwork,
        clarification_answers: dict[str, str] | None = None,
        value_hints: dict[str, list[str]] | None = None,
    ) -> QueryAnalysis: ...
