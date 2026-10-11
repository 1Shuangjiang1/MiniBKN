> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 02：如何启动和测试具体功能

## 1. 环境准备

- Python 3.11（项目约束为 `>=3.11,<3.13`）
- `uv`
- Node.js `^20.19.0` 或 `>=22.12.0`（当前 Vite 锁定包的要求）
- 可选：Docker、DeepSeek/硅基流动 Key、LightRAG 独立 Python 3.12 环境

以下命令均从 `<local-path>` 开始。

## 2. 最快验证：不启动网页、不用外部 API

```powershell
cd minibkn
uv sync --python <local-path> --extra dev --no-editable
.\scripts\demo.ps1
```

这个脚本会在进程内完成：导入供应链 BKN、发现两张 CSV、生成图、建索引、问答、提交动作、确认动作和读取审计轨迹。它会为本次演示创建独立 SQLite 文件，不依赖已经启动的 HTTP 服务。

预期重点：

- `graph` 中有对象与关系数量；
- 回答包含库存不足物料及引用；
- `action_before_confirmation` 是 `pending_confirmation`；
- 确认后为 `succeeded`；
- `trace_events` 包含风险、确认和工具执行事件。

实现见 [demo.py](../../scripts/demo.py)。

## 3. 启动后端

```powershell
cd minibkn
Copy-Item .env.example .env
.venv\Scripts\python.exe -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

浏览器打开：

- 健康检查：<http://127.0.0.1:8000/health>
- Swagger：<http://127.0.0.1:8000/docs>

默认 `.env.example` 使用离线哈希向量、关闭 LLM、关闭 RBAC、关闭 LightRAG，最适合先验证结构化主链路。

## 4. 启动 UI

另开一个 PowerShell：

```powershell
cd minibkn-ui
npm install
npm run dev
```

打开终端显示的地址，通常是 <http://127.0.0.1:5173>。后端地址默认已经填好。未启用权限时 API Key 留空。

## 5. 推荐手工测试案例

### 案例 A：结构化端到端

在 Swagger 依次执行：

1. `POST /api/v1/networks/import`

```json
{"path":"<local-path>"}
```

2. `POST /api/v1/sources`

```json
{
  "id":"supply_chain_files",
  "name":"供应链样例",
  "kind":"csv",
  "path":"<local-path>"
}
```

3. 调用 `/sources/supply_chain_files/discover`。
4. 调用 `/networks/supply_chain/builds`，预期 `status=published`。
5. 调用 `/networks/supply_chain/ask`：

```json
{"question":"哪些物料库存低于安全库存，它们由谁供应？"}
```

预期命中 MAT-001、MAT-003、供应商关系和 CSV 行引用。

### 案例 B：歧义追问

先构建 CRM 示例，再请求：

`POST /api/v1/networks/crm/query-plans/analyze`

```json
{"question":"最近的大客户有哪些？","clarification_answers":{}}
```

预期 `status=needs_clarification`，至少指出“最近”的时间范围和“大客户”的衡量口径不明确。补充 `time_range`、`size_metric` 后再次请求，系统才可给出计划。规则与 LLM 两种 planner 的细节见 [05](05_QUERY_UNDERSTANDING_AND_ROUTING_INTERNALS.md)。

### 案例 C：动作风险与审批

调用：

`POST /api/v1/networks/supply_chain/actions/create_replenishment_alert/risks/simulate`

```json
{"object_type_id":"material","instance_id":"MAT-001","parameters":{},"idempotency_key":"demo-001","subject":{}}
```

预期 `decision=confirm`。再调用 `/execute`，得到 `pending_confirmation` 与执行 ID；用 `/api/v1/action-executions/{id}/confirm` 批准后才运行本地白名单工具。

### 案例 D：权限拒绝

将 `.env` 设置为：

```text
MINIBKN_AUTHORIZATION_ENABLED=true
MINIBKN_AUTHORIZATION_POLICY_FILE=./config/access-policy.example.json
```

示例明文 Key 仅用于本地演示：`demo-sales-key`、`demo-finance-key`、`demo-manager-key`。在 Swagger 的请求头传 `x-api-key`：

- 不传或传错：预期 401；
- finance 调用建模或动作：预期 403；
- sales 读取允许的 CRM 文件：成功；
- manager 建模、审批、审计：成功。

### 案例 E：自动文档路由降级

默认未启动 LightRAG 时，调用 `/ask-routed`：

```json
{"question":"客户有哪些订单？","route":"auto"}
```

预期走 `structured`。若明确 `route=document`，预期返回文档能力未启用，而不是伪造结果。完整 LightRAG 启动见项目 [README](../../README.md) 和 [专项报告](../reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md)。

## 6. 自动化测试

后端：

```powershell
cd minibkn
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m mypy src
```

前端：

```powershell
cd minibkn-ui
npm test
npm run lint
npm run build
```

截至 0.6.0 最终验收，后端 74 项通过，前端 8 项通过；最新数字和运行边界以 [0.6.0 最终验收](../reports/MINIBKN_0_6_FINAL_ACCEPTANCE_REPORT.md) 为准。
