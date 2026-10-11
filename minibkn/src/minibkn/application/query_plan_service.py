# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Safe QueryPlan creation, validation, and deterministic execution."""

import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import httpx

from minibkn.api.errors import MiniBKNError, ResourceNotFoundError
from minibkn.application.answer_generator import EvidenceAnswerGenerator
from minibkn.domain.access_control import current_principal
from minibkn.domain.evidence import EvidenceItem, EvidenceKind
from minibkn.domain.models import AskResult, KnowledgeNetwork, ObjectInstance, RelationInstance
from minibkn.domain.query import (
    AggregateFunction,
    AggregateSpec,
    FilterCondition,
    FilterOperator,
    QueryAmbiguity,
    QueryAnalysis,
    QueryAnalysisStatus,
    QueryExecutionResult,
    QueryIntent,
    QueryPlan,
    TraversalDirection,
)
from minibkn.ports.planner import QueryAnalyzer
from minibkn.ports.repository import KnowledgeGraphRepository, KnowledgeNetworkRepository

if TYPE_CHECKING:
    from minibkn.application.retrieval_service import RetrievalService


class RuleBasedQueryPlanner:
    async def plan(self, question: str, network: KnowledgeNetwork) -> QueryPlan:
        analysis = await self.analyze(question, network)
        if analysis.plan is None:
            raise ValueError("query requires clarification before planning")
        return analysis.plan

    async def analyze(
        self,
        question: str,
        network: KnowledgeNetwork,
        clarification_answers: dict[str, str] | None = None,
        value_hints: dict[str, list[str]] | None = None,
    ) -> QueryAnalysis:
        answers = clarification_answers or {}
        normalized = " ".join(question.strip().split())
        expansions = self._synonyms(normalized, network)
        ambiguities = self._ambiguities(normalized, answers, network)
        sub_questions = [
            item.strip(" ，,。")
            for item in re.split(r"(?:以及|同时|另外|；|;)", normalized)
            if item.strip(" ，,。")
        ]
        if not sub_questions:
            sub_questions = [normalized]
        rewritten = self._rewrite(normalized, expansions)
        if answers:
            additions = "；".join(f"{key}={value}" for key, value in sorted(answers.items()))
            rewritten = f"{rewritten}（补充条件：{additions}）"
        keywords = self._keywords(normalized, expansions)
        if ambiguities:
            return QueryAnalysis(
                original_question=question,
                rewritten_question=rewritten,
                keywords=keywords,
                synonym_expansions=expansions,
                sub_questions=sub_questions,
                ambiguities=ambiguities,
                clarification_answers=answers,
                status=QueryAnalysisStatus.NEEDS_CLARIFICATION,
                planner="rule",
            )
        return QueryAnalysis(
            original_question=question,
            rewritten_question=rewritten,
            keywords=keywords,
            synonym_expansions=expansions,
            sub_questions=sub_questions,
            clarification_answers=answers,
            status=QueryAnalysisStatus.READY,
            planner="rule",
            plan=self._make_plan(rewritten, network),
        )

    @staticmethod
    def _make_plan(question: str, network: KnowledgeNetwork) -> QueryPlan:
        normalized = question.lower()
        matched = []
        for object_type in network.object_types:
            terms = [object_type.id.lower(), object_type.name.lower()]
            terms.extend(prop.name.lower() for prop in object_type.properties)
            terms.extend(prop.display_name.lower() for prop in object_type.properties)
            if any(term and term in normalized for term in terms):
                matched.append(object_type.id)
        aggregate_terms = ("多少", "数量", "总计", "总额", "平均", "count", "sum", "average")
        intent = (
            QueryIntent.AGGREGATE
            if any(x in normalized for x in aggregate_terms)
            else QueryIntent.SEARCH
        )
        aggregates = (
            [AggregateSpec(function=AggregateFunction.COUNT, alias="count")]
            if intent == QueryIntent.AGGREGATE
            else []
        )
        return QueryPlan(intent=intent, object_types=matched, aggregates=aggregates)

    @staticmethod
    def _synonyms(question: str, network: KnowledgeNetwork) -> dict[str, list[str]]:
        aliases = {
            "customer": ["客户", "顾客", "客户方"],
            "order": ["订单", "交易单", "销售单"],
            "supplier": ["供应商", "供货商"],
            "material": ["物料", "材料", "商品"],
            "employee": ["员工", "雇员"],
            "invoice": ["发票", "票据"],
            "payment": ["付款", "支付", "回款"],
        }
        result: dict[str, list[str]] = {}
        for item in network.object_types:
            candidates = list(aliases.get(item.id.lower(), []))
            candidates.extend([item.id, item.name])
            if any(term and term.lower() in question.lower() for term in candidates):
                result[item.id] = list(dict.fromkeys(term for term in candidates if term))
        return result

    @staticmethod
    def _rewrite(question: str, expansions: dict[str, list[str]]) -> str:
        if not expansions:
            return question
        search_terms = [term for values in expansions.values() for term in values]
        return f"{question}（语义扩展：{'、'.join(dict.fromkeys(search_terms))}）"

    @staticmethod
    def _keywords(question: str, expansions: dict[str, list[str]]) -> list[str]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.-]*|\d+(?:\.\d+)?|[\u4e00-\u9fff]{2,}", question)
        stop_words = {"哪些", "什么", "怎么", "如何", "一下", "是否", "这个", "那个"}
        result = [token.lower() for token in tokens if token not in stop_words]
        result.extend(expansions)
        result.extend(term.lower() for values in expansions.values() for term in values)
        return list(dict.fromkeys(result))[:30]

    @staticmethod
    def _ambiguities(
        question: str,
        answers: dict[str, str],
        network: KnowledgeNetwork,
    ) -> list[QueryAmbiguity]:
        result = []
        if (
            any(term in question for term in ("最近", "近期", "近来"))
            and "time_range" not in answers
            and not re.search(r"近?\s*\d+\s*(?:天|周|个月|月|年)", question)
        ):
            result.append(
                QueryAmbiguity(
                    id="time_range",
                    reason="相对时间没有明确范围",
                    question="“最近”具体指多长时间？",
                    options=["近7天", "近30天", "本季度"],
                )
            )
        if (
            any(term in question for term in ("大客户", "重要客户", "高价值客户"))
            and "size_metric" not in answers
            and not any(term in question for term in ("订单金额", "累计收入", "客户等级", "成交额"))
        ):
            result.append(
                QueryAmbiguity(
                    id="size_metric",
                    reason="客户规模缺少判断口径",
                    question="“大客户”按什么指标判断？",
                    options=["累计订单金额", "最近一年收入", "客户等级"],
                )
            )
        schema_terms = [item.id.lower() for item in network.object_types]
        schema_terms.extend(item.name.lower() for item in network.object_types)
        has_entity = any(term and term in question.lower() for term in schema_terms)
        has_known_alias = bool(RuleBasedQueryPlanner._synonyms(question, network))
        if (
            any(term in question for term in ("它", "那个", "这些", "那几个"))
            and not has_entity
            and not has_known_alias
            and "target_entity" not in answers
        ):
            result.append(
                QueryAmbiguity(
                    id="target_entity",
                    reason="代词没有明确指向业务对象",
                    question="你指的是哪一类或哪一个业务对象？",
                    options=[item.name for item in network.object_types[:5]],
                )
            )
        return result


