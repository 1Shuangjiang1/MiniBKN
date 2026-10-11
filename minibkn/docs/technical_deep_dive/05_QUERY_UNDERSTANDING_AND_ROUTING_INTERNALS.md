> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 05：查询理解层到知识路由怎样工作

## 最重要的当前事实

目前存在两个相邻、但没有合并成单一编排器的入口：

1. `/ask-intelligent`：负责改写、同义词、子问题、歧义、QueryPlan 和安全执行；可用 LLM。
2. `/ask-routed`：负责 structured/document/hybrid 路由；`auto` 当前是关键词规则，不调用 LLM。

所以不能说“LLM 先理解问题，再自动决定去 LightRAG 还是结构化库，然后执行 QueryPlan”已经完整实现。UI 的问答页当前调用第二个入口。

## A. 查询理解 `/ask-intelligent`

### 1. 准备可用上下文

服务读取当前 BKN Schema，只向 planner 提供允许的对象 ID、字段、关系和已启用动作；同时从当前用户可见实例中提取 status、type、category 等低基数字段的真实取值，作为枚举提示。

这样 LLM 不能随便发明表名或状态值。

### 2. LLM 或规则分析

如果配置 `MINIBKN_LLM_PROVIDER=openai_compatible` 以及 URL、模型和 Key，会调用兼容 `/chat/completions` 的 planner，`temperature=0`，要求只返回 JSON。否则使用规则 planner；若 LLM 网络失败、JSON 无效或校验失败，也回退规则 planner。

产物 `QueryAnalysis` 包含：

- 原问题与改写问题；
- 关键词、同义词扩展；
- 子问题；
- 假设；
- 歧义和追问选项；
- `status=ready/needs_clarification`；
- 可执行 `QueryPlan` 或 `plan=null`。

代码：[LLM planner](../../src/minibkn/adapters/llm/query_planner.py)、[规则与总服务](../../src/minibkn/application/query_plan_service.py)、[数据合同](../../src/minibkn/domain/query.py)。

### 3. 歧义时停止

“最近的大客户有哪些？”可能缺少时间范围和“大客户”口径。系统返回问题与选项，不执行查询。用户通过 `clarification_answers` 补充后重新分析。

这不是把模糊问题无限扩写，而是判断：缺失条件会不会实质改变结果。会改变就追问；可以安全确定就直接计划。

### 4. Schema 和取值二次校验

LLM 输出只是候选。Pydantic 和服务还会校验：

- intent 与 aggregates/traversals/action_request 是否一致；
- 对象、字段、关系、动作是否真实存在；
- action 是否启用、是否绑定正确对象、是否有明确实例；
- eq/in 的低基数值是否存在。

不能通过校验的计划不会执行，也不允许 SQL 或 Python 代码进入 QueryPlan。

### 5. 分流执行

- `search`：把改写、关键词、子问题和同义词合成检索文本，进入 BM25 + 向量 + RRF。
- `lookup/traverse/aggregate`：进入确定性的 QueryPlan 执行器。
- `action`：只返回“识别到动作，需要走动作端点”，绝不在问答入口直接执行。
- `needs_clarification`：直接停止。

## B. 知识来源路由 `/ask-routed`

请求可以明确指定：

- `structured`：只查结构化索引；
- `document`：只查 LightRAG；
- `hybrid`：两边都查，证据去重后统一回答；
- `auto`：当前根据“文档、制度、合同、手册、条款、政策”等关键词选 document，否则选 structured。

若自动路线选择文档但 LightRAG 不可用，配置允许时降级到结构化并返回 warning；如果用户明确要求 document，则失败会显式报错。

代码：[knowledge_router_service.py](../../src/minibkn/application/knowledge_router_service.py)、[document_knowledge.py](../../src/minibkn/adapters/document_knowledge.py)。

## 两个例子

### “客户 CUST-001 有哪些订单，总金额多少？”

查询理解可生成以 customer 为起点、沿 `placed_by` 关系遍历订单并聚合金额的计划；应走确定性结构化执行，不应依赖文档相似度猜数字。

### “合同规定逾期付款怎样处理？同时列出当前逾期订单”

理想结果应是 hybrid：合同条款走 LightRAG，逾期订单走 QueryPlan，最后合并证据。当前 `/ask-routed` 能并行取两种证据，但不会自动把一个复合问题拆成“文档子问题 + 结构化子问题”；需要调用者明确选 hybrid，而且结构化侧仍以普通检索问答为主。这是下一步总编排器最值得补齐的能力。

## 推荐的后续统一方式（待增强）

让查询分析额外输出 `knowledge_routes` 与每个 `sub_question` 的目标路线：

```json
{
  "sub_questions": [
    {"text":"合同规定逾期付款怎样处理", "route":"document"},
    {"text":"列出当前逾期订单", "route":"structured", "plan":{}}
  ],
  "merge_strategy":"evidence_first"
}
```

服务端仍要白名单校验路线、Schema、集合权限和证据预算；LLM 只提议，不能越过权限边界。
