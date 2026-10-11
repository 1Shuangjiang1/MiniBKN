> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 文档中心

这里集中保存 MiniBKN 的方案、架构、开发报告、使用说明和 AI 交接资料。

> [进入完整文档总导航](MINIBKN_DOCUMENTATION_NAVIGATION.md)：所有资料已经按“当前事实、开发计划、专题说明、历史资料”重新归类，并提供按功能查找入口。

本轮最新：[0.6.0 最终验收](reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md)、[秋招项目完整说明](reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md)、[企业权限报告](reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md)与[LightRAG 接入评测](reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md)。

最新专项报告：[检索与 Ragas](reports/MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md)、[性能韧性安全](reports/MINIBKN_PERFORMANCE_RESILIENCE_SECURITY_REPORT.md)、[UI 浏览器验收](reports/MINIBKN_UI_BROWSER_ACCEPTANCE_REPORT.md)。

## 推荐阅读顺序

1. [项目 README](../README.md)：当前版本能做什么、如何启动和演示。
2. [完整优化执行方案](plans/MINIBKN_COMPREHENSIVE_EXECUTION_PLAN.md)：后续开发的当前主计划。
3. [分步开发计划](plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)：实施状态和每一步验收条件。
4. [架构说明](ARCHITECTURE.md)：当前版本的模块边界。
5. [全量测试最终验收](reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md)：最新已实现能力与真实数字。
6. [非技术完整汇报](guides/MINIBKN_NON_TECHNICAL_FULL_REPORT.md)：面向非技术读者的整体介绍。
7. [全项目代码与文档总交接](handoffs/MINIBKN_COMPLETE_REPOSITORY_HANDOFF_FOR_AI.md)：其他 AI 接手代码与全部资料的首选入口。
8. [秋招项目资料交接](handoffs/MINIBKN_AUTUMN_RECRUITMENT_PROJECT_HANDOFF_FOR_AI.md)：完整项目故事和秋招资料入口。
9. [技术细节专题](technical_deep_dive/README.md)：UI、启动、导入建索引、RBAC、QueryPlan、结构化检索和动作安全的源码级解答。

## 原有快速索引

以下内容保留作为快速入口；完整分类和最新状态以[文档总导航](MINIBKN_DOCUMENTATION_NAVIGATION.md)为准。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [完整优化执行方案](plans/MINIBKN_COMPREHENSIVE_EXECUTION_PLAN.md) | 通用化、AI 建模、Embedding、QueryPlan、风险、增量、LightRAG、UI 和评测总路线 | S3-S10 已实施，LightRAG 在 0.6.0 完成接入 |
| [分步开发计划](plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md) | 后续模块顺序、状态、验收和报告规则 | **当前实施台账** |
| [架构说明](ARCHITECTURE.md) | 当前系统模块、依赖方向和运行链路 | 当前事实，结合最新验收阅读 |
| [验收指南](ACCEPTANCE.md) | 当前版本的启动、演示和验收步骤 | 当前事实，结合最新验收阅读 |
| [项目 README](../README.md) | 快速开始、API 使用和测试命令 | 当前使用入口 |

当不同方案描述冲突时，以“完整优化执行方案”为后续路线依据，以代码和当前架构/验收文档为已实现事实依据。

## 方案与规划 `plans/`

- [完整优化执行方案](plans/MINIBKN_COMPREHENSIVE_EXECUTION_PLAN.md)：11 项优化的统一方案、阶段顺序和验收门槛。
- [评测与 LightRAG 专项规划](plans/MINIBKN_EVALUATION_LIGHTRAG_FEASIBILITY_AND_ROADMAP.md)：非结构化分支与评测的细化资料。
- [早期优化路线图](plans/MINIBKN_OPTIMIZATION_ROADMAP.md)：上一轮开发总监视角的建议，保留作历史决策输入。
- [原始复现方案与进度](plans/MINIBKN_REPRODUCTION_PLAN.md)：从项目解析到 0.4.0 完成过程，属于历史主计划。

## 开发与验收报告 `reports/`

- [阶段 A 报告](reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_A.md)：最小骨架和第一条链路。
- [阶段 B 报告](reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md)：BKN、数据和图构建能力。
- [阶段 C 报告](reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md)：检索、问答和动作链路。
- [阶段 D 报告](reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md)：MCP、自动 Schema、评测和工程收口。
- [最终验收报告](reports/MINIBKN_FINAL_ACCEPTANCE_REPORT.md)：0.4.0 完整验收结论。
- [S0 基线与领域契约报告](reports/MINIBKN_S0_BASELINE_CONTRACTS_DEVELOPMENT_REPORT.md)：新路线第一步的领域合同和 CRM 样例。
- [S1 通用核心报告](reports/MINIBKN_S1_GENERIC_CORE_DEVELOPMENT_REPORT.md)：证据驱动回答、通用类型和 CRM 端到端链路。
- [S3 Embedding 报告](reports/MINIBKN_S3_EMBEDDING_DEVELOPMENT_REPORT.md)：远程 Embedding、缓存、降级与索引版本。
- [S4 QueryPlan 报告](reports/MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md)：查询计划生成、校验和执行。
- [S5 风险 DSL 报告](reports/MINIBKN_S5_RISK_DSL_DEVELOPMENT_REPORT.md)：安全表达式、动作门禁和幂等。
- [S6 增量构建报告](reports/MINIBKN_S6_INCREMENTAL_BUILD_DEVELOPMENT_REPORT.md)：局部图/索引更新与失败恢复。
- [S7 AI 建模报告](reports/MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md)：提案、审核与人工发布。
- [S8 文档接口报告](reports/MINIBKN_S8_DOCUMENT_KNOWLEDGE_INTERFACE_DEVELOPMENT_REPORT.md)：可插拔端口与路由，未实现 LightRAG。
- [S9 控制台报告](reports/MINIBKN_S9_CONTROL_ROOM_UI_DEVELOPMENT_REPORT.md)：独立 React 六工作区产品。
- [S10 CRM 评测报告](reports/MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md)：冻结数据、真实基线、Ragas、Token 与延迟。
- [S3–S10 长程最终验收](reports/MINIBKN_S3_S10_LONG_HORIZON_ACCEPTANCE_REPORT.md)：完整交付、测试、运行方法与未完成边界。
- [全量测试最终验收](reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md)：多行业、真实模型、Ragas、性能、安全和 UI 的最新总验收。
- [全量测试通俗报告](reports/MINIBKN_COMPREHENSIVE_TEST_PLAIN_LANGUAGE_REPORT.md)：面向非技术读者的本轮汇报。
- [企业权限报告](reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md)：用户、角色、文件、文档域和行动权限。
- [LightRAG 接入评测](reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md)：真实入库、检索、路由、混合和隔离测试。
- [秋招项目完整说明](reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md)：完整演进、困难、效果和业务价值。
- [0.6.0 最终验收](reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md)：权限、LightRAG、74 项测试和剩余边界。

