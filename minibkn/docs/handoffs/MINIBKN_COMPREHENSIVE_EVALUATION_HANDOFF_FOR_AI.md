> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 全量测试与评测交接文档

> 用途：向后续接手的 AI 提供本轮全量测试与评测的事实背景、结果入口和阅读索引。\
> 完成日期：2026-08-17\
> 项目目录：`<local-path>`

## 1. 本轮任务是什么

本轮任务是为 MiniBKN 建立一套可重复运行的全栈测试与评测体系，而不是只运行已有单元测试。

工作范围包括：

- 设计采购、财务、人事、CRM 等多业务测试数据；
- 生成表格、业务关系、自然语言问题、动作题和异常数据；
- 测试 BKN 解析、数据发现、主键/外键、知识网络构建与增量更新；
- 使用 DeepSeek 评测 QueryPlan、歧义识别和对抗输入；
- 使用硅基流动 BGE-M3 对比 BM25、哈希向量、真实向量和混合检索；
- 使用 Ragas 与 DeepSeek 检查回答的 Faithfulness；
- 测量上下文 Token、搜索延迟、缓存、冷启动和并发吞吐；
- 测试外部 Embedding 限流、超时、错误响应和非法向量；
- 测试 API Key、QueryPlan 动作隔离、风险模拟、审批、幂等和审计；
- 扩充前端自动化测试，并通过真实浏览器完成完整产品链路；
- 修复测试过程中发现的代码和 UI 问题；
- 保存机器可读原始结果、技术报告、通俗报告和文档导航。

LightRAG 按既定范围没有接入。本轮只验证了非结构化文档端口、路由、禁用状态和降级行为。

## 2. 测试数据和题目

### 多行业数据

使用固定种子 `20260817` 生成：

- 采购：2,000 个对象、2,300 条关系；
- 财务：1,320 个对象、1,200 条关系；
- 人事：1,120 个对象、1,100 条关系；
- 合计：4,440 个对象、4,600 条关系；
- 120 条多行业检索题；
- 60 条未用于提示词调优的 QueryPlan 冻结题；
- 15 条早期标签审计题；
- 6 条 QueryPlan 对抗题；
- 45 条多行业动作安全题；
- 组合主键、部分外键、孤儿记录、重复值、空值和 Schema 漂移样例。

数据生成程序：

- `scripts/generate_enterprise_test_suite.py`
- `scripts/generate_query_planner_holdout.py`

数据目录：

- `evals/enterprise/`
- `evals/datasets/`

### CRM 基准

CRM 基准包含：

- 500 个客户；
- 2,500 个订单；
- 6,000 个订单明细；
- 120 个商品；
- 20 个销售人员；
- 9,140 个业务对象；
- 9,150 个可检索文档；
- 200 条检索问题；
- 30 条动作安全题。

问题分为单实体查询、多跳关系查询、条件过滤和聚合统计。

## 3. 最终自动化结果

- 后端 pytest：本轮后续增强后为 71 项全部通过；
- 后端行覆盖率：89%，覆盖 3,289 / 3,686 行；
- Ruff 格式和代码检查：通过；
- Mypy strict：通过；
- 前端 Vitest：8 项全部通过；
- 前端 TypeScript 检查：通过；
- 前端生产构建：通过；
- 真实密钥内容扫描：0 个仓库文件匹配；
- 53 份 Markdown：0 个失效本地链接；
- 真实浏览器控制台：0 个 error/warning；
- 390 × 844 移动端视口：没有横向溢出。

覆盖率原始结果：`evals/results/comprehensive/coverage.json`。

## 4. QueryPlan 评测

### 60 题冻结集

- 精确准确率：93.33%；
- 组件准确率：97.52%；
- 平均延迟：1,958.10 ms；
- 最大延迟：2,351.97 ms；
- Prompt Token：148,606；
- Completion Token：16,529；
- 总 Token：165,135。

原始结果：

- `evals/results/comprehensive/query_planner_holdout_60_v1.json`

### 对抗集

- 题目数：6；
- 精确准确率：83.33%；
- 5/6 符合预期或被安全校验阻止。

已经阻止的行为包括：

- 通过 QueryPlan 直接执行动作；
- 没有明确实例的动作请求；
- 批量动作或提示注入绕过动作入口。

剩余失败项是请求导出全部薪资等级时，没有字段级权限阻止。原因是系统当前没有用户、角色和字段级 RBAC。

原始结果：

- `evals/results/comprehensive/query_planner_adversarial_v2.json`

相关报告：

- `docs/reports/MINIBKN_QUERY_PLAN_BLIND_AND_ADVERSARIAL_EVALUATION_REPORT.md`

## 5. 检索评测

在 CRM 200 题上得到：

| 检索方式 | Hit@1 | Hit@5 | MRR | Context Precision@5 | Context Recall@5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 |
| 哈希向量 | 0.035 | 0.125 | 0.067 | 0.025 | 0.123 |
| 哈希混合 | 0.355 | 0.535 | 0.419 | 0.107 | 0.443 |
| BGE-M3 向量 | 0.515 | 0.625 | 0.565 | 0.125 | 0.483 |
| BGE-M3 混合 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 |

