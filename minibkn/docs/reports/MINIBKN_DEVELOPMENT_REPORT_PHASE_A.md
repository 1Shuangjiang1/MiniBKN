> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 阶段 A 开发报告（通俗版）

## 1. 这一阶段解决了什么问题

如果把完整的 MiniBKN 比作一座“业务知识城市”，阶段 A 做的不是让城市马上开始营业，而是先完成三件基础工作：

1. 规定城市里有哪些建筑——物料、供应商、关系、行动和风险分别是什么。
2. 建立规划审核——定义写错、关系连到不存在的对象、主键不存在时必须拒绝导入。
3. 建好档案馆和服务窗口——合法定义存进 SQLite，并能通过 API 查询。

因此，现在的 MiniBKN 已经能“读懂业务知识网络的设计图”，但还没有开始读取 CSV 中的真实物料实例，也还不能搜索和执行补货行动。这些会按顺序在阶段 B、C 完成。

## 2. 已经开发的内容

### 2.1 一个可以启动的 Python 后端

项目代码放在 `minibkn/`，与上游 Go 项目隔离。它使用 Python 3.11 和 FastAPI，启动后提供：

- 健康检查：`GET /health`
- 自动 API 文档：`http://127.0.0.1:8000/docs`
- 知识网络导入、列表和 Schema 查询接口

配置统一从 `MINIBKN_` 开头的环境变量读取，默认使用本地 SQLite，不需要安装 MySQL、Redis、Kafka 或 OpenSearch。

### 2.2 定义了系统的核心“名词”

目前系统认识以下领域对象：

| 名词 | 通俗解释 |
| --- | --- |
| KnowledgeNetwork | 一整张业务知识网络 |
| ObjectType | 一类业务对象，例如物料、供应商 |
| DataProperty | 对象的字段，例如 SKU、库存、安全库存 |
| RelationType | 对象之间如何关联，例如“物料由供应商供应” |
| ActionType | 对业务对象可以执行什么，例如创建补货预警 |
| RiskType | 某项行动的风险等级和处置策略 |
| DataSourceBinding | 对象未来从哪份 CSV 或数据库资源读取数据 |
| ToolBinding | 行动未来要调用哪个受控工具 |

这些对象不是散乱的字典，而是带严格字段和类型检查的领域模型。后续功能都围绕它们扩展。

### 2.3 实现了简化版 BKN Lang 解析器

MiniBKN 可以读取上游风格的 `.bkn` 文档，包括：

- 文件开头的 YAML frontmatter：文档类型、ID、名称、标签等。
- Markdown 表格：对象属性、关系端点、字段映射、工具配置和参数绑定。
- 对象主键、展示字段。
- 行动的 YAML 触发条件。

例如，`material.bkn` 会告诉系统：

- `material` 是物料对象类；
- `sku` 是主键；
- `name` 是展示字段；
- `current_stock` 和 `safety_stock` 是库存相关字段；
- 数据未来来自 `materials_csv` 资源。

### 2.4 增加了跨文件校验

只把 Markdown 读成数据还不够，系统还会检查这些定义能不能组成一张正确的网络：

- 同一类文档不能出现重复 ID。
- 主键和展示字段必须真实存在。
- 关系两端的对象类必须存在。
- 关系映射的源字段和目标字段必须存在。
- 行动绑定的对象必须存在。
- 从对象属性取行动参数时，该属性必须存在。
- 风险策略只能是 `allow`、`confirm` 或 `deny`。
- 风险引用的行动必须存在。

这相当于在导入前做一次“业务 Schema 编译”。错误不会拖到后续查询或行动阶段才爆发。

### 2.5 建立了 SQLite 档案馆

解析和校验通过后，知识网络会写入两张表：

- `knowledge_networks`：保存整张网络的基本信息和完整快照。
- `bkn_documents`：分别保存对象类、关系类、行动类和风险类。

