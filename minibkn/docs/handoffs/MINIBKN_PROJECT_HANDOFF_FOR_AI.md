> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 项目完整交接文档

> 本文用于向后续 AI 或开发者完整介绍 MiniBKN 项目本身，包括项目目标、系统架构、核心流程、
> 已实现功能、测试证据、已知边界，以及各部分的详细资料入口。
>
> 本文只记录项目事实，不包含用户个人背景，也不规定阅读者如何讲解项目。

## 0. 项目基本信息

| 项目项 | 内容 |
| --- | --- |
| 项目名称 | MiniBKN |
| 当前版本 | 0.4.0 |
| 项目类型 | Python 为主的 BKN Foundry 核心流程本地复现 |
| 上游项目 | <https://github.com/openbkn-ai/bkn-foundry> |
| 上游分析基线 | `main` / `c2a703edc244ddce7d1d858c6c1f132c43834c08` |
| 上游基线版本 | 0.1.4 |
| 本地运行环境 | Windows、Python 3.11 |
| Python 项目目录 | `<local-path>` |
| 主程序入口 | `minibkn/src/minibkn/main.py` |
| MCP 入口 | `minibkn/src/minibkn/mcp_server.py` |
| 主演示场景 | 供应链库存不足查询与补货预警 |
| 默认数据库 | SQLite |
| 当前状态 | Python 核心主流程已完成并通过本地验收 |

---

## 1. 项目主要是做什么的

MiniBKN 是一个轻量级业务知识网络引擎。

它把 CSV 或 SQLite 中的结构化业务数据转换成：

- 业务对象；
- 对象属性；
- 对象之间的关系；
- 可以针对对象执行的业务行动；
- 行动适用的风险规则。

系统随后可以对这些内容建立关键词和向量索引，回答带来源引用的业务问题，并在用户明确申请
行动时执行以下安全流程：

```text
业务数据
  → 业务 Schema
  → 对象实例和关系边
  → 混合检索
  → 三层业务上下文
  → 带来源回答
  → 明确行动申请
  → 参数校验
  → 风险判断与人工确认
  → 白名单工具执行
  → Trace 审计记录
```

MiniBKN 的核心价值不只是“搜索数据”，而是把业务数据、业务关系、业务行动和风险控制连接成
一条可以本地运行的完整链路。

---

## 2. 项目为什么采用当前架构

上游 BKN Foundry 是大型多语言微服务平台，包含 Kubernetes、多个后端服务、模型服务、
OpenSearch、Redis、Kafka、数据库和权限系统等组件。

MiniBKN 的目标不是完整替代上游平台，而是为本地学习、秋招展示和现场演示复现核心流程。

因此项目采用 Python 模块化单体：

- 所有核心业务模块运行在一个 FastAPI 服务中；
- 各模块通过明确的领域模型和端口接口分离；
- 默认只依赖本地 SQLite；
- 不需要 Kubernetes；
- 不需要外部搜索引擎或向量数据库；
- 不配置 LLM API Key 也能完成主演示；
- 后续可以在不重写业务逻辑的情况下替换数据库、模型、数据源和工具。

这种方案优先保证：

- 主流程完整；
- 本地启动简单；
- 功能可测试；
- 架构边界可解释；
- 结果可以复现；
- 面试现场可以实际运行。

架构决策和完整范围见：

- `MINIBKN_REPRODUCTION_PLAN.md`
- `minibkn/docs/ARCHITECTURE.md`

---

## 3. 系统总体架构

```text
REST API / Swagger / MCP / demo.py
                  |
                  v
       Application Services
       ├── Network Service
       ├── Graph Service
       ├── Retrieval Service
       ├── Schema Generation Service
       └── Action Service
                  |
                  v
           Domain Models
       Object / Relation / Action / Risk
                  |
                  v
              Ports
   Repository / DataSource / Search / LLM / Tool
                  |
                  v
             Adapters
 CSV / SQLite / BM25 / Vector / RRF / LLM / Local Tool
```

### 3.1 入口层

入口层包括：

- FastAPI REST API；
- Swagger/OpenAPI 页面；
- MCP 2.x stdio Server；
- 一键演示脚本。

### 3.2 应用服务层

| 服务 | 作用 |
| --- | --- |
| `KnowledgeNetworkService` | 导入、解析、校验、保存和查询知识网络定义 |
| `KnowledgeGraphService` | 注册数据源、发现资源、物化对象和关系、查询子图 |
| `RetrievalService` | 建索引、搜索、组装三层上下文、生成抽取式回答 |
| `SchemaGenerationService` | 根据已发现资源生成初始 ObjectType 和 RelationType |
| `ActionService` | 行动参数绑定、风险判断、确认、工具调用和 Trace |

### 3.3 领域层

