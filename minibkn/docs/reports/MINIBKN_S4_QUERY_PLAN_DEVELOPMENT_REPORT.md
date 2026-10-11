> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN S4 QueryPlan 产品开发报告

> 完成日期：2026-08-16\
> 前置报告：[S3 真实 Embedding 产品开发报告](MINIBKN_S3_EMBEDDING_DEVELOPMENT_REPORT.md)\
> 对应计划：[分步开发计划](../plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)\
> 状态：已完成

## 1. 与 S3 的衔接

S3 负责可靠地召回候选信息，S4 负责先理解“用户究竟想查什么”。QueryPlan 不依赖硅基流动的具体实现，也不会绕过 S3 的索引版本保护。

## 2. 已完成能力

- 定义并执行受约束的 QueryPlan JSON；
- 支持对象选择、字段投影、字面值过滤、字段间比较；
- 支持 `eq/neq/gt/gte/lt/lte/in/not_in/like/exist/not_exist`；
- 支持最多五跳的入向、出向和双向关系遍历；
- 支持 count、sum、avg、min、max、分组、排序和 limit；
- 聚合结果进入 `computed` 证据；
- 所有对象、字段、关系和动作都由已发布 BKN 白名单校验；
- 扫描超过 10,000 个对象会被成本门禁拒绝；
- 提供 OpenAI-compatible LLM 计划适配器；
- 无 LLM 配置时使用安全的规则型退化计划；
- LLM 输出夹带 `raw_sql` 或未知字段时，Pydantic 会直接拒绝。

## 3. 新增 API

```text
POST /api/v1/networks/{network_id}/query-plans/preview
POST /api/v1/networks/{network_id}/query-plans/execute
POST /api/v1/networks/{network_id}/ask-planned
```

`preview` 只生成和校验计划；`execute` 执行用户明确提交的计划；`ask-planned` 串联计划、执行和证据回答。原 `/ask` 保持兼容。

## 4. 已验证示例

- 通用字段比较：`material.current_stock < material.safety_stock` 只返回 MAT-001、MAT-003；
- CRM 聚合：按客户汇总已付款订单金额；
- 图跳转：从 ORD-001 沿 `placed_by` 找到 CUST-001；
- 非法字段：`customer.password` 返回 `422 INVALID_QUERY_PLAN`；
- LLM 结构化输出：模拟 OpenAI-compatible 服务成功生成聚合计划；
- 任意 SQL：模拟模型返回 `raw_sql` 时被拒绝。

## 5. 测试结果

```text
S4 定向测试：4 passed
全量测试：32 passed
Ruff：通过
Mypy strict：54 个源文件通过
```

## 6. 限制

- 没有真实 LLM Key 时，规则型计划只能完成简单对象识别和计数，复杂自然语言应显式提交 QueryPlan 或配置 LLM；
- 当前执行器在内存中扫描对象，10,000 是安全上限，不是数据库查询优化器；
- 不支持任意 SQL、任意表达式或跨对象字段直接计算；
- QueryPlan 的动作请求只被校验，真实动作仍必须进入 S5 风险门禁。

## 7. 给 S5 的要求

S5 不得直接执行 QueryPlan 中的动作请求。它必须把动作、对象、参数和主体上下文交给通用风险 DSL，得到 allow、confirm 或 deny 后才能进入工具注册表。
