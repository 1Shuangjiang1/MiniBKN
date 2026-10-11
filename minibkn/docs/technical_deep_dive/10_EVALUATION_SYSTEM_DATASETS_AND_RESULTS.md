> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 补充问题 9：整个评估是怎样做的，数据集和效果如何

> 核对版本：MiniBKN 0.6.0\
> 核心原则：不同评测回答不同问题，不能把 200 题检索、60 题规划、30 题 Token、10 题 Ragas、3 题 LightRAG 和自动化测试混成一个“总准确率”。

## 1. 为什么要建立多层评估

这个系统不是只有“问一句、看答案像不像”这一层。完整链路包括数据发现、BKN 建模、检索、QueryPlan、答案生成、动作安全、权限、增量更新、LightRAG 和 UI。只测最终回答会掩盖失败原因。

因此评估被拆成八层：

```text
数据与 Schema 正确性
  → 检索质量
  → QueryPlan 生成质量
  → QueryPlan 执行正确性
  → 回答与上下文质量（Ragas）
  → Token 与传统 RAG 对照
  → 动作/权限/韧性/性能
  → UI 与真实全链路验收
```

当结果不好时，可以判断是“键识别错了”“没召回正确证据”“规划错了”“执行器错了”“回答模型错了”还是“权限门禁失效”，而不是笼统归因于大模型。

## 2. 有哪些数据集

### 2.1 CRM 主基准

固定 seed `20260816` 生成：500 个客户、2,500 个订单、6,000 个订单明细、120 个商品、20 个销售人员，合计 9,140 个业务对象和 9,150 个搜索文档。

配套 200 道检索问题和 30 道动作安全题。200 题包括 70 道单对象查询、70 道订单到客户的关系查询、60 道条件过滤或聚合。

题集：[crm_200.jsonl](../../evals/datasets/crm_200.jsonl)，动作题：[crm_actions_30.jsonl](../../evals/datasets/crm_actions_30.jsonl)。

### 2.2 采购、财务、人事多行业套件

固定 seed `20260817` 生成：

| 业务域 | 对象 | 关系 | 主要表 |
| --- | ---: | ---: | --- |
| 采购 | 2,000 | 2,300 | 供应商、采购员、采购单、明细、付款 |
| 财务 | 1,320 | 1,200 | 客户、发票、收款、部门、报销 |
| 人事 | 1,120 | 1,100 | 部门、员工、请假、调岗 |
| 合计 | 4,440 | 4,600 | 三个完整 BKN 网络 |

配套 120 道多行业检索题、15 道初始 QueryPlan 标签审计题、60 道全新未调优 QueryPlan holdout、6 道对抗题和 45 道动作安全题。

数据入口：[evals/enterprise](../../evals/enterprise)，题集入口：[evals/datasets](../../evals/datasets)。

### 2.3 数据质量专项样本

专门加入组合主键、部分匹配外键、孤儿记录、重复值、空值、`_code` 自然键和 Schema 漂移。

它不是为了得到漂亮分数，而是为了暴露通用数据发现错误。评测因此发现过“外键因为恰好唯一而被并入主键”和“`_code` 组合键得分不足”等问题。

### 2.4 LightRAG 文档冒烟集

三份合成中文文档：客户服务手册、销售折扣制度、CRM 数据治理制度。配套三个可核验问题，验证文本提交、异步索引、文档检索、自动路由、混合返回和引用。文件位于 [crm_public](../../evals/fixtures/documents/crm_public)。

## 3. 检索评估怎样做

### 3.1 对比方案和指标

对比 BM25、token-hashing 离线向量、真实 BGE-M3 向量、BGE-M3+BM25+RRF 混合检索。

同一份 200 题 CRM 数据比较 Hit@1、Hit@5、MRR、ID Precision@5、ID Recall@5、延迟和上下文 Token。

### 3.2 真实结果

