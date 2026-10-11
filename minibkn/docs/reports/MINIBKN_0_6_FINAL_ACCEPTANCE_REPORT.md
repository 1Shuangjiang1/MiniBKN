> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 0.6.0 最终收尾验收报告

## 1. 验收结论

本轮约定的两条工程主线已完成：

1. 企业权限管控已进入结构化读取、检索、QueryPlan、图扩展、文档域和行动链路；
2. LightRAG 已完成真实 sidecar 接入及中文文档入库、索引、检索、路由和混合返回。

秋招完整项目说明、两个专项开发报告、复现脚本、原始结果和其他 AI 交接资料均已补齐。项目默认仍能在不启动 LightRAG、不开启 RBAC 的情况下运行旧的结构化演示。

## 2. 自动化测试

最终命令：

```powershell
$env:PYTHONPATH=(Get-Location).Path
uv run ruff format src tests scripts
uv run ruff check src tests scripts
uv run mypy src
uv run pytest -q --cov=minibkn --cov-report=term-missing
```

结果：

- Pytest：**74 passed**；
- 行覆盖率：**89%**；
- 统计行数：4,061；
- 已覆盖：3,602；
- 未覆盖：459；
- Ruff：通过；
- Mypy strict：66 个源文件通过；
- 用时：126.74 秒。

新增专项覆盖了：非法凭证、资源隔离、受限索引命中、建模/行动拒绝、策略失败关闭、LightRAG API 合同和安全域隔离。既有文档禁用/降级、路由和混合测试继续通过。

## 3. 真实 LightRAG 验收

运行环境：LightRAG 1.5.6、DeepSeek `deepseek-chat`、硅基流动 `BAAI/bge-m3` 1024 维、本地 `crm_public` workspace。

结果：

- 健康检查：通过；
- 三份中文 Markdown 提交：通过；
- 后台索引状态：全部 `processed`；
- 文档检索：3/3；
- auto 文档路由：通过；
- auto 结构化路由：通过；
- hybrid 两路同时执行：通过；
- hybrid 证据：14 条结构化 + 3 条文档；
- 两类引用归一化：通过；
- 重复文档：返回独立 409 错误类型；
- 实际 API Key 未写入仓库或结果。

原始结果：`evals/results/lightrag/integration.json`。

## 4. 权限验收

- 未认证请求：401；
- 已认证但越权：403；
- 用户网络列表按授权过滤；
- CSV/SQLite 资源实例按文件权限过滤；
- 检索候选在排序/回答前过滤；
- QueryPlan 的值提示、扫描、关系和聚合使用授权数据；
- 子图关系两端都可见才返回；
- Schema 和行动列表按资源/行动权限裁剪；
- 风险 subject 使用认证身份，不能由客户端伪造；
- execute、approve、audit 分离；
- LightRAG 只查询允许的安全知识域。

## 5. 本轮发现并修复的问题

1. LightRAG 任务状态没有统一顶层 `status`，现从文档状态归纳；
2. 重复文档 409 原先被归为普通 502，现单独分类；
3. 检索缓存可能由管理员先加载完整文档，现每次请求仍按当前身份重新过滤；
4. 风险模拟的客户端 `subject` 可伪造角色，现由认证身份覆盖可信字段；
5. 文档知识状态会暴露其他安全域名称，现按当前用户过滤详情；
6. 全局 API Key 只有认证没有授权，现增加可选 RBAC，同时保持向后兼容。

## 6. 剩余边界

- 没有企业 SSO/OIDC、动态策略管理和字段级脱敏；
- 真实 LightRAG 只运行了 public 工作区，sales/finance 独立端点为已测试的部署模式；
- 文档小集合 3/3 是全链路冒烟，不是大规模质量结论；
- PDF/DOCX/OCR/表格版面尚未做专项评测；
- LightRAG 默认文件存储不等于生产高可用；
- 根仓库仍把 `minibkn/` 视作新增目录，本轮没有 commit、push 或 PR。

## 7. 最终资料入口

- 完整项目说明：`MINIBKN_AUTUMN_RECRUITMENT_COMPLETE_PROJECT_DESCRIPTION.md`
- 权限报告：`MINIBKN_ENTERPRISE_ACCESS_CONTROL_DEVELOPMENT_REPORT.md`
- LightRAG 报告：`MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md`
- 秋招 AI 交接：`../handoffs/MINIBKN_AUTUMN_RECRUITMENT_PROJECT_HANDOFF_FOR_AI.md`
- 总导航：`../MINIBKN_DOCUMENTATION_NAVIGATION.md`
