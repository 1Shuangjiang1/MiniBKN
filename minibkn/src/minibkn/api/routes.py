"""HTTP routes for schema, graph, retrieval, and question answering."""

from typing import cast

from fastapi import APIRouter, Request, status

from minibkn.api.schemas import (
    AnalyzeQueryRequest,
    AskRequest,
    ConfirmActionRequest,
    CreateModelingSessionRequest,
    ExecuteActionRequest,
    ExecuteQueryPlanRequest,
    GenerateNetworkRequest,
    ImportNetworkRequest,
    IndexResponse,
    IngestDocumentTextRequest,
    IntelligentAskResponse,
    MaterializeResponse,
    NetworkListResponse,
    NetworkSummary,
    PlannedAskResponse,
    PublishModelingSessionRequest,
    RegisterSourceRequest,
    ReviewProposalRequest,
    RoutedAskRequest,
    SearchRequest,
    SimulateRiskRequest,
    SubgraphRequest,
)
from minibkn.application.access_control_service import AccessControlService
from minibkn.application.action_service import ActionService
from minibkn.application.build_service import IncrementalBuildService
from minibkn.application.evaluation_service import EvaluationReportService
from minibkn.application.graph_service import KnowledgeGraphService
from minibkn.application.knowledge_router_service import KnowledgeRouterService
from minibkn.application.modeling_service import ModelingService
from minibkn.application.network_service import KnowledgeNetworkService
from minibkn.application.query_plan_service import QueryPlanService
from minibkn.application.retrieval_service import RetrievalService
from minibkn.application.schema_generation_service import SchemaGenerationService
from minibkn.domain.access_control import Permission, Principal
from minibkn.domain.build import BuildJob
from minibkn.domain.document_knowledge import (
    DocumentIngestResult,
    DocumentJobStatus,
    DocumentKnowledgeStatus,
    RoutedAskResult,
)
from minibkn.domain.modeling import ModelingSession
from minibkn.domain.models import (
    ActionExecution,
    AskResult,
    DataSource,
    KnowledgeNetwork,
    ObjectInstance,
    RiskSimulationResult,
    SearchHit,
    Subgraph,
    TraceEvent,
)
from minibkn.domain.query import QueryAnalysis, QueryExecutionResult, QueryPlan

router = APIRouter(prefix="/api/v1")


def _network_service(request: Request) -> KnowledgeNetworkService:
    return cast(KnowledgeNetworkService, request.app.state.network_service)


def _graph_service(request: Request) -> KnowledgeGraphService:
    return cast(KnowledgeGraphService, request.app.state.graph_service)


def _retrieval_service(request: Request) -> RetrievalService:
    return cast(RetrievalService, request.app.state.retrieval_service)


def _action_service(request: Request) -> ActionService:
    return cast(ActionService, request.app.state.action_service)


def _schema_generation_service(request: Request) -> SchemaGenerationService:
    return cast(SchemaGenerationService, request.app.state.schema_generation_service)


def _query_plan_service(request: Request) -> QueryPlanService:
    return cast(QueryPlanService, request.app.state.query_plan_service)


def _build_service(request: Request) -> IncrementalBuildService:
    return cast(IncrementalBuildService, request.app.state.build_service)


def _modeling_service(request: Request) -> ModelingService:
    return cast(ModelingService, request.app.state.modeling_service)


def _knowledge_router(request: Request) -> KnowledgeRouterService:
    return cast(KnowledgeRouterService, request.app.state.knowledge_router_service)


def _evaluation_service(request: Request) -> EvaluationReportService:
    return cast(EvaluationReportService, request.app.state.evaluation_service)


def _access(request: Request) -> AccessControlService:
    return cast(AccessControlService, request.app.state.access_control_service)


def _principal(request: Request) -> Principal:
    return cast(Principal, request.state.principal)


def _summary(network: KnowledgeNetwork) -> NetworkSummary:
    return NetworkSummary(
        id=network.id,
        name=network.name,
        business_domain=network.business_domain,
        version=network.version,
        lifecycle_status=network.lifecycle_status,
        object_type_count=len(network.object_types),
        relation_type_count=len(network.relation_types),
        action_type_count=len(network.action_types),
        risk_type_count=len(network.risk_types),
        updated_at=network.updated_at,
    )


