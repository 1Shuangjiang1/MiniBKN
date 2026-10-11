# MiniBKN

[English](README.md) | 中文

**把企业表格、业务关系和文档知识组织成可查询、可追溯、可控执行的业务知识网络。**

MiniBKN 是参考 [BKN Foundry](https://github.com/openbkn-ai/bkn-foundry) 思路实现的 Python-first 学习与作品集项目。它不是上游平台的完整移植，也不是官方产品：把复杂微服务部署收敛为 FastAPI + SQLite 模块化单体，配套 React 控制台。当前版本 **0.6.0**。

默认模式**不需要 API Key、模型下载或 LightRAG 服务**，即可运行结构化主链路。配置兼容 OpenAI 的 LLM、语义 Embedding 与独立 LightRAG 后，可以启用查询理解、辅助建模和企业文档分支。

## 1. 能解决什么问题

普通文档问答擅长“找到一段文字”，但企业问题常常是“找到某个客户的订单，再关联订单明细，统计金额，并检查我有没有权限”。MiniBKN 显式记录对象、关系、动作与风险，用检索找证据，用受限查询计划处理关联与统计，用确定性权限和风险规则控制行动。

例如供应链演示：“哪些物料库存低于安全库存，它们由谁供应？”系统关联物料与供应商，返回来源引用；请求补货预警时先校验权限和风险，高金额操作需人工确认。示例工具只生成本地结果，**不真实采购、不支付、不发送通知**。

## 2. 功能与实际边界

| 模块 | 已实现的内容 |
| --- | --- |
| 数据接入 | 本地 CSV、SQLite；发现资源、字段类型、候选单列/组合主键、可解释外键候选 |
| BKN 建模 | YAML frontmatter + Markdown 的对象、关系、动作、风险定义；字段映射与交叉校验 |
| AI 辅助建模 | 自然语言需求与描述增强；逐条提案审核后发布；AI 建议的动作默认禁用、待配置工具 |
| 图与索引 | 对象/关系物化；Schema、实例、动作卡片；BM25 + 向量 + RRF；索引版本校验 |
| QueryPlan | 规则或 LLM 查询理解；改写、关键词/同义词、子问题、歧义追问；受限过滤、关联遍历和聚合 |
| 业务问答 | 三层上下文、统一证据、来源引用；默认确定性抽取回答，而非自由生成答案 |
| 权限与动作 | API Key；principal/角色/网络/资源/文档域/动作 RBAC；allow/confirm/deny 风险 DSL、幂等与审计 |
| 非结构化知识 | 可选 LightRAG REST sidecar；文本提交、异步索引状态、检索；结构化/文档/混合路由 |
| 增量更新 | 检测新增/修改/删除对象和边，差量写图与索引；失败时恢复快照 |
| 产品入口 | FastAPI REST/OpenAPI、3 个 stdio MCP 工具、React 六工作区控制台 |
| 质量与评测 | 单元/集成测试；合成 CRM、采购、财务、HR；检索、计划、动作、Ragas、Token、性能评测脚本 |

重要限制：

- RBAC 目前是资源/文件和文档域级，**没有员工逐行权限、字段脱敏、SSO 或生产多租户隔离**。不能直接用于真实工资自助查询。
- CSV/SQLite 是结构化入口；Excel 需先转 CSV。PDF/Word/OCR 不是 MiniBKN 的现成上传解析器；文档入口提交文本，其他格式需前置解析或 sidecar 支持。
- 外键发现只是候选建议，不能自动保证业务语义正确，需要人工确认。
- `/ask-intelligent` 做 QueryPlan 与追问；`/ask-routed` 做结构化/文档路由，**两者不是已统一的超级入口**。自动路由目前使用规则关键词；控制台问答使用后者。
- QueryPlan 不是任意 SQL 或代码执行器。回答/计划可以建议动作，但**不会自动执行动作**，需要调用单独执行接口。
- 增量构建仍会读取完整数据源来计算差异，不是 CDC；当前回滚和并发边界不等同于生产级事务编排。
- 工具需要开发者白名单注册；自然语言生成的动作不等于已经有实际业务连接器。
- 默认离线 token_hashing 只用于可重复基线，不是语义 Embedding。更换模型或维度后要重建索引。

## 3. 系统架构

```text
React 控制台 / REST 客户端 / MCP
                    │
            FastAPI + 认证/RBAC
                    │
    ┌───────────────┼──────────────────────┐
CSV / SQLite   查询分析与 QueryPlan       文档文本
    │               │                      │
字段剖析→建模审核   受限计划执行       LightRAG sidecar（可选）
    │               │                      │
对象/关系/索引 ─→ 检索 + 子图 ←── 文档/混合路由
                    │
          三层上下文 / 统一证据 / 引用回答
                    │（独立动作请求）
          权限 → 风险 → 必要时确认 → 白名单工具
                    │
               SQLite / 审计 trace
```

领域模型在 `domain/`，流程在 `application/`，接口契约在 `ports/`，数据库、检索、LLM、文档和工具实现位于 `adapters/`。不需要 Neo4j、Redis 或 Kubernetes。

## 4. 安装与启动（最短路径）

准备 Python **3.11 或 3.12**、[uv](https://docs.astral.sh/uv/)、Node.js **22.12+** 和 npm。推荐普通英文路径；不支持 Python 3.13+。命令从下载后项目根目录开始，不依赖作者电脑。

```sh
git clone https://github.com/1Shuangjiang1/MiniBKN.git
cd MiniBKN
```

### 4.1 后端

```sh
cd minibkn
uv sync --frozen --python 3.11 --extra dev --no-editable
```

复制配置（默认可不创建 `.env`，使用内置离线配置）：

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```sh
# Linux / macOS
cp .env.example .env
```

启动：

```sh
uv run --no-sync python -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

健康检查 <http://127.0.0.1:8000/health>；交互式 API 文档 <http://127.0.0.1:8000/docs>。

采用非 editable 安装，避免部分 Windows 中文路径 `.pth` 编码问题。修改源码后重装：`uv sync --frozen --extra dev --no-editable --reinstall-package minibkn`。不要把 `.env` 或密钥上传。

### 4.2 在运行中的服务里装载示例

保持服务终端打开，在另一终端进入 `minibkn`：

```sh
uv run --no-sync python scripts/seed_demo.py --example supply_chain
uv run --no-sync python scripts/seed_demo.py --example crm
```

脚本通过 HTTP 导入 BKN、注册 CSV、发现字段并构建网络，会修改**本地演示数据库**；首次启动空库时使用。重复导入可能报冲突，已有数据可在 API/UI 中重建，勿删除数据库来强制重试。认证启用时加 `--api-key-file /path/to/your/local/key.txt`。

若只想看完整链路输出、还不想启动服务器：

```sh
uv run --no-sync python scripts/demo.py
```

这个脚本启动内存 HTTP 应用并写独立 demo 数据库，不会填充运行中服务器的数据库。

### 4.3 前端

另开终端，在项目根目录：

```sh
cd minibkn-ui
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

打开 <http://127.0.0.1:5173>，连接地址填 `http://127.0.0.1:8000`；离线模式 API Key 留空。六个工作区为数据源、AI 建模、知识网络、业务问答、动作与风险、评测。UI 是中文，英语 README 不代表英语界面。知识网络中选择 `supply_chain` 后，可提问上述库存问题。

源文件路径是**服务端本地路径**，不是浏览器的文件上传；BKN 导入与复杂查询可先使用 Swagger。控制台不覆盖所有 API，不包含完整追问/动作审批向导。

## 5. 自己的数据如何接入

在 `/docs` 按顺序执行（下面路径均以服务工作目录 `minibkn` 为准）：

1. `POST /api/v1/sources`：`{"id":"my_files","name":"My files","kind":"csv","path":"/absolute/path/to/csv-folder"}`；SQLite 用 `kind: sqlite` 和数据库文件路径。
2. `POST /api/v1/sources/my_files/discover`：检查字段、主键与外键候选。
3. 导入自定义 BKN，或调用 `POST /api/v1/sources/my_files/generate-network` 自动生成基础网络；具体参数见实时 Swagger。
4. 要使用提案审核，创建 `/api/v1/modeling-sessions`，逐条审核 `/proposals/{proposal_id}`，最后 `/publish`；不要把 AI 猜测直接当正式模型。
5. `POST /api/v1/networks/{network_id}/builds`：生成/更新对象、关系与索引。
6. 查询、检查引用；动作接入需要实现并注册工具，配置风险规则，测试后开放。

参考 [供应链 BKN](minibkn/examples/supply_chain/bkn/network.bkn) 和 [CRM BKN](minibkn/examples/crm/bkn/network.bkn)。CSV 仅使用合成测试数据，别把真实员工或客户信息加入公开仓库。

## 6. 查询和动作演示

Swagger 提交示例：

| 接口 | 请求 | 观察内容 |
| --- | --- | --- |
| `POST /api/v1/networks/supply_chain/ask` | `{"question":"哪些物料库存低于安全库存，它们由谁供应？"}` | 回答、Schema/实例/动作上下文、引用 |
| `POST /api/v1/networks/crm/query-plans/analyze` | `{"question":"查询 CUST-001 的订单"}` | 改写、关键词、歧义及结构化计划；无模型时是规则降级 |
| `POST /api/v1/networks/crm/ask-intelligent` | `{"question":"查询 CUST-001 的订单"}` | 计划执行或追问；LLM 需第 7 节配置 |
| `POST /api/v1/networks/crm/ask-routed` | `{"question":"客户折扣政策是什么？","route":"document"}` | 文档分支；显式 document 且未启用时返回 503；hybrid/auto 可降级 |
| `POST /api/v1/networks/supply_chain/actions/create_replenishment_alert/execute` | `{"object_type_id":"material","instance_id":"MAT-001"}` | 高金额风险：`pending_confirmation` |
| `POST /api/v1/action-executions/{id}/confirm` | `{"approved":true}` | 本地工具执行状态 |
| `GET /api/v1/traces/{trace_id}` | 无 body | 审计与风险判断事件 |

示例数据中 MAT-001、MAT-003 低于安全库存，供应商为 Precision Components；MAT-001 预警需确认。默认 `/ask` 是检索证据回答，可能同时列出正常库存对象，不保证替你精确筛选。要确定性筛选，可以向 `/api/v1/networks/supply_chain/query-plans/execute` 提交：

```json
{"plan":{"intent":"lookup","object_types":["material"],"filters":[{"field":"current_stock","operator":"lt","value_field":"safety_stock"}]}}
```

精确实体 ID 以各示例 CSV 为准；不同模型的分析文案可能不同。

## 7. 可选 LLM 与语义 Embedding

在 `minibkn/.env` 中配置，填入自己本地密钥文件的路径（或使用相应 `*_API_KEY` 环境变量）：

```dotenv
MINIBKN_LLM_PROVIDER=openai_compatible
MINIBKN_LLM_BASE_URL=https://api.deepseek.com/v1
MINIBKN_LLM_MODEL=deepseek-chat
MINIBKN_LLM_API_KEY_FILE=/path/to/private/deepseek.txt
MINIBKN_EMBEDDING_PROVIDER=siliconflow
MINIBKN_EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
MINIBKN_EMBEDDING_MODEL=BAAI/bge-m3
MINIBKN_EMBEDDING_DIMENSIONS=1024
MINIBKN_EMBEDDING_API_KEY_FILE=/path/to/private/embedding.txt
```

以上是已集成并留有历史验证记录的配置示例，不保证供应商今后的模型可用性/价格。模型调用需要网络并产生费用；数据/Schema 会发送给对应服务商。重启并重建网络索引。缺少密钥可能退回离线实现，查看日志/索引版本确认实际 provider，不能把降级结果算作语义模型测评。

也支持本地 `sentence_transformers`：安装 `uv sync --frozen --extra dev --extra semantic --no-editable` 并设置 `MINIBKN_EMBEDDING_PROVIDER=sentence_transformers`、对应模型及维度；首次下载模型。LLM 主要用于规划、分析、建模增强，默认回答仍是证据抽取，不是已接入通用聊天代理。

## 8. 权限与 LightRAG

### 8.1 权限

简单本地保护：设置 `MINIBKN_API_KEY`，API 请求使用 `x-api-key`。企业式示例：

```dotenv
MINIBKN_AUTHORIZATION_ENABLED=true
MINIBKN_AUTHORIZATION_POLICY_FILE=./config/access-policy.example.json
```

示例用户密钥 `demo-sales-key`、`demo-finance-key`、`demo-manager-key` 是**公开测试值**，必须在真实使用前更换。策略保存 SHA-256 摘要；按网络、资源、文档域、动作及 read/model/execute/approve/audit/admin 权限授权，不是行/字段权限。先在无权限的本地环境准备 CRM，再启用示例策略：示例 manager 不是全局 admin，可能不能注册全局数据源。

### 8.2 LightRAG 文档分支

独立 Python 3.12 sidecar；核心环境无需安装。历史验收使用 **lightrag-hku 1.5.6**，公开版本提供固定版本操作入口：

```sh
uv venv .lightrag-venv --python 3.12
```

```powershell
# Windows，仍在 minibkn 目录
uv pip install --python .lightrag-venv/Scripts/python.exe "lightrag-hku[api]==1.5.6"
./scripts/start_lightrag.ps1 -DeepSeekKeyFile /path/to/private/deepseek.txt -SiliconFlowKeyFile /path/to/private/embedding.txt -SidecarApiKey YOUR_LOCAL_SIDECAR_KEY
```

Linux/macOS 可向 `.lightrag-venv/bin/lightrag-server` 注入 `LLM_BINDING=openai`、`LLM_MODEL`、`LLM_BINDING_HOST`、`LLM_BINDING_API_KEY`、`EMBEDDING_BINDING=openai`、`EMBEDDING_MODEL`、`EMBEDDING_DIM=1024`、`EMBEDDING_BINDING_HOST`、`EMBEDDING_BINDING_API_KEY`、`LIGHTRAG_API_KEY` 后启动；host 保持 `127.0.0.1`、port 9621、workspace crm_public。详见 [LightRAG 操作说明](docs/LIGHTRAG.md)。

配置 MiniBKN：

```dotenv
MINIBKN_DOCUMENT_KNOWLEDGE_PROVIDER=lightrag
MINIBKN_LIGHTRAG_ENDPOINT_MAP_FILE=./evals/config/lightrag-local.json
MINIBKN_LIGHTRAG_API_KEY_FILE=/path/to/private/sidecar-key.txt
```

先装载 CRM。用 `POST /api/v1/networks/crm/documents/text` 提交 `{"collection":"public","title":"折扣制度","text":"标准折扣为 5%，超过 10% 需主管批准。"}`；使用返回 track_id 查询 `/api/v1/networks/crm/document-collections/public/jobs/{track_id}`，等索引完成后请求 `/ask-routed`，`route` 可选 `structured`、`document`、`hybrid`、`auto`。

仓库有 [3 份合成政策文档](minibkn/evals/fixtures/documents/crm_public)。每个敏感知识域应使用独立 endpoint/workspace；不要把财务与公开文档混入同一个 LightRAG 图后再过滤结果。仅 `public` 的本地配置不能演示完整 sales/finance 域。

## 9. MCP 与 Docker

MCP 使用 stdio。先启动 HTTP 后端，然后让 MCP 客户端运行 `minibkn/.venv/Scripts/minibkn-mcp.exe`（Windows）或 `minibkn/.venv/bin/minibkn-mcp`（Unix），设置 `MINIBKN_API_BASE_URL`，启用权限时设置 `MINIBKN_API_KEY` 为用户密钥。工具为 `search_knowledge`、`ask_knowledge`、`request_action`，不绕过动作风险或人工确认。

Docker 可选：在 `minibkn` 下 `docker compose up --build`。容器服务内的示例路径是 `/app/examples/...`，不是宿主机路径；compose 只启动后端，UI 和 LightRAG 分别运行。容器安装依赖不是完整 uv 冻结复现；本轮发布验收以 uv 安装为准。

## 10. 测试与评测

离线验证（不调用付费模型）：

```sh
# minibkn 目录
uv run --no-sync python -m pytest -q
uv run --no-sync python -m ruff format --check src tests scripts
uv run --no-sync python -m ruff check src tests scripts
uv run --no-sync python -m mypy src/minibkn
uv run --no-sync python scripts/evaluate_offline.py
uv run --no-sync python scripts/evaluate_crm.py --embedding-provider token_hashing
# minibkn-ui 目录
npm test
npm run build
```

付费评测需 `--help` 查看明确的 key 文件、input、database、output 参数；可选安装 `uv sync --frozen --extra dev --extra evaluation --no-editable`，Ragas 固定为 0.4.3。建议先小样本，**不要直接批量跑所有付费评测**。新增评测会生成本地结果，不代表自动覆盖历史结论。详细入口见 [评测复现指南](docs/EVALUATION.md)。

公开版本机验收（2026-10-11）：**后端77测试、前端8测试、静态检查和构建通过，后端覆盖率88.70%**；另跑200题离线检索、130个冻结计划执行和30个风险模拟。没有重新跑付费模型/Ragas，详见 [发布报告](docs/PUBLICATION_REPORT.md)。开发测试工具仍有3项依赖安全告警，不能因此声称可直接生产部署，见 [安全说明](SECURITY.md)。

已有历史结果（不是本次发布重跑的模型成绩）：

| 评测 | 样本与结果 | 口径限制 |
| --- | --- | --- |
| CRM 检索 | 200 合成题；BM25/BGE-M3/混合 Hit@1 = 0.700/0.515/0.700 | 混合未优于 BM25，不能宣传全面领先 |
| QueryPlan | 60 题 holdout；精确准确率 93.33% | 独立 6 题对抗测试 5/6，非通用正确率 |
| Ragas Faithfulness | 分层 30 题均值 0.9261 | LLM 裁判、小样本，不是人工标注的线上质量 |
| 传统 RAG 对照 Token | 30 题：回答输入 844.07→280.40，减少 66.78%；总 Token 减少 62.36% | 冻结正确 QueryPlan，**不含在线规划成本**，只说明回答阶段 |
| 动作风险 | 30 题，allow/confirm/deny 各 10，判断准确率 100% | 规则模拟，非真实支付/审批验收 |
| LightRAG | 3 篇政策文档真实索引/检索命中 3/3 | 接入冒烟，非大规模质量证明 |

10 题全指标 Ragas 诊断也保留失败和负向结果，不把它等同于 200 题全量评测。所有数据是固定 seed 的**模拟业务数据**，不是来自某家企业/NUS 的真实数据。查看 [公开评测口径](docs/EVALUATION.md)、[原始结果](minibkn/evals/results)、[历史最终说明](minibkn/docs/reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)。

## 11. 代码与文档导航

```text
README.md / README.zh.md     双语公开入口
docs/                       当前发布、评测、LightRAG、安全说明
minibkn/
  src/minibkn/              后端源码（领域 / 应用 / 端口 / 适配器 / API）
  examples/                 小型供应链与 CRM 演示
  config/                   权限/文档知识域示例策略
  tests/                    单元与 API 集成测试
  scripts/                  导入、数据生成、演示与评测
  evals/                    固定数据集、合成业务表、历史结果
  docs/                     架构、设计、各阶段开发报告、技术深入与交接
minibkn-ui/                 React + TypeScript + Vite 控制台及测试
tools/check_release.py      发布清单、文件完整性、常见密钥格式检查
PUBLICATION_MANIFEST.json   本次公开快照的文件与 SHA-256
```

从 [文档导航](docs/README.md) 开始；完整代码/职责交接见 [项目总交接](minibkn/docs/handoffs/MINIBKN_COMPLETE_REPOSITORY_HANDOFF_FOR_AI.md)；技术细节见 [专题入口](minibkn/docs/technical_deep_dive/README.md)。历史文档保留原阶段状态并标识，不应覆盖此 README 的现状说明。本次发布整理记录在 [发布报告](docs/PUBLICATION_REPORT.md)。

## 12. 常见问题与安全

- “看不到网络”：先 seed/import/build；demo.py 不会把样本写进运行服务。
- “模型改了后搜索异常”：重建图索引，不要混用不同 Embedding 版本。
- “访问 UI 报跨域”：地址/端口应与 `MINIBKN_CORS_ORIGINS` 相符；后端确认启动。
- “401/403”：检查服务 API Key、用户角色及资源范围；不要为解决问题而直接取消生产权限。
- “文档搜不到”：确认 sidecar 可达、知识域映射、API Key、异步任务已经完成；disabled 降级不是检索成功。
- 仅绑定本地回环地址；默认未启用认证、API 接受服务端路径、UI 可存 Key 到 localStorage，**不可直接公网部署**。见 [SECURITY.md](SECURITY.md)。

## 13. 来源、许可与贡献

架构与 BKN 概念参考 [openbkn-ai/bkn-foundry](https://github.com/openbkn-ai/bkn-foundry)，UI 参考企业知识工作台的产品方向；LightRAG 是第三方可选依赖。MiniBKN 不声称是官方平台、NUS 研究成果或生产 SaaS。

保留原 [LICENSE](LICENSE)、[NOTICE](NOTICE)、[Apache 文本](LICENSE-APACHE.txt)、[OpenBKN 文本](LICENSE-OPENBKN.txt) 与源码原许可证头。**不是统一 MIT/Apache 项目**，请按文件和其来源核对适用条款；OpenBKN 文本包含额外条件，未添加任意商用承诺。见 [来源说明](docs/PROVENANCE.md)。

贡献请说明场景、复现步骤和测试结果；勿上传秘密或真实客户数据。当前后续重点是行/字段权限、查询与路由统一入口、非结构化文件解析和更大规模人工审校评测，而非扩大未经验证的效果宣传。
