> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN Python 复现方案与项目进度

> 本文是本项目的长期事实源（Single Source of Truth）。后续每次开发、验证、范围调整或重要讨论，都应同步更新“决策记录”和“进度日志”，以便新对话或其他 AI 无缝接手。

## 0. 当前状态

- 当前阶段：阶段 A-D 与简历相关增强能力已完成，进入最终回归验收
- 阶段状态：数据、图谱、检索、问答、安全行动、Trace、MCP、自动 Schema 与评测链路已实现
- 上游仓库：<https://github.com/openbkn-ai/bkn-foundry>
- 分析基线：`main` / `c2a703edc244ddce7d1d858c6c1f132c43834c08`
- 上游版本：`0.1.4`
- 基线日期：2026-08-10
- 本地环境：Windows；Python 3.13.9 为当前 base，另有 Python 3.11.14 环境；Docker 29.5.2；Node 24.14.0；未发现 Go
- 阶段 A 开发报告：[`MINIBKN_DEVELOPMENT_REPORT_PHASE_A.md`](../reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_A.md)
- 阶段 B 开发报告：[`MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md`](../reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_B.md)
- 阶段 C 开发报告：[`MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md`](../reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_C.md)
- 阶段 D 开发报告：[`MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md`](../reports/MINIBKN_DEVELOPMENT_REPORT_PHASE_D.md)
- 最终验收报告：[`MINIBKN_FINAL_ACCEPTANCE_REPORT.md`](../reports/MINIBKN_FINAL_ACCEPTANCE_REPORT.md)
- 非技术完整汇报：[`MINIBKN_NON_TECHNICAL_FULL_REPORT.md`](../guides/MINIBKN_NON_TECHNICAL_FULL_REPORT.md)
- 初次流程理解与答疑：[`MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md`](../guides/MINIBKN_INITIAL_FLOW_UNDERSTANDING_AND_QA.md)
- AI 项目与用户背景交接材料：`MINIBKN_AI_EXPLAINER_HANDOFF.md`（私人学习资料，未公开）
- 项目完整交接文档：[`MINIBKN_PROJECT_HANDOFF_FOR_AI.md`](../handoffs/MINIBKN_PROJECT_HANDOFF_FOR_AI.md)
- 下一步：用户验收；Docker Desktop 启动后可补做容器镜像构建

### 0.1 简历材料审计（2026-08-11）

用户提供的简历描述是项目的最终能力目标，不作为当前已完成事实。逐项证据如下：

| 简历能力 | 最终实现与证据 | 结论 |
| --- | --- | --- |
| Python + FastAPI 架构 | 六边形边界、异步 SQLite、统一错误和 trace_id | 已满足 |
| 多类型数据接入 | CSV 与 SQLite 的发现、字段推断和读取 | 核心范围已满足；未接 MySQL |
| Schema 定义与字段映射 | BKN 子集解析、交叉校验、自动 Schema 和约束式 AI 描述增强 | 已满足 |
| 知识图谱实例与关联查询 | 对象/关系实例、BFS 子图、供应链多跳上下文 | 已满足主场景 |
| BM25 + 向量 + RRF | token-hashing 离线基线、可选 Sentence Transformers、三种模式实测 | 已满足 |
| Schema→实例/子图→行动三层上下文 | `/ask` 返回三层上下文、引用与可执行行动 | 已满足 |
| AI 辅助 Schema 生成 | OpenAI-compatible 适配器只补描述，不允许改 ID/映射；MockTransport 已测 | 代码完成，真实调用需用户凭证 |
| 可扩展工具执行引擎 | 白名单注册、参数校验、allow/confirm/deny、标准结果与审计 | 已满足 |
| MCP 原生接入 | MCP Python SDK 2.x stdio Server，三个工具，内存 Client 协议测试 | 已满足 |
| Ragas 200 问题与指标 | 200 条数据、完整排名、Ragas ID 指标可复算 | 已满足检索评测；Faithfulness 需评审 LLM |

结论：最初阶段 A 只是可靠底座；经过阶段 B-D 和增强开发，目前简历中的架构、检索、三层
上下文、行动、MCP、自动 Schema 与 200 条评测已有代码或测试证据。不能照抄参考简历中的
`0.51→0.78`、Faithfulness `0.81→0.89` 和 Token 降低 36%，最终表述必须使用本项目实测值。

## 1. 目标理解与成功标准

### 1.1 真正目标

本项目服务于秋招，而不是生产替换 OpenBKN。目标是用 Python 做出一个可在本地一键运行、能讲清架构取舍、能现场演示的 BKN Foundry 核心链路复现版。

复现重点是“思想与主流程”，不是复制上游所有微服务、接口和基础设施：

1. 数据源接入与资源发现。
2. 使用简化 BKN Lang 定义对象、关系、行动和风险。
3. 将业务数据映射为业务知识网络。
4. 建立全文与语义索引。
5. 根据自然语言问题召回 Schema、实例和关系，组装可引用的上下文。
6. 生成有证据的答案。
7. 对行动进行风险/权限检查，调用受控工具，并留下完整审计轨迹。

### 1.2 MVP 验收标准

最终必须用一条供应链演示链路证明系统可用：

