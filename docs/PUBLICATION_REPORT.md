# GitHub 发布整理报告 / Publication report

日期：2026-10-11。版本：MiniBKN 0.6.0。状态：公开副本 verified locally；目标公开仓库为 `https://github.com/1Shuangjiang1/MiniBKN`，实际远程/CI状态见提交与 Actions，而非本文预先声明。

## What is included / 发布内容

完整后端源码、UI 源码/锁文件、单元与集成测试、小型示例、合成业务表和固定问题集、评测脚本与历史原始结果、项目设计/开发/技术/交接文档、许可证与 NOTICE。新增中英文公开 README、当前导航、评测口径/复现、安全、LightRAG 和上传指南；新增服务样例装载助手、离线 GitHub Actions、清单校验。

## What is not included / 排除内容

原 Foundry 无关微服务与部署栈、原 `.git` 历史、个人学习者画像与求职辅导资料、密钥、真实数据、虚拟环境、node_modules、构建产物、缓存、日志、运行数据库。不是删减 MiniBKN 的业务模块。保留历史结果但去标识本机路径；不伪造或更新模型分数。

原开发目录不覆盖；独立发布目录/zip 可上传到自己的仓库。上游 origin 保持不变；发布副本使用独立 Git 历史，不携带原仓库历史。

## Verification

| 检查 | 命令/方式 | 本机结果 |
| --- | --- | --- |
| 基础后端干净安装 | `uv sync --frozen --python 3.11 --extra dev --no-editable` | 成功，无需 semantic/evaluation 可选包 |
| 后端全量测试 | `uv run --no-sync python -m pytest -q --cov=minibkn` | **77 passed**；覆盖率88.70%，3602/4061语句 |
| Ruff 格式/规则 | `ruff format --check src tests scripts` / `ruff check src tests scripts` | 通过；最终重新校验包括新增装载助手和3项回归 |
| 类型检查 | `mypy src/minibkn` | 66源文件通过 |
| UI 干净安装 | `npm ci` | 成功，锁文件依赖可解析 |
| UI 测试/生产构建 | `npm test` / `npm run build` | **8 passed**；Vite生产构建成功 |
| 导出工具回归 | `publication/test_export_project.py`（原开发工作区） | **5 passed**，覆盖URL不被去标识破坏、路径清理、文件白名单、凭证参数化与Markdown换行 |
| 实际 HTTP 链路 | 隔离服务+两个示例装载+精确计划+动作确认+trace | 成功；低库存2行，动作succeeded，trace6事件；重复装载拒绝，显式文档disabled返回503，hybrid返回降级警告 |
| 孤立演示 | `scripts/demo.py` | 5对象/3关系/9索引；确认前pending_confirmation，后succeeded |
| CRM离线执行回归 | `scripts/evaluate_crm.py --embedding-provider token_hashing --output-dir ./data/publication-retrieval` | 200检索题完成；130冻结计划准确执行100%；30风险模拟判断100%；没有调用LLM/Ragas |
| 公共文件检查 | `python tools/check_release.py` | 哈希、常见密钥格式、本机路径、JSON与当前指南链接通过；最终清单数量见manifest |
| npm审计 | `npm audit --omit=dev` / 完整audit | 生产依赖0；开发工具仍3项（1moderate/2critical），见SECURITY |

初轮失败并已修复：导出去标识误匹配https URL（添加4项回归）；离线测试顶层导入可选Ragas/OpenAI（改按需导入）；可选sentence-transformers影响mypy（精确可选import说明）；格式化工具需使用模块配置；示例导入需预先检查已有网络/源。覆盖率初轮对非editable安装使用`--cov=src/minibkn`得到无效0%，改为`--cov=minibkn`后得到上述有效结果。没有隐瞒这些失败。

本次离线基准使用评测脚本默认 **1024维 token_hashing**，不是服务默认128维，也不是BGE-M3：BM25/vector/hybrid Hit@1分别0.700/0.195/0.380；混合离线检索没有优于BM25。原始新增记录为 `minibkn/evals/results/publication/offline-crm-20261011.json`。LLM规划准确率、Faithfulness与其他Ragas指标未在本次重新测量，历史语义模型结果不替换为这次离线分数。

## Remaining constraints

不会在本轮重新调用付费模型跑历史评测，也不声明 Docker、Unix GUI、云端 CI 或生产安全已验收。源码许可证头原样保留；未标注独立文件的最终许可由所有者确认，不能擅自标成 MIT。开发依赖告警需要经审核跨主版本升级，当前不使用force升级掩盖风险。

临时 HTTP 服务使用18765端口，测试结束后停止；测试环境/运行数据不进入zip或提交。zip仅按manifest清单打包，不会包含验收生成的虚拟环境或node_modules。
