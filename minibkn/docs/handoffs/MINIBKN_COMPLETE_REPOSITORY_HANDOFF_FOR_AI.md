> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 全项目代码与文档总交接

> 更新日期：2026-08-19\
> 当前版本：MiniBKN 0.6.0\
> 目标读者：第一次接手本仓库的 AI 或开发者\
> 作用：说明项目边界、当前事实、代码职责、测试与评测资产、全部 MiniBKN 文档，以及“想了解某功能应该看哪里”。

## 1. 接手时先理解项目边界

当前工作区根目录是上游 [BKN Foundry](https://github.com/openbkn-ai/bkn-foundry/blob/main/README.zh.md) 仓库，包含大量 Go/Kubernetes 微服务。用户为秋招准备开发的 Python 复现不是对整个上游仓库的修改，而是两个新增的同级项目：

```text
MINIBKN/
├── minibkn/       # Python/FastAPI 后端、测试、样例、评测和项目文档
├── minibkn-ui/    # React/TypeScript/Vite 轻量控制台
├── qa_docs/       # 其他 AI 生成的通俗解读，不是代码事实真相源
└── 其他目录       # 上游 BKN Foundry 原始工程，主要作为架构和概念参考
```

除非用户明确要求修改上游 Foundry，否则开发范围应优先限制在 `minibkn/`、`minibkn-ui/` 和对应文档。上游根目录的 `adp/`、`deploy/`、`infra/`、`bkn-safe/`、`bkn-trace/` 等不是当前 Python MVP 的运行依赖。

## 2. 当前真实状态

MiniBKN 是一个 Python-first、可本地运行的 BKN 核心链路复现。它将上游复杂微服务收敛为 FastAPI 模块化单体，同时保留业务知识网络的关键概念。

当前已实现主链路：

```text
CSV / SQLite
 → 字段剖析、组合主键和外键候选
 → BKN 对象/字段/关系/动作/风险定义
 → AI 辅助提案、人工审核和版本发布
 → 对象实例和关系图物化
 → BM25 + Embedding + RRF 索引
 → QueryPlan 改写、歧义追问、过滤、遍历和聚合
 → LightRAG 非结构化文档分支与混合路由
 → 统一证据、引用和回答
 → 用户/角色/网络/资源/文档域/动作 RBAC
 → 风险 DSL、审批、白名单工具、幂等与 trace
```

当前验收事实：后端 74 项测试通过、行覆盖率 89%、Ruff 和 Mypy strict 通过；前端 8 项测试和生产构建通过；真实 LightRAG sidecar 已完成 3 文档/3 问题全链路冒烟。准确数字和边界以 [0.6.0 最终验收](../reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md) 为准。

## 3. 哪些文件是最高优先级真相源

发生描述冲突时按以下顺序判断：

1. 当前代码和自动化测试；
2. [0.6.0 最终验收](../reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md)；
3. 对应功能的最新专项报告；
4. [架构文档](../ARCHITECTURE.md)和[验收指南](../ACCEPTANCE.md)；
5. 开发计划；
6. 早期阶段报告和其他 AI 的通俗解读。

较早文档可能写着“LightRAG 未接入”“只有网络级 API Key”“67/71 项测试”，这些是当时的历史状态，不是 0.6.0 当前状态。

## 4. 后端整体架构

依赖方向大致为：

```text
FastAPI routes
      ↓
Application services
      ↓
Domain contracts + Ports
      ↑
Adapters（SQLite、CSV、LLM、Embedding、LightRAG、Tool）
```

- `domain/` 不应该依赖 FastAPI、SQLAlchemy 或具体模型供应商。
- `ports/` 定义抽象接口。
- `adapters/` 对接外部实现。
- `application/` 编排业务用例。
- `api/` 只负责 HTTP 输入输出和调用 service。
- `main.py` 负责依赖组装、配置和中间件。

完整说明见 [ARCHITECTURE.md](../ARCHITECTURE.md)。

## 5. 后端代码逐目录地图

### 5.1 启动与配置

| 文件 | 作用 |
| --- | --- |
| [main.py](../../src/minibkn/main.py) | FastAPI 入口；创建数据库、repository、service、Embedding、LLM、LightRAG、ToolRegistry；注册 CORS、认证授权、trace 和错误处理。 |
| [config.py](../../src/minibkn/config.py) | Pydantic Settings；读取数据库、Embedding、LLM、RBAC、LightRAG、CORS 和评测目录配置。 |
| [mcp_server.py](../../src/minibkn/mcp_server.py) | MCP stdio 服务；暴露 search、ask、request_action，仍通过 HTTP 和动作门禁。 |
| [__init__.py](../../src/minibkn/__init__.py) | 包版本和基础导出。 |

### 5.2 Domain：领域合同和安全规则

| 文件 | 作用 |
| --- | --- |
| [models.py](../../src/minibkn/domain/models.py) | 核心模型：KnowledgeNetwork、ObjectType、RelationType、ActionType、RiskType、实例、搜索文档、上下文和动作执行。 |
| [query.py](../../src/minibkn/domain/query.py) | QueryAnalysis、QueryPlan、Filter、Traversal、Aggregate、ActionRequest 等受限查询合同。 |
| [modeling.py](../../src/minibkn/domain/modeling.py) | AI 建模会话、六类提案、审核状态和 BKN 生命周期。 |
| [access_control.py](../../src/minibkn/domain/access_control.py) | Principal、Permission、资源范围判断和请求级 ContextVar。 |
| [policy.py](../../src/minibkn/domain/policy.py) | 不使用 `eval` 的风险表达式解释器；限制操作符、引用域、深度和节点数。 |
| [document_knowledge.py](../../src/minibkn/domain/document_knowledge.py) | 文档 provider 状态、入库任务、路由枚举和混合回答合同。 |
| [evidence.py](../../src/minibkn/domain/evidence.py) | provider-neutral EvidenceItem 和证据类型。 |
| [build.py](../../src/minibkn/domain/build.py) | 增量变更集与 BuildJob 状态机。 |
| [base.py](../../src/minibkn/domain/base.py) | 严格 Pydantic 基类，默认禁止未知字段。 |
| [errors.py](../../src/minibkn/domain/errors.py) | BKN Lang 解析/验证错误结构。 |

### 5.3 Ports：可替换边界

| 文件 | 作用 |
| --- | --- |
| [repository.py](../../src/minibkn/ports/repository.py) | 网络、图、索引、动作执行持久化接口。 |
| [datasource.py](../../src/minibkn/ports/datasource.py) | 数据源发现和读取接口。 |
| [search.py](../../src/minibkn/ports/search.py) | Embedder 等检索接口。 |
| [planner.py](../../src/minibkn/ports/planner.py) | QueryAnalyzer 接口。 |
| [schema_ai.py](../../src/minibkn/ports/schema_ai.py) | AI Schema enhancer 接口。 |
| [document_knowledge.py](../../src/minibkn/ports/document_knowledge.py) | LightRAG/未来文档系统端口。 |
| [tools.py](../../src/minibkn/ports/tools.py) | 有副作用业务工具执行接口。 |
| [modeling.py](../../src/minibkn/ports/modeling.py) | 建模会话持久化接口。 |

### 5.4 Application：主要业务用例

| 文件 | 作用 |
| --- | --- |
| [network_service.py](../../src/minibkn/application/network_service.py) | 导入、保存、读取和列出 BKN 网络。 |
| [data_profiling.py](../../src/minibkn/application/data_profiling.py) | 字段统计、单/组合主键、外键候选、置信度和推荐。 |
| [schema_generation_service.py](../../src/minibkn/application/schema_generation_service.py) | 从已发现资源生成初始对象/关系；可调用 LLM 做受限增强。 |
| [modeling_service.py](../../src/minibkn/application/modeling_service.py) | 生成逐条提案、校验审核修改、阻止未审发布、组装版本化网络。 |
| [graph_service.py](../../src/minibkn/application/graph_service.py) | 注册/发现数据源；按 BKN 映射物化对象和关系；子图；计算增量变化。 |
| [retrieval_service.py](../../src/minibkn/application/retrieval_service.py) | 构建 Schema/实例/动作索引；授权过滤；混合搜索；一跳子图；证据组装。 |
| [query_plan_service.py](../../src/minibkn/application/query_plan_service.py) | 规则/LLM 查询分析、改写、同义词、歧义、计划校验、过滤/遍历/聚合执行和动作隔离。 |
| [knowledge_router_service.py](../../src/minibkn/application/knowledge_router_service.py) | structured/document/hybrid/auto 路由、文档域权限、降级和证据融合。 |
| [action_service.py](../../src/minibkn/application/action_service.py) | 动作权限后的对象读取、参数绑定、风险判断、审批、幂等、工具调用和事件记录。 |
| [build_service.py](../../src/minibkn/application/build_service.py) | 事务式增量建图+建索引；验证失败时恢复旧状态。 |
| [access_control_service.py](../../src/minibkn/application/access_control_service.py) | 策略文件加载、API Key 哈希认证、角色合并、权限要求和资源过滤。 |
| [answer_generator.py](../../src/minibkn/application/answer_generator.py) | 将统一证据整理成确定性的抽取式回答。 |
| [evaluation_service.py](../../src/minibkn/application/evaluation_service.py) | 只读取已完成的最新机器评测结果供 API/UI 展示。 |

### 5.5 Adapters：具体实现

| 文件 | 作用 |
| --- | --- |
| [bkn_lang/parser.py](../../src/minibkn/adapters/bkn_lang/parser.py) | 解析 `.bkn` frontmatter 和 Markdown 表格。 |
| [bkn_lang/validator.py](../../src/minibkn/adapters/bkn_lang/validator.py) | 对象、字段、关系、动作、风险交叉校验。 |
| [datasource/local.py](../../src/minibkn/adapters/datasource/local.py) | CSV/SQLite 发现、类型推断和全量行读取。 |
| [persistence/database.py](../../src/minibkn/adapters/persistence/database.py) | SQLAlchemy async engine 和建表。 |
| [persistence/tables.py](../../src/minibkn/adapters/persistence/tables.py) | SQLite ORM 表。 |
| [persistence/repository.py](../../src/minibkn/adapters/persistence/repository.py) | Repository 的 SQLAlchemy 实现。 |
| [search/hybrid.py](../../src/minibkn/adapters/search/hybrid.py) | BM25、离线哈希向量、NumPy 相似度、缓存和 RRF。 |
| [search/remote.py](../../src/minibkn/adapters/search/remote.py) | 硅基流动兼容 Embedding、批处理、重试、缓存和降级。 |
| [search/semantic.py](../../src/minibkn/adapters/search/semantic.py) | sentence-transformers 本地语义向量适配器。 |
| [llm/query_planner.py](../../src/minibkn/adapters/llm/query_planner.py) | OpenAI-compatible LLM QueryAnalysis/QueryPlan JSON 生成和 Token 统计。 |
| [llm/openai_compatible.py](../../src/minibkn/adapters/llm/openai_compatible.py) | AI Schema 描述、动作和风险建议。 |
| [document_knowledge.py](../../src/minibkn/adapters/document_knowledge.py) | Disabled provider 与 LightRAG REST sidecar；入库、状态、`/query/data` 和引用归一化。 |
| [tools/registry.py](../../src/minibkn/adapters/tools/registry.py) | 显式工具白名单；当前只含不会真实下单的补货预警演示工具。 |

### 5.6 API 与可观测性

| 文件 | 作用 |
| --- | --- |
| [api/routes.py](../../src/minibkn/api/routes.py) | `/api/v1` 全部业务路由；只做 service 调用和少量对象级权限补充。 |
| [api/schemas.py](../../src/minibkn/api/schemas.py) | HTTP 请求/响应模型和长度、格式限制。 |
| [api/errors.py](../../src/minibkn/api/errors.py) | 统一业务异常。 |
| [observability/trace.py](../../src/minibkn/observability/trace.py) | 请求 trace_id 的创建、读取和 ContextVar 管理。 |
| [evaluation/benchmark.py](../../src/minibkn/evaluation/benchmark.py) | 早期 200 题基准合同与排序指标。 |

`__init__.py` 文件主要用于包导出，不承载核心业务逻辑。

## 6. 前端代码地图

前端是独立轻量 React 19 + TypeScript + Vite 7 单页控制台，没有 BFF、Redux 或 React Router。

| 文件 | 作用 |
| --- | --- |
| [src/App.tsx](../../../minibkn-ui/src/App.tsx) | 六个工作区：数据源、AI 建模、知识网络、业务问答、动作风险、评测。 |
| [src/api.ts](../../../minibkn-ui/src/api.ts) | fetch 封装、base URL、`x-api-key`、JSON 和错误处理。 |
| [src/types.ts](../../../minibkn-ui/src/types.ts) | UI 需要的网络、建模和路由结果类型。 |
| [src/main.tsx](../../../minibkn-ui/src/main.tsx) | React 挂载入口。 |
| [src/styles.css](../../../minibkn-ui/src/styles.css) | 全部视觉样式、响应式和无障碍辅助样式。 |
| [src/App.test.tsx](../../../minibkn-ui/src/App.test.tsx) | 六工作区、API、错误、评测和审核门禁的 8 项测试。 |
| [vite.config.ts](../../../minibkn-ui/vite.config.ts) | Vite + React + Vitest/jsdom 配置。 |
| [package.json](../../../minibkn-ui/package.json) | 依赖和 dev/build/test/lint 命令。 |

当前 UI 问答页调用 `/ask-routed`，尚未把 `/ask-intelligent` 的歧义追问和动作候选做成完整交互向导。

## 7. 配置、样例、数据与运行产物

| 路径 | 作用 |
| --- | --- |
| [.env.example](../../.env.example) | 所有环境变量模板；默认离线哈希、关闭 LLM/RBAC/LightRAG。 |
| [pyproject.toml](../../pyproject.toml) | Python 3.11–3.12 依赖、可选 semantic/evaluation/dev 组和工具配置。 |
| [config/access-policy.example.json](../../config/access-policy.example.json) | sales/finance/manager 示例 RBAC；公开演示 Key 的哈希，不能用于生产。 |
| [config/lightrag-endpoints.example.json](../../config/lightrag-endpoints.example.json) | network/collection 到独立 LightRAG endpoint 的映射模板。 |
| [examples/supply_chain](../../examples/supply_chain) | 可直接运行的对象、关系、动作、风险完整样例。 |
| [examples/crm](../../examples/crm) | 通用化 CRM 对象和关系样例。 |
| [evals/enterprise](../../evals/enterprise) | 采购、财务、人事 BKN、合成表格和数据质量样本。 |
| [evals/datasets](../../evals/datasets) | CRM、跨行业、QueryPlan、对抗和动作冻结题集。 |
| [evals/results](../../evals/results) | 检索、Ragas、Token、性能、QueryPlan 和 LightRAG 原始机器结果。 |
| [evals/fixtures/documents](../../evals/fixtures/documents) | LightRAG 合成文档。 |
| [Dockerfile](../../Dockerfile)、[compose.yaml](../../compose.yaml) | 后端容器运行。 |

`.venv/`、`.lightrag-venv/`、`data/`、`lightrag.log`、缓存目录和临时数据库是本机运行产物，不应作为源代码交付。API Key 只从环境变量或本地 key 文件读取，不得写进 Markdown、代码或测试快照。

## 8. 脚本地图

| 脚本 | 作用 |
| --- | --- |
| [demo.py](../../scripts/demo.py)、[demo.ps1](../../scripts/demo.ps1) | 无外部 API 的供应链全链路一键演示。 |
| [demo_with_ai.ps1](../../scripts/demo_with_ai.ps1) | 使用本地 Key 文件启动 DeepSeek+BGE-M3 演示。 |
| [generate_crm_benchmark.py](../../scripts/generate_crm_benchmark.py) | 固定 seed 生成 CRM 大数据和 200 题。 |
| [generate_enterprise_test_suite.py](../../scripts/generate_enterprise_test_suite.py) | 生成采购、财务、人事和数据质量套件。 |
| [generate_query_planner_holdout.py](../../scripts/generate_query_planner_holdout.py) | 生成新的 QueryPlan 冻结 holdout。 |
| [evaluate_crm.py](../../scripts/evaluate_crm.py) | CRM BM25/向量/混合/执行器评测。 |
| [evaluate_query_planner.py](../../scripts/evaluate_query_planner.py) | DeepSeek QueryPlan 生成准确率、组件、延迟和 Token。 |
| [evaluate_ragas.py](../../scripts/evaluate_ragas.py) | 较早 ID 型 Ragas 入口。 |
| [evaluate_ragas_comprehensive.py](../../scripts/evaluate_ragas_comprehensive.py) | Faithfulness 和综合 Ragas 评测。 |
| [evaluate_rag_vs_bkn.py](../../scripts/evaluate_rag_vs_bkn.py) | 传统 RAG 与 QueryPlan 的质量/Token 对照。 |
| [evaluate_performance.py](../../scripts/evaluate_performance.py) | 冷热缓存、顺序和 50 并发性能。 |
| [evaluate_lightrag_integration.py](../../scripts/evaluate_lightrag_integration.py) | LightRAG 文档入库、查询、路由和融合真实评测。 |
| [evaluate_offline.py](../../scripts/evaluate_offline.py) | 早期离线评测。 |
| [compile_evaluation_summary.py](../../scripts/compile_evaluation_summary.py) | 汇总机器结果供 UI 读取。 |
| [verify_ai_providers.py](../../scripts/verify_ai_providers.py) | 验证 LLM 和 Embedding provider 连通/契约。 |
| [verify_ai_demo.py](../../scripts/verify_ai_demo.py) | 验证 AI 演示主链路。 |
| [verify_retrieval_replay.py](../../scripts/verify_retrieval_replay.py) | 性能优化前后排序和指标重放比较。 |
| [start_lightrag.ps1](../../scripts/start_lightrag.ps1) | 启动独立 LightRAG sidecar。 |

## 9. 测试地图

### 集成测试

| 文件 | 主要覆盖 |
| --- | --- |
| `test_network_api.py` | BKN 导入、列出、读取 Schema。 |
| `test_phase_b_api.py` | 数据发现→图→索引→检索上下文主链路。 |
| `test_phase_c_action_api.py` | 风险、审批、工具执行和 trace。 |
| `test_generic_crm_api.py` | 非供应链领域复用同一问答链路。 |
| `test_enterprise_domains_api.py` | 采购、财务、人事端到端通用性。 |
| `test_schema_generation_api.py` | 自动 Schema 可物化。 |
| `test_modeling_workflow_api.py` | 六类提案、审核门禁、发布和构建。 |
| `test_query_plan_api.py` | 计划执行、歧义、智能入口、动作隔离。 |
| `test_incremental_build_api.py` | 局部更新和失败恢复。 |
| `test_index_version_api.py` | Embedding 版本变化要求重建。 |
| `test_document_knowledge_routing_api.py` | 文档端口、路由、混合、禁用和降级。 |
| `test_authorization_api.py` | RBAC 认证、资源隔离、建模和动作拒绝。 |
| `test_api_key_auth.py` | 简单 API Key 和输入长度。 |
| `test_search_concurrency.py` | 阻塞检索从事件循环卸载。 |
| `test_mcp_server.py` | MCP 工具发现和调用。 |
| `test_evaluation_report_api.py` | UI 只读取完成的正式评测。 |

### 单元测试

`test_bkn_parser.py` 验证 BKN；`test_datasource_adapters.py` 验证 CSV/SQLite 和键发现；`test_domain_contracts.py` 验证严格领域合同；`test_policy_evaluator.py` 验证安全 DSL；`test_hybrid_retriever_cache.py` 验证 BM25/RRF/缓存；`test_remote_embedder.py` 验证远程 Embedding 重试、坏向量、缓存和降级；`test_semantic_embedder.py` 验证本地模型；`test_query_planner_adapter.py` 验证 LLM JSON 合同；`test_schema_ai_adapter.py` 验证 AI Schema 约束；`test_lightrag_adapter.py` 验证 REST 合同和安全域；其余 evaluation tests 验证冻结数据集、指标和参考答案函数。

## 10. 全部 MiniBKN 文档目录与摘要

### 10.1 总入口

| 文档 | 内容 |
| --- | --- |
| [项目 README](../../README.md) | 当前能力、安装、启动、API、LightRAG、评测和验证的最短入口。 |
| [文档中心](../README.md) | 按计划、报告、指南和交接分类的目录。 |
| [文档总导航](../MINIBKN_DOCUMENTATION_NAVIGATION.md) | 阅读顺序、事实优先级和按功能查找。 |
| [架构说明](../ARCHITECTURE.md) | 模块边界、依赖和主链路。 |
| [验收指南](../ACCEPTANCE.md) | 启动、演示、API 和测试验收步骤。 |

### 10.2 Plans：方案与执行路线

| 文档 | 内容 |
| --- | --- |
| [完整优化执行方案](../plans/MINIBKN_COMPREHENSIVE_EXECUTION_PLAN.md) | 通用化、AI、Embedding、键发现、QueryPlan、风险、增量、UI、LightRAG 和评测总路线。 |
| [分步开发计划](../plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md) | S0–S10 顺序、依赖、状态和验收。 |
| [评测与 LightRAG 规划](../plans/MINIBKN_EVALUATION_LIGHTRAG_FEASIBILITY_AND_ROADMAP.md) | Ragas、CRM、文档分支和 LightRAG 可行性。 |
| [全量测试计划](../plans/MINIBKN_COMPREHENSIVE_TEST_AND_EVALUATION_PLAN.md) | 多行业、真实模型、性能、安全、UI 测试计划，已执行。 |
| [查询智能与评测计划](../plans/MINIBKN_QUERY_INTELLIGENCE_AND_EVALUATION_EXECUTION_PLAN.md) | 智能问答、六指标 Ragas 和传统 RAG 对照，已执行。 |
| [早期优化路线图](../plans/MINIBKN_OPTIMIZATION_ROADMAP.md) | 开发总监视角的早期建议，历史参考。 |
| [原始复现计划](../plans/MINIBKN_REPRODUCTION_PLAN.md) | 从上游解析到 0.4.0 的原始路线和进度。 |
| [综合方案中文解读](../plans/综合执行方案中文解读.md) | 总计划的中文解释版。 |
| [综合方案大白话](../plans/综合执行方案大白话解读.md) | 总计划的通俗版本。 |

### 10.3 Reports：开发与验收报告

| 文档 | 内容 |
| --- | --- |
| [阶段 A](../reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_A.md) | 最小 FastAPI/领域骨架。 |
| [阶段 B](../reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md) | BKN、数据源、对象关系和检索基础。 |
| [阶段 C](../reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md) | 问答、动作、风险、审批和 trace。 |
| [阶段 D](../reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md) | MCP、自动 Schema、评测和工程收口。 |
| [0.4.0 早期验收](../reports/MINIBKN_FINAL_ACCEPTANCE_REPORT.md) | 第一轮完整验收，历史状态。 |
| [S0 领域契约](../reports/MINIBKN_S0_BASELINE_CONTRACTS_DEVELOPMENT_REPORT.md) | 通用 Evidence、QueryPlan、文档端口和 CRM 基线。 |
| [S1 通用核心](../reports/MINIBKN_S1_GENERIC_CORE_DEVELOPMENT_REPORT.md) | 去供应链硬编码、通用值类型与证据回答。 |
| [P0 查询智能与数据发现](../reports/MINIBKN_P0_QUERY_INTELLIGENCE_AND_DATA_DISCOVERY_DEVELOPMENT_REPORT.md) | DeepSeek、追问、键发现和真实 BGE-M3 增强。 |
| [S3 Embedding](../reports/MINIBKN_S3_EMBEDDING_DEVELOPMENT_REPORT.md) | 远程/本地 Embedding、缓存、降级和版本。 |
| [S4 QueryPlan](../reports/MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md) | QueryPlan 合同、校验、执行和边界。 |
| [S5 风险 DSL](../reports/MINIBKN_S5_RISK_DSL_DEVELOPMENT_REPORT.md) | 通用风险表达式、幂等和动作门禁。 |
| [S6 增量构建](../reports/MINIBKN_S6_INCREMENTAL_BUILD_DEVELOPMENT_REPORT.md) | 图/索引局部更新、状态和恢复。 |
| [S7 AI 建模](../reports/MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md) | 提案、审核、人工发布和版本。 |
| [S8 文档接口](../reports/MINIBKN_S8_DOCUMENT_KNOWLEDGE_INTERFACE_DEVELOPMENT_REPORT.md) | 文档端口和路由预留的阶段报告。 |
| [S9 控制台](../reports/MINIBKN_S9_CONTROL_ROOM_UI_DEVELOPMENT_REPORT.md) | React 六工作区的产品和技术说明。 |
| [S10 CRM 评测](../reports/MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md) | 9,140 对象、200 问题、30 动作的第一轮正式评测。 |
| [S3–S10 验收](../reports/MINIBKN_S3_S10_LONG_HORIZON_ACCEPTANCE_REPORT.md) | 长程开发范围、测试和当时边界。 |
| [多行业数据集](../reports/MINIBKN_ENTERPRISE_TEST_DATASET_DEVELOPMENT_REPORT.md) | 采购、财务、人事与脏数据生成资产。 |
| [确定性测试基础](../reports/MINIBKN_DETERMINISTIC_TEST_FOUNDATION_REPORT.md) | 测试合同、故障注入和基线。 |
| [QueryPlan 盲测](../reports/MINIBKN_QUERY_PLAN_BLIND_AND_ADVERSARIAL_EVALUATION_REPORT.md) | 60 题 93.33%、对抗结果和失败分析。 |
| [检索与 Ragas](../reports/MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md) | 200 题 BM25/BGE/RRF、30 题 Faithfulness。 |
| [性能韧性安全](../reports/MINIBKN_PERFORMANCE_RESILIENCE_SECURITY_REPORT.md) | 50 并发、429/5xx/坏向量和优化数据。 |
| [UI 浏览器验收](../reports/MINIBKN_UI_BROWSER_ACCEPTANCE_REPORT.md) | Vitest、真实浏览器和移动端。 |
| [全量测试验收](../reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md) | 多行业、检索、Ragas、性能、安全和 UI 总结；部分状态早于 0.6.0。 |
| [全量测试通俗报告](../reports/MINIBKN_COMPREHENSIVE_TEST_PLAIN_LANGUAGE_REPORT.md) | 上一项的非技术解释。 |
| [查询智能与完整评测](../reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md) | 智能入口、六项 Ragas、30 题 Token 对照。 |
| [企业权限报告](../reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md) | 认证、角色、网络、文件、文档域和动作权限。 |
| [LightRAG 接入评测](../reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md) | 真实 sidecar、3 文档、路由、融合和隔离。 |
| [秋招完整项目说明](../reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md) | 从初版问题到当前成果、困难和业务价值。 |
| [0.6.0 最终验收](../reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md) | 当前最新总验收和剩余边界。 |

### 10.4 Guides：理解与问答

| 文档 | 内容 |
| --- | --- |
| [非技术完整汇报](../guides/MINIBKN_NON_TECHNICAL_FULL_REPORT.md) | 面向非技术读者介绍产品、流程和使用。 |
| [初次流程理解与答疑](../guides/MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md) | 表格、关系、图、检索、数据库和动作答疑。 |
| [QueryPlan 说明与剩余工作](../guides/MINIBKN_QUERY_PLAN_EXPLANATION_AND_REMAINING_WORK.md) | QueryPlan 通俗流程、进度和边界。 |
| [QueryPlan 大白话](../guides/QueryPlan大白话解读版.md) | 更口语化的 QueryPlan 解读。 |
| [8 个问题](../guides/qa/MINIBKN_8_QUESTIONS_ANSWER.md) | 第一组源码级项目问题。 |
| [10 个问题第二部分](../guides/qa/MINIBKN_10_QUESTIONS_ANSWER_PART2.md) | 第二组细节答疑。 |
| [5 个问题第三部分](../guides/qa/MINIBKN_5_QUESTIONS_ANSWER_PART3.md) | 第三组细节答疑。 |
| [6 个问题第四部分](../guides/qa/MINIBKN_6_QUESTIONS_ANSWER_PART4.md) | 第四组细节答疑。 |

### 10.5 Technical deep dive：最新源码级专题

专题总入口：[technical_deep_dive/README.md](../technical_deep_dive/README.md)。

| 文档 | 内容 |
| --- | --- |
| [01 UI](../technical_deep_dive/01_UI_FRAMEWORK_AND_INTERVIEW_POSITIONING.md) | 前端框架、复杂度、边界和 AI coding 面试表述。 |
| [02 启动与测试](../technical_deep_dive/02_STARTUP_AND_FUNCTIONAL_TEST_CASES.md) | 后端/UI 启动及手工、自动化测试案例。 |
| [03 导入与薪酬初例](../technical_deep_dive/03_IMPORT_INDEX_AND_PAYROLL_SCENARIO.md) | 结构化/文档索引和工时薪酬初步分析。 |
| [04 认证 RBAC](../technical_deep_dive/04_AUTHENTICATION_AND_RBAC_INTERNALS.md) | API Key、Principal、两层过滤和安全边界。 |
| [05 查询与路由](../technical_deep_dive/05_QUERY_UNDERSTANDING_AND_ROUTING_INTERNALS.md) | `/ask-intelligent` 与 `/ask-routed` 的真实关系。 |
| [06 结构化分支](../technical_deep_dive/06_STRUCTURED_BRANCH_INTERNALS.md) | 混合检索和确定性 QueryPlan 两种执行方式。 |
| [07 动作风险](../technical_deep_dive/07_ACTION_AUTHORIZATION_AND_RISK_INTERNALS.md) | 动作权限、参数、风险、工具和审计。 |
| [08 动作意图](../technical_deep_dive/08_ACTION_INTENT_DECISION_INTERNALS.md) | `intent=action`、action_request 和确认含义。 |
| [09 财务完整案例](../technical_deep_dive/09_PAYROLL_END_TO_END_CASE_STUDY.md) | 工时薪酬从表格到问答、动作和审批的 21 步案例。 |
| [10 完整评估](../technical_deep_dive/10_EVALUATION_SYSTEM_DATASETS_AND_RESULTS.md) | 全部数据集、指标、结果、负结论和口径。 |
| [11 面试说明](../technical_deep_dive/11_QUERYPLAN_AND_AI_MODELING_INTERVIEW_GUIDE.md) | QueryPlan 与 AI BKN 建模的面试表达和追问。 |

### 10.6 Handoffs：给其他 AI 的既有交接

| 文档 | 内容 |
| --- | --- |
| 项目与用户背景（私人学习资料，未公开） | 项目来由和用户个人背景。 |
| 早期讲解交接（私人学习资料，未公开） | 早期供另一个 AI 解读的材料。 |
| [完整项目交接](MINIBKN_PROJECT_HANDOFF_FOR_AI.md) | 0.4/中期功能和深入阅读入口。 |
| [全量评测交接](MINIBKN_COMPREHENSIVE_EVALUATION_HANDOFF_FOR_AI.md) | 多行业评测做了什么、结果在哪。 |
| [查询智能评测交接](MINIBKN_QUERY_INTELLIGENCE_AND_EVALUATION_HANDOFF_FOR_AI.md) | 智能入口、六指标和 Token 对照。 |
| [秋招项目交接](MINIBKN_AUTUMN_RECRUITMENT_PROJECT_HANDOFF_FOR_AI.md) | 0.6.0 项目故事、代码和结果资料。 |
| [全量评测大白话](全量评测结果大白话解读.md) | 其他 AI 对全量评测的通俗解释。 |
| [查询评测大白话](查询智能与评测结果大白话解读.md) | 其他 AI 对查询与评测的通俗解释。 |
| 本文 | 当前最完整的代码、资产和全部文档总入口。 |

工作区根目录的 技术细节大白话全解（私人学习资料，未公开） 和 MiniBKN 秋招全攻略（私人学习资料，未公开） 是其他 AI 的二次解读，可辅助阅读，但不能覆盖代码和最新验收事实。

## 11. 想了解某项功能，应该看什么

| 目标 | 先看文档 | 再看代码/测试 |
| --- | --- | --- |
| 整体项目是什么 | 秋招完整说明、09 财务案例 | `main.py`、`routes.py` |
| 如何启动和演示 | 项目 README、02 启动、ACCEPTANCE | `scripts/demo.py` |
| 数据源和主外键 | P0 报告、03/09 专题 | `local.py`、`data_profiling.py`、datasource tests |
| BKN Lang | ARCHITECTURE、阶段 B | `parser.py`、`validator.py`、examples |
| AI 辅助建模 | S7、11 面试说明 | `modeling_service.py`、`schema_generation_service.py`、modeling test |
| 图物化和增量 | S6、09 案例 | `graph_service.py`、`build_service.py`、incremental test |
| Embedding/混合检索 | S3、检索与 Ragas、06 | `retrieval_service.py`、`search/*` |
| QueryPlan | S4、05/06/11 | `domain/query.py`、`query_plan_service.py`、query tests |
| LightRAG | LightRAG 报告、05 | `document_knowledge.py`、routing/lightrag tests |
| 权限 | 企业权限报告、04 | `access_control.py`、`access_control_service.py`、authorization test |
| 动作和风险 | S5、07/08 | `action_service.py`、`policy.py`、action/policy tests |
| MCP | README | `mcp_server.py`、MCP test |
| UI | S9、UI 验收、01 | `minibkn-ui/src/App.tsx`、App.test.tsx |
| 评测数字 | 10 完整评估、查询智能完整评测、0.6 验收 | `scripts/evaluate_*`、`evals/results` |
| 秋招面试 | 秋招完整说明、11 面试说明 | 对应专题源码，不只背结论 |

## 12. 启动和验证命令

后端：

```powershell
cd minibkn
uv sync --python <local-path> --extra dev --no-editable
Copy-Item .env.example .env
.venv\Scripts\python.exe -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

一键离线演示：

```powershell
cd minibkn
.\scripts\demo.ps1
```

前端：

```powershell
cd minibkn-ui
npm install
npm run dev
```

质量验证：

```powershell
cd minibkn
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff format --check src tests scripts
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m mypy src

cd ..\minibkn-ui
npm test
npm run lint
npm run build
```

LightRAG、真实模型和完整评测的命令见项目 README 与对应专项报告；不要在输出中打印本地 Key。

## 13. 当前已知边界

- RBAC 已覆盖网络、资源、文档域和动作，但没有通用行级/字段级 ABAC。
- API Key 策略是本地 MVP，不是企业 OIDC/SSO。
- `/ask-intelligent` 与 `/ask-routed` 尚未统一成按子问题编排结构化和文档分支的总入口。
- UI 尚未完整展示歧义追问、自然语言动作候选和审批工作台。
- QueryPlan 不支持任意 SQL、复杂 temporal join、窗口函数和跨对象计算表达式。
- 当前只注册补货预警演示工具；没有真实 ERP/CRM/考勤写回。
- LightRAG 真实评测只有一个 public workspace 和 3 题冒烟。
- 混合检索在编号密集 CRM 集上只追平 BM25；ID Precision@5 为 0.14。
- 合成数据与 LLM judge 结果不能直接外推为生产指标。
- SQLite、本地向量矩阵和单进程部署适合作品集，不代表生产高可用。

## 14. 后续 AI 接手工作规则

1. 先阅读根目录 `AGENTS.md` 与 `rules/`，再读本文和目标模块专项报告。
2. 修改前确认目标属于 Python MVP 还是上游 Foundry；不要混改。
3. 已实现、演示级和计划中能力必须明确区分。
4. 不删除、覆盖用户已有改动；当前根仓库可能把 `minibkn/` 和 `minibkn-ui/` 整体视为未跟踪目录。
5. 不提交、推送或创建 PR，除非用户明确批准。
6. 不读取后在对话、日志、Markdown或测试快照中输出 API Key；只传文件路径或环境变量。
7. 修改代码后补相应测试，并报告命令、边界和覆盖缺口。
8. 新增开发模块时更新分步计划、专项开发报告、通俗报告和文档导航。
9. 评测数字必须链接原始 JSON，注明样本、模型、对照和外推限制。
10. 文档冲突时回到代码、测试和最新验收，不根据文件名猜当前状态。

## 15. 最短接手路径

如果上下文有限，只读以下五份：

1. 本文；
2. [项目 README](../../README.md)；
3. [秋招完整项目说明](../reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md)；
4. [0.6.0 最终验收](../reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md)；
5. 将要修改功能对应的 technical deep dive 和测试文件。

读完后，从 [main.py](../../src/minibkn/main.py) 看依赖组装，从 [routes.py](../../src/minibkn/api/routes.py) 找入口，再进入对应 application service、domain contract、adapter 和测试。
