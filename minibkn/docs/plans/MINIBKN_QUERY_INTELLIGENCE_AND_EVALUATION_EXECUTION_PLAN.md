> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 查询智能与完整评测执行计划

> 建立日期：2026-08-17\
> 状态：已完成，最终结果以对应开发报告和原始 JSON 为准

## 1. 目标

本轮同时解决三个问题：

1. 把已经存在的查询改写、同义词扩展、子问题拆解和歧义追问接成一个可直接使用的问答入口；
2. 在已有 Faithfulness 和 ID 检索指标之外，补充答案相关性、事实正确性、LLM 上下文精确率/召回率和噪声敏感度；
3. 使用同一问题、同一回答模型和同一提示词，比较传统 RAG 与 QueryPlan 引导的 MiniBKN 的实际 API Token 用量和质量。

## 2. 当前基线

- QueryPlan 已支持 LLM 改写、关键词、同义词、子问题、歧义和追问答案；
- 60 题跨领域冻结集完全正确率为 93.33%，组件准确率为 97.52%；
- 这些字段此前主要通过 `/query-plans/analyze` 返回，普通问答缺少完整交互入口；
- Ragas 已在 200 题上测 ID Context Precision/Recall，在分层 30 题上测 Faithfulness；
- 旧 Token 结果比较 BM25 与 BGE-M3 Top-5 检索上下文，只得到 4.28%，不能回答“BKN 相对传统 RAG 节省多少”。

## 3. 实施步骤

### 步骤 A：查询智能闭环

- 新增 `/ask-intelligent`；
- 第一次请求先返回分析结果；
- 有实质歧义时停止执行并返回追问；
- 用户提交 `clarification_answers` 后重新分析；
- 结构化查询进入 QueryPlan 确定性执行；
- 纯相关性搜索使用改写问题、关键词、同义词和子问题组成检索查询；
- 动作意图只返回已识别请求，不在问答入口执行，继续走风险模拟和审批入口；
- LLM 故障时保留规则降级。

### 步骤 B：Ragas 指标扩展

指标分为三层，避免混淆：

| 层级 | 指标 | 数据规模 |
| --- | --- | --- |
| 确定性检索 | ID Context Precision、ID Context Recall | CRM 200 题 |
| 生成忠实度 | Faithfulness | 已有分层 30 题 |
| 完整诊断 | Faithfulness、Factual Correctness、Answer Relevancy、LLM Context Precision、LLM Context Recall、Noise Sensitivity | 新分层诊断集 |

完整诊断需要参考答案。本轮从冻结 QueryPlan 的期望行和期望实例生成自然语言参考事实，不使用模型凭空生成 gold。

### 步骤 C：传统 RAG 对照实验

传统 RAG 基线定义为：

- BGE-M3 + BM25 混合检索；
- Top-20 证据；
- 不使用 QueryPlan、结构化过滤、关系遍历或聚合下推；
- 使用 DeepSeek 生成最终答案。

MiniBKN 方案定义为：

- 使用同一批冻结问题；
- QueryPlan 经过白名单校验；
- 数据库执行过滤、遍历和聚合；
- 只把执行结果和必要证据交给同一个 DeepSeek 回答模型。

公平性约束：

- 同一问题；
- 同一 CRM 数据版本；
- 同一回答模型；
- 同一 system prompt 和回答模板；
- 都不把参考答案交给回答模型；
- Token 使用 DeepSeek API 返回值，不使用字符数或自定义分词器估算；
- 同时报告检索覆盖和结构化执行正确率，防止通过少给上下文虚假节省 Token。

## 4. 验收标准

- 查询智能入口覆盖“需追问、补充后执行、搜索扩展、动作不执行”四类路径；
- 新增功能有单元或集成测试；
- 六项 Ragas 指标均可运行并记录单题结果、均值和失败数；
- Token 对照样本不少于 30 题，过滤聚合和多跳查询各占一半；
- 结果文件不包含 API Key；
- 全量 pytest、Ruff 和 Mypy 通过；
- 开发报告、原始结果、复现命令和 AI 交接文档齐全；
- 文档导航中不存在失效本地链接。

## 5. 结果文件约定

- Token 对照：`evals/results/comprehensive/token/rag_vs_bkn_token_30.json`
- 完整 Ragas：`evals/results/comprehensive/ragas/rag_vs_bkn_full_metrics_10.json`
- 评测程序：`scripts/evaluate_rag_vs_bkn.py`
- 开发报告：`docs/reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md`
- AI 交接：`docs/handoffs/MINIBKN_QUERY_INTELLIGENCE_AND_EVALUATION_HANDOFF_FOR_AI.md`

## 6. 结果解释边界

- 新对照只覆盖 CRM 冻结题，不代表所有行业；
- QueryPlan 使用数据集提供的冻结计划，用于隔离“执行与上下文组织”的收益；自然语言规划准确率继续引用独立的 60 题盲测；
- 10 题完整生成式指标是诊断实验，不替代 200 题确定性检索指标；
- LLM 裁判存在波动，报告必须保留模型、样本和成功/失败数；
- 若 MiniBKN Token 更低但质量下降，不得宣称优化成功。