```text
CSV / SQLite 数据
  -> 数据源注册与 Schema 发现
  -> 导入 BKN 定义
  -> 对象/关系映射
  -> 全文 + 向量索引
  -> 自然语言检索与子图查询
  -> 带来源引用的回答
  -> 补货预警行动的风险检查与执行
  -> trace_id 串联检索、决策、工具调用和结果
```

验收时应满足：

- Windows 本地无需 Kubernetes 即可启动。
- 默认使用 SQLite，核心演示不依赖 MySQL、Redis、Kafka 或 OpenSearch。
- 有 API 文档、架构说明、示例数据、自动化测试和一键演示脚本。
- 无 LLM API Key 时仍可跑通检索与抽取式回答；配置兼容 OpenAI 的模型后可增强自动 Schema
  的业务说明。
- 高风险行动未经确认不得执行；每次执行均可通过 `trace_id` 回放。

## 2. 上游项目解析

### 2.1 项目性质

BKN Foundry 是纯后端、多语言 monorepo。根 README 明确说明它不包含 Web UI，正式完整安装以 Linux + Kubernetes 为主要目标。当前仓库约有 1,933 个 Go 文件、570 个 Python 文件和 138 个 `.bkn` 文件；但核心 BKN、查询、检索、数据虚拟化与执行工厂主要是 Go，Python 主要用于 Agent、模型服务、沙箱、迁移工具和验收测试。

根 `package.json` 不是业务运行时依赖，只用于 OpenAPI 文档 lint/渲染：

- `@redocly/cli`
- `widdershins`

仓库没有统一的根 `requirements.txt`。Python 依赖分散在各子模块：

- `infra/bkn-agent`：FastAPI、Pydantic、LangChain、LangGraph、MCP、SQLAlchemy、MySQL checkpoint、OpenTelemetry。
- `infra/mf-model-manager`：FastAPI、旧版 OpenAI SDK、Transformers、spaCy、datasets、模型评测工具。
- `infra/sandbox`：FastAPI、Pydantic v2、httpx、structlog、进程与隔离工具。
- `data-migrator`：PyYAML、sqlparse、pymongo、opensearch-py 与内部数据库 SDK。
- `adp/execution-factory/tests`：pytest、Allure、requests、数据库和协议测试依赖；其中部分依赖私有 PyPI，不适合作为本项目基础。

结论：不能通过“安装根依赖并运行一个入口”复现上游；必须裁剪能力并重新组织为 Python 模块化单体。

### 2.2 核心模块、入口与依赖

| 上游模块 | 入口/默认端口 | 主要职责 | 关键依赖 | MiniBKN 处理 |
| --- | --- | --- | --- | --- |
| BKN Backend | `adp/bkn/bkn-backend/server/main.go` / 13014 | KN、对象类、关系类、行动类、风险类、导入导出和调度元数据 | MariaDB/DM8、OpenSearch、模型服务、VEGA、Execution Factory | 保留核心领域模型、BKN 导入校验和元数据管理 |
| Ontology Query | `adp/bkn/ontology-query/server/main.go` / 13018 | 实例、属性、子图、行动执行与行动日志查询 | BKN Backend、VEGA、OpenSearch、模型服务、Execution Factory | 合并为查询与行动应用服务 |
| Context Loader | `adp/context-loader/agent-retrieval/server/main.go` / 30779 | Schema/实例召回、重排、子图、逻辑属性、行动/Skill 召回、MCP | BKN、Ontology Query、VEGA、Execution Factory、模型服务、可选 Redis | 保留混合检索、重排和上下文组装；MCP 延后 |
| VEGA | `adp/vega/vega-backend/server/main.go` / 13014（独立 Pod） | Catalog、资源发现、数据查询、索引构建、同步任务 | RDS、OpenSearch、Redis、Kafka/MQ、embedding 服务 | 以 DataSource/Resource 适配器简化，MVP 支持 CSV 与 SQLite |
| Execution Factory | `adp/execution-factory/operator-integration/server/main.go` / 9000 | 工具、Skill、MCP 注册和执行，沙箱协作 | DB、Redis、Hydra、模型服务、Sandbox、VEGA | 保留工具注册、白名单、参数校验和受控执行；不执行任意用户代码 |
| BKN Agent | `infra/bkn-agent/main.py` / 30800 | Agent、对话、任务、模型调用和工具装载 | FastAPI、LangGraph、模型 API、Context Loader、Execution Factory、MySQL | MVP 不引入 LangGraph，把 `/ask` 作为可解释的 RAG 编排接口 |
| BKN Safe | `bkn-safe/server/main.go` / 3000 | Hydra 登录/授权、Casbin、用户目录 | Hydra、MariaDB、LDAP | 简化为 API Key/角色策略与行动确认；完整 OAuth 延后 |
| BKN Trace | `bkn-trace/agent-observability/main.go` / 8080 | OTLP 接入后的 Trace/证据查询 | OpenTelemetry Collector、OpenSearch、MariaDB | MVP 使用 SQLite 事件账本 + trace_id；OTLP/OpenSearch 延后 |

上游核心服务普遍采用六边形/整洁架构：`interfaces` 定义端口，`logics` 放领域与应用逻辑，`driveradapters` 提供 HTTP/MCP 入口，`drivenadapters` 连接数据库、搜索、模型和其他服务。MiniBKN 将保留这种边界，但在一个 Python 进程内实现，避免为了“像微服务”而人为增加本地部署成本。