class QueryPlanService:
    def __init__(
        self,
        networks: KnowledgeNetworkRepository,
        graph: KnowledgeGraphRepository,
        planner: QueryAnalyzer | None = None,
        retrieval: "RetrievalService | None" = None,
    ) -> None:
        self._networks = networks
        self._graph = graph
        self._fallback_planner = RuleBasedQueryPlanner()
        self._planner = planner or self._fallback_planner
        self._retrieval = retrieval
        self._answer_generator = EvidenceAnswerGenerator()

    async def preview(self, network_id: str, question: str) -> QueryPlan:
        analysis = await self.analyze(network_id, question)
        if analysis.plan is None:
            raise MiniBKNError(
                error_code="QUERY_CLARIFICATION_REQUIRED",
                message="the question must be clarified before a query plan can be generated",
                status_code=409,
                details=[item.model_dump(mode="json") for item in analysis.ambiguities],
            )
        return analysis.plan

    async def analyze(
        self,
        network_id: str,
        question: str,
        clarification_answers: dict[str, str] | None = None,
    ) -> QueryAnalysis:
        network = await self._network(network_id)
        value_hints = await self._value_hints(network_id)
        try:
            analysis = await self._planner.analyze(
                question, network, clarification_answers, value_hints
            )
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            if self._planner is self._fallback_planner:
                raise
            logging.getLogger(__name__).warning(
                "query analyzer failed; using rule fallback: %s", type(exc).__name__
            )
            analysis = await self._fallback_planner.analyze(
                question, network, clarification_answers, value_hints
            )
        if analysis.plan is not None:
            self._validate(analysis.plan, network)
            invalid_values = self._invalid_filter_values(analysis.plan, value_hints)
            if invalid_values:
                analysis = analysis.model_copy(
                    update={
                        "status": QueryAnalysisStatus.NEEDS_CLARIFICATION,
                        "plan": None,
                        "ambiguities": invalid_values,
                    }
                )
        return analysis

    async def _value_hints(self, network_id: str) -> dict[str, list[str]]:
        enum_terms = {
            "status",
            "state",
            "type",
            "category",
            "segment",
            "level",
            "priority",
            "stage",
            "currency",
            "kind",
        }
        principal = current_principal()
        objects = [
            item
            for item in await self._graph.list_objects(network_id)
            if principal.allows_resource(item.resource_id)
        ]
        values: dict[str, set[str]] = defaultdict(set)
        for item in objects:
            for field, value in item.properties.items():
                tokens = set(field.lower().split("_"))
                if value is None or not tokens & enum_terms:
                    continue
                text = str(value)
                if len(text) <= 64 and len(values[f"{item.object_type_id}.{field}"]) < 20:
                    values[f"{item.object_type_id}.{field}"].add(text)
        return {key: sorted(items) for key, items in values.items() if items}

    @staticmethod
    def _invalid_filter_values(
        plan: QueryPlan, value_hints: dict[str, list[str]]
    ) -> list[QueryAmbiguity]:
        result = []
        for condition in plan.filters:
            if condition.operator not in {FilterOperator.EQ, FilterOperator.IN}:
                continue
            matching = [
                values
                for field, values in value_hints.items()
                if field == condition.field or field.endswith(f".{condition.field}")
            ]
            if len(matching) != 1:
                continue
            allowed = matching[0]
            submitted = condition.value if isinstance(condition.value, list) else [condition.value]
            if all(str(value) in allowed for value in submitted):
                continue
            result.append(
                QueryAmbiguity(
                    id=f"filter_value:{condition.field}",
                    reason="计划中的筛选值不是数据中存在的低基数字段值",
                    question=f"字段 {condition.field} 应使用哪个实际值？",
                    options=allowed,
                )
            )
        return result

    async def execute(self, network_id: str, plan: QueryPlan) -> QueryExecutionResult:
        network = await self._network(network_id)
        self._validate(plan, network)
        if plan.intent == QueryIntent.ACTION:
            raise MiniBKNError(
                error_code="ACTION_REQUIRES_ACTION_ENDPOINT",
                message="actions must be executed through the risk-controlled action endpoint",
                status_code=422,
            )
        principal = current_principal()
        objects = [
            item
            for item in await self._graph.list_objects(network_id)
            if principal.allows_resource(item.resource_id)
        ]
        if len(objects) > 10000:
            raise MiniBKNError(
                error_code="QUERY_PLAN_TOO_EXPENSIVE",
                message="query plan would scan more than 10000 objects",
                status_code=422,
            )
        relations = await self._graph.list_relations(network_id)
        visible = {(item.object_type_id, item.instance_id) for item in objects}
        relations = [
            item
            for item in relations
            if (item.source_object_type_id, item.source_instance_id) in visible
            and (item.target_object_type_id, item.target_instance_id) in visible
        ]
        selected = self._select_objects(plan, objects)
        selected, selected_edges = self._traverse(plan, selected, objects, relations)
        rows = [self._row(item) for item in selected]
        if plan.aggregates:
            rows = self._aggregate(plan, rows)
        else:
            rows = self._project(plan, rows)
        rows = rows[: plan.limit]
        evidence = self._evidence(network_id, selected[: plan.limit], selected_edges, rows, plan)
        return QueryExecutionResult(
            plan=plan,
            rows=rows,
            evidence=evidence[: plan.evidence_budget.max_items],
            citations=list(dict.fromkeys(item.citation for item in evidence)),
            scanned_objects=len(objects),
        )

    async def ask(self, network_id: str, question: str) -> tuple[str, QueryExecutionResult]:
        plan = await self.preview(network_id, question)
        result = await self.execute(network_id, plan)
        return self._answer_generator.generate(result.evidence), result

    async def ask_intelligently(
        self,
        network_id: str,
        question: str,
        clarification_answers: dict[str, str] | None = None,
    ) -> tuple[QueryAnalysis, str, QueryExecutionResult | None, AskResult | None, bool]:
        """Analyze once, stop safely for clarification, then execute the approved read path.

        Structured plans run through the deterministic executor. Relevance-style search plans use
        the rewritten question and expansion terms in the normal hybrid retriever. Action plans are
        never executed here; callers receive the validated request and must use the risk-controlled
        action endpoint explicitly.
        """

        analysis = await self.analyze(network_id, question, clarification_answers)
        if analysis.plan is None:
            return analysis, "", None, None, False
        if analysis.plan.intent == QueryIntent.ACTION:
            return (
                analysis,
                "动作请求已经识别，但尚未执行。请先通过风险模拟和审批接口确认。",
                None,
                None,
                True,
            )
        if analysis.plan.intent == QueryIntent.SEARCH and self._retrieval is not None:
            query = self._retrieval_query(analysis)
            retrieval = await self._retrieval.ask(network_id, query)
            return analysis, retrieval.answer, None, retrieval, False
        execution = await self.execute(network_id, analysis.plan)
        answer = self._answer_generator.generate(execution.evidence)
        return analysis, answer, execution, None, False

    @staticmethod
    def _retrieval_query(analysis: QueryAnalysis) -> str:
        terms = [analysis.rewritten_question]
        terms.extend(analysis.keywords)
        terms.extend(analysis.sub_questions)
        for key, values in analysis.synonym_expansions.items():
            terms.append(key)
            terms.extend(values)
        return " ".join(dict.fromkeys(term.strip() for term in terms if term.strip()))

    async def _network(self, network_id: str) -> KnowledgeNetwork:
        network = await self._networks.get(network_id)
        if network is None:
            raise ResourceNotFoundError("knowledge network", network_id)
        return network

    @staticmethod
    def _validate(plan: QueryPlan, network: KnowledgeNetwork) -> None:
        object_map = {item.id: item for item in network.object_types}
        relation_ids = {item.id for item in network.relation_types}
        action_map = {item.id: item for item in network.action_types if item.enabled}
        errors = []
        for object_id in plan.object_types:
            if object_id not in object_map:
                errors.append(f"unknown object type: {object_id}")
        valid_fields = {
            f"{item.id}.{prop.name}" for item in network.object_types for prop in item.properties
        }
        valid_fields.update(prop.name for item in network.object_types for prop in item.properties)
        referenced_fields = list(plan.select) + list(plan.group_by)
        referenced_fields += [item.field for item in plan.filters]
        referenced_fields += [item.value_field for item in plan.filters if item.value_field]
        referenced_fields += [item.field for item in plan.aggregates if item.field]
        referenced_fields += [item.field for item in plan.order_by]
        for field in referenced_fields:
            if field not in valid_fields and field not in {item.alias for item in plan.aggregates}:
                errors.append(f"unknown field: {field}")
        for traversal in plan.traversals:
            if traversal.relation not in relation_ids:
                errors.append(f"unknown relation: {traversal.relation}")
        if plan.action_request:
            action = action_map.get(plan.action_request.action_type_id)
            if action is None:
                errors.append(f"unknown or disabled action: {plan.action_request.action_type_id}")
            if not plan.action_request.instance_id:
                errors.append("action request requires one explicit instance_id")
            if plan.action_request.object_type_id not in object_map:
                errors.append(f"unknown action object type: {plan.action_request.object_type_id}")
            elif action and plan.action_request.object_type_id != action.bound_object_type:
                errors.append("action object type does not match the action binding")
        if errors:
            raise MiniBKNError(
                error_code="INVALID_QUERY_PLAN",
                message="; ".join(errors),
                status_code=422,
            )

    @classmethod
    def _select_objects(
        cls, plan: QueryPlan, objects: list[ObjectInstance]
    ) -> list[ObjectInstance]:
        selected = [
            item
            for item in objects
            if not plan.object_types or item.object_type_id in plan.object_types
        ]
        return [item for item in selected if all(cls._matches(item, f) for f in plan.filters)]

    @classmethod
    def _matches(cls, item: ObjectInstance, condition: FilterCondition) -> bool:
        owner, field = cls._split_field(condition.field)
        if owner and owner != item.object_type_id:
            return False
        left = item.properties.get(field)
        if condition.operator == FilterOperator.EXIST:
            return left is not None
        if condition.operator == FilterOperator.NOT_EXIST:
            return left is None
        if condition.value_field:
            right_owner, right_field = cls._split_field(condition.value_field)
            if right_owner and right_owner != item.object_type_id:
                return False
            right = item.properties.get(right_field)
        else:
            right = condition.value
        return cls._compare(left, condition.operator, right)

    @staticmethod
    def _compare(left: Any, operator: FilterOperator, right: Any) -> bool:
        if operator == FilterOperator.EQ:
            return bool(left == right)
        if operator == FilterOperator.NEQ:
            return bool(left != right)
        if operator == FilterOperator.LIKE:
            return str(right).lower() in str(left).lower()
        if operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
            included = left in right if isinstance(right, list) else False
            return included if operator == FilterOperator.IN else not included
        try:
            left_number, right_number = float(left), float(right)
        except (TypeError, ValueError):
            left_text, right_text = str(left), str(right)
            comparisons = {
                FilterOperator.GT: left_text > right_text,
                FilterOperator.GTE: left_text >= right_text,
                FilterOperator.LT: left_text < right_text,
                FilterOperator.LTE: left_text <= right_text,
            }
            return comparisons.get(operator, False)
        comparisons = {
            FilterOperator.GT: left_number > right_number,
            FilterOperator.GTE: left_number >= right_number,
            FilterOperator.LT: left_number < right_number,
            FilterOperator.LTE: left_number <= right_number,
        }
        return comparisons.get(operator, False)

    @staticmethod
    def _traverse(
        plan: QueryPlan,
        selected: list[ObjectInstance],
        objects: list[ObjectInstance],
        relations: list[RelationInstance],
    ) -> tuple[list[ObjectInstance], list[RelationInstance]]:
        object_map = {(item.object_type_id, item.instance_id): item for item in objects}
        selected_map = {(item.object_type_id, item.instance_id): item for item in selected}
        selected_edges: list[RelationInstance] = []
        for step in plan.traversals:
            frontier = set(selected_map)
            for _ in range(step.max_hops):
                next_frontier: set[tuple[str, str]] = set()
                for edge in relations:
                    if edge.relation_type_id != step.relation:
                        continue
                    source = (edge.source_object_type_id, edge.source_instance_id)
                    target = (edge.target_object_type_id, edge.target_instance_id)
                    matched = (
                        step.direction in {TraversalDirection.OUT, TraversalDirection.BOTH}
                        and source in frontier
                    ) or (
                        step.direction in {TraversalDirection.IN, TraversalDirection.BOTH}
                        and target in frontier
                    )
                    if matched:
                        selected_edges.append(edge)
                        next_frontier.update((source, target))
                selected_map.update(
                    {key: object_map[key] for key in next_frontier if key in object_map}
                )
                frontier = next_frontier
        return list(selected_map.values()), list(dict.fromkeys(selected_edges))

    @staticmethod
    def _row(item: ObjectInstance) -> dict[str, Any]:
        row = {
            "_object_type": item.object_type_id,
            "_instance_id": item.instance_id,
            "_display_name": item.display_name,
        }
        row.update(item.properties)
        row.update(
            {f"{item.object_type_id}.{key}": value for key, value in item.properties.items()}
        )
        return row

    @staticmethod
    def _project(plan: QueryPlan, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not plan.select:
            return rows
        return [{field: row.get(field) for field in plan.select} for row in rows]

    @staticmethod
    def _aggregate(plan: QueryPlan, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        required_fields = set(plan.group_by)
        required_fields.update(item.field for item in plan.aggregates if item.field)
        eligible_rows = [row for row in rows if all(field in row for field in required_fields)]
        for row in eligible_rows:
            groups[tuple(row.get(field) for field in plan.group_by)].append(row)
        if not groups:
            groups[()] = []
        result = []
        for key, entries in groups.items():
            output = dict(zip(plan.group_by, key, strict=True))
            for aggregate in plan.aggregates:
                values = [entry.get(aggregate.field) for entry in entries]
                numeric = [float(value) for value in values if value is not None]
                if aggregate.function == AggregateFunction.COUNT:
                    value: Any = len(entries)
                elif aggregate.function == AggregateFunction.SUM:
                    value = sum(numeric)
                elif aggregate.function == AggregateFunction.AVG:
                    value = sum(numeric) / len(numeric) if numeric else None
                elif aggregate.function == AggregateFunction.MIN:
                    value = min(numeric) if numeric else None
                else:
                    value = max(numeric) if numeric else None
                output[aggregate.alias] = value
            result.append(output)
        for sort in reversed(plan.order_by):
            populated = [row for row in result if row.get(sort.field) is not None]
            missing = [row for row in result if row.get(sort.field) is None]
            populated.sort(
                key=lambda row: QueryPlanService._sortable(row.get(sort.field)),
                reverse=sort.direction == "desc",
            )
            result = populated + missing
        return result

    @staticmethod
    def _sortable(value: Any) -> tuple[int, float, str]:
        try:
            return (0, float(value), "")
        except (TypeError, ValueError):
            return (1, 0.0, str(value))

    @staticmethod
    def _evidence(
        network_id: str,
        objects: list[ObjectInstance],
        relations: list[RelationInstance],
        rows: list[dict[str, Any]],
        plan: QueryPlan,
    ) -> list[EvidenceItem]:
        result = (
            [
                EvidenceItem(
                    id=f"computed:{index}",
                    network_id=network_id,
                    kind=EvidenceKind.COMPUTED,
                    title="QueryPlan computed result",
                    content=(
                        "结构化查询计划已根据筛选条件完成计算，结果为："
                        + "，".join(f"{key}={value}" for key, value in row.items())
                    ),
                    citation=f"computed://query-plan/{index}",
                    attributes={"row": row},
                )
                for index, row in enumerate(rows)
            ]
            if plan.aggregates
            else []
        )
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
                attributes={"properties": item.properties},
            )
            for item in objects
        )
        result.extend(
            EvidenceItem(
                id=f"relation:{edge.relation_type_id}:{edge.source_instance_id}:{edge.target_instance_id}",
                network_id=network_id,
                kind=EvidenceKind.RELATION,
                title=edge.relation_type_id,
                content=(
                    f"{edge.source_instance_id} -[{edge.relation_type_id}]-> "
                    f"{edge.target_instance_id}"
                ),
                citation=f"bkn://relation/{edge.relation_type_id}",
            )
            for edge in relations
        )
        return result

    @staticmethod
    def _split_field(field: str) -> tuple[str, str]:
        if "." not in field:
            return "", field
        return tuple(field.split(".", 1))  # type: ignore[return-value]