应用层只依赖 Repository 接口，不直接依赖 SQLite。以后如果需要切换到 MySQL，只需增加新的 Repository 适配器，不必重写业务逻辑。

### 2.6 提供了三个主要 API

| API | 作用 |
| --- | --- |
| `POST /api/v1/networks/import` | 从本地 BKN 目录导入一张知识网络 |
| `GET /api/v1/networks` | 查看已经导入的网络及各类定义数量 |
| `GET /api/v1/networks/{kn_id}/schema` | 查看某张网络的完整 Schema |

所有请求都会获得 `x-trace-id`。发生错误时，响应体也包含相同的 `trace_id`，方便以后将一次请求中的检索、行动和审计事件串起来。

错误响应示例：

```json
{
  "error_code": "INVALID_BKN_DEFINITION",
  "message": "BKN directory does not exist: ...",
  "trace_id": "trace-..."
}
```

### 2.7 准备了供应链主演示

示例目录已经包含：

- 物料 ObjectType
- 供应商 ObjectType
- “由……供应” RelationType
- “创建补货预警” ActionType
- “高价值补货需确认” RiskType
- `materials.csv` 和 `suppliers.csv`

阶段 A 只解析这些定义。阶段 B 会让 CSV 中的具体记录真正进入查询链路。

## 3. 现在可以怎样体验

进入 `minibkn/` 后执行：

```powershell
uv sync --python <local-path> --extra dev --no-editable
Copy-Item .env.example .env
.venv\Scripts\python.exe -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/docs`，调用 `POST /api/v1/networks/import`，请求体填写：

```json
{
  "path": "<local-path>"
}
```

导入成功后：

- `GET /api/v1/networks` 会显示 1 张网络。
- 网络包含 2 个对象类、1 个关系类、1 个行动类和 1 个风险类。
- `GET /api/v1/networks/supply_chain/schema` 可以看到完整解析结果。

## 4. 质量验证结果

本阶段执行了三类检查：

```text
pytest：3 passed
Ruff：All checks passed
mypy：24 个源文件无类型问题
```

测试覆盖：

- 正确供应链网络的解析。
- 对象主键、数据源、行动触发条件和工具绑定。
- 关系指向不存在对象时必须拒绝。
- API 健康检查和 trace ID。
- 导入、保存、列表、读取 Schema 的完整 SQLite 链路。
- 查询不存在网络返回 404。
- 导入不存在目录返回统一的 BKN 定义错误。

## 5. 开发时遇到的问题

项目路径中包含中文。Windows 下使用 Python 3.11 的 editable install 时，会生成包含中文绝对路径的 `.pth` 文件；某些环境按 GBK 读取它，Python 会在启动阶段报编码错误。

最终方案是使用：

```powershell
uv sync --no-editable
```

这样安装的是普通本地包，不再依赖有问题的 `.pth` 文件。README 和长期开发文档已经记录该约束。

## 6. 这一阶段还没有做什么

以下功能并非遗漏，而是有意留给下一阶段：

- 尚未注册和发现 CSV/SQLite 数据源。
- 尚未把 CSV 行转换为物料、供应商实例。
- 尚未根据 `supplier_id` 生成实例关系。
- 尚未实现子图查询。
- 尚未建立全文或向量索引。
- 尚未实现自然语言问答。
- 尚未执行补货工具，也没有完整 Trace 事件账本。

## 7. 下一步建议

阶段 B 建议继续按以下顺序推进：

1. DataSource/Resource 注册与 CSV Schema 发现。
2. 根据 ObjectType 映射读取对象实例。
3. 根据 RelationType 字段映射建立关系。
4. 实现实例查询和一跳/多跳子图查询。
5. 在数据查询正确后，再增加全文与向量检索。
6. 最后实现 `/ask` 的上下文组装和带引用回答。

这样可以先证明“业务知识网络确实连对了”，再在正确数据之上做 AI 检索，定位问题会更清晰。