领域层定义系统的核心业务对象和约束：

- KnowledgeNetwork；
- ObjectType；
- DataProperty；
- RelationType；
- ActionType；
- RiskType；
- DataSource；
- Resource；
- ObjectInstance；
- RelationInstance；
- SearchDocument；
- ActionExecution；
- TraceEvent。

### 3.4 端口层

端口定义业务层需要的能力，但不绑定具体技术实现：

- KnowledgeNetwork Repository；
- KnowledgeGraph Repository；
- Execution Repository；
- DataSource Adapter；
- Embedder；
- Schema Enhancer；
- Tool。

### 3.5 适配器层

当前适配器包括：

- BKN Lang 解析器；
- CSV 数据源；
- SQLite 数据源；
- SQLAlchemy SQLite Repository；
- BM25 检索；
- token-hashing 向量；
- Sentence Transformers 适配器；
- RRF 融合；
- OpenAI-compatible Schema 描述增强；
- 本地补货预警工具。

代码目录说明见本文第 20 节。

---

## 4. BKN Schema 能力

MiniBKN 实现了上游 BKN Lang 的必要子集。

当前支持的文档类型：

- `knowledge_network`；
- `object_type`；
- `relation_type`；
- `action_type`；
- `risk_type`。

当前解析内容：

- YAML frontmatter；
- Markdown 属性表；
- 对象主键；
- 对象展示字段；
- 数据源绑定；
- 关系端点；
- 关系字段映射；
- 行动绑定对象；
- 行动工具绑定；
- 行动参数绑定；
- Trigger Condition YAML；
- 风险策略；
- 风险适用行动；
- 风险阈值。

### 4.1 跨文档校验

导入时会检查：

- 重复 ID；
- 主键和展示字段是否存在；
- 关系源端和目标端对象是否存在；
- 关系映射字段是否存在；
- 行动绑定对象是否存在；
- 行动属性参数绑定是否存在；
- 风险策略是否合法；
- 风险引用的行动是否存在。

错误的 BKN 定义会在导入阶段被拒绝，不会等到查询或行动时才失败。

详细资料：

- 阶段 A 报告：`MINIBKN_DEVELOPMENT_REPORT_PHASE_A.md`
- 示例定义：`minibkn/examples/supply_chain/bkn/`
- 解析器代码：`minibkn/src/minibkn/adapters/bkn_lang/`
- 领域模型：`minibkn/src/minibkn/domain/models.py`

---

## 5. 数据源与资源发现

### 5.1 当前支持的数据源

- 单个 CSV 文件；
- CSV 文件目录；
- SQLite 数据库文件。

### 5.2 资源发现内容

系统会记录：

- 资源 ID；
- 资源名称；
- 所属数据源；
- 字段名称；
- 推断字段类型；
- 主键标记或主键候选；
- 数据行数。

CSV 支持 UTF-8 BOM。SQLite 使用表结构信息识别字段和主键。

### 5.3 当前不支持的数据源

- MySQL；
- PostgreSQL；
- Oracle；
- HTTP API；
- PDF；
- Word；
- Markdown 文档；
- 企业知识库；
- LightRAG。

详细资料：

- 阶段 B 报告：`MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md`
- 数据源适配器：`minibkn/src/minibkn/adapters/datasource/`
- 数据源端口：`minibkn/src/minibkn/ports/datasource.py`

---

## 6. 自动 Schema 生成

在资源发现之后，系统可以根据表和字段生成初始 KnowledgeNetwork。

### 6.1 对象生成

每个 Resource 生成一个 ObjectType：

- 资源名转换为对象 ID；
- 资源字段转换为 DataProperty；
- 字段类型保留；
- 字段与源字段一一映射；
- 已识别主键作为对象主键；
- 没有主键时使用第一个字段；
- 如果存在 `name` 字段则作为展示字段，否则使用主键。

### 6.2 关系生成

当前只使用确定性字段规则：

- 源对象属性以 `_id` 结尾；
- 另一个对象使用同名属性作为主键；
- 两个条件满足时生成 RelationType。

例如：

```text
material.supplier_id
supplier.supplier_id（主键）
```

会生成 `material_to_supplier`。

如果字段名称不同，即使业务含义相同，当前规则也无法自动识别。

### 6.3 可选 AI 增强

配置 OpenAI-compatible 模型后，可以让 AI 改善对象和关系的描述。

AI 不能：

- 修改 ID；
- 修改主键；
- 修改字段；
- 修改字段映射；
- 新增对象；
- 新增关系。

当前真实外部 LLM 调用没有执行，因为用户没有提供凭证；适配器通过 MockTransport 测试。

详细资料：

