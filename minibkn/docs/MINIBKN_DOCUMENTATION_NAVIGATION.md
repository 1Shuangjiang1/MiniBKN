> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 文档总导航

> 更新日期：2026-08-18\
> 作用：说明先看什么、深入某模块去哪里，以及哪些是当前事实、计划或历史资料。\
> 整理原则：不移动旧文件，避免原有链接失效；通过分级和索引整理。

## 1. 第一次阅读：只看这六份

1. [项目 README](../README.md)：启动方式、API 和当前功能入口。
2. [秋招项目完整说明](reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md)：从初版问题到最终架构、优化、困难、效果和价值。
3. [全量测试通俗报告](reports/MINIBKN_COMPREHENSIVE_TEST_PLAIN_LANGUAGE_REPORT.md)：这轮到底怎么测、结果好不好、还缺什么。
4. [全量测试最终验收](reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md)：主要真实数字、测试范围与限制。
5. [QueryPlan 通俗说明与剩余工作](guides/MINIBKN_QUERY_PLAN_EXPLANATION_AND_REMAINING_WORK.md)：查询计划、真实完成度和下一步。
6. [验收指南](ACCEPTANCE.md)：实际启动和验收。

只想知道“现在做到哪里”时，优先相信代码、自动化测试和最新最终验收报告，而不是较早路线规划。

## 2. 文档状态与冲突处理

| 类型 | 含义 |
| --- | --- |
| 当前事实 | 有代码或测试支撑，可用于验收，但要保留报告中的限制 |
| 当前计划 | 尚未全部实现的路线，不能当作已交付功能 |
| 专题说明 | 对某项功能或问题的解释 |
| 历史资料 | 用于理解演进，不作为最新状态依据 |

发生冲突时按此顺序判断：

> 当前代码与测试 → 最新最终验收 → 对应阶段报告 → 当前分步计划 → 早期规划和历史报告

## 3. 当前事实与验收入口

| 文档 | 解决的问题 | 状态 |
| --- | --- | --- |
| [架构说明](ARCHITECTURE.md) | 模块边界、依赖方向、主要链路 | 当前事实 |
| [验收指南](ACCEPTANCE.md) | 如何启动、演示和检查 | 当前事实 |
| [S3–S10 最终验收](reports/MINIBKN_S3_S10_LONG_HORIZON_ACCEPTANCE_REPORT.md) | 上一轮范围、测试和限制 | 历史总验收 |
| [S10 CRM 评测](reports/MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md) | 数据集、基线、指标和简历口径 | 当前事实 |
| [S4 QueryPlan 报告](reports/MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md) | 计划格式、校验、执行和 API | 当前事实 |
| [QueryPlan 通俗说明](guides/MINIBKN_QUERY_PLAN_EXPLANATION_AND_REMAINING_WORK.md) | 示例、准确边界和后续开发 | 当前专题说明 |
| [P0 查询智能与数据发现报告](reports/MINIBKN_P0_QUERY_INTELLIGENCE_AND_DATA_DISCOVERY_DEVELOPMENT_REPORT.md) | DeepSeek、歧义追问、键发现、BGE-M3 和最新测试 | **最新增强报告** |
| [全量测试最终验收](reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md) | 原 67 项后端、8 项前端及后续 71 项后端回归、真实模型、Ragas、性能与浏览器验收 | **最新总验收** |
| [全量测试通俗报告](reports/MINIBKN_COMPREHENSIVE_TEST_PLAIN_LANGUAGE_REPORT.md) | 面向非技术读者解释本轮结果 | **最新通俗报告** |
| [查询智能与完整评测](reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md) | 智能问答闭环、六项 Ragas、传统 RAG 对照与真实 Token | **最新专项评测** |
| [企业权限报告](reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md) | 用户、角色、文件、文档域和行动权限 | **0.6.0 当前事实** |
| [LightRAG 接入评测](reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md) | 真实 sidecar、入库、检索、路由与融合 | **0.6.0 当前事实** |
| [秋招项目完整说明](reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md) | 完整演进、困难、效果、价值与边界 | **最新总说明** |
| [0.6.0 最终验收](reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md) | 74 项测试、权限和真实 LightRAG 收尾验收 | **最新最终验收** |

## 4. 按功能查文档

### 整个项目