可以由实验支持的结论：

- BGE-M3 向量相对哈希向量，Hit@1 提高 48 个百分点；
- BGE-M3 向量相对哈希向量，Hit@5 提高 50 个百分点；
- 在当前包含大量客户号、订单号的 CRM 集合上，BGE-M3 混合检索追平 BM25，但没有超过 BM25；
- 哈希向量不能作为真实语义 Embedding 的替代品。

原始结果：

- BGE-M3：`evals/results/comprehensive/retrieval/latest-siliconflow.json`
- 哈希基线：`evals/results/comprehensive/retrieval/latest-token_hashing.json`
- NumPy 优化后重放：`evals/results/comprehensive/retrieval/replay_after_numpy.json`

优化后重放全部 200 题时，少量同分文档发生顺序交换，但 Hit@1、Hit@5、MRR、Precision@5 和 Recall@5 全部保持不变。

## 6. Ragas 与回答忠实度

Ragas 工作分成两部分：

1. 对全部 200 题计算基于文档 ID 的 Context Precision / Recall；
2. 从不同题型分层抽取 30 题，实际调用系统回答，再使用 DeepSeek 计算 Faithfulness。

Faithfulness 结果：

- 样本数：30；
- 成功评分：30；
- 失败评分：0；
- 平均值：0.9261；
- 最低值：0.8148。

聚合问题可能关联大量底层记录。评测器将送入裁判模型的证据窗口固定为前 20 条，并在结果中记录原始证据数量以及是否发生截断。

原始结果：

- `evals/results/comprehensive/ragas/bge_m3_faithfulness_30.json`

评测程序：

- `scripts/evaluate_ragas_comprehensive.py`

后续补充了 10 题六指标传统 RAG/MiniBKN 对照：Faithfulness、Factual Correctness、Answer Relevancy、LLM Context Precision、LLM Context Recall 和 Noise Sensitivity。结果与解释入口：

- `docs/reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md`
- `evals/results/comprehensive/ragas/rag_vs_bkn_full_metrics_10.json`
- `evals/results/comprehensive/ragas/rag_vs_bkn_factual_correctness_rescore_10.json`

## 7. Token 结果

- BM25 平均 Top-5 上下文 Token：73.45；
- BGE-M3 混合平均 Top-5 上下文 Token：70.31；
- 当前实测降幅：约 4.28%。

本轮结果不支持“上下文 Token 降低 36%”。

后续采用新的同口径实验，比较传统混合 RAG Top-20 与冻结 QueryPlan 确定性执行：30 道 CRM 多跳/聚合题中，使用同一 DeepSeek 回答模型和提示词，平均输入 Token 减少 66.78%，平均总 Token 减少 62.36%，冻结计划结构化执行正确率为 30/30。原始结果：

- `evals/results/comprehensive/token/rag_vs_bkn_token_30.json`

4.28% 与 66.78% 回答的是不同实验问题，不能互相替换。66.78% 也不能外推为所有查询和行业的统一降幅。

## 8. 动作与风险安全

CRM 30 题动作集结果：

- allow：10；
- confirm：10；
- deny：10；
- 判定准确率：100%；
- 风险模拟产生的副作用：0。

多行业 45 条动作题也通过集成验证。

系统的动作链路包括：

- 动作必须绑定 BKN 中已登记的 ActionType；
- 自动从目标对象绑定参数；
- 风险规则从 BKN RiskType 解析；
- 支持 allow、confirm、deny；
- confirm 状态必须经过独立确认接口；
- 支持幂等键和 trace 事件审计；
- QueryPlan 不能代替动作接口执行动作。

当前安全边界不包括用户级 RBAC、字段级脱敏和组织权限体系。

## 9. 性能与并发

被测条件：

- 9,150 个检索文档；
- BGE-M3 1024 维向量；
- 单应用进程；
- 20 次顺序请求；
- 50 次并发请求。

第一次测试发现同步 Embedding 和纯 Python 向量点积阻塞 FastAPI 事件循环：

- 混合检索 50 并发 P95：49,038 ms；
- 吞吐：1.02 req/s。

修复内容：

- 把阻塞检索移入工作线程；
- 为 BM25 和 Embedding 缓存增加并发保护；
- 将逐条 Python 点积改为 NumPy 矩阵计算；
- 按索引版本缓存文档和向量矩阵。

修复后：

- 50/50 请求成功；
- 混合检索 P50：3,479.69 ms；
- 混合检索 P95：4,312.02 ms；
- 吞吐：11.52 req/s；
- P95 相对最初实现下降约 91.2%；
- 吞吐约为最初实现的 11.3 倍。

原始结果：

- 修复前：`evals/results/comprehensive/performance/bge_m3_single_process.json`
- 线程卸载后：`evals/results/comprehensive/performance/bge_m3_single_process_after_thread_offload.json`
- NumPy 优化后：`evals/results/comprehensive/performance/bge_m3_after_numpy.json`

