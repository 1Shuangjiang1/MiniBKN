> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 04：认证层与 RBAC 是怎样工作的

## 一句话区分

- **认证 Authentication**：确认请求者是谁。
- **授权 Authorization**：确认这个人能对哪个网络、文件、文档域和动作做什么。

MiniBKN 当前使用本地 API Key + JSON 策略文件实现演示级认证与 RBAC，没有接入企业 SSO、OAuth/OIDC 或 IAM。

## 认证过程

请求在 HTTP 中携带：

```text
x-api-key: <用户的演示 Key>
```

FastAPI 中间件在业务路由之前执行：

1. 读取 `x-api-key`；
2. 对输入 Key 计算 SHA-256；
3. 与策略文件中的摘要做恒定时间比较；
4. 找到对应 `Principal`；
5. 把 Principal 放入当前异步请求的 `ContextVar`；
6. 做路由级粗授权；
7. 请求结束后清理上下文，避免身份串到其他请求。

代码入口：

- [main.py 的中间件与路由授权](../../src/minibkn/main.py)
- [AccessControlService.authenticate](../../src/minibkn/application/access_control_service.py)
- [Principal 与 ContextVar](../../src/minibkn/domain/access_control.py)
- [示例策略文件](../../config/access-policy.example.json)

策略中存 Key 的 SHA-256，而不是明文。它能避免把演示 Key 直接写进策略，但 SHA-256 不是专门的密码哈希；生产中仍应使用身份提供商、短期令牌、轮换和密钥管理服务。

## RBAC 数据结构

一个 Principal 合并其多个角色后，得到六组授权范围：

| 字段 | 含义 |
| --- | --- |
| `permissions` | read、model、execute、approve、audit、admin |
| `networks` | 能进入哪些知识网络 |
| `resources` | 能看到哪些 CSV/SQLite 资源 |
| `document_collections` | 能访问哪些 LightRAG 安全域 |
| `actions` | 能执行哪些动作 |
| `roles` | 角色名称，也会进入风险判断上下文 |

`*` 代表该维度全部允许；`admin` 或 `permissions=["*"]` 是全局管理权限。

## 两层授权，而不只是路由拦截

### 第一层：HTTP 路由权限

`_authorize_http_request` 根据方法和路径要求：

- GET、搜索、问答、QueryPlan、风险模拟：`read`；
- 数据源、建模、构建等写操作：`model`；
- 动作执行：`execute` + 指定 action 在白名单中；
- 确认：`approve`；
- 执行记录、trace、评测：`audit`。

若 URL 带 network ID，还会检查 Principal 是否获准访问该网络。

### 第二层：对象和证据过滤

只做路由级权限不够。用户即使能进入 CRM 网络，也未必能看所有文件。因此：

- 数据源列表会移除未授权资源；
- 对象实例按 `resource_id` 过滤；
- 关系只有两端对象都可见才保留；
- 搜索文档的 citation 若是 `resource://...`，会在检索前过滤；
- QueryPlan 执行只扫描获准资源中的对象；
- 子图只能从可见对象出发；
- 动作取目标实例时再次按资源权限过滤；
- LightRAG 查询只把获准 collection 交给 adapter。

对应代码：

- [access_control_service.py](../../src/minibkn/application/access_control_service.py)
- [retrieval_service.py](../../src/minibkn/application/retrieval_service.py)
- [query_plan_service.py](../../src/minibkn/application/query_plan_service.py)
- [graph_service.py](../../src/minibkn/application/graph_service.py)
- [knowledge_router_service.py](../../src/minibkn/application/knowledge_router_service.py)
- [action_service.py](../../src/minibkn/application/action_service.py)

安全原则是“在进入检索/计算上下文前过滤”，不是等大模型生成答案后再遮盖。

## 为什么 LightRAG collection 要物理隔离

MiniBKN 不只是查询后按 collection 标签过滤。endpoint 映射规定一个 network 下不同 collection 指向不同 LightRAG endpoint/workspace。原因是文档切块、实体关系和向量一旦混进同一工作区，检索阶段可能已经跨域泄漏；最后过滤结果来不及阻止模型内部召回。

实现见 [LightRAGDocumentKnowledge](../../src/minibkn/adapters/document_knowledge.py)。

## “认证身份不能由请求者自己填写”

风险模拟请求允许有 `subject` 字段，便于关闭 RBAC 的离线演示。但启用认证后，`ActionService._trusted_subject` 会用当前认证 Principal 覆盖 `id`、`roles`、`role`。用户不能提交 `{"role":"manager"}` 假装自己是经理。

## 当前边界

- API Key 是本地演示认证，不是完整企业登录。
- 权限策略启动时读取，修改文件后通常要重启。
- 没有行级与字段级授权，也没有组织层级 ABAC。
- 当前确认接口先做通用 approve 检查，再根据 execution 网络检查；已能防止普通执行者自行批准。
- UI 不负责安全，后端即便被直接调用也必须拒绝越权请求。

测试依据：[test_authorization_api.py](../../tests/integration/test_authorization_api.py) 与 [企业权限报告](../reports/MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md)。
