> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN S9 轻量控制台产品开发报告

> 完成日期：2026-08-16\
> 前置报告：[S8 文档知识接口预留产品开发报告](MINIBKN_S8_DOCUMENT_KNOWLEDGE_INTERFACE_DEVELOPMENT_REPORT.md)\
> 对应计划：[分步开发计划](../plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)\
> 状态：已完成

## 1. 与 S8 的衔接及架构边界

Foundry 架构规则禁止把 UI 放进后端项目，因此控制台建立在同级目录 `minibkn-ui/`，作为独立产品直接调用 MiniBKN `/api/v1`。没有新增页面专属 BFF，Python 后端也不依赖 React 产品。

S8 返回的 requested_route、executed_routes、warnings 和统一 evidence 已直接用于问答页面。文档提供者禁用时，界面会显示真实降级警告，不会伪装成已经执行 LightRAG。

## 2. 六个用户工作区

1. 数据源：登记 CSV 文件夹或 SQLite，随后执行字段发现并展示已连接资源；
2. AI 建模：用自然语言创建会话，查看对象、字段、主键、关系、动作、风险提案，逐条接受/拒绝并人工发布；
3. 知识网络：查看版本与对象/关系/动作/风险数量，执行 S6 增量构建并查看 BuildJob；
4. 业务问答：选择 auto、structured、document 或 hybrid 路线，同时查看回答、实际路线、证据与引用；
5. 动作与风险：先做无副作用风险模拟，再按需提交真实动作门禁；
6. 评测：读取 S10 最近一次正式报告，没有真实数据时只显示空状态，不预填简历数字。

## 3. 视觉与使用体验

前端设计规范最终采用工业控制室方向：深色刚性网格、琥珀色风险强调、青绿色运行状态、等宽数据标签和构建遥测面板。它与项目“业务知识运行与安全门禁”的主题一致，而不是通用管理后台模板。

界面支持：

- 980px 和 680px 两级响应式布局；
- 窄屏横向导航，不再引起整页横向溢出；
- 明确 label、键盘焦点、skip navigation 和 aria-live 状态；
- `prefers-reduced-motion` 降低动画；
- API 地址和可选 API Key 只保存在浏览器本地存储；
- 后端新增可配置 CORS 白名单，默认只允许本地 Vite 地址。

## 4. 运行方式

先启动 Python 后端，再启动控制台：

```powershell
cd minibkn
uv run minibkn

cd ..\minibkn-ui
npm install
npm run dev
```

浏览器访问 Vite 输出的本地地址，默认是 `http://127.0.0.1:5173`。左下角可修改后端地址和 API Key。

## 5. 测试与视觉验收

```text
后端全量测试：42 passed
后端 Ruff：通过
后端 Mypy strict：62 个源文件通过
前端交互测试：2 passed
前端 TypeScript：通过
前端生产构建：通过（JS gzip 65.97 kB，CSS gzip 3.03 kB）
npm audit：0 vulnerabilities
```

除自动测试外，已在真实本地浏览器中检查默认桌面视口和 390×844 窄屏视口。修复了窄屏导航的内在宽度导致整页变成 780px 的问题，最终页面宽度不超过视口。

## 6. 当前限制

- UI 是本地求职 MVP，没有登录、角色管理和多人协作；API Key 只适用于本地演示，不等于企业认证；
- 建模修改 payload 目前只提供接受/拒绝，复杂“修改后接受”仍需通过 API 或后续 JSON 编辑器；
- 动作表单采用手工输入 id 和 JSON，后续可根据网络 Schema 自动生成；
- 评测页依赖 S10 即将提供的 `/api/v1/evaluations/latest`；
- 外部 Google Fonts 加载失败时会使用系统字体，不影响功能。

## 7. 给 S10 的要求

S10 必须产出机器可读的最近评测结果接口，字段中明确数据集版本、样本数、各基线指标、延迟、Token、运行时间，以及未执行的 LLM/Ragas 指标及原因。UI 只展示该真实结果，不在前端计算或猜测数字。
