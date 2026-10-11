> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN S10 CRM 正式评测产品开发报告

> 完成日期：2026-08-16\
> 前置报告：[S9 轻量控制台产品开发报告](MINIBKN_S9_CONTROL_ROOM_UI_DEVELOPMENT_REPORT.md)\
> 对应计划：[分步开发计划](../plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)\
> 状态：已完成

## 1. 与 S9 的衔接

S9 的评测页只负责读取真实报告。S10 新增 `GET /api/v1/evaluations/latest`，直接返回磁盘上最近一次完整 JSON；如果还没有报告就返回 404，而不是给界面填默认数字。

## 2. 冻结数据集

本次不再使用早期“5 个供应链实体反复改写”的 200 题。新 CRM 数据由固定 seed `20260816` 生成，因此任何人都能得到完全相同的数据和标签：

| 数据 | 数量 |
| --- | ---: |
| 客户 | 500 |
| 订单 | 2,500 |
| 订单明细 | 6,000 |
| 产品 | 120 |
| 销售人员 | 20 |
| 业务对象合计 | 9,140 |
| 关系边 | 15,000 |

200 个问题冻结为：70 个单对象查询、70 个订单到客户的关联查询、60 个条件过滤/聚合。另有 30 个动作安全题，allow、confirm、deny 各 10 个。

它仍然是“贴近真实业务分布的确定性合成数据”，不应描述成来自某家真实公司的生产数据。

## 3. 对比对象

- B0：BM25 词法检索；
- B1：token-hashing 向量编排基线；它只验证向量通道，明确不是语义 Embedding；
- B2：BM25 + token-hashing + RRF；
- B3：Reranker 尚未实现，不报告数字；
- B4：在 130 个已冻结、已验证 QueryPlan 上测安全执行器，包括 70 个关系跳转和 60 个过滤/聚合。

当前未提供硅基流动 API Key，所以没有把远程语义模型混进离线基线。拿到 Key 后应保留同一数据集重新跑 B1/B2，才可以比较真实 Embedding 的收益。

## 4. 真实检索结果

Top-5 端到端结果如下：

| 基线 | Hit@1 | Hit@5 | MRR | 标注 Context Precision@5 | 标注 Context Recall@5 | P50 | P95 | 平均上下文 Token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 | 837.08ms | 1344.47ms | 78.25 |
| 哈希向量 | 0.035 | 0.125 | 0.0673 | 0.025 | 0.1225 | 795.12ms | 964.40ms | 71.22 |
| RRF 混合 | 0.355 | 0.535 | 0.4185 | 0.107 | 0.4425 | 780.86ms | 972.38ms | 83.32 |

结论不是“混合一定更好”。在这个以精确订单号、客户号和结构化字段为主的数据集上，BM25 明显最好；哈希向量没有语义能力，混入 RRF 后反而拖累 BM25。这组数字证明 S3 接入真实 Embedding 的必要性，也阻止项目把哈希基线包装成模型能力。

## 5. QueryPlan 与动作安全

| 模块 | 样本 | 结果 | P50 | P95 |
| --- | ---: | ---: | ---: | ---: |
| QueryPlan 安全执行 | 130 | Exact Accuracy = 1.000 | 606.05ms | 648.02ms |
| 动作风险模拟 | 30 | Decision Accuracy = 1.000 | — | — |

QueryPlan 的 1.0 只说明：给定冻结且合法的结构化计划后，过滤、聚合和关系跳转执行正确。它不代表 LLM 从自然语言生成 QueryPlan 的准确率；当前没有 LLM Key，所以没有测这项能力。

动作评测没有执行真实工具，side effects 为 0。10 个普通订单返回 allow，10 个大额订单返回 confirm，10 个已取消订单返回 deny。

## 6. Ragas、Faithfulness 与 Token

实际安装并运行 Ragas 0.4.3 的 `IDBasedContextPrecision`，Top-5 结果为：

- BM25：0.140；
- 哈希向量：0.025；
- RRF 混合：0.107。

它与本地标注 Context Precision 完全一致，说明指标可复算。Faithfulness 需要独立 evaluator LLM；当前 API Key 未配置，所以报告保持 `null` 和明确的 skipped 原因。

本轮回答链路是抽取式，不调用回答 LLM，因此 LLM input/output token 都是 0。报告中的平均上下文 Token 使用 MiniBKN 与检索一致的 tokenizer 对 Top-5 证据计数，不是供应商账单 Token。没有公平的“三层上下文对照组”，所以本阶段不声称“Token 降低 36%”。

## 7. 性能解读

当前 9,146 条索引文档下 P50 接近 0.8 秒。原因之一是 `HybridRetriever.search` 每个请求都会重新分词整库、计算文档频次和平均长度；即使请求纯 vector，也会同时计算 BM25 和向量排序。

后续性能优化应包括：

- 构建索引时缓存 token、文档频次和平均长度；
- 按搜索模式只执行必要通道；
- 用向量数据库或 ANN 替换全量余弦排序；
- 给 QueryPlan 建对象类型和字段索引，避免每次扫描 9,140 对象；
- 优化后必须在同一冻结集重跑，旧结果不得覆盖。

## 8. 可复现命令与结果位置

```powershell
.venv\Scripts\python.exe scripts\generate_crm_benchmark.py
.venv\Scripts\python.exe scripts\evaluate_crm.py
uv sync --extra dev --extra evaluation --no-editable --reinstall-package minibkn
.venv\Scripts\python.exe scripts\evaluate_ragas.py
```

- 冻结问题：`evals/datasets/crm_200.jsonl`；
- 动作题：`evals/datasets/crm_actions_30.jsonl`；
- 数据与 BKN：`evals/crm/`；
- 原始完整排名：`evals/results/crm-20260816-124843-683506.json`；
- Ragas 结果：`evals/results/crm-ragas-20260816-130058-755217.json`；
- UI/API 当前读取：`evals/results/latest.json`。

## 9. 对简历目标的结论

现在可以有证据地写“构建 9,140 对象 CRM 合成业务集、200 查询与 30 动作安全题，完成 BM25/向量编排/RRF/QueryPlan 端到端评测”。

暂时不能写参考材料中的 Context Precision 0.51→0.78、Faithfulness 0.81→0.89 或 Token 降低 36%，因为本轮数据、指标口径和模型条件不支持这些数字。下一轮配置真实 Embedding 与 evaluator LLM 后，再使用同一冻结集产生可比较结果。
