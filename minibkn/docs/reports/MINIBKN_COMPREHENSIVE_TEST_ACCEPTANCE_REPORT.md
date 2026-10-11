> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 全量测试与评测最终验收报告

> 完成日期：2026-08-17\
> 对应计划：`docs/plans/MINIBKN_COMPREHENSIVE_TEST_AND_EVALUATION_PLAN.md`\
> 结论：当前已实现范围通过验收；LightRAG 仍按约定只验收接口，不计作已接入能力。

## 1. 验收范围与结论

| 能力 | 测试内容 | 结果 |
| --- | --- | --- |
| BKN 与通用建模 | 采购、财务、人事、CRM、组合键、外键、脏数据 | 通过 |
| QueryPlan | 60 题新冻结集、6 题对抗集、结构校验和动作隔离 | 通过门槛，有 1 项权限缺口 |
| 检索 | BM25、哈希向量、BGE-M3、RRF Hybrid，完整 200 题 | 完成并保留原始结果 |
| Ragas | ID Precision/Recall 200 题；Faithfulness 分层 30 题 | 30/30 成功，均值 0.9261 |
| 动作安全 | allow/confirm/deny、模拟、确认、幂等、审计 | 冻结集 100% |
| 增量更新 | 新增、修改、删除、无变化、失败不污染 | 通过 |
| 性能韧性 | 冷热缓存、20 顺序、50 并发、429/5xx/超时/坏向量 | 通过，且修复并发瓶颈 |
| API 安全 | API Key、恒定时间比较、超长输入、错误合同 | 通过 |
| 前端 | 8 项自动化、真实浏览器完整主链路、390px 移动端 | 通过 |
| LightRAG | 禁用状态、显式错误、自动降级、可替换端口 | 通过接口验收；未接入 LightRAG |

## 2. 测试资产

新增可重复生成的企业测试套件，固定种子 `20260817`：

- 采购：2,000 对象、2,300 关系；
- 财务：1,320 对象、1,200 关系；
- 人事：1,120 对象、1,100 关系；
- 合计：4,440 对象、4,600 关系；
- 120 条多行业检索题；
- 60 条 QueryPlan 新冻结题，另有 15 条标签审计题与 6 条对抗题；
- 45 条多行业动作安全题；
- 复合主键、部分外键、孤儿记录、重复值、空值和 Schema 漂移样例。

CRM 基准继续使用 500 客户、2,500 订单、6,000 明细、120 商品、20 销售，共 9,150 个检索文档与 200 题。

## 3. 关键真实结果

### 3.1 QueryPlan

- 新冻结 60 题精确准确率：**93.33%**；
- 组件准确率：**97.52%**；
- 平均延迟：**1,958.10 ms**；
- 总 Token：**165,135**；
- 对抗集：5/6 安全或符合预期，准确率 **83.33%**。

剩余失败是“导出全部薪资等级”没有被字段级权限拦截。当前系统只有网络级 API Key，没有用户、角色和字段级 RBAC，因此这项必须保留为已知缺口。

### 3.2 检索与 Ragas

| 模式 | Hit@1 | Hit@5 | MRR | Precision@5 | Recall@5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 |
| 哈希向量 | 0.035 | 0.125 | 0.067 | 0.025 | 0.123 |
| BGE-M3 向量 | 0.515 | 0.625 | 0.565 | 0.125 | 0.483 |
| BGE-M3 混合 | 0.700 | 0.700 | 0.700 | 0.140 | 0.525 |

BGE-M3 向量相比哈希向量 Hit@1 提高 48 个百分点、Hit@5 提高 50 个百分点；但在这个含大量业务编号的测试集上，混合检索只是追平 BM25，并未超过。

性能优化后又重放全部 200 题。少量同分结果因 float32 发生末位顺序交换，但五项检索质量指标全部保持不变。

Ragas Faithfulness 分层 30 题：30/30 成功，平均 **0.9261**，最低 **0.8148**。

### 3.3 Token

BM25 平均上下文 73.45 Token，BGE-M3 混合 70.31 Token，下降约 **4.28%**。当前实验不支持“降低 36%”的简历表述。

> 后续更新：新的实验不再比较两种 Top-5 检索算法，而是比较传统混合 RAG Top-20 与冻结 QueryPlan 确定性执行。30 道多跳/聚合题上，DeepSeek API 实测平均输入 Token 减少 66.78%、总 Token 减少 62.36%，结构化执行正确率 30/30。详见[查询智能与完整评测](MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)。