| 模式 | Hit@1 | Hit@5 | MRR | Precision@5 | Recall@5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 |
| 哈希向量 | 0.035 | 0.125 | 0.067 | 0.025 | 0.123 |
| BGE-M3 向量 | 0.515 | 0.625 | 0.565 | 0.125 | 0.483 |
| BGE-M3 混合 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 |

结论不是“混合检索全面超过 BM25”。数据集中有大量客户号、订单号，BM25 本来就很强；BGE-M3 相比哈希向量有巨大提升，但混合方案只追平 BM25。这是保留的真实负结论。

原始结果：[真实 BGE-M3](../../evals/results/comprehensive/retrieval/latest-siliconflow.json)、[哈希基线](../../evals/results/comprehensive/retrieval/latest-token_hashing.json)、[优化后重放](../../evals/results/comprehensive/retrieval/replay_after_numpy.json)。

### 3.3 为什么 Precision@5 只有 0.14

当前 gold 文档集合较窄。多跳问题可能需要客户、订单和关系等多条合理证据，但标签可能只标一个目标 ID，其他正确上下文会被计为非 gold。

因此不能使用最初设想中的 0.51→0.78。下一步要人工扩充多证据 gold，不能靠调整算法把分数“刷高”。

## 4. QueryPlan 评估怎样做

必须分开两件事：自然语言能否生成正确 QueryPlan，以及给定正确 QueryPlan 后执行器能否正确执行。

### 4.1 LLM 规划能力

使用 DeepSeek `deepseek-chat`、temperature=0，对运行前冻结且未用于提示词调优的 60 题 holdout 生成 `QueryAnalysis + QueryPlan`。

覆盖采购、财务、人事，以及精确查询、过滤、聚合、分组、关系跳转、歧义追问。结果为：

- 精确正确率：**93.33%**，即 56/60；
- 组件正确率：**97.52%**；
- 平均延迟：**1,958.10 ms**；
- 总 Token：**165,135**。

四个失败被保留，包括关系 intent 不一致、业务口径歧义、过度追问和缺失关系。

原始结果：[query_planner_holdout_60_v1.json](../../evals/results/comprehensive/query_planner_holdout_60_v1.json)。

### 4.2 对抗测试

六题尝试批量动作、空实例动作、绕过动作端点、导出敏感薪资等。修复前为 50%；增加动作硬门禁后为 **83.33%（5/6）**。

剩余失败是敏感字段导出。0.6.0 后续增加了角色、网络、文件、文档域和动作 RBAC，但字段级、行级权限仍未完成，所以不能宣称该风险完全解决。

原始结果：[query_planner_adversarial_v2.json](../../evals/results/comprehensive/query_planner_adversarial_v2.json)。

### 4.3 确定性执行器

早期 CRM 中有 130 个冻结且验证过的计划：70 个关系跳转、60 个过滤/聚合。给定正确计划后，执行器 Exact Accuracy 为 **1.000**。

这个 100% 只证明过滤、遍历和聚合代码正确，不能拿来表示 LLM 规划准确率；后者应引用 60 题的 93.33%。

## 5. Ragas 评估怎样做

### 5.1 200 题 ID 指标

对 200 题计算 IDBasedContextPrecision/Recall，与本地 gold ID 指标相互校验。它评价“找到了哪些文档”，不评价自然语言答案是否正确。

### 5.2 30 题 Faithfulness

从单实体、多跳、过滤和聚合中分层抽取 30 题，实际调用 `/ask`，用 DeepSeek 作为 Ragas judge 检查回答是否能由上下文推出。

- 30/30 成功；
- 平均 Faithfulness：**0.9261**；
- 最低：**0.8148**。

原始结果：[bge_m3_faithfulness_30.json](../../evals/results/comprehensive/ragas/bge_m3_faithfulness_30.json)。

### 5.3 六指标诊断

选择 10 题：5 题多跳、5 题过滤/聚合。传统 RAG 与 MiniBKN 使用相同问题、DeepSeek、提示词和最多 10 条上下文。