### 2.3 上游核心数据流

#### 读取与问答链路

```text
用户 / Agent / CLI
  -> BKN Agent 或 Context Loader
  -> 召回 KN Schema（对象类、关系类、属性）
  -> Ontology Query 执行实例/子图查询
  -> VEGA 根据 ObjectType 绑定的 Resource 访问源库或本地索引快照
  -> Context Loader 进行召回、粗排、精排与上下文压缩
  -> LLM 结合事实与来源生成答案
  -> BKN Trace 记录意图、知识节点、数据来源和模型输出
```

#### 数据构建链路

```text
MySQL / CSV
  -> VEGA Catalog 注册
  -> 自动发现表并生成 Resource
  -> BKN ObjectType/RelationType 绑定 Resource 与字段
  -> VEGA BuildTask 同步数据到 OpenSearch
  -> 对指定字段建立全文索引与 embedding 向量
  -> Context Loader 可执行 Schema 和实例级语义召回
```

上游示例特别强调：资源建索引后，读取路径会从源库实时查询切换为索引快照；源数据变化需要重建索引才能可见。MiniBKN 也应显式保留 `source_version/index_version`，用来展示实时读与快照读之间的一致性取舍。

#### 行动链路

```text
问题/调度触发
  -> BKN 中定位对象与 ActionType/Skill
  -> 加载参数 Schema、关系证据和 RiskType
  -> 权限与风险检查
  -> Execution Factory 调用白名单工具
  -> 记录 ActionExecution、工具结果与审计事件
  -> trace_id 支持全链路回放
```

### 2.4 代码与文档中的重要发现

1. 根 README 引用的 `docs/bkn-architecture.zh.md` 在当前提交中不存在，只有 SVG 架构图。
2. `adp/README.zh.md` 仍描述 Java VEGA 和内置 Web Console，但当前 VEGA Backend 已是 Go，根 README 也明确 UI 位于独立 BKN Studio 仓库。分析应以当前代码、模块 README 和端到端示例为准。
3. `rules/ARCHITECTURE.md` 中“Foundry 后端微服务少于 5 个”更像目标约束，当前 monorepo 的实际可部署后端数量明显更多。
4. 上游为多许可证仓库：上游衍生代码多为 Apache 2.0，OpenBKN 新增文件使用带附加条件的 OpenBKN License。MiniBKN 应采用独立实现、注明概念来源，不直接复制 BKN Safe、SDK、CLI 等 OpenBKN 新增代码。
5. 当前机器默认 Python 3.13，而上游 Python 服务与计划采用的部分 AI 依赖在 3.11 上兼容性更稳。应创建项目专用 Python 3.11 虚拟环境；机器已经具备 3.11.14，可直接使用。

## 3. 推荐复现架构

### 3.1 架构选择

采用“模块化单体 + 可插拔适配器”，而不是微服务或 Kubernetes：

```text
FastAPI / CLI
  -> Application Services
     -> BKN Registry / Query / Retrieval / Action / Trace
        -> Ports
           -> SQLite Repository
           -> CSV/SQLite DataSource Adapter
           -> Local Embedding Adapter
           -> OpenAI-compatible LLM Adapter（可选）
           -> Whitelisted Tool Adapter
```

原因：

- 仍能讲清领域边界、端口/适配器、依赖倒置和未来拆分点。
- 一条命令启动，适合面试演示和 Windows 本地开发。
- 可以用接口替换 SQLite、OpenSearch、MySQL、远程工具与真实模型，不会把 MVP 写成一次性脚本。
- 规避多个服务、服务发现、消息队列和集群配置掩盖核心业务价值。

### 3.2 建议目录

实现代码与上游源码隔离，放在当前仓库的 `minibkn/`：

```text
minibkn/
  pyproject.toml
  .env.example
  README.md
  src/minibkn/
    main.py                    # FastAPI 入口
    api/                       # REST 路由、DTO、统一错误
    domain/                    # KN/Object/Relation/Action/Risk/Trace 领域模型
    application/               # 导入、建索引、检索、问答、行动用例
    ports/                     # Repository/Search/LLM/Tool/DataSource 接口
    adapters/
      persistence/             # SQLite + SQLAlchemy
      datasource/              # CSV、SQLite；后续 MySQL
      bkn_lang/                # .bkn frontmatter + Markdown 表格解析
      search/                  # FTS/embedding/混合排序
      llm/                     # OpenAI-compatible + extractive fallback
      tools/                   # 白名单 HTTP/本地演示工具
    observability/             # trace_id、事件账本、结构化日志
  examples/supply_chain/       # 数据、BKN 定义、演示工具
  tests/
    unit/
    integration/
    e2e/
  scripts/
    demo.ps1                   # Windows 一键演示
```

### 3.3 MVP 领域对象

- `KnowledgeNetwork`：网络基本信息与版本。
- `ObjectType`：对象类型、属性、主键、展示字段、资源绑定。
- `RelationType`：源/目标对象、关系方向、字段映射。
- `ActionType`：目标对象、输入 Schema、触发条件、工具绑定。
- `RiskType`：风险级别、命中条件、处置策略（allow/confirm/deny）。
- `DataSource` / `Resource`：连接配置、发现出的表/文件与字段 Schema。
- `SearchDocument`：Schema 或实例的索引文档、来源定位、版本和向量。
- `ActionExecution`：行动状态、输入、输出、审批和错误。
- `TraceEvent`：一次请求内的检索、查询、风险判断、工具调用与响应事件。

