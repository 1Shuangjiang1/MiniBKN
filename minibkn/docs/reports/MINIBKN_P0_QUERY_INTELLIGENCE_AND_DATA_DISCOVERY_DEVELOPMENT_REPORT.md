> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN P0 查询智能与数据发现产品开发报告

> 完成日期：2026-08-17\
> 项目版本：0.5.0\
> 前置资料：[S4 QueryPlan 报告](MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md)、[S3–S10 最终验收](MINIBKN_S3_S10_LONG_HORIZON_ACCEPTANCE_REPORT.md)、[QueryPlan 通俗说明](../guides/MINIBKN_QUERY_PLAN_EXPLANATION_AND_REMAINING_WORK.md)\
> 状态：P0 第一轮实现与本地验收完成

## 1. 这轮解决了什么

上一版已经能安全执行一张写好的 QueryPlan，但从自然语言生成计划的能力较弱。这一轮补齐：

- 使用 DeepSeek 对问题进行改写、关键词提取、业务同义词识别和子问题拆分；
- 识别会改变查询结果的歧义，返回追问，不带着猜测直接执行；
- 用户补充答案后重新分析并生成 QueryPlan；
- 计划仍必须经过 Pydantic 格式和 BKN 对象/字段/关系/动作白名单校验；
- 外部 LLM 失败或输出非法格式时，降级到安全规则规划器；
- CSV/SQLite 增加字段剖析、单主键、组合主键和外键候选发现；
- 接入真实硅基流动 `BAAI/bge-m3` Embedding；
- 缓存 BM25 语料分词和文档频率统计；
- 建立 14 题自然语言 QueryPlan 冻结集并完成两轮真实 DeepSeek 评测。

## 2. 系统到底如何解析并执行 QueryPlan

可以把整个过程理解成“前台填写工单，后台审核工单，仓库按工单取货”。

### 第一步：理解用户的话

用户说：

> 统计已付款订单的总金额。

DeepSeek 会结合当前 BKN 中允许使用的对象、字段和关系，把它整理成：

- 业务对象：订单 `order`；
- 条件：`status = paid`；
- 统计方式：对 `amount` 求和；
- 意图：聚合 `aggregate`。

它同时返回改写后的问题、关键词、同义词、子问题和假设，便于用户检查 AI 是否理解正确。

### 第二步：先检查有没有歧义

如果用户问“最近的大客户怎么样”，系统不会立刻查询，因为至少缺少：

- “最近”是 7 天、30 天还是本季度；
- “大客户”按订单金额、客户等级还是其他指标；
- “怎么样”要列表、总额、趋势还是风险。

此时返回 `needs_clarification` 和追问列表，`plan` 为 `null`，因此没有东西可以被误执行。用户把答案作为 `clarification_answers` 再提交，系统才继续生成计划。

### 第三步：生成结构化工单

明确问题生成的核心计划类似：

```json
{
  "intent": "aggregate",
  "object_types": ["order"],
  "filters": [
    {"field": "status", "operator": "eq", "value": "paid"}
  ],
  "aggregates": [
    {"function": "sum", "field": "amount", "alias": "total_amount"}
  ],
  "limit": 20
}
```

### 第四步：程序审核工单

系统不会因为计划来自大模型就直接相信它，而是检查：

1. JSON 是否完全符合 QueryPlan 契约；
2. `order` 是否是当前 BKN 中存在的对象；
3. `status`、`amount` 是否是允许查询的字段；
4. 比较和聚合操作是否属于允许枚举；
5. 是否夹带 SQL、代码、未知字段或禁用动作；
6. 查询是否会扫描超过 10,000 个对象。

对于 `status/type/segment/level` 等低基数业务枚举，系统只向规划模型提供最多 20 个短值，不发送姓名、ID、邮箱、地址或地理字段。模型生成不存在的枚举筛选值时，计划会被转换成追问而不是静默执行并返回错误的空结果。

任一检查失败都会拒绝执行。真实测试中，DeepSeek 首次自创了 `steps` 格式，系统正确拒绝；随后通过向模型提供完整 JSON Schema 修正规划提示，而不是放宽安全校验。

