"""MiniBKN FastAPI application entry point."""

import logging
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from minibkn.adapters.datasource import CsvDataSourceAdapter, SQLiteDataSourceAdapter
from minibkn.adapters.document_knowledge import DisabledDocumentKnowledge, LightRAGDocumentKnowledge
from minibkn.adapters.llm import OpenAICompatibleQueryPlanner, OpenAICompatibleSchemaEnhancer
from minibkn.adapters.persistence.database import Database
from minibkn.adapters.persistence.repository import (
    SqlAlchemyExecutionRepository,
    SqlAlchemyKnowledgeGraphRepository,
    SqlAlchemyKnowledgeNetworkRepository,
    SqlAlchemyModelingRepository,
)
from minibkn.adapters.search import (
    CachingEmbedder,
    FailoverEmbedder,
    HybridRetriever,
    SentenceTransformerEmbedder,
    SiliconFlowEmbedder,
    TokenHashingEmbedder,
)
from minibkn.adapters.tools import ReplenishmentAlertTool, ToolRegistry
from minibkn.api.errors import MiniBKNError
from minibkn.api.routes import router
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
from minibkn.config import Settings
from minibkn.domain.access_control import Permission, reset_principal, set_principal
from minibkn.domain.errors import BknLangError
from minibkn.domain.models import DataSourceKind
from minibkn.observability.trace import (
    current_trace_id,
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)
from minibkn.ports.document_knowledge import DocumentKnowledgePort
from minibkn.ports.search import Embedder