### 3.4 MVP API

API 采用 `/api/v1`，并遵循上游统一错误封套和 `x-trace-id` 约定：

- `POST /api/v1/sources`：注册 CSV/SQLite 数据源。
- `POST /api/v1/sources/{source_id}/discover`：发现资源和字段。
- `POST /api/v1/networks/import`：导入简化 BKN Lang 目录或压缩包。
- `GET /api/v1/networks`：列出网络。
- `GET /api/v1/networks/{kn_id}/schema`：查看网络 Schema。
- `POST /api/v1/networks/{kn_id}/index`：构建/重建索引并记录版本。
- `POST /api/v1/networks/{kn_id}/search`：Schema + 实例混合检索。
- `POST /api/v1/networks/{kn_id}/subgraph`：从对象实例遍历关系。
- `POST /api/v1/networks/{kn_id}/ask`：检索、组装上下文并生成带引用回答。
- `POST /api/v1/networks/{kn_id}/actions/{action_id}/execute`：风险检查后执行行动。
- `POST /api/v1/action-executions/{execution_id}/confirm`：确认需要人工批准的行动。
- `GET /api/v1/traces/{trace_id}`：回放完整调用链。

### 3.5 技术栈

| 领域 | 选择 | 说明 |
| --- | --- | --- |
| 运行时 | Python 3.11 | 兼容 AI/数据依赖，机器已有该版本 |
| Web/API | FastAPI + Uvicorn + Pydantic v2 | 自动 OpenAPI，便于现场演示 |
| 持久化 | SQLAlchemy 2 + aiosqlite + SQLite | 零外部依赖；Repository 可替换 MySQL |
| BKN Lang | PyYAML + Markdown 表格解析 | 支持 frontmatter、对象/关系/行动/风险的必要子集 |
| 图查询 | SQLite 实例边 + 应用层 BFS | 当前小数据集无需额外图数据库，关系可持久化、可遍历 |
| 全文检索 | Python BM25 | 本地、可解释、无需 OpenSearch |
| 向量检索 | token-hashing + cosine；可选 Sentence Transformers | 默认离线确定性，可切换真实语义模型 |
| LLM | 基于 httpx 的 OpenAI-compatible 接口 | 可选增强 Schema 说明；无 Key 时不影响抽取式回答 |
| 工具调用 | Pydantic 校验 + 进程内白名单注册表 | 不运行任意代码，不访问真实采购系统 |
| 日志/Trace | 标准结构化日志 + SQLite 事件账本 | 统一 trace_id；后续可接 OpenTelemetry |
| 测试/质量 | pytest、pytest-asyncio、httpx、Ruff、mypy | 单元、集成、端到端分层 |
| 依赖管理 | `pyproject.toml` + uv | 快速、可锁定、便于复现 |

## 4. 环境变量与预配置清单

### 4.1 上游完整平台需要什么

原项目不是主要靠一个 `.env` 启动，而是通过各服务 YAML、Kubernetes ConfigMap/Secret 和少量环境变量配置。完整部署至少涉及：

- RDS/MariaDB：host、port、user、password、database、数据库类型。
- OpenSearch：host、port、protocol、user、password。
- Redis：直连/哨兵地址、账号、密码、TLS。
- Kafka/MQ：broker、tenant、认证机制、账号和密码。
- Hydra/BKN Safe：OAuth public/admin URL、数据库、LDAP（可选）。
- 模型服务：LLM 与 embedding 模型名、API 地址和凭证。
- 服务互联：BKN、Ontology Query、VEGA、Context Loader、Execution Factory、Sandbox、Trace 等内部地址。
- OpenTelemetry：OTLP endpoint、采样率和启用开关。
- 官方示例还要求 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASS`、`PLATFORM_HOST` 和可被平台访问的工具后端 URL。

这些都不应成为 MiniBKN MVP 的前置条件。

### 4.2 MiniBKN MVP 建议变量

`.env.example` 提供安全默认值，所有变量均可不配置：

| 变量 | 是否必填 | 默认/用途 |
| --- | --- | --- |
| `MINIBKN_DATABASE_URL` | 否 | `sqlite+aiosqlite:///./data/minibkn.db` |
| `MINIBKN_DATA_DIR` | 否 | `./data`，索引与上传数据目录 |
| `MINIBKN_LOG_LEVEL` | 否 | `INFO` |
| `MINIBKN_API_KEY` | 否 | 本地开发为空；演示鉴权时设置 |
| `MINIBKN_EMBEDDING_PROVIDER` | 否 | `token_hashing`；可改为 `sentence_transformers` |
| `MINIBKN_EMBEDDING_DIMENSIONS` | 否 | 默认 `128`，离线向量维度 |
| `MINIBKN_EMBEDDING_MODEL` | 使用语义模型时 | Sentence Transformers 模型名称 |
| `MINIBKN_LLM_PROVIDER` | 否 | `extractive`；AI Schema 增强时改为 `openai_compatible` |
| `MINIBKN_LLM_API_KEY` | 使用 AI 增强时 | 模型服务密钥，禁止提交 Git |
| `MINIBKN_LLM_BASE_URL` | 使用 AI 增强时 | OpenAI-compatible base URL |
| `MINIBKN_LLM_MODEL` | 使用 AI 增强时 | 模型名称 |
| `MINIBKN_API_BASE_URL` | MCP HTTP 网关时 | 默认 `http://127.0.0.1:8000` |