### 第五步：确定性执行

审核通过后，执行器不再让大模型自由发挥，而是按顺序：

1. 读取当前网络的对象和关系；
2. 只保留 `order`；
3. 筛选 `status = paid`；
4. 如有 `traversals`，沿指定关系和方向跳转；
5. 如有 `select`，选择字段；如有 `aggregates`，执行计数、求和、平均或最值；
6. 应用分组、聚合排序、`limit` 和证据条数限制；
7. 返回结果、对象证据、关系证据、计算证据和引用。

CRM 演示数据中，两笔已付款订单金额为 `128000.5` 和 `8600.0`，程序实际返回 `136600.5`。

### 第六步：动作仍然单独过安全门

QueryPlan 可以描述动作意图，但查询执行器不会直接执行动作。动作必须进入 S5 的风险模拟、权限条件、人工确认、幂等和审计链路。这样即使 LLM 错把查询理解成动作，也不能绕过安全门。

## 3. 新增查询分析 API

```text
POST /api/v1/networks/{network_id}/query-plans/analyze
```

第一次请求：

```json
{"question": "最近的大客户怎么样"}
```

如有歧义，响应包含：

```json
{
  "status": "needs_clarification",
  "ambiguities": [
    {
      "id": "time_range",
      "question": "最近具体指多长时间？",
      "options": ["近7天", "近30天", "本季度"]
    }
  ],
  "plan": null
}
```

第二次把问题和答案一起提交：

```json
{
  "question": "最近的大客户怎么样",
  "clarification_answers": {
    "time_range": "近30天",
    "metric": "累计订单金额"
  }
}
```

无剩余歧义时返回 `ready` 和可检查的 `plan`。原 `preview`、`execute`、`ask-planned` 保持兼容；`preview` 遇到歧义返回 `409 QUERY_CLARIFICATION_REQUIRED`。

## 4. LLM 和 Embedding 配置

- QueryPlan：DeepSeek `deepseek-chat`，OpenAI-compatible Chat Completions；
- Embedding：硅基流动 `BAAI/bge-m3`，1024 维；
- 密钥：程序支持 `*_API_KEY_FILE`，只读取本地单行密钥文件，不复制到源码、Markdown 或日志；
- 演示脚本默认读取用户提供的 `<local-path>`，也可以通过参数换路径；
- 外部服务故障时，Embedding 可锁定降级到同维 token hashing；QueryPlan 降级到规则分析器。