- 服务代码：`minibkn/src/minibkn/application/schema_generation_service.py`
- AI 适配器：`minibkn/src/minibkn/adapters/llm/openai_compatible.py`
- AI 端口：`minibkn/src/minibkn/ports/schema_ai.py`
- 测试：`minibkn/tests/unit/test_schema_ai_adapter.py`

---

## 7. 对象和关系物化

物化将 BKN Schema 和源数据转换为具体图实例。

### 7.1 对象实例生成

系统根据 ObjectType 的 DataSourceBinding 找到 Resource，读取数据行，再按照每个属性的
`mapped_field` 生成 ObjectInstance。

实例 ID 由对象主键组成，展示名称由 display key 生成。

每个实例保留：

- 所属网络；
- 对象类型；
- 实例 ID；
- 展示名称；
- 来源资源；
- 来源行号；
- 全部业务属性。

### 7.2 关系实例生成

系统按照 RelationType 的源对象、目标对象和映射字段遍历实例。

当所有映射字段值相等时，生成 RelationInstance。

### 7.3 存储位置

对象和关系主要存入 MiniBKN SQLite：

- `object_instances`；
- `relation_instances`。

当前不会生成一个包含所有实例和关系的独立图文件。

详细资料：

- 服务代码：`minibkn/src/minibkn/application/graph_service.py`
- Repository：`minibkn/src/minibkn/adapters/persistence/repository.py`
- 数据库表：`minibkn/src/minibkn/adapters/persistence/tables.py`

---

## 8. 子图查询

系统支持从一个 ObjectInstance 出发遍历关系边。

接口允许设置深度 1～5。

查询结果包含：

- 访问到的 ObjectInstance 节点；
- 连接这些节点的 RelationInstance 边。

主演示中：

```text
MAT-001 Temperature Sensor
  -- supplied_by -->
SUP-001 Precision Components
```

当前图遍历使用 Python BFS，适合本项目小数据量场景，没有使用 Neo4j 或其他图数据库。

详细资料：

- `minibkn/src/minibkn/application/graph_service.py`
- `MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md`

---

## 9. 搜索索引

建立索引时，系统生成三层 SearchDocument。

### 9.1 Schema 文档

包括：

- ObjectType；
- RelationType。

内容包含名称、描述、属性、关系端点等。

### 9.2 Instance 文档

每个 ObjectInstance 生成一个文档，包含：

- 对象类型；
- 展示名称；
- 实例 ID；
- 全部属性名和值；
- 来源资源和行号。

### 9.3 Action 文档

每个启用的 ActionType 生成一个文档，包含：

- 行动名称；
- 行动描述；
- 绑定对象类型；
- BKN 来源。

### 9.4 当前未直接索引的内容

具体 RelationInstance 不会单独生成 SearchDocument。关系类型定义可以被检索，具体关系边用于
命中实例之后的子图扩展。

### 9.5 存储

SearchDocument 和向量保存在 SQLite 的搜索文档表中。

详细资料：

- `minibkn/src/minibkn/application/retrieval_service.py`
- `minibkn/src/minibkn/adapters/persistence/repository.py`

---

## 10. BM25、Vector 和 RRF

### 10.1 BM25

关键词检索，适合：

- 物料编号；
- 字段名称；
- 精确业务词；
- 专有名词。

### 10.2 Vector

当前默认实现是 128 维 token-hashing 离线向量：

- 不需要下载模型；
- 结果确定；
- 适合测试向量通道和 RRF；
- 不等于训练过的语义 embedding。

项目同时提供 Sentence Transformers 适配器：

- 延迟加载模型；
- 调用 `SentenceTransformer.encode`；
- 请求归一化向量；
- 用假模块完成适配器测试；
- 当前没有下载真实模型并重新进行完整评测。

### 10.3 RRF

RRF 根据 BM25 和 Vector 的排名进行融合，不要求两路分数在相同尺度。

当前默认 `rrf_k=60`。

### 10.4 搜索模式

- `bm25`；
- `vector`；
- `hybrid`，默认。

`/search` 的 `limit` 范围为 1～50，默认 10。

详细资料：

- 检索实现：`minibkn/src/minibkn/adapters/search/hybrid.py`
- 语义适配器：`minibkn/src/minibkn/adapters/search/semantic.py`
- 搜索端口：`minibkn/src/minibkn/ports/search.py`
- 评测结果：`MINIBKN_FINAL_ACCEPTANCE_REPORT.md`

---

## 11. 三层上下文与问答

`/ask` 当前执行：

1. 对问题进行混合检索，取前 20 条；
2. Schema 最多保留 5 条；
3. Instance 最多保留 8 条；
4. Action 最多保留 5 条；
5. 围绕命中的实例读取关系并扩展子图；
6. 生成回答；
7. 返回上下文和引用。

### 11.1 ContextBundle