OpenAI-compatible 的 `API Key + Base URL + Model` 只用于可选的 AI Schema 描述增强。即使
不提供，也不会阻塞主链路开发、演示和自动化测试。

## 5. 开发阶段与验收

### 阶段 A：工程骨架与领域契约

- 创建 Python 3.11 项目、配置、统一错误响应和 trace_id 中间件。
- 定义领域模型、Repository/Adapter 接口和数据库表。
- 实现 BKN Lang 必要子集的解析、校验和导入。
- 添加单元测试与供应链示例定义。

验收：服务可启动；无效 BKN 定义能返回明确校验错误；导入后可读取网络 Schema。

### 阶段 B：数据到知识网络的读取闭环

- CSV/SQLite 数据源注册与 Schema 发现。
- ObjectType 字段映射、RelationType 外键映射。
- 实例查询和子图遍历。
- 全文 + 本地 embedding 索引、混合排序、索引版本管理。
- `/search` 与 `/ask`，回答携带对象、字段、行标识等来源引用。

验收：从零执行演示脚本后，能回答“哪些物料库存低于安全库存，它们由谁供应？”并返回正确对象、关系和引用。

状态：**已完成（2026-08-11）**。当前回答生成使用确定性抽取逻辑；语义模型和生成式 LLM
是后续增强，不影响无 Key 的完整链路验证。

### 阶段 C：安全行动与可追踪闭环

- ActionType/RiskType 解析和参数 Schema 校验。
- allow/confirm/deny 风险策略。
- 白名单工具执行与状态机（pending/running/succeeded/failed/denied）。
- Trace 事件回放，串联搜索证据、风险判断、工具请求和结果。

验收：低风险行动可直接执行；高风险行动首次返回“需要确认”，确认后调用 mock 补货后端；被禁止行动无法触达工具；三类路径都有审计记录。

状态：**已完成（2026-08-11）**。当前工具为进程内白名单演示工具，不会真实下单或访问外部系统。

### 阶段 D：工程化与秋招展示

- 一键 `demo.ps1`、完整 README、架构图、API 示例和故障排查。
- 单元、集成、E2E 测试；Ruff/mypy；覆盖核心失败路径。
- Dockerfile（单容器）与可选 Docker Compose。
- 整理面试讲解：为什么从微服务收敛为模块化单体、实时读与索引快照、混合检索、风险门禁、trace 证据链。

验收：新机器按 README 在合理步骤内启动；自动化测试与演示脚本通过；不需要阅读上游源码即可理解项目。

状态：**已完成（2026-08-11）**。Docker 配置已生成，但本机 Docker Desktop daemon 未运行，
因此容器构建保留为环境恢复后的手工验收项；Python 原生链路已通过。

### 后续增强（完整链路完成后再做）

- MySQL Connector 与增量索引。
- APScheduler 行动调度。
- MCP Server/Client 兼容。
- OpenTelemetry 导出、OpenSearch/Qdrant/pgvector 适配器。
- JWT/OAuth2/Casbin、多租户、细粒度数据权限。
- LangGraph 多轮 Agent、Skill 包管理和隔离沙箱。
- 简易可视化页面；原项目本身无 UI，因此不是首阶段范围。

## 6. 明确不复现的内容

首轮不实现：

- Kubernetes、Helm、多节点部署与服务发现。
- 原项目全部微服务和全部 OpenAPI 兼容。
- MariaDB、Redis、Kafka、OpenSearch 的强制依赖。
- Hydra OAuth 全流程、LDAP、完整组织目录和商业授权能力。
- 任意 Python/Go 代码沙箱。
- 完整 BKN Lang、指标系统、所有调度和迁移能力。
- BKN Studio 或其他 Web 前端。

这些内容不影响“数据 → 知识网络 → 检索/问答 → 安全行动 → Trace”的主链路展示。

## 7. 风险与应对

| 风险 | 应对 |
| --- | --- |
| 上游主分支持续快速变化、文档与代码有漂移 | 固定当前 commit；每次引用注明基线，不跟随无关更新 |
| 本地模型首次下载较大或网络不稳定 | 缓存模型；提供纯全文/抽取式 fallback；后续支持国内镜像地址 |
| Python 3.13 的 AI 依赖兼容性不稳定 | 使用项目专用 Python 3.11 虚拟环境 |
| 动态工具执行带来安全风险 | MVP 只允许注册过的 HTTP/内置工具，host allowlist，参数先校验，高风险需确认 |
| 为了“像原项目”而过度微服务化 | 坚持模块化单体，接口边界为将来拆分保留可能性 |
| 许可证边界不清 | 独立实现并保留来源说明，不复制 OpenBKN License 的新代码或商业能力 |

## 8. 待用户确认的默认决策

如果用户直接回复“通过”，表示接受以下默认项：

