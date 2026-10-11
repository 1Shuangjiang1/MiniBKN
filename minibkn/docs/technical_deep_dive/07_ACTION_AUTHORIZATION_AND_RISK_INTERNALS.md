> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 07：执行动作时的权限与风险判定

## 动作不是“模型说执行就执行”

完整安全链路是：

```text
动作请求
 → HTTP 权限：execute + network + action
 → BKN 动作存在、启用且绑定对象正确
 → 目标实例存在且调用者有权看
 → 参数按白名单绑定，拒绝多余/缺失参数
 → 风险 DSL 计算
 → deny / pending_confirmation / running
 → 白名单 ToolRegistry
 → 标准化结果、幂等记录、trace 审计
```

核心代码：[action_service.py](../../src/minibkn/application/action_service.py)、[policy.py](../../src/minibkn/domain/policy.py)、[工具白名单](../../src/minibkn/adapters/tools/registry.py)。

## 第一关：动作权限

路由中间件要求 Principal：

- 具有 `execute`；
- 可以访问目标 network；
- `actions` 中包含当前 action ID 或 `*`。

审批人另需 `approve`，查询执行记录和 trace 需 `audit`。读权限不能自动推导出写权限。

## 第二关：BKN 动作合同

服务确认 action 存在且 `enabled=true`，并检查请求中的 object type 与 `bound_object_type` 一致。实例从当前用户可访问的 resource 中查找；无权限时表现为找不到，避免泄漏对象存在性。

参数只接受 ActionType 声明的绑定：可以从实例属性取得，也可被明确 override。缺参数拒绝，出现未知参数也拒绝。这防止调用者把任意字段塞给工具。

例子见 [补货动作 BKN](../../examples/supply_chain/bkn/action_types/create_replenishment_alert.bkn)。

## 第三关：风险 DSL

RiskType 在 BKN 文件中声明：适用哪些动作、condition、policy。condition 只允许一组安全 JSON/YAML 运算符：and/or/not、比较、in、加减乘除、max/min/abs，以及三种引用域：

- `object.*`：目标实例已有属性；
- `action.*`：绑定后的动作参数；
- `subject.*`：认证用户身份和角色。

没有使用 Python `eval`。表达式限制最大深度和节点数；未知运算、缺失引用、除零或评估错误都失败关闭为 `deny`。

补货例子的风险计算是：

```text
max(0, safety_stock - current_stock) × unit_cost >= 500
```

匹配后 policy 为 `confirm`，所以必须人工批准。定义见 [high_value_replenishment.bkn](../../examples/supply_chain/bkn/risk_types/high_value_replenishment.bkn)。

## 三种最终决策

- 任一匹配风险为 `deny`：`denied`，不会调用工具；
- 无 deny，但有 `confirm`，或 ActionType 自身 `requires_approval=true`：`pending_confirmation`；
- 都没有：进入 `running` 并调用工具。

优先级是 deny 高于 confirm 高于 allow。

## 第四关：工具白名单

BKN 只能引用已在 `ToolRegistry` 注册的 `(toolbox_id, tool_id)`。未注册返回 `TOOL_NOT_ALLOWED`。当前主程序只注册了供应链的本地 `create_replenishment_alert` 演示工具，它只返回“已创建预警”，不会下单或修改外部系统。

因此“BKN 文件写了一个 URL”并不能让模型任意访问网络。接入真实 ERP/CRM 时，需要开发专门 adapter，并补充超时、重试、签名、最小服务账号、幂等和补偿事务。

## 幂等与审计

请求可带 `idempotency_key`，防止相同业务请求被重复执行。每一步写入统一 execution 状态和 trace 事件，例如：

- `action.requested`
- `risk.evaluated`
- `action.awaiting_confirmation`
- `action.confirmation_approved`
- `tool.started`
- `tool.succeeded` / `tool.failed`

客户端还可传/接收 `x-trace-id`，用于回放一次完整决策。

## 工时修改场景怎样设计（当前未实现工具）

`adjust_timesheet` 可以定义：

- 绑定对象：timesheet；
- 参数：employee_id、work_date、job_code 从实例绑定，new_hours 由用户提供；
- deny：调用者既不是授权 HR，也不在允许的管理范围；
- deny：记录已经月结；
- confirm：修改他人记录，或改动超过 2 小时；
- allow：获准行政人员在开放期间做小幅更正；
- 工具：调用考勤服务，而不是直接编辑 CSV。

但行级组织范围、月结状态服务和考勤写回工具都还要新增。现有 DSL 能表达部分规则，现有门禁能承载执行流程，但不能把“框架可扩展”说成“功能已交付”。

测试依据：[test_phase_c_action_api.py](../../tests/integration/test_phase_c_action_api.py)、[test_policy_evaluator.py](../../tests/unit/test_policy_evaluator.py)、[test_authorization_api.py](../../tests/integration/test_authorization_api.py)。