## 使用与理解资料 `guides/`

- [非技术完整汇报](guides/MINIBKN_NON_TECHNICAL_FULL_REPORT.md)：系统是什么、用户怎么使用。
- [初次流程理解与答疑](guides/MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md)：围绕表格、关系、检索、数据库和动作的梳理。
- [`guides/qa/`](guides/qa/)：四份基于源码的详细问题解答。

## 技术细节专题 `technical_deep_dive/`

- [专题导航](technical_deep_dive/README.md)：八个问题的入口、当前事实和未实现边界。
- [UI 与面试表述](technical_deep_dive/01_UI_FRAMEWORK_AND_INTERVIEW_POSITIONING.md)
- [启动与测试案例](technical_deep_dive/02_STARTUP_AND_FUNCTIONAL_TEST_CASES.md)
- [导入、索引和工时薪酬场景](technical_deep_dive/03_IMPORT_INDEX_AND_PAYROLL_SCENARIO.md)
- [认证与 RBAC](technical_deep_dive/04_AUTHENTICATION_AND_RBAC_INTERNALS.md)
- [查询理解与知识路由](technical_deep_dive/05_QUERY_UNDERSTANDING_AND_ROUTING_INTERNALS.md)
- [结构化分支](technical_deep_dive/06_STRUCTURED_BRANCH_INTERNALS.md)
- [动作权限与风险](technical_deep_dive/07_ACTION_AUTHORIZATION_AND_RISK_INTERNALS.md)
- [动作意图识别](technical_deep_dive/08_ACTION_INTENT_DECISION_INTERNALS.md)
- [财务工时与薪酬端到端完整案例](technical_deep_dive/09_PAYROLL_END_TO_END_CASE_STUDY.md)：用一个扩展后的现实案例串联数据发现、BKN、建图、索引、权限、查询、LightRAG、动作、审批和审计。
- [完整评估体系](technical_deep_dive/10_EVALUATION_SYSTEM_DATASETS_AND_RESULTS.md)：数据集、检索、QueryPlan、Ragas、Token、动作、权限、性能、LightRAG 与 UI 的分层评估。
- [QueryPlan 与 AI 建模面试说明](technical_deep_dive/11_QUERYPLAN_AND_AI_MODELING_INTERVIEW_GUIDE.md)：项目故事、准确口径、常见追问和源码入口。

## AI 交接资料 `handoffs/`

- [全项目代码与文档总交接](handoffs/MINIBKN_COMPLETE_REPOSITORY_HANDOFF_FOR_AI.md)：**当前最完整入口**，包含项目边界、全部核心代码职责、脚本、测试、评测资产、全部 MiniBKN 文档摘要和按功能反向索引。
- [完整项目交接](handoffs/MINIBKN_PROJECT_HANDOFF_FOR_AI.md)：较早的项目功能、结构和深入阅读入口，保留作历史补充。
- [全量测试与评测交接](handoffs/MINIBKN_COMPREHENSIVE_EVALUATION_HANDOFF_FOR_AI.md)：上一轮完整测评做了什么、结果在哪里、哪些结论有数据支持。
- [查询智能与完整评测交接](handoffs/MINIBKN_QUERY_INTELLIGENCE_AND_EVALUATION_HANDOFF_FOR_AI.md)：最新智能问答闭环、六项 Ragas 和传统 RAG Token 对照。
- [秋招项目资料交接](handoffs/MINIBKN_AUTUMN_RECRUITMENT_PROJECT_HANDOFF_FOR_AI.md)：当前完整项目事实和深入阅读位置。
- 项目与用户背景（私人学习资料，未公开）：项目来由和用户背景。
- 讲解任务背景（私人学习资料，未公开）：较早的交接材料，保留作为补充上下文。

## 文档维护规则

- 新的总体路线只更新“完整优化执行方案”，不要再新建同类总计划。
- 每个开发阶段分别更新技术开发记录和一份通俗报告。
- 已实现事实必须有代码或测试支持；计划中的能力要明确标注“未实现”。
- 评测数字必须同时记录数据版本、配置、模型、代码版本和原始结果。
- API Key、数据库密码和个人隐私不得写入任何 Markdown。
- 移动或改名文档后，要同步更新本索引和相对链接。