### 3.4 性能

在 9,150 文档、BGE-M3 1024 维、单进程、50 并发条件下：

- 修复前混合检索 P95：49,038 ms，吞吐 1.02 req/s；
- 修复后 P95：**4,312 ms**，吞吐 **11.52 req/s**；
- 50/50 请求成功；
- P95 下降约 91.2%，吞吐约 11.3 倍。

## 4. 测试发现并修复的问题

1. CSV 初始主键误把外键并入复合主键；
2. `_code` 类型自然键无法识别为组合主键；
3. BM25 模式仍错误调用付费 Embedding；
4. 业务编号会被重复中文领域词挤出首位；
5. 远程 Embedding 每批重新建连接；
6. QueryPlan 的 `in` 参数、聚合意图、遍历意图合同不严；
7. QueryPlan 可尝试绕过动作专用安全入口；
8. 搜索每次从 SQLite 重载 9,150 文档；
9. 同步向量检索阻塞 FastAPI 事件循环；
10. Python 点积造成高并发 CPU 瓶颈；
11. Ragas 0.4.3 接口与默认输出 Token 不兼容；
12. UI 直接渲染 2 MB 逐题结果导致页面检查超时；
13. 已审核提案仍能重复操作，未审完也能点击发布。

对应修复均已加入回归测试或可复现性能结果。

## 5. 最终自动化结果

- 后端：**67 passed**；
- 后端覆盖率：本报告当时为 **89%**（3,250 / 3,646 行）；查询智能增强后复测仍为 **89%**（3,289 / 3,686 行）；
- Ruff：通过；
- Mypy strict：通过；
- 前端 Vitest：**8 passed**；
- 前端 TypeScript：通过；
- 前端生产构建：通过；
- 仓库对两份真实密钥内容的精确扫描：**0 个匹配文件**；
- 浏览器控制台：0 个 error/warning；
- 390px 移动端：无横向溢出。

## 6. 真实浏览器验收链路

浏览器实际完成：

> 登记 CRM CSV → 发现 2 张表 → 生成 14 条提案 → 全部人工接受 → 发布 `crm_reviewed` → 增量构建 7 对象/4 关系/10 索引文档 → 业务问答与证据展示 → 供应链风险模拟 → 动作停在 `pending_confirmation` → 读取最新评测并显示 READY。

浏览器验收在默认本地演示数据库中留下 `crm_files`、`crm_reviewed`、`supply_chain_files`、`supply_chain` 和一条待确认动作记录。这些是可见的演示数据，未自动删除。

## 7. 未完成与不能宣称的部分

- LightRAG 未安装、未接入、未评测；只有接口与路由预留。
- 没有用户级/角色级/字段级 RBAC，不能宣称完整企业权限系统。
- Context Precision@5 当前为 0.14，不是 0.78；gold evidence 还需人工扩充。
- 本报告原始 Top-5 检索算法对比的 Token 降幅为 4.28%；后续传统 RAG/QueryPlan 30 题对照的输入 Token 降幅为 66.78%。两者口径不同。
- Faithfulness 只对 30 题做 LLM Judge，另外 200 题跑的是 ID 型检索指标。
- QueryPlan 的规则降级器对部分中文业务编号问题较弱；正式演示建议配置 DeepSeek。
- 性能测试是单机进程内 HTTP，不等同于生产集群容量。

## 8. 原始结果入口

- UI 汇总：`evals/results/latest.json`
- 真实 BGE：`evals/results/comprehensive/retrieval/latest-siliconflow.json`
- 哈希基线：`evals/results/comprehensive/retrieval/latest-token_hashing.json`
- Ragas：`evals/results/comprehensive/ragas/bge_m3_faithfulness_30.json`
- QueryPlan 60：`evals/results/comprehensive/query_planner_holdout_60_v1.json`
- 对抗集：`evals/results/comprehensive/query_planner_adversarial_v2.json`
- 性能：`evals/results/comprehensive/performance/bge_m3_after_numpy.json`
- 覆盖率：`evals/results/comprehensive/coverage.json`
- 优化后排序重放：`evals/results/comprehensive/retrieval/replay_after_numpy.json`