- [项目 README](../README.md)：最短入口。
- [非技术完整汇报](guides/MINIBKN_NON_TECHNICAL_FULL_REPORT.md)：面向非技术读者的完整介绍。
- [初次流程理解与答疑](guides/MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md)：表格、BKN、关系、检索、数据库和动作。
- [完整项目交接](handoffs/MINIBKN_PROJECT_HANDOFF_FOR_AI.md)：给其他 AI 或新开发者的全面背景。
- [秋招项目完整说明](reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md)：当前完整项目故事和证据口径。

### 通用业务建模和 AI 建模

- [S0 基线与领域契约](reports/MINIBKN_S0_BASELINE_CONTRACTS_DEVELOPMENT_REPORT.md)
- [S1 通用核心](reports/MINIBKN_S1_GENERIC_CORE_DEVELOPMENT_REPORT.md)
- [S7 AI 建模工作流](reports/MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md)
- [完整优化执行方案](plans/MINIBKN_COMPREHENSIVE_EXECUTION_PLAN.md)

S2 第一轮已经实现字段剖析、组合主键和外键候选；专门的候选接受/拒绝 API 与 UI 仍待补充。

### 检索、Embedding 和 QueryPlan

- [S3 Embedding 报告](reports/MINIBKN_S3_EMBEDDING_DEVELOPMENT_REPORT.md)
- [S4 QueryPlan 报告](reports/MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md)
- [QueryPlan 通俗说明](guides/MINIBKN_QUERY_PLAN_EXPLANATION_AND_REMAINING_WORK.md)
- [S10 CRM 评测](reports/MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md)
- [查询智能与完整评测](reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)

硅基流动 BGE-M3 和 DeepSeek 已完成真实评测。最新未调优 60 题 QueryPlan 冻结集精确准确率为 93.33%，组件准确率为 97.52%；6 题对抗集为 83.33%。

### 动作、安全和风险控制

- [S5 风险 DSL 报告](reports/MINIBKN_S5_RISK_DSL_DEVELOPMENT_REPORT.md)
- [S0 基线与领域契约](reports/MINIBKN_S0_BASELINE_CONTRACTS_DEVELOPMENT_REPORT.md)
- [S10 CRM 评测](reports/MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md)
- [企业权限报告](reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md)

当前已实现本地策略文件 RBAC，但不等于完整企业 SSO/IAM；QueryPlan 中的动作也不会绕过风险链路直接执行。

### 增量更新

- [S6 增量构建报告](reports/MINIBKN_S6_INCREMENTAL_BUILD_DEVELOPMENT_REPORT.md)
- [分步开发计划](plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)

### 非结构化文档和 LightRAG

- [S8 文档知识接口报告](reports/MINIBKN_S8_DOCUMENT_KNOWLEDGE_INTERFACE_DEVELOPMENT_REPORT.md)
- [评测与 LightRAG 专项规划](plans/MINIBKN_EVALUATION_LIGHTRAG_FEASIBILITY_AND_ROADMAP.md)
- [LightRAG 接入与评测](reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md)

LightRAG 1.5.6 已通过 REST sidecar 实际接入；默认仍关闭。真实 `crm/public` 工作区完成 3 份文档索引和 3/3 检索，安全域隔离通过适配器自动化测试。

### UI

- [S9 控制台报告](reports/MINIBKN_S9_CONTROL_ROOM_UI_DEVELOPMENT_REPORT.md)
- [UI 自动化与真实浏览器验收](reports/MINIBKN_UI_BROWSER_ACCEPTANCE_REPORT.md)
- [验收指南](ACCEPTANCE.md)

### 评测和简历数字

- [S10 CRM 评测](reports/MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md)
- [检索与 Ragas 真实评测](reports/MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md)
- [性能、韧性与安全报告](reports/MINIBKN_PERFORMANCE_RESILIENCE_SECURITY_REPORT.md)
- [全量测试最终验收](reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md)
- [查询智能与完整评测](reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)
- [S3–S10 最终验收](reports/MINIBKN_S3_S10_LONG_HORIZON_ACCEPTANCE_REPORT.md)
- [评测与 LightRAG 专项规划](plans/MINIBKN_EVALUATION_LIGHTRAG_FEASIBILITY_AND_ROADMAP.md)

简历必须标明评测口径。200 题 ID Context Precision@5 仍为 0.14；独立 30 题 Faithfulness 为 0.9261。新的传统 RAG 对照在 30 道冻结 QueryPlan 多跳/聚合题上测得输入 Token 减少 66.78%，不能外推为所有查询的统一降幅。

