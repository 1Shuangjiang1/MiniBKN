> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 查询智能与完整评测产品开发报告

> 完成日期：2026-08-17\
> 外部服务：DeepSeek `deepseek-chat`、硅基流动 `BAAI/bge-m3`\
> 前置报告：[P0 查询智能与数据发现](MINIBKN_P0_QUERY_INTELLIGENCE_AND_DATA_DISCOVERY_DEVELOPMENT_REPORT.md)、[检索与 Ragas 真实评测](MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md)

## 1. 本轮结论

本轮完成了三项交付：

1. 把已有的查询改写、同义词扩展、子问题拆解和歧义追问接入统一的智能问答入口；
2. 把 Ragas 从 Faithfulness 和 ID 检索指标扩展为六项生成式诊断指标；
3. 新建传统 RAG 与 QueryPlan 引导 MiniBKN 的同口径 Token 和质量对照实验。

30 题对照中，MiniBKN 相比传统混合 RAG：

- 平均输入 Token 从 844.07 降至 280.40，减少 **66.78%**；
- 平均总 Token 从 945.47 降至 355.87，减少 **62.36%**；
- 传统 RAG 参考证据平均覆盖率为 0.25，MiniBKN 为 1.00；
- 冻结 QueryPlan 结构化执行正确率为 1.00。

这里的传统 RAG 是“BGE-M3 + BM25 混合检索 Top-20，再由 DeepSeek 回答”，不使用 QueryPlan、数据库过滤、关系遍历或聚合下推。

## 2. 查询改写和追问到底是什么状态

这些能力此前并不是完全没有实现。上一轮已经具备：

- DeepSeek 问题改写；
- 关键词提取；
- 业务同义词扩展；
- 独立子问题拆解；
- 时间范围、业务口径、代词指向等实质歧义识别；
- `clarification_answers` 回填；
- LLM 输出失败后的规则降级；
- QueryPlan Schema、字段、关系和动作白名单校验。

已有 60 题跨采购、财务和人事的未调优冻结集结果：完全正确率 93.33%，组件准确率 97.52%。

真正缺少的是一个完整产品入口。用户需要先调用 `/query-plans/analyze`，自己判断是否要追问，再调用其他接口执行。现在新增：

```text
POST /api/v1/networks/{network_id}/ask-intelligent
```

它完成以下闭环：

1. 分析原问题；
2. 返回改写、关键词、同义词和子问题；
3. 有歧义时返回 `needs_clarification`，不查询、不执行；
4. 用户把答案放入 `clarification_answers` 再次提交；
5. 结构化问题进入 QueryPlan 确定性执行；
6. 相关性搜索使用改写问题、关键词、同义词和子问题共同检索；
7. 动作意图只返回已识别的动作请求，必须另走风险模拟和审批入口。

规则降级器的同义词也由“只标记命中的词”改为真正返回候选扩展。例如“客户”会同时提供 `customer`、客户、顾客、客户方等检索词。

## 3. 为什么上一轮没有测其他 Ragas 指标

上一轮 CRM 200 题主要有：

- 正确文档 ID；
- 部分冻结 QueryPlan；
- 部分期望实例 ID 或结构化行。

但它没有为每题准备统一的自然语言参考答案。Faithfulness 只需要问题、回答和上下文，因此可以先测；Factual Correctness、LLM Context Recall 等指标需要参考答案。如果直接运行，会把 gold 数据缺失当成系统错误。

本轮只选择有冻结 QueryPlan 的题目，并从 `expected_rows`、`expected_instance_ids` 和实际结构化证据生成可核验参考事实。参考答案没有交给被测回答模型，只交给 Ragas 裁判。

## 4. 六项 Ragas 诊断结果

样本为 10 题分层集合：5 题多跳、5 题过滤聚合。传统 RAG 与 MiniBKN 使用相同问题、相同 DeepSeek 回答模型、相同提示词和最多 10 条上下文。

| 指标 | 传统 RAG | MiniBKN | 方向 |
| --- | ---: | ---: | --- |
| Faithfulness | 0.9650 | 0.9000 | 越高越好 |
| Factual Correctness | 0.2760 | 0.9000 | 越高越好 |
| Answer Relevancy | 0.7745 | 0.8866 | 越高越好 |
| LLM Context Precision | 0.4000 | 0.9583 | 越高越好 |
| LLM Context Recall | 0.2000 | 1.0000 | 越高越好 |
| Noise Sensitivity | 0.3231 | 0.1000 | 越低越好 |

所有评分均为 10/10 成功，没有裁判失败。

### Faithfulness 为什么没有超过传统 RAG

Faithfulness 只检查“回答是否能从给定上下文推出”，不检查答案是否真的回答正确。传统 RAG 在聚合题中根据检索到的少量订单回答了错误数量，但它明确说明只统计当前证据，因此仍可能得到高 Faithfulness。

MiniBKN 的 10 题中有一题聚合答案数值正确、计算证据明确，但 DeepSeek 裁判给出 0；同一题在优化后的 2 题复跑中曾得到 1，说明小样本 LLM 裁判存在波动。更大样本的独立 30 题 Faithfulness 结果仍为 0.9261。

### Factual Correctness 为什么重评

