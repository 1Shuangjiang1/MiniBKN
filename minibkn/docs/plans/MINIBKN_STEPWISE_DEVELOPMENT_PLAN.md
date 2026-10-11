> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 分步开发计划

> 版本：v2.0\
> 日期：2026-08-17\
> 上位方案：[通用化与 AI 全流程增强项目执行方案](MINIBKN_COMPREHENSIVE_EXECUTION_PLAN.md)\
> 用途：后续开发期间持续参考和更新的执行台账。

> S3–S10 最终验收：[长程开发最终验收报告](../reports/MINIBKN_S3_S10_LONG_HORIZON_ACCEPTANCE_REPORT.md)

## 1. 开发目标

把当前 0.4.0 供应链演示版逐步升级为通用企业业务知识引擎。每一步必须形成可运行的纵向结果，不能只留下接口或无法验证的半成品。

## 2. 固定开发规则

每一步按照同一流程执行：

1. 阅读本计划、上一步开发报告和相关代码；
2. 写出本步验收条件及失败测试；
3. 实现最小完整链路，并保持 `/api/v1` 向后兼容；
4. 运行单元、集成、格式和类型检查；
5. 写本步产品开发报告，记录实现、使用方式、测试、限制和下一步接口；
6. 从第二步开始，报告必须引用并核对上一步的交付；
7. 未经真实评测，不在报告或简历中填写效果提升数字。

报告统一保存在 `docs/reports/`，文件名使用 `MINIBKN_S{编号}_{主题}_DEVELOPMENT_REPORT.md`。

## 3. 分步路线与状态

| 步骤 | 模块 | 核心交付 | 依赖 | 状态 |
| --- | --- | --- | --- | --- |
| S0 | 基线与领域契约 | Evidence、QueryPlan、建模提案、BKN 版本、BuildJob/ChangeSet；CRM 最小样例；契约测试 | 0.4.0 | 已完成（2026-08-16） |
| S1 | 通用核心 | 删除供应链专属回答逻辑；证据驱动通用回答；扩展基础业务类型；最小版本状态 | S0 | 已完成（2026-08-16） |
| S2 | 数据发现与键关系 | 数据剖析、组合主键、外键候选、评分、可审核结果 | S1 | 已完成第一轮（2026-08-17） |
| S3 | 真实 Embedding | 硅基流动适配、批处理、缓存、索引版本、BM25 降级 | S1 | 已完成并通过真实 BGE-M3 冒烟（2026-08-17） |
| S4 | QueryPlan 执行 | LLM 计划生成、改写/子问题/歧义追问、白名单、执行 | S0、S1、S3 | 已增强并通过 DeepSeek 评测（2026-08-17） |
| S5 | 风险与动作 | 安全风险 DSL、模拟、审批、权限、幂等和审计 | S0、S4 | 已完成（2026-08-16） |
| S6 | 增量构建 | 指纹、变更集、依赖影响、局部图和索引更新、版本切换 | S0、S2、S3 | 已完成（2026-08-16） |
| S7 | AI 建模工作流 | 自然语言建模、提案审核、动作/风险建议、漂移解释 | S0、S2、S5 | 已完成（2026-08-16） |
| S8 | 文档知识接口预留 | 文档知识端口、禁用适配器、路由与统一证据契约；不安装 LightRAG | S0、S4 | 接口已完成，LightRAG 实现已跳过（2026-08-16） |
| S9 | 简单 UI | 数据源、AI 建模、网络、问答、动作风险、评测六页 | S4–S8 | 已完成（2026-08-16） |
| S10 | 正式评测 | CRM/动作/文档冻结集、基线、Ragas、Token、延迟、报告 | 各被评模块 | 已完成（2026-08-16） |

## 4. S0 验收条件

开发报告：[S0 基线与领域契约产品开发报告](../reports/MINIBKN_S0_BASELINE_CONTRACTS_DEVELOPMENT_REPORT.md)

- 新领域契约是冻结、禁止多余字段的 Pydantic 模型；
- QueryPlan 能表达检索、过滤、关系跳转、聚合、排序、限制和证据预算；
- Evidence 能统一表示 Schema、实例、关系、动作、计算和文档证据；
- 建模提案有类型、置信度、证据和审核状态；
- BKN 版本有草稿、已审核、已批准、已发布状态；
- ChangeSet 能表达新增、更新、删除，BuildJob 有明确状态；
- 增加 CRM 最小样例，证明契约不依赖供应链；
- 原 13 项测试保持通过，新契约测试通过。

## 5. S1 验收条件

开发报告：[S1 通用核心产品开发报告](../reports/MINIBKN_S1_GENERIC_CORE_DEVELOPMENT_REPORT.md)

- `RetrievalService` 中不再出现库存、供应商等领域专属判断；
- 回答只使用本次召回和子图中的证据，不扫描全库后偷偷回答；
- `AskResult` 兼容原字段，并新增结构化 `evidence`；
- 供应链与 CRM 都能通过同一套回答器完成问答；
- 日期、时间、Decimal 和 JSON 值能规范化为可持久化的数据；
- 当前导入语义明确为发布版，网络响应显示生命周期状态；
- 第二步报告引用第一步契约报告，并说明复用关系；
- 全量测试、Ruff 和 Mypy 通过。

## 6. 后续更新方法

P0 增强报告：[查询智能与数据发现产品开发报告](../reports/MINIBKN_P0_QUERY_INTELLIGENCE_AND_DATA_DISCOVERY_DEVELOPMENT_REPORT.md)

S6 开发报告：[S6 增量构建产品开发报告](../reports/MINIBKN_S6_INCREMENTAL_BUILD_DEVELOPMENT_REPORT.md)

S7 开发报告：[S7 AI 辅助建模工作流产品开发报告](../reports/MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md)

S8 开发报告：[S8 文档知识接口预留产品开发报告](../reports/MINIBKN_S8_DOCUMENT_KNOWLEDGE_INTERFACE_DEVELOPMENT_REPORT.md)

S9 开发报告：[S9 轻量控制台产品开发报告](../reports/MINIBKN_S9_CONTROL_ROOM_UI_DEVELOPMENT_REPORT.md)

S10 开发报告：[S10 CRM 正式评测产品开发报告](../reports/MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md)

每完成一步：

- 把状态改为“已完成（日期）”；
- 在该步骤下补充实际报告链接；
- 如果设计发生变化，记录原因，不覆盖历史结论；
- 下一步开始前，先检查前一步“遗留限制”是否成为阻塞项。