返回内容：

- `schema`：Schema SearchHit；
- `instances`：实例 SearchHit；
- `subgraph`：相关节点和边；
- `actions`：行动 SearchHit。

### 11.2 当前回答方式

主演示问题使用确定性抽取逻辑：

- 查找 `current_stock < safety_stock` 的对象；
- 查找对应供应商；
- 生成固定结构的业务回答。

其他问题如果存在子图，会返回相关对象名称，并提示结合上下文和引用核验。

当前没有实现通用 LLM 生成式问答。

### 11.3 引用

- Schema/Action：`bkn://...`；
- Instance：`resource://资源ID#row=行号`。

详细资料：

- `minibkn/src/minibkn/application/retrieval_service.py`
- `MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md`
- `MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md`

---

## 12. 行动定义

ActionType 必须提前定义，不从表格自动生成，也不由 AI 在查询时临时编造。

行动定义包含：

- ID；
- 名称；
- 描述；
- 是否启用；
- 绑定对象类型；
- Trigger Condition；
- 工具类型、Toolbox ID、Tool ID；
- 参数名称；
- 参数来源；
- 对象属性绑定。

已启用的行动会进入搜索索引。

当前行动相关性主要由问题和以下文本之间的 BM25/Vector 排名决定：

- 行动名称；
- 行动描述；
- 绑定对象类型。

执行阶段还会再次验证行动和对象类型是否匹配。

示例定义：

- `minibkn/examples/supply_chain/bkn/action_types/create_replenishment_alert.bkn`

---

## 13. 行动执行与风险控制

问答和行动执行是两个独立步骤。

用户或 MCP 客户端必须明确提供：

- network ID；
- action type ID；
- object type ID；
- instance ID；
- 可选参数覆盖。

### 13.1 参数绑定

系统按照 ActionType 定义从 ObjectInstance 属性中提取参数。

检查内容：

- 必填参数是否存在；
- 用户覆盖参数是否合法；
- 是否包含未知参数。

### 13.2 风险评估

系统加载所有适用于当前 ActionType 的 RiskType。

当前策略优先级：

```text
deny > confirm > allow
```

### 13.3 当前主演示风险公式

```text
预计补货价值 = max(0, 安全库存 - 当前库存) × 单价
```

阈值为 500。

- 达到阈值：`pending_confirmation`；
- 低于阈值：直接执行；
- 匹配 deny：拒绝。

### 13.4 行动状态

- `pending_confirmation`；
- `running`；
- `succeeded`；
- `failed`；
- `denied`。

已结束或非待确认状态的行动不能重复确认。

详细资料：

- `minibkn/src/minibkn/application/action_service.py`
- `MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md`
- 示例风险：`minibkn/examples/supply_chain/bkn/risk_types/high_value_replenishment.bkn`

---

## 14. 工具白名单

系统不允许 ActionType 执行任意 Python 代码。

工具必须预先注册到 ToolRegistry：

```text
(toolbox_id, tool_id) → Tool 实现
```

未注册工具返回 `TOOL_NOT_ALLOWED`。

当前注册工具：

```text
procurement / create_replenishment_alert
```

当前实现只返回本地补货预警结果，不访问外部系统。

详细资料：

- `minibkn/src/minibkn/adapters/tools/`
- `minibkn/src/minibkn/main.py`

---

## 15. Trace 审计

每次行动执行使用一个 `trace_id`。

高价值行动成功路径事件：

```text
action.requested
risk.evaluated
action.awaiting_confirmation
action.confirmation_approved
tool.started
tool.succeeded
```

拒绝确认时出现：

```text
action.confirmation_rejected
```

工具失败时出现：

```text
tool.failed
```

TraceEvent 保存在 SQLite，可通过 API 按 `trace_id` 查询。

HTTP 请求也会生成或透传 `x-trace-id`。错误体中的 `trace_id` 与响应头一致。

详细资料：

- `minibkn/src/minibkn/observability/trace.py`
- `minibkn/src/minibkn/application/action_service.py`
- `MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md`

---

## 16. API 与鉴权

### 16.1 系统接口