第一次参考答案把聚合 gold 写成 `count=2441` 一类机器字段。四道答案数值完全正确的聚合题被裁判判为 0，MiniBKN 均值只有 0.6000。

参考答案改成“对于原问题，符合条件的记录数量为 2441”后，只重跑 Factual Correctness：

- 传统 RAG：0.2760；
- MiniBKN：0.9000；
- 20 个系统样本全部评分成功。

第一次全指标原始结果仍然保留，没有覆盖或删除。

## 5. 聚合证据优化

冒烟阶段暴露了一个真实问题：聚合结果最初位于证据列表末尾，内容只是 `{'count': 2441}`。当证据预算耗尽时，计算结果甚至可能被前面的实例证据挤掉。

修复后：

- 计算证据排在聚合查询证据首位；
- 内容改为“结构化查询计划已根据筛选条件完成计算，结果为：count=2441”；
- 聚合计算结果不会再被实例证据挤出预算；
- 2 题优化复测中，MiniBKN Faithfulness、Context Precision 和 Context Recall 均为 1.0。

## 6. Token 对照实验

### 样本与公平性

- 30 题：15 题多跳、15 题过滤聚合；
- 数据：同一份 9,140 对象 CRM 数据库；
- 检索：同一 BGE-M3 索引；
- 回答：同一 DeepSeek `deepseek-chat`；
- 提示词：完全相同；
- Token：直接读取 DeepSeek API `usage`；
- 传统 RAG：混合检索 Top-20；
- MiniBKN：冻结 QueryPlan 确定性执行后，提供最多 20 条必要证据。

### 实际结果

| 项目 | 传统 RAG | MiniBKN | 变化 |
| --- | ---: | ---: | ---: |
| 平均输入 Token | 844.07 | 280.40 | -66.78% |
| 平均输出 Token | 101.40 | 75.47 | -25.57% |
| 平均总 Token | 945.47 | 355.87 | -62.36% |
| 30 题输入 Token 总量 | 25,322 | 8,412 | -66.78% |
| 30 题总 Token | 28,364 | 10,676 | -62.36% |
| 参考证据平均覆盖率 | 0.25 | 1.00 | +0.75 |

冻结 QueryPlan 的结构化执行正确率为 30/30。该结果支持“在本次 CRM 多跳和聚合对照中，QueryPlan 引导的上下文组织减少 66.8% 输入 Token”，但不能直接外推到所有问题和所有行业。

旧报告中的 4.28% 比较的是 BM25 Top-5 与 BGE-M3 混合 Top-5，它回答的是“换检索算法是否省上下文”；本轮 66.78% 回答的是“传统 RAG 与结构化 QueryPlan 执行是否省输入”。两者实验问题不同，均保留。

## 7. 测试与验证

新增覆盖：

- 智能问答遇到歧义时停止；
- 补充答案后继续查询；
- 同义词和子问题进入搜索查询；
- 计算证据优先且为自然语言；
- 评测分层抽样、参考答案和结构化正确性辅助函数。

最终质量门以本轮结束时的全量命令结果为准：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
```

实际结果：

- Pytest：71 项全部通过；
- 覆盖率：89%，覆盖 3,289 / 3,686 行；
- Ruff format：108 个文件符合格式；
- Ruff check：通过；
- Mypy strict：64 个源文件通过；
- Markdown：53 份，失效本地链接 0；
- 扫描 445 个非虚拟环境文件，真实密钥内容匹配 0。

## 8. 原始结果与复现入口

- 30 题 Token：`evals/results/comprehensive/token/rag_vs_bkn_token_30.json`
- 六项 Ragas：`evals/results/comprehensive/ragas/rag_vs_bkn_full_metrics_10.json`
- 修正参考答案后的事实正确性：`evals/results/comprehensive/ragas/rag_vs_bkn_factual_correctness_rescore_10.json`
- 优化前冒烟：`evals/results/comprehensive/ragas/rag_vs_bkn_smoke_2.json`
- 优化后冒烟：`evals/results/comprehensive/ragas/rag_vs_bkn_smoke_2_v2.json`
- 原有 30 题 Faithfulness：`evals/results/comprehensive/ragas/bge_m3_faithfulness_30.json`
- 评测程序：`scripts/evaluate_rag_vs_bkn.py`
- 执行计划：[查询智能与完整评测执行计划](../plans/MINIBKN_QUERY_INTELLIGENCE_AND_EVALUATION_EXECUTION_PLAN.md)

密钥只从 `<local-path>` 的本地文件读取，没有写入源码、结果或文档。

## 9. 当前限制

- Token 对照使用冻结的正确 QueryPlan，规划模型本身的准确率应单独引用 60 题盲测结果；
- 30 题仅覆盖多跳和过滤聚合，没有覆盖闲聊、模糊发现或动作；
- 六项生成式 Ragas 只有 10 题，适合作为诊断，不应包装成大规模统计结论；
- LLM 裁判存在波动，尤其是数字聚合和 Faithfulness；
- 当前 React 控制台尚未为 `/ask-intelligent` 增加追问卡片；
- 规则降级器能提供追问和检索扩展，但复杂筛选仍应使用 LLM 规划器；
- 企业字段级 RBAC 仍未完成。
