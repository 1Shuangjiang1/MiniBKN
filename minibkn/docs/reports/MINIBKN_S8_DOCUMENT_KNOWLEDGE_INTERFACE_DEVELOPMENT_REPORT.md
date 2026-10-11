> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN S8 文档知识接口预留产品开发报告

> 完成日期：2026-08-16\
> 前置报告：[S7 AI 辅助建模工作流产品开发报告](MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md)\
> 对应计划：[分步开发计划](../plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)\
> 状态：接口已完成；LightRAG 实现按用户要求跳过

## 1. 与 S7 的衔接

S7 明确了结构化 BKN 是业务对象、关系、动作和风险规则的权威来源。S8 没有改变这一点，只允许外部文档系统返回“文档证据”。即使未来接入 LightRAG，最终回答仍由 MiniBKN 汇总，动作仍只能读取已发布 BKN 并经过 S5 门禁。

## 2. 这一步实际做了什么

系统现在有一个标准插槽 `DocumentKnowledgePort`。任何未来文档引擎只要实现两个能力即可接入：

- 报告自身是否启用以及支持哪些能力；
- 根据 network、问题和数量限制返回统一 `EvidenceItem` 文档证据。

核心服务不认识 LightRAG 的内部存储、实体、关系或回答格式。适配器负责把外部结果转成统一证据，MiniBKN 负责路由、去重、引用和最终回答。

## 3. 已完成的路由能力

统一问答支持四种 route：

- `structured`：只走 MiniBKN 结构化图与索引；
- `document`：只走文档知识提供者；
- `hybrid`：两路都查，合并证据后统一回答；
- `auto`：根据问题判断，业务数据问题走结构化，制度、合同、手册、政策等问题优先走文档。

当前默认提供者是 `disabled`。显式请求 document 会返回清楚的 503 错误；auto 或 hybrid 可按配置安全降级到结构化证据，并在响应中返回 warning，避免用户误以为已经检索过文档。

## 4. 新增 API

```text
GET  /api/v1/document-knowledge/status
POST /api/v1/networks/{network_id}/ask-routed
```

`ask-routed` 返回 requested_route、executed_routes、evidence、citations 和 warnings，因此 UI 与评测程序能够判断系统实际上走了哪条链路。

## 5. 为未来 LightRAG 留出的接入点

未来只需新增一个外部适配器并在创建应用时注入，无需修改 RetrievalService、动作服务或路由 API。推荐的实现仍是独立 REST sidecar，并把 LightRAG 的实体、关系、文本块和引用转换成 `EvidenceKind.DOCUMENT`。

本阶段没有：

- 安装 LightRAG 包；
- 启动 LightRAG Server；
- 创建 workspace；
- 导入任何非结构化文档；
- 编写依赖 LightRAG 私有数据结构的代码。

## 6. 配置

`.env.example` 已增加：

```text
MINIBKN_DOCUMENT_KNOWLEDGE_PROVIDER=disabled
MINIBKN_DOCUMENT_KNOWLEDGE_DEGRADE_WHEN_DISABLED=true
```

provider 字段现在用于明确当前状态；未来实现具体适配器时再增加 endpoint、workspace 和鉴权配置。

## 7. 测试结果

```text
全量测试：42 passed
Ruff：通过
Mypy strict：62 个源文件通过
```

测试使用一个内存中的假文档提供者，证明不修改核心代码即可注入；覆盖纯文档查询、混合证据、状态接口、默认禁用错误，以及 auto 路由降级和 warning。

## 8. 当前限制与 S9 要求

- auto 目前是透明的关键词规则，未来可替换为可评测的意图分类器；
- 还没有真实文档入库、删除、workspace 隔离或文档增量同步接口；
- S9 UI 应展示当前文档能力状态、实际执行路线和降级警告，不能把未启用的 LightRAG 显示为可用；
- S10 的文档指标只能验证路由契约与假适配器，不能宣称真实 LightRAG 效果。