## 5. 当前开发计划

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [完整优化执行方案](plans/MINIBKN_COMPREHENSIVE_EXECUTION_PLAN.md) | 11 项优化的总体目标 | 当前总体计划，部分已实现 |
| [分步开发计划](plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md) | S0–S10 依赖、状态和验收 | **当前实施台账** |
| [评测与 LightRAG 专项规划](plans/MINIBKN_EVALUATION_LIGHTRAG_FEASIBILITY_AND_ROADMAP.md) | 评测深化和文档分支 | 当前专题计划，LightRAG 未实施 |
| [全量测试与评测执行计划](plans/MINIBKN_COMPREHENSIVE_TEST_AND_EVALUATION_PLAN.md) | 多行业数据、盲测、真实模型、Ragas、性能、安全和 UI 验收 | **已完成** |
| [查询智能与完整评测执行计划](plans/MINIBKN_QUERY_INTELLIGENCE_AND_EVALUATION_EXECUTION_PLAN.md) | 智能问答闭环、六指标 Ragas 和传统 RAG 对照 | **已完成** |
| [综合执行方案大白话解读](plans/综合执行方案大白话解读.md) | 总计划通俗版 | 辅助说明 |
| [综合执行方案中文解读](plans/综合执行方案中文解读.md) | 总计划中文详解 | 辅助说明 |

## 6. 开发报告：按时间阅读

### 第一轮：Python 主流程复现（历史）

1. [阶段 A](reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_A.md)
2. [阶段 B](reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md)
3. [阶段 C](reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md)
4. [阶段 D](reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md)
5. [早期最终验收](reports/MINIBKN_FINAL_ACCEPTANCE_REPORT.md)

这一组记录从零到一的过程。判断当前能力时，应继续看第二轮最终验收。

### 第二轮：通用化和 S3–S10

1. [S0 基线与领域契约](reports/MINIBKN_S0_BASELINE_CONTRACTS_DEVELOPMENT_REPORT.md)
2. [S1 通用核心](reports/MINIBKN_S1_GENERIC_CORE_DEVELOPMENT_REPORT.md)
3. [P0/S2 查询智能与数据发现](reports/MINIBKN_P0_QUERY_INTELLIGENCE_AND_DATA_DISCOVERY_DEVELOPMENT_REPORT.md)
4. [S3 Embedding](reports/MINIBKN_S3_EMBEDDING_DEVELOPMENT_REPORT.md)
5. [S4 QueryPlan](reports/MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md)
6. [S5 风险 DSL](reports/MINIBKN_S5_RISK_DSL_DEVELOPMENT_REPORT.md)
7. [S6 增量构建](reports/MINIBKN_S6_INCREMENTAL_BUILD_DEVELOPMENT_REPORT.md)
8. [S7 AI 建模](reports/MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md)
9. [S8 文档接口](reports/MINIBKN_S8_DOCUMENT_KNOWLEDGE_INTERFACE_DEVELOPMENT_REPORT.md)
10. [S9 控制台](reports/MINIBKN_S9_CONTROL_ROOM_UI_DEVELOPMENT_REPORT.md)
11. [S10 CRM 评测](reports/MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md)
12. [S3–S10 最终验收](reports/MINIBKN_S3_S10_LONG_HORIZON_ACCEPTANCE_REPORT.md)
13. [多行业测试数据集开发报告](reports/MINIBKN_ENTERPRISE_TEST_DATASET_DEVELOPMENT_REPORT.md)
14. [确定性测试基础报告](reports/MINIBKN_DETERMINISTIC_TEST_FOUNDATION_REPORT.md)
15. [QueryPlan 盲测与对抗评测](reports/MINIBKN_QUERY_PLAN_BLIND_AND_ADVERSARIAL_EVALUATION_REPORT.md)
16. [检索与 Ragas 真实评测](reports/MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md)
17. [性能、韧性与安全](reports/MINIBKN_PERFORMANCE_RESILIENCE_SECURITY_REPORT.md)
18. [UI 自动化与真实浏览器验收](reports/MINIBKN_UI_BROWSER_ACCEPTANCE_REPORT.md)
19. [全量测试最终验收](reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md)
20. [全量测试通俗报告](reports/MINIBKN_COMPREHENSIVE_TEST_PLAIN_LANGUAGE_REPORT.md)
21. [查询智能与完整评测](reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)
22. [企业权限管控](reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md)
23. [LightRAG 接入与评测](reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md)
24. [秋招项目完整说明](reports/MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md)
25. [0.6.0 最终验收](reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md)

