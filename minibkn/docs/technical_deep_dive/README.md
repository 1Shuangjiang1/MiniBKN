> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 技术细节专题导航

> 核对日期：2026-08-18\
> 适用版本：MiniBKN 0.6.0\
> 用途：回答本项目 UI、启动、数据建模、权限、查询、检索和动作安全的技术细节；供本人复习或其他 AI 继续解读。

## 先说清楚三种标记

- **已实现**：当前代码与自动化测试中真实存在。
- **演示级**：链路可运行，但不等于企业生产系统已经具备同等级能力。
- **待增强**：本文为了完整解释现实场景提出的合理设计，当前代码尚未实现。

这三个标记非常重要。例如当前 RBAC 已能限制网络、文件、文档集合和动作，但还没有“员工只能看自己那几行工资数据”的行级权限；不能把后者当成已经交付。

## 八个问题与一个完整案例

1. [UI 框架、复杂度与面试表述](01_UI_FRAMEWORK_AND_INTERVIEW_POSITIONING.md)
2. [启动方法与功能测试案例](02_STARTUP_AND_FUNCTIONAL_TEST_CASES.md)
3. [数据导入、索引构建与工时薪酬案例](03_IMPORT_INDEX_AND_PAYROLL_SCENARIO.md)
4. [认证层与 RBAC 内部原理](04_AUTHENTICATION_AND_RBAC_INTERNALS.md)
5. [查询理解层到知识路由的内部原理](05_QUERY_UNDERSTANDING_AND_ROUTING_INTERNALS.md)
6. [结构化分支逐步解析](06_STRUCTURED_BRANCH_INTERNALS.md)
7. [动作权限与风险判定原理](07_ACTION_AUTHORIZATION_AND_RISK_INTERNALS.md)
8. [大模型如何识别动作意图](08_ACTION_INTENT_DECISION_INTERNALS.md)
9. [财务工时与薪酬端到端完整案例](09_PAYROLL_END_TO_END_CASE_STUDY.md)
10. [完整评估体系、数据集与真实结果](10_EVALUATION_SYSTEM_DATASETS_AND_RESULTS.md)
11. [QueryPlan 与 AI 辅助 BKN 建模面试说明](11_QUERYPLAN_AND_AI_MODELING_INTERVIEW_GUIDE.md)

## 建议同时查看的现有资料

- [项目架构](../ARCHITECTURE.md)
- [验收指南](../ACCEPTANCE.md)
- [0.6.0 最终验收](../reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md)
- [企业权限开发报告](../reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md)
- [LightRAG 接入评测](../reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md)
- [QueryPlan 与完整评测](../reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)

## 给后续阅读者的事实边界

当前系统是 Python/FastAPI 模块化单体，React 控制台直接访问 HTTP API；SQLite 保存网络、图、索引和执行记录；LightRAG 是可选 sidecar。默认不开 LLM、真实 Embedding、RBAC 和 LightRAG，也能完成离线结构化演示。生产 SSO、行级/字段级权限、持久化向量数据库、通用外部业务写入工具，以及把 QueryPlan 与 LightRAG 路由合成一个总编排器，仍属于后续工程化范围。