@router.post(
    "/networks/import", response_model=KnowledgeNetwork, status_code=status.HTTP_201_CREATED
)
async def import_network(payload: ImportNetworkRequest, request: Request) -> KnowledgeNetwork:
    return await _network_service(request).import_directory(payload.path)


@router.get("/networks", response_model=NetworkListResponse)
async def list_networks(request: Request) -> NetworkListResponse:
    networks = await _network_service(request).list_networks()
    networks = _access(request).filter_networks(_principal(request), networks)
    return NetworkListResponse(entries=[_summary(item) for item in networks], total=len(networks))


@router.get("/networks/{network_id}/schema", response_model=KnowledgeNetwork)
async def get_network_schema(network_id: str, request: Request) -> KnowledgeNetwork:
    network = await _network_service(request).get_network(network_id)
    principal = _principal(request)
    if principal.is_admin or "*" in principal.resources:
        return network
    visible_objects = [
        item
        for item in network.object_types
        if item.data_source is None or principal.allows_resource(item.data_source.source_id)
    ]
    visible_ids = {item.id for item in visible_objects}
    return network.model_copy(
        update={
            "object_types": visible_objects,
            "relation_types": [
                item
                for item in network.relation_types
                if item.endpoint.source_object_type in visible_ids
                and item.endpoint.target_object_type in visible_ids
            ],
            "action_types": [
                item
                for item in network.action_types
                if item.bound_object_type in visible_ids and principal.allows_action(item.id)
            ],
        }
    )


@router.post("/sources", response_model=DataSource, status_code=status.HTTP_201_CREATED)
async def register_source(payload: RegisterSourceRequest, request: Request) -> DataSource:
    return await _graph_service(request).register_source(
        payload.id, payload.name, payload.kind, payload.path
    )


@router.get("/sources", response_model=list[DataSource])
async def list_sources(request: Request) -> list[DataSource]:
    sources = await _graph_service(request).list_sources()
    return _access(request).filter_sources(_principal(request), sources)


@router.post("/sources/{source_id}/discover", response_model=DataSource)
async def discover_source(source_id: str, request: Request) -> DataSource:
    return await _graph_service(request).discover_source(source_id)


@router.post("/sources/{source_id}/generate-network", response_model=KnowledgeNetwork)
async def generate_network(
    source_id: str, payload: GenerateNetworkRequest, request: Request
) -> KnowledgeNetwork:
    return await _schema_generation_service(request).generate(
        source_id, payload.network_id, payload.name, payload.use_ai
    )


@router.post("/networks/{network_id}/materialize", response_model=MaterializeResponse)
async def materialize_network(network_id: str, request: Request) -> MaterializeResponse:
    object_count, relation_count = await _graph_service(request).materialize(network_id)
    return MaterializeResponse(
        network_id=network_id,
        object_count=object_count,
        relation_count=relation_count,
    )


@router.post("/networks/{network_id}/builds", response_model=BuildJob)
async def run_incremental_build(network_id: str, request: Request) -> BuildJob:
    return await _build_service(request).run(network_id)


@router.get("/builds/{build_id}", response_model=BuildJob)
async def get_build(build_id: str, request: Request) -> BuildJob:
    job = await _build_service(request).get(build_id)
    _access(request).require(_principal(request), Permission.READ, job.network_id)
    return job


@router.post(
    "/modeling-sessions", response_model=ModelingSession, status_code=status.HTTP_201_CREATED
)
async def create_modeling_session(
    payload: CreateModelingSessionRequest, request: Request
) -> ModelingSession:
    return await _modeling_service(request).create(
        payload.source_id,
        payload.network_id,
        payload.name,
        payload.instruction,
        payload.use_ai,
    )


@router.get("/modeling-sessions", response_model=list[ModelingSession])
async def list_modeling_sessions(request: Request) -> list[ModelingSession]:
    principal = _principal(request)
    return [
        item
        for item in await _modeling_service(request).list_all()
        if principal.allows_network(item.network_id)
    ]