| 方法与路径 | 功能 |
| --- | --- |
| `GET /health` | 健康检查 |
| `POST /api/v1/networks/import` | 导入 BKN 目录 |
| `GET /api/v1/networks` | 查询知识网络列表 |
| `GET /api/v1/networks/{id}/schema` | 查询完整 Schema |
| `POST /api/v1/sources` | 注册数据源 |
| `GET /api/v1/sources` | 查询数据源 |
| `POST /api/v1/sources/{id}/discover` | 发现资源和字段 |
| `POST /api/v1/sources/{id}/generate-network` | 自动生成知识网络 |
| `POST /api/v1/networks/{id}/materialize` | 物化对象和关系 |
| `GET /api/v1/networks/{id}/object-types/{type}/instances` | 查询对象实例 |
| `POST /api/v1/networks/{id}/subgraph` | 查询子图 |
| `POST /api/v1/networks/{id}/index` | 建立搜索索引 |
| `POST /api/v1/networks/{id}/search` | 搜索知识网络 |
| `POST /api/v1/networks/{id}/ask` | 问答 |
| `POST /api/v1/networks/{id}/actions/{action}/execute` | 申请执行行动 |
| `POST /api/v1/action-executions/{id}/confirm` | 批准或拒绝行动 |
| `GET /api/v1/action-executions/{id}` | 查询行动状态 |
| `GET /api/v1/traces/{trace_id}` | 查询 Trace 事件 |

### 16.2 统一错误

错误格式：

```json
{
  "error_code": "ERROR_CODE",
  "message": "Error description",
  "trace_id": "trace-..."
}
```

### 16.3 API Key

设置 `MINIBKN_API_KEY` 后：

- `/api/*` 需要 `x-api-key`；
- `/health` 保持公开。

当前不是完整企业鉴权系统，没有：

- OAuth2；
- RBAC；
- 多租户；
- 部门权限；
- 数据行权限；
- 审批人身份验证；
- 多级审批。

接口代码：

- `minibkn/src/minibkn/api/routes.py`
- `minibkn/src/minibkn/api/schemas.py`
- `minibkn/src/minibkn/main.py`

---

## 17. MCP 能力

MiniBKN 使用 MCP Python SDK 2.x，提供 stdio Server。

MCP Server 通过 HTTP Gateway 调用正在运行的 MiniBKN FastAPI 服务。

当前工具：

| MCP 工具 | 功能 |
| --- | --- |
| `search_knowledge` | 搜索知识网络 |
| `ask_knowledge` | 带上下文和引用的问答 |
| `request_action` | 申请执行受控行动 |

MCP 不会绕过 ActionService：

- 参数仍需校验；
- 风险仍需评估；
- confirm 仍需人工确认；
- 工具仍需进入白名单。

测试使用 MCP Client 和 Server 在内存中完成工具发现和 `ask_knowledge` 调用。

详细资料：

- `minibkn/src/minibkn/mcp_server.py`
- `minibkn/tests/integration/test_mcp_server.py`
- `MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md`

---

## 18. 配置与环境变量

环境变量前缀为 `MINIBKN_`。

| 变量 | 默认值/用途 |
| --- | --- |
| `MINIBKN_APP_NAME` | `MiniBKN` |
| `MINIBKN_HOST` | `127.0.0.1` |
| `MINIBKN_PORT` | `8000` |
| `MINIBKN_DATABASE_URL` | 本地 SQLite |
| `MINIBKN_DATA_DIR` | `./data` |
| `MINIBKN_LOG_LEVEL` | `INFO` |
| `MINIBKN_API_KEY` | 默认空，设置后保护 `/api/*` |
| `MINIBKN_API_BASE_URL` | MCP 网关访问地址 |
| `MINIBKN_EMBEDDING_PROVIDER` | 默认 `token_hashing` |
| `MINIBKN_EMBEDDING_DIMENSIONS` | 默认 128 |
| `MINIBKN_EMBEDDING_MODEL` | Sentence Transformers 模型名 |
| `MINIBKN_LLM_PROVIDER` | 默认 `extractive` |
| `MINIBKN_LLM_API_KEY` | 可选模型密钥 |
| `MINIBKN_LLM_BASE_URL` | OpenAI-compatible 地址 |
| `MINIBKN_LLM_MODEL` | 模型名称 |

配置文件：

- `minibkn/.env.example`
- `minibkn/src/minibkn/config.py`

---

## 19. 主演示与使用结果

### 19.1 主演示数据

- `materials.csv`：3 条物料；
- `suppliers.csv`：2 条供应商；
- 物化结果：5 个对象、3 条关系；
- 索引：9 个 SearchDocument。

### 19.2 主演示问题

```text
哪些物料库存低于安全库存，它们由谁供应？
```

正确结果：

- Temperature Sensor，MAT-001，当前库存 8，安全库存 30；
- Relay Module，MAT-003，当前库存 4，安全库存 25；
- 两者供应商都是 Precision Components。

### 19.3 高风险行动

MAT-001：

```text
(30 - 8) × 42.5 = 935
```

超过阈值 500：

```text
pending_confirmation → approved → succeeded
```

### 19.4 低风险行动

MAT-003：

```text
(25 - 4) × 18.8 = 394.8
```

低于阈值，直接执行。

### 19.5 一键演示

项目目录：

```powershell
cd "<local-path>"
.\scripts\demo.ps1
```

详细使用：

