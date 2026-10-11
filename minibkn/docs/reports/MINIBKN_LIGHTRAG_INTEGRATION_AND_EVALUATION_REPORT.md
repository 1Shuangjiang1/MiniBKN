> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN × LightRAG 接入与全链路评测报告

## 1. 结论

LightRAG 已不再只是接口预留。MiniBKN 0.6.0 已通过独立 REST sidecar 完成真实接入，并实际验证了健康检查、中文文档入库、异步索引状态、文档检索、自动路由、结构化/文档混合返回、引用归一化和故障降级。

核心职责保持清晰：

- MiniBKN 管结构化权威数据、QueryPlan、权限、证据融合、回答和行动门禁；
- LightRAG 管非结构化文档切分、实体关系抽取、图与向量索引；
- MiniBKN 调用 `/query/data` 获取原始实体、关系、文本块和引用，不直接采信另一个系统生成的最终答案。

## 2. 为什么使用 sidecar

LightRAG 官方建议外部项目优先使用 API Server 的 REST 接口。将它装入 MiniBKN 主进程会带来 100 多个额外包、不同的存储生命周期和模型配置，增加启动与故障耦合。

当前设计因此具备：

- LightRAG 停机时，自动/混合路线可降级到结构化证据；
- 显式指定文档路线时返回清晰错误，不伪装成功；
- MiniBKN 默认仍可完全离线运行；
- 可以独立扩容、重建或更换某个文档知识域；
- 不把 LightRAG 的依赖加入 MiniBKN 核心安装包。

## 3. 已实现能力

### 3.1 适配器

`LightRAGDocumentKnowledge` 实现：

- `GET /health`：检查每个安全知识域；
- `POST /documents/text`：提交 Markdown/纯文本；
- `GET /documents/track_status/{track_id}`：跟踪后台索引；
- `POST /query/data`：获取原始检索数据；
- 将文本块转成统一 `EvidenceItem` 和 `document://` 引用；
- 某些知识域失败时保留其他成功域，全部失败才返回 503；
- 识别重复文档 409，与一般网络/服务失败区分。

### 3.2 MiniBKN API

- `POST /api/v1/networks/{id}/documents/text`
- `GET /api/v1/networks/{id}/document-collections/{collection}/jobs/{track_id}`
- `GET /api/v1/document-knowledge/status`
- `POST /api/v1/networks/{id}/ask-routed`

路由支持 `structured`、`document`、`hybrid`、`auto`。当前自动路由以可解释关键词规则为主；包含“制度、合同、手册、条款、政策、文档”等词时走文档路线，否则走结构化路线。混合路线先执行结构化检索，再查询获准文档域，最后去重并统一回答。

## 4. 真实运行环境

本轮使用：

- LightRAG：`lightrag-hku==1.5.6`，独立 Python 3.12 环境；
- LLM：DeepSeek `deepseek-chat`，用于文档实体关系抽取和查询关键词；
- Embedding：硅基流动 `BAAI/bge-m3`，1024 维；
- 存储：LightRAG 默认 JSON KV、NanoVectorDB、NetworkX；
- Workspace：`crm_public`；
- 服务仅绑定 `127.0.0.1:9621`，并启用独立 X-API-Key。

密钥只从 `<local-path>` 的本地文件读取，没有写入源码、报告或结果。

## 5. 测试文档

在 `evals/fixtures/documents/crm_public/` 新建了三份无真实机密的中文材料：

1. 客户服务手册：普通/VIP 响应时限、投诉升级和禁止披露项；
2. 销售折扣制度：10%、20% 两级审批和必填信息；
3. CRM 数据治理制度：敏感字段、离职凭证停用和审计保留期。

三份文档都完成后台处理，LightRAG 生成文本块、实体和关系并持久化。测试过程中发现 `/documents/track_status` 的返回没有统一顶层 `status`，实际状态位于每个 document 中；适配器已增加状态归纳逻辑，这是本轮真实联调修复的问题。

## 6. 实测结果

真实文档检索问题：

| 问题 | 预期依据 | 结果 |
|---|---|---|
| 销售折扣超过 10% 需要谁审批？ | 销售经理 | 通过 |
| VIP 客户工单首次响应时限？ | 2 小时 | 通过 |
| 离职员工访问凭证多久停用？ | 4 小时 | 通过 |

结果为 **3/3**。每题均返回文档文本块和 `document://public/...#chunk=...` 引用。

路由与融合：

- 制度问题的 `auto` 路由执行 `document`；
- 纯客户订单问题的 `auto` 路由执行 `structured`；
- “客户订单与折扣审批制度”的 `hybrid` 路由同时执行两条链路；
- 混合响应中包含 14 条结构化证据和 3 条文档证据；
- 引用同时包含 BKN Schema、CSV 行、关系和文档块。

原始机器结果：`evals/results/lightrag/integration.json`。复现脚本：`scripts/evaluate_lightrag_integration.py`。

## 7. 启动和复现

首次建立独立环境：

```powershell
uv venv .lightrag-venv --python 3.12
uv pip install --python .lightrag-venv\Scripts\python.exe "lightrag-hku[api]"
.\scripts\start_lightrag.ps1
```

另开终端运行评测：

```powershell
$env:PYTHONPATH=(Get-Location).Path
uv run python scripts/evaluate_lightrag_integration.py --api-key-file data/lightrag/api-key.txt
```

MiniBKN 使用配置：

```text
MINIBKN_DOCUMENT_KNOWLEDGE_PROVIDER=lightrag
MINIBKN_LIGHTRAG_ENDPOINT_MAP_FILE=./evals/config/lightrag-local.json
MINIBKN_LIGHTRAG_API_KEY_FILE=./data/lightrag/api-key.txt
```

## 8. 测试资产

- REST 合同和安全域隔离：`tests/unit/test_lightrag_adapter.py`
- 路由、混合、禁用和降级：`tests/integration/test_document_knowledge_routing_api.py`
- 真实 sidecar 评测：`scripts/evaluate_lightrag_integration.py`
- 文档样本：`evals/fixtures/documents/crm_public/`
- 原始结果：`evals/results/lightrag/integration.json`

## 9. 当前边界

- 本轮真实 sidecar 只启动 `crm/public` 一个知识域；多知识域隔离通过 MockTransport 自动化验证，生产需为 sales/finance 分别部署固定 workspace；
- 当前自动路由是规则型，不是学习型分类器；
- 文档评测为 3 题工程冒烟，不应包装成大型统计结论；
- 尚未测试 PDF/DOCX 的复杂版面、OCR、表格和图片；
- 默认本地存储适合作品集演示，不代表生产高可用；
- LightRAG WebUI 的账户体系不是 MiniBKN 企业 RBAC，不能替代安全域隔离。

本报告引用的上游契约来自 [LightRAG 官方仓库](https://github.com/HKUDS/LightRAG) 和 [API Server 文档](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md)。