1. 在当前仓库新建 `minibkn/`，不修改上游核心源码。
2. 采用 Python 3.11 + FastAPI + SQLite 的模块化单体。
3. 主链路同时覆盖“可引用问答”和“安全行动执行”，完成后再做附加能力。
4. 默认本地 embedding；LLM 使用 OpenAI-compatible 可选配置，无 Key 也可测试。
5. 第一版只有 API/Swagger/CLI 演示，不做 Web UI。
6. 供应链库存预警作为唯一主演示场景，避免同时维护多个浅场景。

## 9. 决策记录

| 日期 | 决策 | 原因 | 状态 |
| --- | --- | --- | --- |
| 2026-08-10 | 不复现完整微服务/K8s，改为 Python 模块化单体 | 符合秋招、本地运行和 Python 主导目标 | 用户已确认 |
| 2026-08-10 | 先完成端到端主链路，再开发附加组件 | 与用户优先级一致，降低半成品风险 | 用户已确认 |
| 2026-08-10 | 使用供应链库存预警作为主场景 | 同时覆盖关系查询、检索、风险和行动 | 用户已确认 |
| 2026-08-10 | 本文作为跨对话进度与决策事实源 | 便于后续 AI/开发者接手 | 已生效 |
| 2026-08-11 | Windows 中文路径下使用 `uv sync --no-editable` | 避免 Python 3.11 按 GBK 读取 editable `.pth` 时启动失败 | 已生效 |
| 2026-08-11 | 阶段 A 只实现元数据与 Schema 闭环 | 严格按批准范围逐步开发，不提前混入检索和行动代码 | 已完成 |
| 2026-08-11 | 简历描述按“最终目标”管理，不作为当前事实 | 保证面试表述可由代码、测试和评测复现 | 已生效 |
| 2026-08-11 | 阶段 B 使用 token-hashing 向量基线 + BM25 + RRF | 无网络、无模型下载仍能验证混合检索编排和排序证据 | 已完成；后续替换语义模型 |
| 2026-08-11 | 小规模图使用 SQLite 边表和 BFS | 减少依赖，同时保留实例、关系和遍历边界 | 已完成 |
| 2026-08-11 | 工具执行必须经过显式注册表 | 阻止 BKN 定义触发任意代码或未授权外部调用 | 已完成 |
| 2026-08-11 | 高价值风险阈值写入 BKN 定义 | 风险条件可配置、可解释、可测试，避免藏在路由代码中 | 已完成 |

## 10. 进度日志

### 2026-08-10 · 阶段一分析

- 克隆并固定上游 `main` 提交 `c2a703ed`，版本 `0.1.4`。
- 阅读根 README、中文 README、根 `package.json`、全部仓库级协作/架构/开发/测试规则。
- 阅读 BKN、Ontology Query、Context Loader、VEGA、Execution Factory、BKN Safe、BKN Trace、Data Migrator 与 BKN Agent 的入口、配置和模块文档。
- 阅读官方 01/02/03/05 端到端示例，确认数据构建、检索、关系查询、行动和 Skill 路由的真实调用顺序。
- 盘点 Python requirements/pyproject、主要 Go 入口和服务间依赖。
- 检查本机 Python、Docker、Node 环境，确认应使用已有 Python 3.11 而不是 base 3.13。
- 完成 Python MVP 架构、范围、环境变量、阶段验收和风险方案。
- 未进行业务代码实现、依赖安装、数据库初始化、部署、提交或远程写操作。

阶段一方案随后已由用户确认，实施结果见下一条阶段 A 日志。

### 2026-08-11 · 阶段 A 开发完成

- 在 `minibkn/` 创建独立 Python 3.11 项目，使用 `pyproject.toml`、`uv.lock` 和项目专用 `.venv`。
- 创建 FastAPI 应用工厂、环境配置、健康检查、Swagger/OpenAPI 入口。
- 实现统一错误封套和 `x-trace-id` 生成/透传；错误体中的 `trace_id` 与响应头一致。
- 定义 KnowledgeNetwork、ObjectType、RelationType、ActionType、RiskType、数据属性、数据源绑定、工具绑定等领域契约。
- 定义 `KnowledgeNetworkRepository` 端口，并用 SQLAlchemy async + SQLite 实现网络与 BKN 文档持久化。
- 实现简化 BKN Lang 解析器：YAML frontmatter、Markdown 表格、Keys、Trigger Condition YAML block。
- 实现跨文档校验：重复 ID、主键/展示键、关系端点和字段映射、行动对象/参数绑定、风险到行动引用。
- 提供 `POST /api/v1/networks/import`、`GET /api/v1/networks`、`GET /api/v1/networks/{id}/schema`。
- 新增供应链示例：2 个对象类、1 个关系类、1 个行动类、1 个风险类，以及后续阶段使用的两份 CSV。
- 新增解析器单元测试、无效关系回归测试、API + SQLite 集成测试；覆盖成功导入、列表、Schema、404 和无效目录错误。
- 发现并解决 Windows 中文路径下 editable install 的编码问题，安装命令固定为 `uv sync --no-editable`。
- 验证结果：`pytest` 3 passed；Ruff 全部通过；mypy 对 24 个源文件检查通过。
- 未实现范围：数据源发现、CSV 实例导入、图遍历、索引、问答、行动执行和 Trace 事件账本，按计划留给阶段 B/C。