根据[硅基流动 Embeddings 官方 API 文档](https://docs.siliconflow.cn/en/api-reference/embeddings/create-embeddings)，`dimensions` 只支持 Qwen3 Embedding 系列，因此 BGE-M3 请求不再发送该字段，返回向量后再严格验证实际维度。

## 5. 主键、外键和关系发现增强

数据发现现在会计算：

- 总行数、非空数量、空值率；
- 去重数量、唯一率；
- 字段类型和名称标识符信号；
- 单字段唯一性；
- 最多两字段的组合唯一性；
- 源字段值域在目标主键值域中的覆盖率；
- 字段名称、类型和目标对象语义一致性。

每个候选包含字段、目标资源、置信度、推荐状态和可解释理由。只有高置信候选自动进入生成的 BKN；其余候选保留在资源发现结果中，供建模审核。统计结果不保存原始样例值，避免在数据源 API 中额外暴露客户或订单数据。

SQLite 显式声明的主键优先级最高；CSV 可发现 `region + code` 这类组合主键和对应组合外键。

## 6. BM25 性能优化

旧实现每次查询都会重新：

1. 给所有文档分词；
2. 统计每个词出现于多少文档；
3. 计算平均文档长度。

现在这些“只随索引版本变化”的语料统计进入有界 LRU 缓存。缓存键包含网络、索引更新时间和文档数量；索引重建后自然使用新版本，不会复用旧统计。测试验证同一版本第二次查询命中缓存，不同版本产生新条目。

## 7. 真实验证结果

### 自动化质量门

```text
Pytest：50 passed
Ruff format：97 files formatted
Ruff check：通过
Mypy strict：64 个源文件通过
```

### 真实外部服务

- DeepSeek 明确问题：`ready`，生成 `aggregate` 计划；
- DeepSeek 含糊问题：`needs_clarification`，返回多项追问；
- 硅基流动：2 个输入成功返回 2 个 1024 维向量；
- 完整 CRM API：7 个对象、4 条关系、10 条索引文档；
- QueryPlan 执行：已付款订单总额 `136600.5`；
- 混合检索：“上海企业客户”第一名为 `CUST-001`。

### 自然语言 QueryPlan 冻结集

数据集：`evals/datasets/crm_query_planner_14.jsonl`。

原始结果：[v1](../../evals/results/query-planner-deepseek-20260817.json)、[v2](../../evals/results/query-planner-deepseek-20260817-v2.json)。

| 轮次 | 整张计划严格一致率 | 组件准确率 | 说明 |
| --- | ---: | ---: | --- |
| v1 | 0.5000 | 0.8302 | 意图标签、count 字段和遍历起点不稳定 |
| v2 | 1.0000 | 1.0000 | 增加严格意图、遍历和相对时间规则后复跑 |

必须保留边界：这是 14 题、单一 CRM Schema、同一 DeepSeek 模型、提示词针对失败项调整后的冻结集。它证明这组代表性问题可以稳定工作，不等于任意企业问题都有 100% 准确率。下一步应扩充到未参与提示词调整的盲测集。

## 8. 如何演示

在 `minibkn` 目录运行真实 AI 后端：

```powershell
.\scripts\demo_with_ai.ps1
```

然后访问 `http://127.0.0.1:8000/docs`。建议演示顺序：

1. 导入 CRM BKN，注册并发现 CRM CSV；
2. 物化网络并构建真实 BGE-M3 索引；
3. 用 `/query-plans/analyze` 提交“统计已付款订单的总金额”；
4. 把返回计划交给 `/query-plans/execute`，展示 `136600.5` 和证据；
5. 提交“最近的大客户怎么样”，展示系统先追问而不是乱猜；
6. 补充答案后再次分析；
7. 用 `/search` 演示真实语义/混合检索。

一键验收真实服务与完整 CRM 链路：

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python.exe scripts\verify_ai_demo.py `
  --deepseek-key-file <local-path> `
  --siliconflow-key-file <local-path>
```

## 9. 仍然存在的限制

- 14 题规划集太小，缺少财务、人事、采购等盲测 Schema；
- 规则降级规划器只适合简单对象识别、统计识别和常见歧义；
- LLM API 仍可能超时、限流或发生模型漂移；
- 当前追问是无状态请求，客户端需要把原问题和答案再次提交；
- 新查询分析可通过 Swagger/API 完整演示，但现有 React 控制台尚未接入追问卡片和回答回填；
- 主外键候选已可审核，但还没有专门的“接受/拒绝候选”HTTP 接口和 UI；
- 没有 Reranker，真实 Embedding 尚未在 200 题 CRM 检索集上完成新一轮正式对比；
- 普通明细排序、遍历后的目标过滤和复杂跨对象计算仍需继续增强。

## 10. P1 推荐顺序

对整个系统最有正向价值的 P1 建议是：

1. **Reranker 与真实 200 题复评**：最直接改善检索结果，也最容易产生可信简历指标；
2. **QueryPlan 盲测扩容和修复回路**：加入未参与调优的多行业题，错误计划自动重试一次，再交人工确认；
3. **真实身份与 RBAC**：动作系统要进入实际业务演示，这是安全底座；
4. **动作意图到风险模拟的完整 UI 闭环**：展示“查询—判断—确认—执行—审计”的项目亮点；
5. **Faithfulness 与 Token 消融评测**：补齐简历效果评价，但应排在真实检索质量之后；
6. **建模界面差异编辑**：提升产品完整度，技术收益低于前五项。

不建议现在优先做纯视觉重构；当前更应把准确率、盲测、安全和端到端动作链路做扎实。
