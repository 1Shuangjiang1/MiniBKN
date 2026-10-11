> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 企业权限管控产品开发报告

## 1. 本轮交付结论

MiniBKN 0.6.0 已从“一把全局 API Key”升级为可选的企业 RBAC。系统现在能够识别具体用户、合并角色权限，并在读取文件数据、检索、QueryPlan、子图扩展、文档查询和行动执行之前做授权判断。

这次实现的核心不是“最后把答案里的敏感字删掉”，而是让未授权内容根本不进入本轮检索和计算上下文，降低模型根据隐藏资料泄露信息的风险。

## 2. 原来的问题

旧版本的 `MINIBKN_API_KEY` 只能回答“请求是否来自知道统一密码的人”。所有合法请求拥有完全相同的能力，因此无法表达：

- 销售可以读客户和订单，但不能看财务文件；
- 财务可以读发票制度，但不能执行销售行动；
- 经理可以审批，普通员工不能审批；
- 同一个问题由不同用户提问时，应检索不同的数据和文档。

另外，旧风险模拟接口接收客户端自己填写的 `subject`。如果直接把它当真实身份，调用者可以伪造角色。新实现会在启用权限后用认证身份覆盖 `id`、`role` 和 `roles`，不相信客户端自报身份。

## 3. 权限模型

权限策略保存在 JSON 文件中，示例见 `config/access-policy.example.json`。主要分为五层：

| 层级 | 作用 |
|---|---|
| 用户 Principal | 标识当前是谁，可绑定多个角色 |
| 功能权限 | `read`、`model`、`execute`、`approve`、`audit`、`admin` |
| 网络范围 | 用户可访问哪些 BKN 业务网络 |
| 资源范围 | 用户可访问哪些 CSV/SQLite 资源，也就是哪些结构化“文件/表” |
| 文档知识域 | 用户可查询哪些 LightRAG 安全知识域 |
| 行动范围 | 用户可执行哪些白名单业务行动 |

用户密钥不以明文写入策略，只保存 SHA-256 摘要。原有全局 API Key 保留为本地管理员/恢复通道；未开启 RBAC 时保持旧行为，避免破坏原有演示和测试。

## 4. 权限如何进入主链路

```text
x-api-key
  → 验证用户密钥摘要
  → 合并用户的角色授权
  → 检查接口操作权限和业务网络
  → 过滤可见资源/对象/关系/索引文档
  → 执行检索或 QueryPlan
  → 只用已授权证据生成回答
  → 行动另行检查 execute/action，审批另查 approve
```

结构化检索会从 `resource://...` 引用中识别数据资源并在排序前过滤。QueryPlan 的枚举值提示、扫描对象、关系遍历、聚合和证据生成也使用过滤后的对象集合。子图只保留两端都可见的关系，防止通过关系边推断受限对象。

网络 Schema 会移除绑定到不可见资源的对象类型、相关关系和不可执行行动。资源列表同样只显示获得授权的资源。

## 5. LightRAG 权限边界

LightRAG 当前不是完整的企业多租户权限中心。如果把公开制度和财务机密放进同一个工作区，模型在图谱摘要阶段已经可能混合两者，查询后再删除引用并不能保证不泄露。

因此 MiniBKN 采用“安全知识域隔离”：

```text
crm/public  → 一个固定 LightRAG endpoint/workspace
crm/sales   → 另一个固定 LightRAG endpoint/workspace
crm/finance → 另一个固定 LightRAG endpoint/workspace
```

请求只会并行访问当前用户获准的知识域，再合并证据。这比单工作区结果后过滤更安全，也符合 LightRAG 工作区在服务启动后固定的生命周期特点。

## 6. 关键代码和配置

- 身份契约与请求上下文：`src/minibkn/domain/access_control.py`
- 策略加载、认证和过滤：`src/minibkn/application/access_control_service.py`
- HTTP 权限门禁：`src/minibkn/main.py`
- 检索前资源过滤：`src/minibkn/application/retrieval_service.py`
- QueryPlan 权限过滤：`src/minibkn/application/query_plan_service.py`
- 图与行动权限：`src/minibkn/application/graph_service.py`、`action_service.py`
- 策略示例：`config/access-policy.example.json`
- 自动化测试：`tests/integration/test_authorization_api.py`

启用方式：

```powershell
$env:MINIBKN_AUTHORIZATION_ENABLED="true"
$env:MINIBKN_AUTHORIZATION_POLICY_FILE=".\config\access-policy.example.json"
```

示例中的演示密钥是公开测试值，不得用于真实环境。生产环境应生成高熵密钥，只把摘要写入策略，并通过企业密钥管理系统分发原始值。

## 7. 测试结果

新增测试覆盖：

- 无凭证返回 401；
- 合法用户只能看到授权网络；
- 客户文件读者可以读取客户实例，但订单实例为空；
- 管理员已缓存完整索引后，普通用户检索仍不会命中受限订单行；
- 无建模权限不能重建索引；
- 无行动权限不能调用工具；
- Schema 按可见资源裁剪；
- 策略中出现明文或非法摘要时启动失败，默认关闭而不是放行。

本轮新增权限专项测试 2 项，连同 LightRAG 适配器专项共 3 项均通过。全量结果以本轮最终验收和最新测试输出为准。

## 8. 当前边界

这是适合本地作品集和中小型内部应用的 RBAC，不应包装成成熟 IAM 产品。当前没有实现：

- OAuth2/OIDC、SSO、LDAP/AD；
- 动态策略数据库和管理后台；
- 行级条件策略与逐字段脱敏；
- 密钥轮换、撤销列表和集中式审计平台；
- 跨实例策略缓存失效。

如果进入生产化，下一步应接企业身份提供商，使用签名 JWT/短期令牌，并把策略决策事件发送到不可篡改审计存储。