@router.get("/modeling-sessions/{session_id}", response_model=ModelingSession)
async def get_modeling_session(session_id: str, request: Request) -> ModelingSession:
    session = await _modeling_service(request).get(session_id)
    _access(request).require(_principal(request), Permission.READ, session.network_id)
    return session


@router.patch(
    "/modeling-sessions/{session_id}/proposals/{proposal_id}",
    response_model=ModelingSession,
)
async def review_modeling_proposal(
    session_id: str,
    proposal_id: str,
    payload: ReviewProposalRequest,
    request: Request,
) -> ModelingSession:
    session = await _modeling_service(request).get(session_id)
    _access(request).require(_principal(request), Permission.MODEL, session.network_id)
    return await _modeling_service(request).review(
        session_id, proposal_id, payload.status, payload.reviewed_by, payload.payload
    )


@router.post(
    "/modeling-sessions/{session_id}/publish",
    response_model=KnowledgeNetwork,
)
async def publish_modeling_session(
    session_id: str,
    payload: PublishModelingSessionRequest,
    request: Request,
) -> KnowledgeNetwork:
    session = await _modeling_service(request).get(session_id)
    _access(request).require(_principal(request), Permission.MODEL, session.network_id)
    return await _modeling_service(request).publish(session_id, payload.published_by)


@router.get(
    "/networks/{network_id}/object-types/{object_type_id}/instances",
    response_model=list[ObjectInstance],
)
async def list_instances(
    network_id: str, object_type_id: str, request: Request
) -> list[ObjectInstance]:
    return await _graph_service(request).list_instances(network_id, object_type_id)


@router.post("/networks/{network_id}/subgraph", response_model=Subgraph)
async def get_subgraph(network_id: str, payload: SubgraphRequest, request: Request) -> Subgraph:
    return await _graph_service(request).subgraph(
        network_id, payload.object_type_id, payload.instance_id, payload.depth
    )


@router.post("/networks/{network_id}/index", response_model=IndexResponse)
async def build_index(network_id: str, request: Request) -> IndexResponse:
    counts = await _retrieval_service(request).build_index(network_id)
    return IndexResponse(network_id=network_id, **counts)


@router.post("/networks/{network_id}/search", response_model=list[SearchHit])
async def search_network(
    network_id: str, payload: SearchRequest, request: Request
) -> list[SearchHit]:
    return await _retrieval_service(request).search(
        network_id, payload.query, payload.limit, payload.mode
    )


@router.post("/networks/{network_id}/ask", response_model=AskResult)
async def ask_network(network_id: str, payload: AskRequest, request: Request) -> AskResult:
    return await _retrieval_service(request).ask(network_id, payload.question)


@router.get("/document-knowledge/status", response_model=DocumentKnowledgeStatus)
async def document_knowledge_status(request: Request) -> DocumentKnowledgeStatus:
    return await _knowledge_router(request).status()


