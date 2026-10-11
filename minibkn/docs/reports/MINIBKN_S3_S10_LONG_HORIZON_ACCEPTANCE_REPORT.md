> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN S3–S10 长程开发最终验收报告

> 验收日期：2026-08-16\
> 执行范围：S3、S4、S5、S6、S7、S8 接口、S9、S10\
> 特别约束：S8 不实现或安装 LightRAG，只保留可插拔接口\
> 状态：开发与本地验收完成，等待用户审查工作树

> 后续更新：2026-08-17 已完成 S2 第一轮、DeepSeek 查询增强和真实 BGE-M3 冒烟。最新状态见 [P0 查询智能与数据发现报告](MINIBKN_P0_QUERY_INTELLIGENCE_AND_DATA_DISCOVERY_DEVELOPMENT_REPORT.md)；本文的“尚未完成”保留为 2026-08-16 的历史验收快照。

## 1. 最终交付总览

| 阶段 | 主要交付 | 验收报告 |
| --- | --- | --- |
| S3 | 硅基流动 Embedding、批处理、缓存、failover、索引版本 | [S3](MINIBKN_S3_EMBEDDING_DEVELOPMENT_REPORT.md) |
| S4 | LLM/规则 QueryPlan、白名单校验、过滤、跳转、聚合 | [S4](MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md) |
| S5 | 通用风险 DSL、模拟、审批优先级、幂等、审计 | [S5](MINIBKN_S5_RISK_DSL_DEVELOPMENT_REPORT.md) |
| S6 | 指纹变更集、局部图/索引更新、构建状态、失败恢复 | [S6](MINIBKN_S6_INCREMENTAL_BUILD_DEVELOPMENT_REPORT.md) |
| S7 | 自然语言建模会话、六类提案、逐条审核、人工发布 | [S7](MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md) |
| S8 | 文档知识端口、禁用适配器、auto/structured/document/hybrid 路由 | [S8](MINIBKN_S8_DOCUMENT_KNOWLEDGE_INTERFACE_DEVELOPMENT_REPORT.md) |
| S9 | 独立 React 控制台，六个产品工作区 | [S9](MINIBKN_S9_CONTROL_ROOM_UI_DEVELOPMENT_REPORT.md) |
| S10 | 9,140 对象 CRM、200 查询、30 动作题、真实基线和 Ragas | [S10](MINIBKN_S10_CRM_EVALUATION_DEVELOPMENT_REPORT.md) |

S2 不在用户本次 S3–S10 指令中，本轮没有补做统计型主外键识别。S6、S7 继续使用已有数据发现规则，并在各自报告中保留了这一限制。

## 2. 完整运行链路

```text
CSV / SQLite
  → 资源发现
  → 人工可审核的 AI 建模提案
  → 发布 BKN 对象 / 字段 / 关系 / 动作 / 风险
  → 增量构建对象图、关系与 Embedding 索引
  → QueryPlan 或混合检索
  → 结构化证据 + 可选文档证据端口
  → 统一回答与引用
  → 风险模拟 / 人工确认 / 幂等动作 / Trace
  → 冻结 CRM 数据集与可复算评测
```

LightRAG 没有进入该链路。未来适配器只负责返回 `EvidenceKind.DOCUMENT`，MiniBKN 仍掌握路由、回答与动作门禁。

## 3. 最终自动验收

Python 后端：

```text
Pytest：44 passed
Ruff format --check：92 files already formatted
Ruff check：通过
Mypy strict：63 个源文件通过
```

React 控制台：

```text
Vitest：2 passed
TypeScript：通过
Vite production build：通过
npm audit：0 vulnerabilities
产物：JS gzip 65.97 kB；CSS gzip 3.03 kB
```

人工浏览器验收：

- 默认桌面视口可正常展示和导航；
- 390×844 窄屏可正常展示；
- 修复前整页宽度为 780px，修复后 document 宽度为 375px，不再横向溢出；
- 标题、表单 label、skip navigation、状态播报和 reduced motion 均存在。

## 4. 正式评测摘要

- BM25 Hit@1：0.700；
- token-hashing Vector Hit@1：0.035；
- Hybrid RRF Hit@1：0.355；
- QueryPlan 冻结计划执行准确率：1.000（130 题）；
- 风险决策准确率：1.000（30 题）；
- Ragas IDBasedContextPrecision@5：BM25 0.140、Vector 0.025、Hybrid 0.107；
- Faithfulness：未运行，原因是没有 evaluator LLM Key；
- LLM Token：0，因为该轮为抽取式回答；Top-5 上下文 Token 已分别记录。

这些结果没有达到参考简历中的目标数字。报告明确保留真实结果，并证明下一次最有价值的实验是接入真实硅基流动 Embedding 后在同一冻结集复跑。

## 5. 如何启动完整程序

后端：

```powershell
cd minibkn
uv sync --python <local-path> --extra dev --extra evaluation --no-editable --reinstall-package minibkn
Copy-Item .env.example .env
.venv\Scripts\python.exe -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

控制台：

```powershell
cd minibkn-ui
npm install
npm run dev
```

随后访问 `http://127.0.0.1:5173`。完整的使用、评测和验收命令分别位于 [README](../../README.md)、[评测说明](../../evals/README.md) 与 [验收指南](../ACCEPTANCE.md)。

## 6. 尚未完成或不能宣称的部分

- S2 统计剖析、组合主键与多候选外键审核尚未实现；
- LightRAG 只完成端口、禁用适配器和路由，没有真实文档入库或查询；
- 未配置硅基流动 Key，因此 S10 没有真实语义 Embedding 数字；
- 未配置 evaluator LLM，因此没有 Faithfulness；
- 没有公平的三层上下文消融实验，因此不能宣称 Token 降低 36%；
- UI 没有企业认证、多人协作或可视化 JSON 修改器；
- 检索器没有缓存 BM25 语料统计，大数据 P50 约 0.8 秒；
- 当前没有 Reranker，B3 只记录为未实现。

## 7. 工作树与审查状态

没有执行 commit、push、PR 或外部写入。根仓库当前把整个 `minibkn/` 视为新增目录，`minibkn-ui/` 也是新增产品；根 `.gitignore` 只修改了两条规则，使阶段报告不再被通用 `reports/` 规则吞掉。所有改动等待用户审查后再决定是否提交。