- `minibkn/README.md`
- `minibkn/docs/ACCEPTANCE.md`
- `MINIBKN_NON_TECHNICAL_FULL_REPORT.md`

---

## 20. 代码目录导航

```text
minibkn/
├── src/minibkn/
│   ├── adapters/
│   │   ├── bkn_lang/      BKN 文档解析
│   │   ├── datasource/    CSV、SQLite 数据源
│   │   ├── llm/           OpenAI-compatible Schema 增强
│   │   ├── persistence/   数据库、表和 Repository
│   │   ├── search/        BM25、Vector、RRF、Sentence Transformers
│   │   └── tools/         ToolRegistry 和补货工具
│   ├── api/               FastAPI 路由、请求模型、错误
│   ├── application/       五个应用服务
│   ├── domain/            领域模型和错误
│   ├── evaluation/        200 条数据集与评分
│   ├── observability/     trace_id
│   ├── ports/             Repository、DataSource、Search、LLM、Tool 端口
│   ├── config.py          环境配置
│   ├── main.py            FastAPI 入口
│   └── mcp_server.py      MCP 入口
├── examples/supply_chain/
│   ├── bkn/               示例 BKN 定义
│   └── data/              示例 CSV 数据
├── scripts/
│   ├── demo.py            端到端演示
│   ├── demo.ps1           Windows 一键入口
│   ├── evaluate_offline.py
│   └── evaluate_ragas.py
├── tests/
│   ├── unit/
│   └── integration/
├── evals/
│   ├── datasets/
│   └── results/
├── docs/
│   ├── ARCHITECTURE.md
│   └── ACCEPTANCE.md
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## 21. 测试与质量结果

最终验证：

| 检查项 | 结果 |
| --- | --- |
| Pytest | 13 passed |
| Ruff format | 58 files formatted |
| Ruff lint | All checks passed |
| mypy strict | 44 source files, no issues |
| 一键演示 | 通过，最后为 `tool.succeeded` |
| MCP Client/Server | 协议测试通过 |
| Docker Compose 配置 | 解析通过 |
| Docker 镜像构建 | 未验证，Docker Desktop daemon 当时未运行 |

测试覆盖：

- BKN 正确和错误解析；
- 无效关系；
- FastAPI + SQLite；
- CSV/SQLite 数据发现；
- 对象和关系物化；
- 子图；
- 建索引、搜索和问答；
- 高风险确认；
- 高风险拒绝；
- 低风险直达；
- 重复确认冲突；
- Trace；
- API Key；
- 自动 Schema；
- AI Schema 请求约束；
- Sentence Transformers 适配器；
- MCP 工具发现和调用。

验收命令和结果：

- `minibkn/docs/ACCEPTANCE.md`
- `MINIBKN_FINAL_ACCEPTANCE_REPORT.md`

---

## 22. 200 条检索评测

评测集由以下部分组成：

- 5 个业务实体；
- 8 种查询模板；
- 5 种表达包装；
- 总计 200 条查询。

每条记录保存：

- query；
- expected document ID；
- Vector 排名；
- BM25 排名；
- Hybrid 排名。

### 22.1 指标

| 模式 | Hit@1 | Hit@3 | MRR | Top-5 平均上下文字数 |
| --- | ---: | ---: | ---: | ---: |
| Vector | 0.515 | 0.760 | 0.6442 | 862.39 |
| BM25 | 0.735 | 0.890 | 0.8227 | 687.94 |
| Hybrid RRF | 0.730 | 0.835 | 0.7934 | 802.56 |

Hybrid 相比 Vector：

- Hit@1 增加 0.215；
- MRR 增加 0.1492。

BM25 略高于 Hybrid，因为数据集中包含大量精确 ID 和字段关键词。

### 22.2 Ragas

Ragas `IDBasedContextPrecision@1`：

- Vector：0.515；
- BM25：0.735；
- Hybrid：0.730。

Faithfulness 未运行，因为需要独立评审 LLM。

### 22.3 结果位置

- 数据集：`minibkn/evals/datasets/supply_chain_200.jsonl`
- 离线完整结果：`minibkn/evals/results/offline-20260810-201136-533116.json`
- Ragas 结果：`minibkn/evals/results/ragas-id-20260810-201221-175873.json`
- 结果解释：`MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md`

参考简历中的 Context Precision 0.78、Faithfulness 0.89 和 Token 降低 36% 不是本项目实测值。

---

## 23. 工程化与部署

### 23.1 依赖管理

- `pyproject.toml`；
- `uv.lock`；
- Python 3.11；
- Windows 中文路径使用 `--no-editable`。

中文路径下 editable install 可能生成 UTF-8 `.pth`，而 Python 3.11 按 GBK 读取时启动失败。

推荐：

```powershell
uv sync --extra dev --no-editable --reinstall-package minibkn
```

### 23.2 Docker

项目包含：

- `Dockerfile`；
- `compose.yaml`；
- `.dockerignore`。

Compose 配置已成功解析。

Docker Desktop daemon 当时未运行，因此没有完成镜像构建验证。

### 23.3 Ragas 依赖兼容

Ragas 0.4.3 仍引用被 `langchain-community` 0.4 删除的旧 VertexAI 模块。

评测扩展固定：

```text
langchain-community >= 0.3.31, < 0.4
```

该兼容方案已成功运行 Ragas ID 指标。

---

## 24. 当前已实现能力总表

| 能力 | 状态 |
| --- | --- |
| Python/FastAPI 服务 | 已实现 |
| SQLite 持久化 | 已实现 |
| BKN 子集解析与校验 | 已实现 |
| CSV 数据源 | 已实现 |
| SQLite 数据源 | 已实现 |
| 对象实例物化 | 已实现 |
| 关系实例物化 | 已实现 |
| 1～5 层子图查询 | 已实现 |
| BM25 | 已实现 |
| token-hashing Vector | 已实现 |
| RRF | 已实现 |
| Sentence Transformers 适配器 | 已实现，未真实模型端到端评测 |
| 三层上下文 | 已实现 |
| 来源引用 | 已实现 |
| 库存主演示抽取式问答 | 已实现 |
| 通用生成式问答 | 未实现 |
| 自动 Schema | 已实现 |
| AI Schema 描述增强 | 适配器已实现，未真实外部调用 |
| 行动参数绑定 | 已实现 |
| allow/confirm/deny 风险门禁 | 已实现 |
| ToolRegistry 白名单 | 已实现 |
| 本地补货预警工具 | 已实现 |
| 行动状态机 | 已实现 |
| Trace 事件回放 | 已实现 |
| API Key | 已实现 |
| MCP 2.x Server | 已实现并测试 |
| 一键演示 | 已实现并通过 |
| 200 条评测 | 已实现并运行 |
| Docker 配置 | 已实现，镜像未构建验证 |
| PDF/Word 文档接入 | 未实现 |
| LightRAG | 未集成 |
| MySQL/PostgreSQL | 未实现 |
| 实时同步/CDC | 未实现 |
| OAuth/RBAC/多租户 | 未实现 |
| 多级审批 | 未实现 |
| 真实采购/打款工具 | 未实现 |
| Web 图谱可视化 | 未实现 |

---

## 25. 与 LightRAG 的关系

LightRAG 主要面向非结构化文档，通过 LLM 抽取实体和关系，支持 local、global、hybrid、
naive、mix 查询模式，并管理文本块、实体、关系、向量和图存储。

MiniBKN 当前主要面向：

- 结构化数据；
- 明确字段映射；
- 可校验关系；
- 精确数据行引用；
- 业务行动；
- 风险和审批；
- 工具执行与审计。

可能的未来组合：

```text
结构化业务数据 → MiniBKN
企业文档 → LightRAG
统一查询层 → 融合证据
业务行动 → MiniBKN 安全执行链路
```

当前没有实现该组合。

详细讨论：

- `MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md`
- `MINIBKN_AI_EXPLAINER_HANDOFF.md`
- LightRAG README：<https://github.com/HKUDS/LightRAG/blob/main/README.md>

---

## 26. 当前明确边界

MiniBKN 不是上游完整平台，也不是生产级企业业务系统。

当前范围不包括：

- 完整 Kubernetes 微服务部署；
- 上游所有 BKN Lang 能力；
- 所有数据源连接器；
- 企业文档解析；
- 自动从自然语言生成正式业务图谱；
- 实时查询原始数据库；
- 任意 SQL；
- 任意 Python 代码执行；
- 企业级身份和权限；
- 多级审批；
- 真实采购、打款和通知；
- 完整 Web UI；
- 生产级性能和高可用验证。

当前完成的是：

```text
数据 → 图谱 → 检索/问答 → 安全行动 → Trace
```

这一条主链路的本地可运行复现。

---

## 27. 详细资料索引

### 27.1 想了解项目规划、范围和决策

查看：

- `MINIBKN_REPRODUCTION_PLAN.md`

内容：

- 上游项目分析；
- 原始技术栈；
- 环境变量；
- MVP 架构；
- 阶段 A-D；
- 决策记录；
- 全部进度日志；
- 简历材料审计。

### 27.2 想看项目最终是否真的完成

查看：

- `MINIBKN_FINAL_ACCEPTANCE_REPORT.md`

内容：

- 验收结论；
- 测试结果；
- 一键演示结果；
- 200 条评测；
- 复现命令；
- 项目边界。

### 27.3 想看每个开发阶段做了什么

查看：

- `MINIBKN_DEVELOPMENT_REPORT_PHASE_A.md`：工程骨架、领域模型、BKN 解析；
- `MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md`：数据源、对象关系、检索和问答；
- `MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md`：行动、风险、确认、工具和 Trace；
- `MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md`：工程化、自动 Schema、MCP 和评测。

### 27.4 想看完整项目介绍

查看：

- `MINIBKN_NON_TECHNICAL_FULL_REPORT.md`

内容：

- 项目背景；
- 整体流程；
- 系统架构；
- 功能和使用方法；
- 术语；
- 评测；
- 常见问题。

### 27.5 想看用户第一次理解时提出的问题

查看：

- `MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md`

内容：

- 表格关系；
- 图结构存储；
- 对象和关系检索；
- 数据库与索引；
- 行动召回；
- LightRAG；
- 企业文档扩展。

### 27.6 想了解项目和用户背景

查看：

- `MINIBKN_AI_EXPLAINER_HANDOFF.md`

内容：

- 用户背景和目标；
- 项目基础事实；
- 用户已经提出的问题；
- 当前流程、功能和边界。

### 27.7 想运行项目

查看：

- `minibkn/README.md`

### 27.8 想看架构

查看：

- `minibkn/docs/ARCHITECTURE.md`
- `minibkn/src/minibkn/application/`
- `minibkn/src/minibkn/ports/`
- `minibkn/src/minibkn/adapters/`

### 27.9 想验收项目

查看：

- `minibkn/docs/ACCEPTANCE.md`
- `minibkn/scripts/demo.ps1`
- `minibkn/scripts/demo.py`

### 27.10 想看 API

查看：

- `minibkn/src/minibkn/api/routes.py`
- `minibkn/src/minibkn/api/schemas.py`
- 启动服务后的 `http://127.0.0.1:8000/docs`