@router.post(
    "/networks/{network_id}/documents/text",
    response_model=DocumentIngestResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_document_text(
    network_id: str, payload: IngestDocumentTextRequest, request: Request
) -> DocumentIngestResult:
    return await _knowledge_router(request).ingest_text(
        network_id, payload.collection, payload.title, payload.text
    )


@router.get(
    "/networks/{network_id}/document-collections/{collection}/jobs/{track_id}",
    response_model=DocumentJobStatus,
)
async def document_job_status(
    network_id: str, collection: str, track_id: str, request: Request
) -> DocumentJobStatus:
    return await _knowledge_router(request).job_status(network_id, collection, track_id)


@router.get("/evaluations/latest", response_model=dict[str, object])
async def latest_evaluation(request: Request) -> dict[str, object]:
    return _evaluation_service(request).latest()


@router.post("/networks/{network_id}/ask-routed", response_model=RoutedAskResult)
async def ask_network_routed(
    network_id: str, payload: RoutedAskRequest, request: Request
) -> RoutedAskResult:
    return await _knowledge_router(request).ask(network_id, payload.question, payload.route)


@router.post("/networks/{network_id}/query-plans/preview", response_model=QueryPlan)
async def preview_query_plan(network_id: str, payload: AskRequest, request: Request) -> QueryPlan:
    return await _query_plan_service(request).preview(network_id, payload.question)


@router.post("/networks/{network_id}/query-plans/analyze", response_model=QueryAnalysis)
async def analyze_query(
    network_id: str, payload: AnalyzeQueryRequest, request: Request
) -> QueryAnalysis:
    return await _query_plan_service(request).analyze(
        network_id, payload.question, payload.clarification_answers
    )


@router.post("/networks/{network_id}/query-plans/execute", response_model=QueryExecutionResult)
async def execute_query_plan(
    network_id: str, payload: ExecuteQueryPlanRequest, request: Request
) -> QueryExecutionResult:
    return await _query_plan_service(request).execute(network_id, payload.plan)


@router.post("/networks/{network_id}/ask-planned", response_model=PlannedAskResponse)
async def ask_network_with_plan(
    network_id: str, payload: AskRequest, request: Request
) -> PlannedAskResponse:
    answer, execution = await _query_plan_service(request).ask(network_id, payload.question)
    return PlannedAskResponse(question=payload.question, answer=answer, execution=execution)


@router.post(
    "/networks/{network_id}/ask-intelligent",
    response_model=IntelligentAskResponse,
)
async def ask_network_intelligently(
    network_id: str, payload: AnalyzeQueryRequest, request: Request
) -> IntelligentAskResponse:
    analysis, answer, execution, retrieval, requires_confirmation = await _query_plan_service(
        request
    ).ask_intelligently(network_id, payload.question, payload.clarification_answers)
    return IntelligentAskResponse(
        question=payload.question,
        status=analysis.status,
        analysis=analysis,
        answer=answer,
        execution=execution,
        retrieval=retrieval,
        requires_action_confirmation=requires_confirmation,
    )


@router.post(
    "/networks/{network_id}/actions/{action_type_id}/execute",
    response_model=ActionExecution,
)
async def execute_action(
    network_id: str,
    action_type_id: str,
    payload: ExecuteActionRequest,
    request: Request,
) -> ActionExecution:
    return await _action_service(request).execute(
        network_id,
        action_type_id,
        payload.object_type_id,
        payload.instance_id,
        payload.parameters,
        payload.idempotency_key,
    )


@router.post(
    "/networks/{network_id}/actions/{action_type_id}/risks/simulate",
    response_model=RiskSimulationResult,
)
async def simulate_action_risks(
    network_id: str,
    action_type_id: str,
    payload: SimulateRiskRequest,
    request: Request,
) -> RiskSimulationResult:
    return await _action_service(request).simulate_risks(
        network_id,
        action_type_id,
        payload.object_type_id,
        payload.instance_id,
        payload.parameters,
        payload.subject,
    )


@router.post("/action-executions/{execution_id}/confirm", response_model=ActionExecution)
async def confirm_action(
    execution_id: str, payload: ConfirmActionRequest, request: Request
) -> ActionExecution:
    execution = await _action_service(request).get_execution(execution_id)
    _access(request).require(_principal(request), Permission.APPROVE, execution.network_id)
    return await _action_service(request).confirm(execution_id, payload.approved)


@router.get("/action-executions/{execution_id}", response_model=ActionExecution)
async def get_action_execution(execution_id: str, request: Request) -> ActionExecution:
    execution = await _action_service(request).get_execution(execution_id)
    _access(request).require(_principal(request), Permission.AUDIT, execution.network_id)
    return execution


@router.get("/traces/{trace_id}", response_model=list[TraceEvent])
async def get_trace(trace_id: str, request: Request) -> list[TraceEvent]:
    events = await _action_service(request).list_trace(trace_id)
    execution_id = next(
        (str(item.payload["execution_id"]) for item in events if item.payload.get("execution_id")),
        "",
    )
    if execution_id:
        execution = await _action_service(request).get_execution(execution_id)
        _access(request).require(_principal(request), Permission.AUDIT, execution.network_id)
    return events