| 指标 | 传统 RAG | MiniBKN | 方向 |
| --- | ---: | ---: | --- |
| Faithfulness | 0.9650 | 0.9000 | 越高越好 |
| Factual Correctness | 0.2760 | 0.9000 | 越高越好 |
| Answer Relevancy | 0.7745 | 0.8866 | 越高越好 |
| LLM Context Precision | 0.4000 | 0.9583 | 越高越好 |
| LLM Context Recall | 0.2000 | 1.0000 | 越高越好 |
| Noise Sensitivity | 0.3231 | 0.1000 | 越低越好 |

传统 RAG 的 Faithfulness 更高，不代表回答更正确。Faithfulness 只判断答案是否忠于它拿到的上下文；传统 RAG 可能根据不完整证据给出错误数量，但仍然“忠于片段”。

这组只有 10 题，用于诊断，不是大规模统计结论；LLM judge 对数字聚合也存在波动。

原始结果：[rag_vs_bkn_full_metrics_10.json](../../evals/results/comprehensive/ragas/rag_vs_bkn_full_metrics_10.json)。

## 6. Token 对照怎样做

30 题中 15 题多跳、15 题过滤聚合。两边使用相同 CRM 数据、BGE-M3、DeepSeek、回答提示词和最多 20 条上下文，Token 直接读取 DeepSeek API usage。

传统 RAG 使用 BM25+BGE-M3 Top-20；MiniBKN 使用冻结正确 QueryPlan 先确定性执行，再给模型必要证据。

| 项目 | 传统 RAG | MiniBKN | 变化 |
| --- | ---: | ---: | ---: |
| 平均输入 Token | 844.07 | 280.40 | **-66.78%** |
| 平均输出 Token | 101.40 | 75.47 | -25.57% |
| 平均总 Token | 945.47 | 355.87 | **-62.36%** |
| 参考证据覆盖率 | 0.25 | 1.00 | +0.75 |

冻结计划执行正确率 30/30。

这个实验能支持“在 CRM 多跳和聚合的 30 题对照中，QueryPlan 引导的上下文组织减少 66.8% 输入 Token”。不能外推为所有问题，也不能当作 LLM 自动规划 100% 正确；规划准确率仍是独立的 93.33%。

原始结果：[rag_vs_bkn_token_30.json](../../evals/results/comprehensive/token/rag_vs_bkn_token_30.json)。旧的 4.28% 比较 BM25 Top-5 与混合检索 Top-5；66.78% 比较传统 RAG 与 QueryPlan，口径不同。

## 7. 动作、权限和增量评估

### 7.1 动作安全

CRM 30 题按 allow/confirm/deny 各 10 题，多行业另有 45 题。验证风险模拟、deny 不调用工具、confirm 必须审批、拒绝审批、幂等、动作端点隔离和 trace。冻结动作集结果为 100%。

### 7.2 权限

0.6.0 增加非法凭证、网络限制、文件资源过滤、文档 collection 隔离、建模/动作拒绝、审批/审计权限和策略失败关闭测试。目前是资源级 RBAC，不等于字段级和行级权限。

### 7.3 增量更新

测试新增、修改、删除、无变化和失败恢复，验证只有变化文档重新 Embedding，失败时恢复旧图、旧索引和 manifest。

## 8. 性能、韧性和安全评估

被测规模为 9,150 文档、BGE-M3 1024 维、单应用进程、50 并发。首次测试暴露同步计算阻塞事件循环。经过线程卸载、缓存锁和 NumPy 矩阵计算后：

| 指标 | 最初 | 优化后 |
| --- | ---: | ---: |
| 50 并发 P95 | 49,038 ms | **4,312 ms** |
| 吞吐 | 1.02 req/s | **11.52 req/s** |
| 错误 | 0/50 | **0/50** |

P95 下降约 91.2%，吞吐约提升 11.3 倍。BM25 warm P50 约 31.64 ms。

