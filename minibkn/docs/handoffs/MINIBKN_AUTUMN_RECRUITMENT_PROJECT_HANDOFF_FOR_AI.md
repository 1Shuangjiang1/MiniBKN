> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 秋招项目资料交接（供其他 AI 读取）

## 1. 交接目的

这份文档只说明 MiniBKN 项目的事实、当前状态和资料位置。后续其他 AI 如需帮助项目所有者整理秋招材料，应先从下面指定文件获取项目背景和可核验结果。

## 2. 项目所有者和项目定位

项目所有者正在准备秋招，技术理解仍在逐步建立，希望以 Python、FastAPI、RAG、QueryPlan、知识图谱、MCP 和 AI 应用工程为主要项目方向。

MiniBKN 参考 `openbkn-ai/bkn-foundry` 的 BKN 思想，是一个独立的 Python 主流程复现与增强项目，不是上游仓库的完整复刻。项目将企业结构化表格/数据库、BKN 业务对象关系和动作风险、LightRAG 非结构化文档统一到可引用问答和受控行动链路中。

## 3. 当前主要功能

- CSV/SQLite 数据发现、字段画像、主外键候选；
- BKN Schema、实例、关系、行动和风险建模；
- BM25、BGE-M3、RRF 混合检索；
- QueryPlan 过滤、遍历、聚合、投影和排序；
- DeepSeek 查询改写、同义词、子问题和歧义追问；
- 三层上下文、统一 EvidenceItem 和引用；
- 风险 DSL、白名单行动、人工确认、幂等和 Trace；
- 增量物化、增量索引和索引版本；
- AI 辅助建模提案和人工发布；
- MCP 工具接口；
- 独立 React 控制台；
- 用户/角色/网络/文件/文档域/行动 RBAC；
- LightRAG REST sidecar、文档入库、索引状态、路由和混合证据；
- CRM 测试集、Ragas、Token 对照、性能和安全测试。

## 4. 首选阅读顺序

### 4.1 先理解完整项目

1. `docs/reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md`
2. `README.md`
3. `docs/ARCHITECTURE.md`
4. `docs/MINIBKN_DOCUMENTATION_NAVIGATION.md`

### 4.2 核对最终功能和测试

1. `docs/reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md`
2. `docs/reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md`
3. `docs/reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md`
4. `docs/reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md`
5. `docs/reports/MINIBKN_S3_S10_LONG_HORIZON_ACCEPTANCE_REPORT.md`

### 4.3 理解早期到最终的演进

1. `docs/reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_A.md`
2. `docs/reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md`
3. `docs/reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md`
4. `docs/reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md`
5. `docs/reports/MINIBKN_S0_BASELINE_CONTRACTS_DEVELOPMENT_REPORT.md`
6. `docs/reports/MINIBKN_S1_GENERIC_CORE_DEVELOPMENT_REPORT.md`
7. `docs/reports/MINIBKN_S3_EMBEDDING_DEVELOPMENT_REPORT.md` 至 `MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md`

## 5. 按专题查阅

| 专题 | 文件 |
|---|---|
| QueryPlan 通俗流程 | `docs/guides/MINIBKN_QUERY_PLAN_EXPLANATION_AND_REMAINING_WORK.md` |
| 查询智能和六项 Ragas | `docs/reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md` |
| CRM 数据集 | `docs/reports/MINIBKN_ENTERPRISE_TEST_DATASET_DEVELOPMENT_REPORT.md` |
| 检索和 Ragas | `docs/reports/MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md` |
| 性能、韧性、安全 | `docs/reports/MINIBKN_PERFORMANCE_RESILIENCE_SECURITY_REPORT.md` |
| 风险 DSL | `docs/reports/MINIBKN_S5_RISK_DSL_DEVELOPMENT_REPORT.md` |
| 增量更新 | `docs/reports/MINIBKN_S6_INCREMENTAL_BUILD_DEVELOPMENT_REPORT.md` |
| AI 建模 | `docs/reports/MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md` |
| RBAC | `docs/reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md` |
| LightRAG | `docs/reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md` |
| UI | `docs/reports/MINIBKN_S9_CONTROL_ROOM_UI_DEVELOPMENT_REPORT.md` |
| 完整 API/使用 | `README.md`、`docs/ACCEPTANCE.md` |

## 6. 代码入口

- 应用组装和认证：`src/minibkn/main.py`
- HTTP API：`src/minibkn/api/routes.py`、`api/schemas.py`
- 领域模型：`src/minibkn/domain/`
- BKN 解析：`src/minibkn/adapters/bkn_lang/`
- 结构化建图：`src/minibkn/application/graph_service.py`
- 检索：`src/minibkn/application/retrieval_service.py`
- QueryPlan：`src/minibkn/application/query_plan_service.py`
- 风险和行动：`src/minibkn/application/action_service.py`
- 增量构建：`src/minibkn/application/build_service.py`
- AI 建模：`src/minibkn/application/modeling_service.py`
- 权限：`src/minibkn/domain/access_control.py`、`application/access_control_service.py`
- LightRAG：`src/minibkn/adapters/document_knowledge.py`、`application/knowledge_router_service.py`
- 测试：`tests/unit/`、`tests/integration/`
- 前端：同级目录 `../minibkn-ui/`

## 7. 原始评测证据

- 全量结果根目录：`evals/results/`
- CRM 200 题检索：`evals/results/crm/`
- QueryPlan 盲测：`evals/results/comprehensive/query_plan/`
- Ragas：`evals/results/comprehensive/ragas/`
- 传统 RAG/QueryPlan Token：`evals/results/comprehensive/token/rag_vs_bkn_token_30.json`
- LightRAG：`evals/results/lightrag/integration.json`
- LightRAG 测试文档：`evals/fixtures/documents/crm_public/`

## 8. 当前可核验数字

- CRM：9,140 个对象、9,150 个检索文档、200 题和 30 个动作题；
- BGE-M3：BM25/Vector/Hybrid Hit@1 为 0.700/0.515/0.700；
- 独立 30 题 Faithfulness：0.9261；
- 10 题六项诊断：MiniBKN Context Precision 0.9583、Context Recall 1.000、Noise Sensitivity 0.100；
- 30 题传统 RAG 对照：输入 Token 减少 66.78%，总 Token 减少 62.36%，冻结 QueryPlan 30/30；
- LightRAG：3 份文档完成索引，3 个问题 3/3，混合响应含 14 条结构化和 3 条文档证据；
- 后端上一轮 71 项通过、89% 覆盖率；本轮总数以最新验收报告和当前测试输出为准；
- 前端上一轮 8 项通过，TypeScript 和生产构建通过。

数字口径和限制必须以对应专项报告为准，不能把不同样本的指标合并或外推。

## 9. 事实边界

- 合成企业数据，不是真实公司的生产数据；
- RBAC 是本地策略文件，不是完整 SSO/IAM；
- LightRAG 真实运行的是 `crm/public` 工作区，多安全域通过适配器自动化测试；
- 项目根工作树仍由项目所有者决定如何整理 Git 历史，本次没有提交、推送或创建 PR；
- 项目与 NUS 或其他机构的关系只能依据项目所有者能够提供的真实证明材料陈述。
