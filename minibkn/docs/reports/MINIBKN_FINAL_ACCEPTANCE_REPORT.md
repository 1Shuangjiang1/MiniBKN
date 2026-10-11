> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 最终验收报告

## 1. 验收结论

MiniBKN 0.4.0 已完成本次约定的 Python 主流程复现，并通过本地自动化验收。程序可以从 CSV
或 SQLite 发现业务数据，构建 Schema、对象实例和关系，进行 BM25/向量/RRF 检索，组装
Schema→实例/子图→行动三层上下文，返回带引用回答，并通过风险门禁安全执行白名单行动，
最后用 trace_id 回放完整过程。

简历相关增强中的自动 Schema、OpenAI-compatible 描述增强、Sentence Transformers 适配器、
MCP 2.x Server、API Key 和 200 条检索评测也已落地。需要外部凭证或模型下载的路径通过接口
隔离和模拟测试验证，未把未执行的外部实验包装成已完成结果。

## 2. 最终自动化结果

| 检查项 | 结果 |
| --- | --- |
| Pytest | 13 passed |
| Ruff format | 58 files already formatted |
| Ruff lint | All checks passed |
| mypy strict | 44 source files, no issues |
| 一键演示 | 通过，最终事件为 `tool.succeeded` |
| Docker Compose 配置解析 | 通过 |
| Docker 镜像构建 | 未执行：Docker Desktop daemon 未运行 |

13 个测试覆盖 BKN 解析与非法关系、FastAPI/SQLite 集成、CSV/SQLite 资源发现、实例与子图、
检索问答、行动确认/拒绝/幂等、API Key、自动 Schema、AI Schema 请求约束、语义向量适配器和
MCP Client/Server 协议调用。

## 3. 一键演示结果

- 发现资源：`materials_csv`、`suppliers_csv`；
- 图谱：5 个对象、3 条关系；
- 索引：9 个文档，其中 Schema 3、实例 5、行动 1；
- 问答：正确识别 MAT-001、MAT-003 库存不足，供应商均为 Precision Components；
- 引用：同时包含 BKN 文件与 CSV 精确行号；
- 风险：MAT-001 首次为 `pending_confirmation`；
- 确认后：状态为 `succeeded`；
- Trace：请求→风险判断→等待确认→批准→工具开始→工具成功。

## 4. 评测结果

固定数据集包含 200 条供应链查询，评测文件保存了每条问题、正确文档 ID 和三种检索模式的
完整排名。

| 模式 | Hit@1 / Ragas ID Context Precision@1 | Hit@3 | MRR | Top-5 平均上下文字数 |
| --- | ---: | ---: | ---: | ---: |
| Vector | 0.515 | 0.760 | 0.6442 | 862.39 |
| BM25 | 0.735 | 0.890 | 0.8227 | 687.94 |
| Hybrid RRF | 0.730 | 0.835 | 0.7934 | 802.56 |

Hybrid 相比当前离线 Vector 基线的 Hit@1 提升 0.215，MRR 提升 0.1492。BM25 在这个包含
大量精确 ID 和字段词的数据集上略胜 Hybrid，这是需要如实说明的数据集特征。Ragas
Faithfulness 需要评审 LLM，因没有用户凭证而未运行；参考简历中的 0.78、0.89 和 Token 降低
36% 不属于本项目实测结果。

## 5. 如何验收

在 `minibkn` 目录执行：

```powershell
uv sync --extra dev --extra evaluation --no-editable --reinstall-package minibkn
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff format --check src tests scripts
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m mypy src
.\scripts\demo.ps1
.venv\Scripts\python.exe scripts\evaluate_offline.py
.venv\Scripts\python.exe scripts\evaluate_ragas.py
```

启动服务：

```powershell
.venv\Scripts\python.exe -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/docs` 可手工验收 API。Docker Desktop 启动后，再执行
`docker compose up --build` 完成容器环境复核。

## 6. 项目边界

这是面向学习、秋招与本地演示的核心复现，不是对上游商业平台的替换。没有复现 Kubernetes
微服务部署、所有数据库连接器、多租户 OAuth、任意代码沙箱和完整 Web Studio。当前演示工具
只生成本地补货预警，不会真实采购。上述边界不会截断数据→图谱→检索/问答→安全行动→Trace
的完整主链路。

## 7. 简历使用建议

可以陈述已经实现的架构、模块和本报告中的实测指标。若要写 Faithfulness、真实多语言语义
模型对比或 Token 降幅，应先提供评审 LLM/模型环境，运行新实验并保存结果，再更新简历。