韧性测试覆盖远程 Embedding 429、503、超时、空响应、维度错误、NaN/Infinity、降级和索引版本不一致。原始结果：[bge_m3_after_numpy.json](../../evals/results/comprehensive/performance/bge_m3_after_numpy.json)。这是单机测试，不是生产集群容量承诺。

## 9. LightRAG 评估

真实环境为 LightRAG 1.5.6、DeepSeek、BGE-M3 1024 维和一个本地 `crm_public` workspace。

三份中文文档成功索引，三个问题全部返回正确文档块和引用；auto 文档路由、auto 结构化路由、hybrid 两路执行均通过。混合结果包含 14 条结构化证据和 3 条文档证据。

这是 3/3 工程冒烟，不是大规模文档质量结论。原始结果：[integration.json](../../evals/results/lightrag/integration.json)。

## 10. 工程与 UI 验收

0.6.0 最终结果：

- 后端 **74 项测试通过**，行覆盖率 **89%**；
- Ruff format/check 通过；
- Mypy strict 66 个源文件通过；
- 前端 8 项测试通过、TypeScript 和生产构建通过；
- 真实浏览器完成数据源、AI 建模、发布、构建、问答、风险模拟和评测展示；
- 390px 移动端无横向溢出；
- 仓库真实 API Key 内容扫描 0 命中。

较早报告中的 67/71 tests 和“LightRAG 尚未接入”是历史阶段；当前状态以 [0.6.0 最终验收](../reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md) 为准。

## 11. 整体效果怎样评价

### 有证据支持的优点

- QueryPlan 自动生成在 60 题跨行业 holdout 上达到 93.33% exact；
- 对精确结构化多跳/聚合，QueryPlan 比传统 Top-20 RAG 提供更完整、更短的上下文；
- 30 题对照输入 Token 减少 66.78%，结构化执行 30/30；
- 10 题诊断中事实正确性、上下文精确/召回和抗噪明显优于传统 RAG；
- 真 Embedding 明显优于哈希向量；
- 权限、动作、增量、故障和 UI 均有自动化/全链路验证；
- 性能测试真正发现并修复了并发瓶颈。

### 不能夸大的部分

- 混合检索没有超过 BM25；
- ID Precision@5 只有 0.14；
- 六指标 Ragas 只有 10 题；
- LightRAG 只有 3 题冒烟；
- 全部业务数据是固定种子的合成数据，不是真实生产流量；
- 行级/字段级权限、企业 SSO、生产向量库和高可用尚未完成；
- LLM judge 有波动，不能把单个 Ragas 分数当绝对真理。

## 12. 面试概括版本

> 我没有只做几个人工挑选的问答截图，而是把评估拆成数据质量、检索、QueryPlan 生成和执行、Ragas、Token、动作安全、权限、增量、性能和 UI 多层。核心 CRM 集有 9,140 个对象和 200 个问题，另外构建了采购、财务、人事跨行业冻结集。DeepSeek 在 60 题未调优 QueryPlan holdout 上 exact accuracy 为 93.3%；30 道多跳/聚合对照中，QueryPlan 相比传统混合 RAG 输入 Token 减少 66.8%，必要证据覆盖从 0.25 提升到 1.0。也保留了负结论：混合检索在编号密集数据上只追平 BM25，Context Precision@5 只有 0.14。

## 13. 详细资料入口

- [全量测试最终验收](../reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md)
- [查询智能与完整评测](../reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)
- [检索与 Ragas](../reports/MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md)
- [QueryPlan 盲测与对抗评测](../reports/MINIBKN_QUERY_PLAN_BLIND_AND_ADVERSARIAL_EVALUATION_REPORT.md)
- [性能、韧性与安全](../reports/MINIBKN_PERFORMANCE_RESILIENCE_SECURITY_REPORT.md)
- [LightRAG 接入评测](../reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md)
