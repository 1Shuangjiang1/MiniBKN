> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 08：大模型怎样判断要不要执行动作

## 直接答案

有明确参数。查询理解的核心字段是：

```json
{
  "intent":"action",
  "action_request":{
    "action_type_id":"create_replenishment_alert",
    "object_type_id":"material",
    "instance_id":"MAT-001",
    "parameters":{}
  }
}
```

`intent` 的可选值是 `search`、`lookup`、`traverse`、`aggregate`、`action`。只有 `intent=action` 时才允许且必须有 `action_request`。Pydantic 在对象创建时强制这一合同。

定义见 [domain/query.py](../../src/minibkn/domain/query.py)。

## LLM 的判断依据

LLM planner 获得当前 BKN 中允许的对象、关系、字段和“已启用动作 ID”。提示词要求：只有用户明确提出业务操作，且能落到已知动作时，才生成 action intent；不能发明动作、字段或实例。

例如：

- “MAT-001 库存是多少？” → lookup/search；
- “MAT-001 是否应该补货？” → 仍是查询/判断，不应自动执行；
- “为 MAT-001 创建补货预警” → action + 明确 action_request；
- “帮我处理一下库存” → 目标和动作不清楚，应追问，而不是猜测执行。

实现见 [OpenAICompatibleQueryPlanner](../../src/minibkn/adapters/llm/query_planner.py)。

## LLM 输出后还有三重限制

1. 数据合同校验：action intent 缺 `action_request` 直接无效。
2. Schema 校验：action 必须存在且启用，object type 必须匹配动作绑定。
3. 实例校验：必须给一个明确 `instance_id`；不允许“把所有库存低的物料都处理了”在问答入口批量执行。

所以参数不是一个简单的 `should_execute=true`。它是一个结构化动作候选，包含“做什么、对谁做、参数是什么”。

## `requires_action_confirmation` 到底是什么

`/ask-intelligent` 的响应还有：

```json
{"requires_action_confirmation":true}
```

这个命名容易误解。当前含义是：**问答入口识别到动作，但不会执行，请调用显式动作/风险流程。** 它不代表风险 DSL 已经计算出“一定需要人工审批”。

真正的 `allow/confirm/deny` 只有在 `/risks/simulate` 或 `/actions/.../execute` 读取目标实例并计算 RiskType 后才能确定。

代码见 [QueryPlanService.ask_intelligently](../../src/minibkn/application/query_plan_service.py) 和 [ActionService](../../src/minibkn/application/action_service.py)。

## 实际调用流程

用户：“为 MAT-001 创建补货预警。”

1. `/ask-intelligent` 返回 `intent=action`、完整 `action_request`、`requires_action_confirmation=true`；没有副作用。
2. UI 展示即将操作的对象、动作和参数，让用户确认意图。
3. 调 `/risks/simulate`，返回 `confirm`，仍无副作用。
4. 用户显式提交 `/execute`，服务端重新做权限、参数和风险检查。
5. 若状态为 `pending_confirmation`，具有 approve 权限的人调用 `/confirm`。
6. 只有最终通过才调用白名单工具。

## 当前实现中的一个重要限制

规则 planner 当前主要识别检索和聚合，没有像 LLM planner 那样通用地产生 action_request；想获得自然语言动作识别，通常需要启用配置好的 OpenAI-compatible LLM，或者由客户端直接提交结构化动作端点。

此外，当前 UI 问答页调用 `/ask-routed`，不是 `/ask-intelligent`，所以网页上尚未把“自然语言动作识别 → 展示候选 → 风险模拟 → 审批”串成一个向导。后端安全能力已经分段存在，UI 总编排仍待增强。

## 为什么不能让 LLM 直接决定最终执行

LLM 适合把自然语言转成候选意图，但不应负责最终权限和风险结论：

- 权限来自已认证身份，不来自模型推测；
- 风险需要真实对象值和确定性规则；
- 同一请求需要幂等和审计；
- 高风险动作必须支持独立审批人；
- 模型输出可能不稳定，不能代替事务边界。

因此本项目采用“LLM 提议、类型系统校验、策略引擎裁决、白名单工具执行”的分工。