## 10. 外部服务韧性与 API 安全

已经测试：

- 硅基流动 429 限流后重试；
- 5xx 持续失败后的错误或离线降级；
- 网络读取超时；
- Embedding 空响应；
- 返回向量数量错误；
- 向量维度错误；
- NaN/Infinity 非法向量；
- API Key 缺失和错误值；
- API Key 恒定时间比较；
- 超过 4,000 字符的搜索和问答输入；
- QueryPlan 提示注入和动作绕过。

真实 DeepSeek 与硅基流动密钥只从用户指定的本地文件读取。仓库内容与两份真实密钥进行精确匹配扫描，结果为 0 个匹配文件。

## 11. 前端和真实浏览器验收

前端自动化从 2 项扩充到 8 项，覆盖：

- 六个工作区与无障碍导航；
- 连接地址和 API Key 保存；
- 数据源登记；
- 问答证据和引用；
- 后端错误展示；
- 评测报告读取；
- 提案未审完时禁止发布；
- 已审核提案不再重复显示审核按钮。

真实浏览器完成的链路：

> 登记 CRM CSV → 发现 2 张表 → 生成 14 条建模提案 → 全部接受 → 发布 `crm_reviewed` → 增量构建 → 业务问答和证据展示 → 供应链风险模拟 → 提交动作并停在 `pending_confirmation` → 读取评测报告并显示 READY。

浏览器还检查了控制台错误和 390 × 844 移动端布局。

浏览器验收在默认演示数据库中留下：

- `crm_files`；
- `crm_reviewed`；
- `supply_chain_files`；
- `supply_chain`；
- 一条 `pending_confirmation` 动作记录。

这些演示数据没有被自动删除。

## 12. 测试发现并修复的主要问题

本轮修复包括：

1. CSV 外键被错误并入组合主键；
2. `_code` 类型自然键识别不足；
3. BM25 模式错误调用付费 Embedding；
4. 精确业务编号被重复中文词挤出首位；
5. 远程 Embedding 每批重新建立连接；
6. QueryPlan 的 `in`、聚合和遍历合同不完整；
7. QueryPlan 可能尝试绕过动作专用入口；
8. 搜索反复从 SQLite 加载全部文档；
9. 同步检索阻塞事件循环；
10. Python 点积导致并发性能不足；
11. Ragas 0.4.3 调用方式和默认输出 Token 不兼容；
12. UI 加载约 2 MB 逐题报告导致页面检查超时；
13. 已审核提案仍可重复操作；
14. 提案未审完时发布按钮仍可点击。

## 13. 应优先阅读的报告

### 最新总结果

- `docs/reports/MINIBKN_COMPREHENSIVE_TEST_ACCEPTANCE_REPORT.md`
- `docs/reports/MINIBKN_COMPREHENSIVE_TEST_PLAIN_LANGUAGE_REPORT.md`

### 专项结果

- `docs/reports/MINIBKN_RETRIEVAL_AND_RAGAS_EVALUATION_REPORT.md`
- `docs/reports/MINIBKN_PERFORMANCE_RESILIENCE_SECURITY_REPORT.md`
- `docs/reports/MINIBKN_QUERY_PLAN_BLIND_AND_ADVERSARIAL_EVALUATION_REPORT.md`
- `docs/reports/MINIBKN_UI_BROWSER_ACCEPTANCE_REPORT.md`
- `docs/reports/MINIBKN_ENTERPRISE_TEST_DATASET_DEVELOPMENT_REPORT.md`
- `docs/reports/MINIBKN_DETERMINISTIC_TEST_FOUNDATION_REPORT.md`

### 测试计划与文档索引

- `docs/plans/MINIBKN_COMPREHENSIVE_TEST_AND_EVALUATION_PLAN.md`
- `docs/MINIBKN_DOCUMENTATION_NAVIGATION.md`

### 机器可读汇总

- `evals/results/latest.json`

## 14. 当前不能当成已完成能力的内容

- LightRAG 实现和非结构化文档真实评测；
- 企业用户体系、角色权限和字段级 RBAC；
- Context Precision 0.78；
- 上下文 Token 降低 36%；
- 生产集群容量和跨机器压测；
- 全部 200 题的 LLM Faithfulness；
- 真实企业生产数据评测。

当前 200 题 ID Context Precision@5 为 0.14。旧检索算法对比的 Token 降幅为 4.28%；新传统 RAG/QueryPlan 30 题对照的输入 Token 降幅为 66.78%。Faithfulness 0.9261 来自分层抽取的 30 题，不是全部 200 题。

## 15. 工作区状态

本轮没有执行 Git commit、push 或创建 PR。

仓库当前将 `minibkn/` 与 `minibkn-ui/` 整体显示为未跟踪目录，因此 Git 无法提供这些文件相对历史提交的完整逐行差异。代码、数据集、评测结果和文档全部保留在本地工作区。
