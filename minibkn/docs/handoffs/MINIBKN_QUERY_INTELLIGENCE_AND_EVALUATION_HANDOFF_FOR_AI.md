> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 查询智能与评测交接文档

> 完成日期：2026-08-17\
> 用途：提供本轮功能、实验、结果和文件入口的事实背景。

## 1. 本轮完成的工作

- 新增统一智能问答接口 `/api/v1/networks/{network_id}/ask-intelligent`；
- 将问题改写、关键词、同义词、子问题、歧义和追问答案接入完整问答流程；
- 结构化问题由 QueryPlan 执行，相关性问题使用扩展后的查询检索；
- 动作意图在智能问答入口不执行，仍需风险模拟和审批；
- 规则降级器返回真正的同义词候选，而不是只返回命中的原词；
- 聚合计算证据改为首位自然语言证据；
- 新增传统 RAG 与 MiniBKN 的 Token/质量对照程序；
- 新增六项生成式 Ragas 诊断；
- 保留优化前后和参考答案修正前后的原始结果。

## 2. 查询智能已有证据

此前已经完成的独立盲测：

- 数据集：`evals/datasets/enterprise_query_planner_holdout_60.jsonl`；
- 原始结果：`evals/results/comprehensive/query_planner_holdout_60_v1.json`；
- 完全正确率：93.33%；
- 组件准确率：97.52%；
- 包含采购、财务、人事和歧义追问。

本轮新增入口相关代码：

- `src/minibkn/application/query_plan_service.py`
- `src/minibkn/api/schemas.py`
- `src/minibkn/api/routes.py`
- `src/minibkn/main.py`

相关测试：

- `tests/integration/test_query_plan_api.py`
- `tests/unit/test_query_planner_adapter.py`

## 3. Token 对照实验

传统 RAG：BGE-M3 + BM25 混合检索 Top-20，不使用 QueryPlan。\
MiniBKN：冻结 QueryPlan 经过确定性过滤、遍历和聚合后提供必要证据。\
两者使用同一问题、数据库、DeepSeek 回答模型和提示词。

样本：30 题，其中多跳 15 题、过滤聚合 15 题。

| 指标 | 传统 RAG | MiniBKN |
| --- | ---: | ---: |
| 平均输入 Token | 844.07 | 280.40 |
| 平均总 Token | 945.47 | 355.87 |
| 参考证据覆盖率 | 0.25 | 1.00 |

- 输入 Token 减少：66.78%；
- 总 Token 减少：62.36%；
- 冻结 QueryPlan 结构化执行正确率：30/30。

原始结果：`evals/results/comprehensive/token/rag_vs_bkn_token_30.json`。

## 4. Ragas 指标

现有三组评测需要分开看：

1. 200 题 ID Context Precision/Recall：`evals/results/comprehensive/ragas/bge_m3_faithfulness_30.json` 的 `id_metrics`；
2. 30 题 Faithfulness：同一文件的 `faithfulness`，均值 0.9261；
3. 10 题六指标传统 RAG/MiniBKN 对照：`evals/results/comprehensive/ragas/rag_vs_bkn_full_metrics_10.json`。

10 题对照结果：

| 指标 | 传统 RAG | MiniBKN |
| --- | ---: | ---: |
| Faithfulness | 0.9650 | 0.9000 |
| Factual Correctness | 0.2760 | 0.9000 |
| Answer Relevancy | 0.7745 | 0.8866 |
| LLM Context Precision | 0.4000 | 0.9583 |
| LLM Context Recall | 0.2000 | 1.0000 |
| Noise Sensitivity | 0.3231 | 0.1000 |

Noise Sensitivity 越低越好，其他指标越高越好。全部指标 10/10 成功。

Factual Correctness 的 0.276/0.900 来自自然语言 gold 修正后的重评：

- `evals/results/comprehensive/ragas/rag_vs_bkn_factual_correctness_rescore_10.json`

第一次机器字段形式 gold 的结果仍在：

- `evals/results/comprehensive/ragas/rag_vs_bkn_full_metrics_10.json`

其中 Factual Correctness 为传统 RAG 0.313、MiniBKN 0.600。其他五项使用该文件的结果。

## 5. 优化过程

第一次 2 题冒烟发现聚合计算证据位于末尾且内容为 Python 字典字符串，MiniBKN Faithfulness 为 0.5。代码调整后计算证据位于首位并使用自然语言，2 题复测的 Faithfulness、Context Precision、Context Recall 均为 1.0。

文件：

- 优化前：`evals/results/comprehensive/ragas/rag_vs_bkn_smoke_2.json`
- 优化后：`evals/results/comprehensive/ragas/rag_vs_bkn_smoke_2_v2.json`

## 6. 应查看的文档

- 完整开发与结果：[查询智能与完整评测产品开发报告](../reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)
- 执行方案：[查询智能与完整评测执行计划](../plans/MINIBKN_QUERY_INTELLIGENCE_AND_EVALUATION_EXECUTION_PLAN.md)
- 旧 Ragas 结果：[检索与 Ragas 真实评测](../reports/MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md)
- QueryPlan 既有实现：[P0 查询智能与数据发现](../reports/MINIBKN_P0_QUERY_INTELLIGENCE_AND_DATA_DISCOVERY_DEVELOPMENT_REPORT.md)
- QueryPlan 盲测：[QueryPlan 盲测与对抗评测](../reports/MINIBKN_QUERY_PLAN_BLIND_AND_ADVERSARIAL_EVALUATION_REPORT.md)
- 文档总入口：[MiniBKN 文档总导航](../MINIBKN_DOCUMENTATION_NAVIGATION.md)

## 7. 结果边界

- Token 对照使用冻结 QueryPlan，不代表自然语言规划 100% 正确；
- Token 样本为 30 题 CRM 多跳和聚合题；
- 六项生成式 Ragas 样本为 10 题；
- Faithfulness 新对照中 MiniBKN 没有超过传统 RAG；
- LLM 裁判存在波动；
- `/ask-intelligent` 已有后端 API，React 控制台尚未增加追问界面；
- LightRAG、企业 RBAC 和字段级权限仍未完成；
- 本轮没有提交、推送或创建 PR。

## 8. 最终自动化状态

- 后端测试：71 项通过；
- 行覆盖率：89%，3,289 / 3,686 行；
- Ruff format/check：通过；
- Mypy strict：64 个源文件通过；
- 53 份 Markdown：0 个失效本地链接；
- 445 个非虚拟环境文件：0 个真实密钥内容匹配。