### 27.11 想看数据库设计

查看：

- `minibkn/src/minibkn/adapters/persistence/database.py`
- `minibkn/src/minibkn/adapters/persistence/tables.py`
- `minibkn/src/minibkn/adapters/persistence/repository.py`

### 27.12 想看检索实现

查看：

- `minibkn/src/minibkn/application/retrieval_service.py`
- `minibkn/src/minibkn/adapters/search/hybrid.py`
- `minibkn/src/minibkn/adapters/search/semantic.py`
- `minibkn/src/minibkn/ports/search.py`

### 27.13 想看图谱和关系实现

查看：

- `minibkn/src/minibkn/application/graph_service.py`
- `minibkn/src/minibkn/domain/models.py`
- `minibkn/examples/supply_chain/bkn/relation_types/`

### 27.14 想看行动、风险和 Trace

查看：

- `minibkn/src/minibkn/application/action_service.py`
- `minibkn/src/minibkn/adapters/tools/`
- `minibkn/src/minibkn/observability/trace.py`
- `minibkn/examples/supply_chain/bkn/action_types/`
- `minibkn/examples/supply_chain/bkn/risk_types/`

### 27.15 想看自动 Schema 和 AI 增强

查看：

- `minibkn/src/minibkn/application/schema_generation_service.py`
- `minibkn/src/minibkn/adapters/llm/openai_compatible.py`
- `minibkn/src/minibkn/ports/schema_ai.py`

