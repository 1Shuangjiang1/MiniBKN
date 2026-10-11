> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 06：结构化分支每一步怎样工作

## 总流程

```text
问题
  → 权限检查
  → 结构化搜索或 QueryPlan
  → 只读取当前用户可见的索引/对象
  → BM25 + 向量 + RRF，或确定性过滤/遍历/聚合
  → 以命中实例扩展一跳子图
  → Schema、实例、关系、动作证据统一化
  → 带 citation 的抽取式回答
```

结构化分支有两种执行方式，适合的问题不同。

## 方式一：检索式结构化问答

`POST /networks/{id}/ask` 或 `/ask-routed` 的 structured 路线走这里。

### 1. 检查索引版本

必须已经构建索引；当前 Embedding 版本和索引清单不一致时要求重建，避免用不同维度或模型比较向量。

### 2. 权限过滤

从索引中先移除 citation 对应未授权 resource 的实例文档；Schema 和动作定义仍可保留，但业务数据行不会进入召回语料。

### 3. 双路召回

- BM25：擅长精确编号、名称和关键词；业务编号会额外加权。
- 向量：擅长语义相近表达；可使用 SiliconFlow、sentence-transformers 或离线哈希基线。
- RRF：不直接比较两种分数，而按各自名次融合，公式近似 `1/(k+BM25名次)+1/(k+向量名次)`。

实现：[hybrid.py](../../src/minibkn/adapters/search/hybrid.py)。

### 4. 三层上下文

最多取 5 条 Schema、8 条实例、5 条动作命中。随后以实例为种子扩展一跳关系，把相邻对象和关系加入上下文。例如命中 MAT-001 后，可带出 `supplied_by` 与供应商。

### 5. 统一证据和回答

证据带 `resource://资源#row=行号` 或 `bkn://...` 引用。当前 `EvidenceAnswerGenerator` 是抽取式、确定性的证据整理器，并非默认再让大模型自由生成，因此更容易复现，也相对不易凭空编造。

代码：[retrieval_service.py](../../src/minibkn/application/retrieval_service.py)、[answer_generator.py](../../src/minibkn/application/answer_generator.py)。

## 方式二：确定性 QueryPlan

当问题要求精确筛选、遍历或聚合，`/ask-intelligent` 生成并执行受限 JSON 计划。

### 1. 计划校验

对象、字段、关系和动作必须来自 BKN；limit 最大 100；跳数最大 5；总扫描对象超过 10,000 会拒绝。计划不接受 SQL、函数调用或任意代码。

### 2. 加载可见图

只加载 Principal 有权访问 resource 的对象，关系必须两端都可见。

### 3. 选择与过滤

先按 object type 选对象，再执行允许的操作符：eq、neq、gt、gte、lt、lte、in、not_in、like、exist、not_exist。字段可以是 `amount` 或 `order.amount`。

### 4. 遍历

从已筛选的起点集合出发，按指定 relation、方向和最多跳数扩展。它不是通用图查询语言，只实现受限且可审计的遍历。

### 5. 投影或聚合

- 普通结果：按 `select` 选择列；
- 聚合：count/sum/avg/min/max，可 group_by、order_by；
- 最后应用 limit 和 evidence budget。

### 6. 计算证据

聚合结果会生成 `computed://query-plan/...` 证据；实例与关系仍保留资源行和 BKN 引用。结果不是让 LLM 心算出来的，而是 Python 执行器计算。

实现：[QueryPlanService.execute](../../src/minibkn/application/query_plan_service.py) 与 [QueryPlan 合同](../../src/minibkn/domain/query.py)。

## 现实例子

问题：“统计 2026 年 8 月 E001 的总工时。”

理想计划大致为：

```json
{
  "version":"1.0",
  "intent":"aggregate",
  "object_types":["timesheet"],
  "filters":[
    {"field":"employee_id","operator":"eq","value":"E001"},
    {"field":"work_date","operator":"gte","value":"2026-08-01"},
    {"field":"work_date","operator":"lte","value":"2026-08-31"}
  ],
  "aggregates":[{"function":"sum","field":"hours","alias":"total_hours"}],
  "limit":20,
  "answer_mode":"text"
}
```

执行器会筛选行并求和，而不是用向量检索返回“看起来相关的几行”后让模型估算。

安全注意：当前系统不会自动把认证用户的 employee_id 强制写进计划，因为 Principal 尚无该属性。若用于工资/工时自助查询，必须先增加行级授权，再允许这个例子上线。

## 怎样选择两种方式

- 模糊找资料、查编号或需要相关上下文：检索式问答。
- 精确条件、统计、排序、多跳业务关系：QueryPlan。
- 规则制度、合同原文：文档分支。
- 同时需要制度解释和当前业务数字：hybrid 编排。