下一步：进入阶段 B，先实现 CSV/SQLite DataSource 与 Resource 发现，再做对象实例映射和关系子图查询。

### 2026-08-11 · 简历材料审计与阶段 B 开发完成

- 对照简历逐项检查阶段 A，确认它只满足工程底座、Schema 契约和字段映射，不能声称已完成
  混合检索、图实例、MCP、AI Schema 或 Ragas 指标。
- 新增 CSV 适配器：支持单文件/目录扫描、UTF-8 BOM、字段类型推断、简单主键提示、行数统计。
- 新增 SQLite 适配器：发现业务表、读取 `PRAGMA table_info`、识别字段/主键/行数并加载数据。
- 新增 DataSource/Resource/ResourceField、ObjectInstance、RelationInstance、SearchDocument 等领域模型，
  以及对应 SQLite 持久化表和 Repository 端口。
- 根据 ObjectType 的 `mapped_field` 和主键生成对象实例；根据 RelationType 映射生成关系边。
- 新增实例查询与应用层 BFS 子图遍历，示例 `MAT-001` 可定位到供应商 `SUP-001`。
- 实现可解释 BM25、128 维离线 token-hashing 向量、cosine 相似度和 RRF 排名融合；搜索结果
  返回两路名次和融合分数。
- 索引内容分为 Schema、实例、行动三层；`/ask` 返回 Schema→实例/子图→行动上下文及
  `bkn://`、`resource://...#row=` 引用。
- 为库存问题加入无 LLM 的确定性回答路径，正确识别 `MAT-001`、`MAT-003` 和供应商
  Precision Components；这保证没有 API Key 也能演示全链路。
- 新增数据源、发现、materialize、实例、subgraph、index、search、ask API。
- 新增 SQLite 适配器单元测试和阶段 B API 端到端测试。
- 验证结果：5 个测试通过；Ruff 通过；mypy 对 31 个源文件通过。
- 明确未完成：训练过的语义 embedding、AI Schema 生成、生成式 LLM、行动执行、MCP、
  Ragas 评测集与简历中的所有效果数字。

下一步：进入阶段 C，完成从“检索到行动”的安全执行闭环和 Trace 事件回放；随后再接真实
语义模型、AI Schema、MCP 与 Ragas 评估。

### 2026-08-11 · 阶段 C 开发完成

- 新增 ActionExecution 状态机：`pending_confirmation`、`running`、`succeeded`、`failed`、
  `denied`。
- 根据 ActionType 参数绑定规则从对象实例自动取值；覆盖参数会经过未知字段和缺失字段校验。
- 在风险定义中加入 `value_threshold`，运行时计算 `(安全库存 - 当前库存) × 单价`。
- `MAT-001` 预计补货价值 935，必须人工确认；`MAT-003` 预计价值 394.8，可直接执行。
- 新增 ToolRegistry 白名单和本地补货预警工具；未注册工具返回 `TOOL_NOT_ALLOWED`，不允许任意
  代码执行。
- 行动结果统一为状态、结果、错误、参数、风险判断、trace_id 和时间戳结构。
- 新增 TraceEvent SQLite 账本，记录请求、风险评估、等待确认、批准/拒绝、工具开始、成功或失败。
- 新增行动执行、确认/拒绝、状态查询和 Trace 回放 API。
- 自动化测试覆盖高风险暂停、确认成功、重复确认冲突、低风险直达、拒绝不调用工具。
- 验证结果：7 个测试通过；Ruff 通过；mypy 对 35 个源文件通过。

下一步：阶段 D 加入一键演示、Docker、验收脚本与架构/故障排查文档，然后继续语义模型、
AI Schema、MCP 和评测增强。

### 2026-08-11 · 阶段 D 与简历相关增强完成

- 新增一键端到端演示脚本，独立创建数据库并验证数据发现、物化、索引、问答、高风险确认、
  工具成功和 Trace 回放。
- 新增单容器 Dockerfile、Compose、`.dockerignore`、架构说明和完整验收清单。
- 可选 API Key 保护 `/api/*`；`/health` 保持公开，自动化测试覆盖未授权和授权请求。
- 新增 Sentence Transformers 语义向量适配器，保持 token-hashing 离线 fallback；用假模块测试
  模型加载、归一化向量调用和返回值。
- 资源发现后可确定性生成 ObjectType、RelationType 和字段映射；可选 OpenAI-compatible AI
  只增强说明字段，禁止修改标识和映射，适配器用 MockTransport 测试。
- 使用 MCP Python SDK 2.x 建立 stdio Server，暴露搜索、问答和行动三个工具；使用 MCP Client
  完成工具发现和调用测试。
- 构建 200 条确定性供应链检索集，保存每条预期文档和三路完整排名；vector/BM25/hybrid 的
  Hit@1 分别为 0.515/0.735/0.730，MRR 为 0.6442/0.8227/0.7934。
- 实际运行 Ragas `IDBasedContextPrecision@1`，结果与 Hit@1 一致；Ragas 0.4.3 对
  langchain-community 0.4 存在已知导入错误，因此评测扩展固定兼容的 0.3.31 版本线。
- Faithfulness 需要评审 LLM，当前没有用户凭证，明确记录为未运行，不使用参考简历数字。
- Docker CLI 可用但 Docker Desktop daemon 未运行，镜像构建未验证；此项不影响原生 Python
  程序验收。

