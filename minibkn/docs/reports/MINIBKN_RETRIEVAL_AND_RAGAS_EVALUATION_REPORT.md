> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 检索与 Ragas 真实评测报告

> 评测日期：2026-08-17\
> 数据规模：CRM 9,150 个可检索文档，200 个检索问题\
> 外部模型：硅基流动 `BAAI/bge-m3`（1024 维）、DeepSeek `deepseek-chat`

## 1. 本阶段完成了什么

本阶段把原来的离线哈希向量基线，扩展为三组可复现实验：

1. BM25 关键词检索；
2. 哈希向量与哈希混合检索；
3. 真实 BGE-M3 向量与 BGE-M3 混合检索。

随后用 Ragas 0.4.3 对全部 200 题计算基于文档 ID 的 Context Precision / Recall，并对分层抽样的 30 题实际调用 `/ask`，再用 DeepSeek 逐条核验回答是否忠于证据。

## 2. 检索结果

| 方案 | Hit@1 | Hit@5 | MRR | Context Precision@5 | Context Recall@5 | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 | 32.73 ms |
| 哈希向量 | 0.035 | 0.125 | 0.067 | 0.025 | 0.123 | 95.61 ms |
| 哈希混合 | 0.355 | 0.535 | 0.419 | 0.107 | 0.443 | 101.78 ms |
| BGE-M3 向量 | 0.515 | 0.625 | 0.565 | 0.125 | 0.483 | 957.00 ms |
| BGE-M3 混合 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 | 431.51 ms |

结论：真实 Embedding 相比哈希向量有实质提升，向量 Hit@1 提高 48 个百分点，Hit@5 提高 50 个百分点。当前数据集包含大量订单号、客户号等精确标识符，因此 BM25 本身非常强，BGE-M3 混合检索追平 BM25，但没有超过它。这是有效的负结论，不能把它包装成“混合检索全面优于 BM25”。

## 3. Ragas Faithfulness

正式结果：

- 分层样本：30 题，覆盖单实体、多跳、过滤与聚合；
- 成功评分：30/30；
- Faithfulness 平均值：**0.9261**；
- 最低值：**0.8148**；
- 评测失败：0。

聚合问题可能关联上千条数据库记录。评测器把可送入裁判模型的证据固定限制为前 20 条，并在结果中保存 `evidence_count` 与 `evidence_truncated`，避免不同运行因为上下文过长而不可比较。

## 4. Token 结果

- BM25 平均上下文 Token：73.45；
- BGE-M3 混合平均上下文 Token：70.31；
- 当前可证明的下降：约 **4.28%**。

因此，简历草稿中的“平均上下文 Token 降低 36%”目前没有被实验支持，不能直接使用。若要达到该目标，需要加入基于 QueryPlan 的字段级裁剪、聚合下推和证据压缩，再用同一数据集复测。

### 后续 QueryPlan 对照结果

以上 4.28% 比较的是 BM25 Top-5 与 BGE-M3 混合 Top-5，只衡量“更换检索算法”带来的上下文变化。后续已完成传统 RAG 与 QueryPlan 引导 MiniBKN 的新实验：30 道多跳/聚合题上，使用同一 DeepSeek 回答模型和提示词，API 实测平均输入 Token 从 844.07 降至 280.40，减少 66.78%；平均总 Token 减少 62.36%。

新口径、质量对照和外推限制见[查询智能与完整评测产品开发报告](MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)。

## 5. 结果文件与复现入口

- BGE-M3 检索：`evals/results/comprehensive/retrieval/latest-siliconflow.json`
- 哈希基线：`evals/results/comprehensive/retrieval/latest-token_hashing.json`
- Ragas 正式结果：`evals/results/comprehensive/ragas/bge_m3_faithfulness_30.json`
- 评测程序：`scripts/evaluate_crm.py`
- Ragas 程序：`scripts/evaluate_ragas_comprehensive.py`
- NumPy 优化后 200 题排序重放：`evals/results/comprehensive/retrieval/replay_after_numpy.json`

密钥仅从用户指定的本地文件读取，没有写入代码、结果或文档。

## 6. 尚未解决的评测问题

Context Precision@5 只有 0.14，主要因为当前 gold 文档集合较窄，而多跳/聚合问题可能有多个合理证据。下一轮应人工抽查并扩充 gold evidence，同时增加答案正确性指标；在此之前，不应宣称 Context Precision 达到 0.78。

向量矩阵改为 NumPy float32 后重放全部 200 题：BM25 Top-5 顺序 200/200 完全一致，向量为 186/200，混合为 195/200。差异均为同分或极近分文档的顺序交换；重新计算后的 Hit@1、Hit@5、MRR、Precision@5、Recall@5 与表中数值完全一致。

后续已经在分层 10 题上补充 Faithfulness、Factual Correctness、Answer Relevancy、LLM Context Precision、LLM Context Recall 与 Noise Sensitivity。该 10 题结果用于诊断，不替代本报告的 200 题确定性检索指标。