## 7. 问答和学习资料

- [技术细节专题导航](technical_deep_dive/README.md)：按源码核对的 UI、运行、建模、权限、查询、检索与动作说明，以及完整财务案例。
- [财务工时与薪酬完整案例](technical_deep_dive/09_PAYROLL_END_TO_END_CASE_STUDY.md)：通过员工、工时、工价、奖金和制度文档，逐步串联整个项目流程及当前实现边界。
- [完整评估体系与结果](technical_deep_dive/10_EVALUATION_SYSTEM_DATASETS_AND_RESULTS.md)：解释各数据集、指标、对照实验、原始结果和不能外推的边界。
- [QueryPlan 与 AI 建模面试说明](technical_deep_dive/11_QUERYPLAN_AND_AI_MODELING_INTERVIEW_GUIDE.md)：如何准确介绍两项核心能力，以及常见技术追问。
- [初次流程理解与答疑](guides/MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md)
- [8 个核心问题](guides/qa/MINIBKN_8_QUESTIONS_ANSWER.md)
- [10 个核心问题第二部分](guides/qa/MINIBKN_10_QUESTIONS_ANSWER_PART2.md)
- [5 个核心问题第三部分](guides/qa/MINIBKN_5_QUESTIONS_ANSWER_PART3.md)
- [6 个核心问题第四部分](guides/qa/MINIBKN_6_QUESTIONS_ANSWER_PART4.md)
- [QueryPlan 通俗说明](guides/MINIBKN_QUERY_PLAN_EXPLANATION_AND_REMAINING_WORK.md)

技术细节专题中的工时薪酬案例明确区分了现有文件级 RBAC 与尚未实现的行级/字段级权限；查询路由文档也明确区分 `/ask-intelligent` 和 `/ask-routed`，应优先用于准备技术追问。

## 8. AI 和开发者交接

- [全项目代码与文档总交接](handoffs/MINIBKN_COMPLETE_REPOSITORY_HANDOFF_FOR_AI.md)：**首选总入口**；代码目录、前端、配置、脚本、测试、评测资产、全部文档和功能反向索引。
- [完整项目交接](handoffs/MINIBKN_PROJECT_HANDOFF_FOR_AI.md)：较早综合交接，保留作历史补充。
- [全量测试与评测交接](handoffs/MINIBKN_COMPREHENSIVE_EVALUATION_HANDOFF_FOR_AI.md)：本轮测试范围、真实数字、原始结果和限制。
- [查询智能与完整评测交接](handoffs/MINIBKN_QUERY_INTELLIGENCE_AND_EVALUATION_HANDOFF_FOR_AI.md)：智能问答、六项 Ragas 和传统 RAG Token 对照的事实与结果入口。
- [秋招项目资料交接](handoffs/MINIBKN_AUTUMN_RECRUITMENT_PROJECT_HANDOFF_FOR_AI.md)：供其他 AI 理解完整项目、代码和结果文件。
- 项目与用户背景（私人学习资料，未公开）
- 早期讲解任务背景（私人学习资料，未公开）：历史补充。

其他 AI 接手时，建议先读取“全项目代码与文档总交接”，再读取最新最终验收和将要修改模块的专题文档与测试。

## 9. 历史规划资料

- [原始复现方案与进度](plans/MINIBKN_REPRODUCTION_PLAN.md)
- [早期优化路线图](plans/MINIBKN_OPTIMIZATION_ROADMAP.md)
- [早期最终验收](reports/MINIBKN_FINAL_ACCEPTANCE_REPORT.md)
- 阶段 A–D 报告

这些文件记录决策过程，但不是判断当前状态的首选资料。

## 10. 文档维护规则

1. 总体路线优先更新现有“完整优化执行方案”，避免再建同类总计划。
2. 每个模块完成后更新分步计划，并增加对应产品开发报告。
3. 最新总验收必须汇总测试、限制、未完成项和复现命令。
4. 已实现能力必须有代码或测试依据；计划能力明确标注未实现或接口预留。
5. 评测数字记录数据版本、模型、配置、代码版本和原始结果。
6. API Key、密码、令牌和个人隐私不得写入 Markdown。
7. 新增、移动或改名文档后同步更新本导航。