下一步：全量重装当前源码，执行测试、Ruff、mypy、一键演示与评测复核，并生成最终验收报告。

### 2026-08-11 · 最终验收完成

- 项目版本更新为 0.4.0，使用 `--no-editable` 重装当前源码与评测扩展。
- 最终结果：13 tests passed；Ruff format/lint 全通过；mypy strict 检查 44 个源文件无问题。
- 一键演示再次通过：2 个资源、5 个对象、3 条关系、9 个索引文档，库存问答正确，高风险
  行动从 `pending_confirmation` 经批准到 `succeeded`，Trace 以 `tool.succeeded` 结束。
- 离线 200 条评测和 Ragas ID 评测再次运行，指标与阶段 D 报告一致。
- Docker Compose 配置解析通过；Docker Desktop daemon 未运行，`docker info` 无法连接，镜像
  构建作为唯一环境依赖项保留给用户启动 Docker 后复核。
- 新增最终验收报告，集中给出复现命令、证据、指标解释和项目边界。

### 2026-08-11 · 新增面向非技术负责人的完整汇报

- 用户反馈阶段通俗报告仍包含较多专业概念，因此新增一份可独立阅读的完整项目汇报。
- 文档使用“资料管理员、关系分析员、安全执行员、审计员”的业务类比，解释项目目标和价值。
- 补充模块化单体、五层架构、五个业务服务、端到端流程和安全门禁的非技术说明。
- 汇总阶段 A-D 的全部工作、用户可用功能、术语表、200 条评测解释、项目边界和秋招讲法。
- 提供一键演示、Swagger 逐步操作、自动 Schema、语义模型、API Key、MCP 和常见故障的完整
  使用指南，读者无需先阅读其他技术文档。

### 2026-08-11 · 用户初次流程理解分析与答疑

- 逐条审核用户对“表格→图谱→检索→上下文→行动”的理解，确认主方向正确并纠正四项关键
  偏差：关系推断边界、索引快照、图文件存储和问答/执行分离。
- 根据当前代码明确记录关系的两种来源：显式 RelationType 映射，以及同名 `*_id` 到目标主键
  的确定性自动推断；可选 AI 目前只增强描述，不新增或修改关系。
- 解释检索对象：Object/Relation Schema、对象实例和启用行动直接参与检索，具体关系实例用于
  命中后的子图扩展，不作为独立搜索文档。
- 记录当前 `/ask` 的数量边界：统一召回 20，Schema 最多 5、Instance 最多 8、Action 最多 5；
  `/subgraph` 支持 1～5 层显式遍历。
- 解释数据库连接采用“物化 + 索引快照”，不是提问时由 AI 生成任意 SQL；数据更新后需重新
  materialize 和 index。
- 对照 LightRAG 官方资料，说明其文档实体关系抽取、local/global/hybrid/naive/mix 模式与
  MiniBKN 结构化业务数据、安全行动的差异。
- 给出企业文档接入、候选实体审核、LightRAG 融合查询和实时/权限治理的阶段 E-H 建议路线。

### 2026-08-11 · 建立编程 AI 与讲解 AI 的交接机制

- 用户反馈现有解释仍偏技术化和学术化，决定将“代码与事实维护”和“教学表达”交给不同 AI。
- 新增讲解型 AI 交接手册，集中提供当前主流程、精确实现边界、主演示、常见问题标准口径、
  LightRAG 分工、质量指标和禁止错误表述。
- 在交接手册中记录用户学习特点，要求讲解 AI 先给直接答案和具体例子，每次最多引入三个新
  术语，并通过复述检查理解。
- 新增可直接复制的讲解型 AI 启动提示词，提供入门教学、自由答疑、流程纠错和模拟面试四种
  模式，避免再次一次性输出高密度技术报告。
- 规定今后编程 AI 在数据源、检索、行动、权限、评测等事实变化后同步更新交接手册，形成稳定
  的“编程 AI → 事实手册 → 讲解 AI → 用户”协作链路。

### 2026-08-11 · 调整 AI 交接材料边界

- 用户指出交接材料不应规定另一个 AI 的讲解方式，只需提供项目基础和用户个人情况。
- 重写交接手册，保留用户背景、已有疑问、项目来源、完整流程、当前代码能力、测试指标、
  LightRAG 背景、已实现和未实现范围及文档入口。
- 删除角色指令、表达限制、教学路线、模拟面试方式、禁止表述和维护命令等讲解控制内容。
- 删除单独的讲解启动提示词，避免限制另一个 AI 的表达和互动方式。

### 2026-08-12 · 新增纯项目完整交接文档

- 根据用户要求新增一份只介绍 MiniBKN 项目的完整交接文档，不包含用户个人背景，也不规定
  其他 AI 的讲解方式。
- 文档集中记录项目目标、模块化单体架构、BKN Schema、数据源、自动 Schema、对象关系物化、
  混合检索、三层上下文、行动风控、Trace、MCP、环境配置、演示、测试和评测结果。
- 增加完整能力状态表，区分已实现、适配器已实现但未外部实测、尚未实现三类状态。
- 增加按主题组织的详细资料索引，使后续 AI 或开发者可以直接定位规划、代码、API、数据库、
  检索、图谱、行动、MCP、测试和评测文件。