def create_app(
    settings: Settings | None = None,
    document_knowledge: DocumentKnowledgePort | None = None,
) -> FastAPI:
    settings = settings or Settings()
    settings.prepare_directories()
    logging.basicConfig(level=settings.log_level.upper())
    embedding_api_key = _resolve_api_key(
        settings.embedding_api_key, settings.embedding_api_key_file
    )
    llm_api_key = _resolve_api_key(settings.llm_api_key, settings.llm_api_key_file)
    access_control = AccessControlService(
        settings.authorization_enabled,
        settings.authorization_policy_file,
        settings.api_key,
    )

    database = Database(settings.database_url)
    repository = SqlAlchemyKnowledgeNetworkRepository(database)
    graph_repository = SqlAlchemyKnowledgeGraphRepository(database)
    execution_repository = SqlAlchemyExecutionRepository(database)
    modeling_repository = SqlAlchemyModelingRepository(database)
    network_service = KnowledgeNetworkService(repository)
    graph_service = KnowledgeGraphService(
        repository,
        graph_repository,
        {
            DataSourceKind.CSV: CsvDataSourceAdapter(),
            DataSourceKind.SQLITE: SQLiteDataSourceAdapter(),
        },
    )
    embedder: Embedder
    if settings.embedding_provider == "sentence_transformers":
        embedder = SentenceTransformerEmbedder(settings.embedding_model)
    elif settings.embedding_provider == "siliconflow" and embedding_api_key:
        remote_embedder: Embedder = SiliconFlowEmbedder(
            api_key=embedding_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            base_url=settings.embedding_api_base,
            batch_size=settings.embedding_batch_size,
            timeout=settings.embedding_timeout_seconds,
        )
        if settings.embedding_failover_enabled:
            remote_embedder = FailoverEmbedder(
                remote_embedder, TokenHashingEmbedder(settings.embedding_dimensions)
            )
        embedder = remote_embedder
    else:
        if settings.embedding_provider == "siliconflow":
            logging.warning("SiliconFlow API key is missing; using deterministic token hashing")
        embedder = TokenHashingEmbedder(settings.embedding_dimensions)
    if settings.embedding_cache_entries:
        embedder = CachingEmbedder(embedder, settings.embedding_cache_entries)
    retriever = HybridRetriever(embedder)
    retrieval_service = RetrievalService(repository, graph_repository, retriever)
    if document_knowledge is None and settings.document_knowledge_provider == "lightrag":
        if settings.lightrag_endpoint_map_file is None:
            raise ValueError("LightRAG endpoint map file is required for the lightrag provider")
        document_knowledge = LightRAGDocumentKnowledge(
            settings.lightrag_endpoint_map_file,
            _resolve_api_key(settings.lightrag_api_key, settings.lightrag_api_key_file),
            settings.lightrag_query_mode,
            settings.lightrag_timeout_seconds,
        )
    document_knowledge = document_knowledge or DisabledDocumentKnowledge()
    knowledge_router_service = KnowledgeRouterService(
        retrieval_service,
        document_knowledge,
        settings.document_knowledge_degrade_when_disabled,
    )
    tools = ToolRegistry()
    tools.register("procurement", "create_replenishment_alert", ReplenishmentAlertTool())
    action_service = ActionService(repository, graph_repository, execution_repository, tools)
    schema_enhancer = None
    if (
        settings.llm_provider == "openai_compatible"
        and llm_api_key
        and settings.llm_base_url
        and settings.llm_model
    ):
        schema_enhancer = OpenAICompatibleSchemaEnhancer(
            settings.llm_base_url, llm_api_key, settings.llm_model
        )
    schema_generation_service = SchemaGenerationService(
        repository, graph_repository, schema_enhancer
    )
    query_planner = None
    if (
        settings.llm_provider == "openai_compatible"
        and llm_api_key
        and settings.llm_base_url
        and settings.llm_model
    ):
        query_planner = OpenAICompatibleQueryPlanner(
            settings.llm_base_url, llm_api_key, settings.llm_model
        )
    query_plan_service = QueryPlanService(
        repository, graph_repository, query_planner, retrieval_service
    )
    build_service = IncrementalBuildService(
        repository, graph_repository, graph_service, retrieval_service
    )
    modeling_service = ModelingService(modeling_repository, repository, schema_generation_service)
    evaluation_service = EvaluationReportService(settings.evaluation_results_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await database.create_schema()
        yield
        await database.close()

    app = FastAPI(
        title=settings.app_name,
        version="0.6.0",
        description="Python-first local reproduction of the BKN Foundry core workflow",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.network_service = network_service
    app.state.graph_service = graph_service
    app.state.retrieval_service = retrieval_service
    app.state.action_service = action_service
    app.state.schema_generation_service = schema_generation_service
    app.state.query_plan_service = query_plan_service
    app.state.build_service = build_service
    app.state.modeling_service = modeling_service
    app.state.knowledge_router_service = knowledge_router_service
    app.state.evaluation_service = evaluation_service
    app.state.access_control_service = access_control
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next: Any) -> Any:
        trace_id = request.headers.get("x-trace-id") or new_trace_id()
        token = set_trace_id(trace_id)
        principal_token = None
        try:
            supplied_api_key = request.headers.get("x-api-key", "")
            if settings.authorization_enabled and request.url.path.startswith("/api/"):
                principal = access_control.authenticate(supplied_api_key)
                principal_token = set_principal(principal)
                _authorize_http_request(access_control, principal, request)
                request.state.principal = principal
                response = await call_next(request)
            else:
                api_key_matches = secrets.compare_digest(
                    supplied_api_key.encode("utf-8"), settings.api_key.encode("utf-8")
                )
                if (
                    settings.api_key
                    and request.url.path.startswith("/api/")
                    and not api_key_matches
                ):
                    response = _error_response(
                        401, "UNAUTHORIZED", "A valid x-api-key header is required"
                    )
                else:
                    principal_token = set_principal(access_control.authenticate(supplied_api_key))
                    request.state.principal = access_control.authenticate(supplied_api_key)
                    response = await call_next(request)
        except MiniBKNError as exc:
            response = _error_response(exc.status_code, exc.error_code, exc.message, exc.details)
        finally:
            if principal_token is not None:
                reset_principal(principal_token)
            reset_trace_id(token)
        response.headers["x-trace-id"] = trace_id
        return response

    @app.exception_handler(MiniBKNError)
    async def application_error_handler(request: Request, exc: MiniBKNError) -> JSONResponse:
        return _error_response(exc.status_code, exc.error_code, exc.message, exc.details)

    @app.exception_handler(BknLangError)
    async def bkn_error_handler(request: Request, exc: BknLangError) -> JSONResponse:
        details = [{"path": issue.path, "message": issue.message} for issue in exc.issues]
        return _error_response(400, "INVALID_BKN_DEFINITION", str(exc), details)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"path": ".".join(str(item) for item in error["loc"]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return _error_response(400, "INVALID_PARAMETER", "Request validation failed", details)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _authorize_http_request(access: AccessControlService, principal: Any, request: Request) -> None:
    path = request.url.path
    network_match = re.search(r"/networks/([^/]+)", path)
    network_id = network_match.group(1) if network_match else ""
    if network_id in {"import"}:
        network_id = ""
    action_match = re.search(r"/actions/([^/]+)", path)
    if action_match and path.endswith("/execute"):
        access.require_action(principal, network_id, action_match.group(1))
        return
    if "/confirm" in path:
        access.require(principal, Permission.APPROVE)
        return
    if "/traces/" in path or "/evaluations/" in path or "/action-executions/" in path:
        access.require(principal, Permission.AUDIT, network_id)
        return
    read_suffixes = (
        "/search",
        "/ask",
        "/ask-routed",
        "/ask-planned",
        "/ask-intelligent",
        "/query-plans/preview",
        "/query-plans/analyze",
        "/query-plans/execute",
        "/subgraph",
        "/risks/simulate",
    )
    if request.method == "GET" or path.endswith(read_suffixes):
        access.require(principal, Permission.READ, network_id)
        return
    access.require(principal, Permission.MODEL, network_id)


def _resolve_api_key(value: str, key_file: Path | None) -> str:
    if value:
        return value.strip()
    if key_file is None:
        return ""
    try:
        return key_file.read_text(encoding="utf-8-sig").strip()
    except OSError:
        logging.getLogger(__name__).warning("configured API key file could not be read")
        return ""


def _error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error_code": error_code,
        "message": message,
        "trace_id": current_trace_id(),
    }
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)


app = create_app()


def run() -> None:
    settings = Settings()
    uvicorn.run("minibkn.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
