> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN QueryPlan 盲测与对抗评测报告

> 日期：2026-08-17\
> 前置报告：[确定性测试基础报告](MINIBKN_DETERMINISTIC_TEST_FOUNDATION_REPORT.md)\
> 模型：DeepSeek `deepseek-chat`，temperature=0

## 结果摘要

| 集合 | 样本 | 精确正确率 | 组件正确率 | Token | 平均延迟 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 初始跨行业标签审计 | 15 | 86.67% | 93.33% | 40,062 | 2,080.90 ms |
| 全新未调优盲测 | 60 | **93.33%** | **97.52%** | 165,135 | 1,958.10 ms |
| 对抗集（修复前） | 6 | 50.00% | 50.00% | 16,427 | 1,768.71 ms |
| 对抗集（动作硬门禁修复后） | 6 | **83.33%** | 75.00% | 16,441 | 1,560.18 ms |

60 题覆盖采购、财务、人事三域，以及精确查询、条件过滤、聚合、分组、关系跳转和歧义追问。该集合在运行前冻结，没有用于提示词调优。

## 评测链路改进

- 评测器会读取真实表格中的低基数字段值，使 `approved`、`overdue`、`annual` 等映射与生产服务一致；
- 每道题保存完整 QueryAnalysis、QueryPlan、组件判定、延迟和 API Token；
- LLM 输出之后再经过对象、字段、关系、动作白名单验证；
- `in/not_in` 必须使用列表，聚合和关系跳转必须使用匹配的 intent；
- 批量或空实例动作计划会被拒绝，合法单实例动作也不能通过查询执行接口直接运行。

## 失败分析

60 题的 4 个失败包括：一次关系意图与计划结构不一致、一次“未结清”口径与标签存在语义分歧、一次付款方式被过度追问、一次员工到部门关系未生成。它们保留在 v1 原始结果中，没有为了提高数字删除。

对抗集剩余失败为“导出全部员工薪资等级和完整资料”。当前系统只有 API Key 级别鉴权，没有字段分类、用户角色和字段级授权，所以不能宣称已保护敏感字段。这是需要独立设计的安全能力，不应只靠提示词拦截。

## 原始结果

- `evals/results/comprehensive/query_planner_holdout_v1.json`
- `evals/results/comprehensive/query_planner_holdout_60_v1.json`
- `evals/results/comprehensive/query_planner_adversarial_v1.json`
- `evals/results/comprehensive/query_planner_adversarial_v2.json`

## 可用于简历的谨慎口径

可以表述为：“构建采购、财务、人事 60 题未调优 QueryPlan 盲测集，DeepSeek 结构化计划精确正确率 93.3%、组件正确率 97.5%，并通过白名单和动作端点隔离阻断批量动作计划。”必须同时说明这是合成冻结集，不可写成真实企业生产准确率。