### 27.16 想看 MCP

查看：

- `minibkn/src/minibkn/mcp_server.py`
- `minibkn/tests/integration/test_mcp_server.py`

### 27.17 想看测试

查看：

- `minibkn/tests/unit/`
- `minibkn/tests/integration/`

### 27.18 想看评测

查看：

- `minibkn/src/minibkn/evaluation/benchmark.py`
- `minibkn/scripts/evaluate_offline.py`
- `minibkn/scripts/evaluate_ragas.py`
- `minibkn/evals/datasets/`
- `minibkn/evals/results/`

---

## 28. 最终交接摘要

MiniBKN 0.4.0 已经实现并验证以下完整流程：

```text
CSV / SQLite
  → 资源和字段发现
  → BKN Schema
  → 对象实例和关系边
  → Schema / Instance / Action 索引
  → BM25 + Vector + RRF
  → 实例关系扩展
  → 三层上下文和来源引用
  → 抽取式业务回答
  → 明确行动申请
  → 参数绑定和校验
  → allow / confirm / deny
  → 白名单工具
  → ActionExecution 和 TraceEvent
```

当前项目适合：

- 本地学习；
- 秋招作品展示；
- 供应链主演示；
- BKN、RAG、知识图谱和安全行动流程研究；
- 作为后续文档接入、真实语义模型、企业权限和外部工具的开发基础。

项目全部新增内容当前仍在本地工作区，尚未提交或推送 Git。
