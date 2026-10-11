> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN S5 风险 DSL 与动作门禁产品开发报告

> 完成日期：2026-08-16\
> 前置报告：[S4 QueryPlan 产品开发报告](MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md)\
> 对应计划：[分步开发计划](../plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)\
> 状态：已完成

## 1. 与 S4 的衔接

S4 可以在 QueryPlan 中识别动作请求，但不会执行。S5 建立了独立风险门禁：无论动作来自 API、未来的 QueryPlan 还是 AI 推荐，都必须经过同一个规则引擎。

## 2. 已完成能力

- 风险条件正式保存在 BKN frontmatter 中；
- 用白名单表达式树替代 `eval` 和供应链专属公式；
- 支持 object、action、subject 三种引用范围；
- 支持 and、or、not、比较、集合包含、加减乘除、max/min/abs；
- 表达式限制深度 20、节点 200；
- BKN 导入时校验操作符、参数数量、引用范围以及对象/动作字段；
- 风险计算失败时强制生成 deny，动作不会执行；
- 冲突顺序保持 deny > confirm > allow；
- ActionType 的 `requires_approval` 会产生明确确认门禁；
- 新增只读风险模拟 API，不会创建执行记录或调用工具；
- 旧 `value_threshold` 文件仍可由导入适配器转换，当前供应链示例已迁移到新 DSL。

## 3. 风险规则示例

当前补货规则通过 `sub → max → mul → gte` 计算缺口金额。规则本身位于 BKN，执行器不再认识 `current_stock`、`safety_stock` 或 `unit_cost` 的业务含义。

## 4. 新增 API

```text
POST /api/v1/networks/{network_id}/actions/{action_type_id}/risks/simulate
```

返回 allow、confirm 或 deny 及每条规则的命中情况。请求中的 subject 只用于模拟；真实执行接口不会信任客户端自报角色。后续接入认证系统后，真实 subject 必须来自服务端身份上下文。

## 5. 测试结果

```text
全量测试：38 passed
Ruff：通过
Mypy strict：55 个源文件通过
```

覆盖嵌套业务规则、安全算术、恶意操作符、除零、缺失引用、复杂度约束、风险模拟，以及原有确认/拒绝/执行/Trace 回归。

## 6. 限制

- 当前没有正式 OAuth/角色系统，真实 subject 权限规则会因缺失引用而 fail closed；
- 风险版本随 KnowledgeNetwork 保存，尚未提供单独的规则发布审批表；
- 工具补偿事务和跨系统回滚仍需结合具体业务工具实现；
- AI 只能在 S7 起草风险提案，不能发布或批准规则。

## 7. 给 S6 的要求

增量构建不得绕过风险版本。每次动作和模拟继续记录当前网络版本；局部更新失败时不能让半成品图或索引成为在线版本。
