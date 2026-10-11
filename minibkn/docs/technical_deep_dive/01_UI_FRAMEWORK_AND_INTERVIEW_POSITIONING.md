> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 01：UI 用了什么，复杂吗，面试时怎么说

## 结论

UI 使用 **React 19 + TypeScript + Vite 7**，是一个轻量的单页控制台，不是复杂前端平台。

它没有使用 Next.js、Vue、Redux、React Router、Ant Design，也没有单独的 BFF（Backend for Frontend）。页面状态主要由 React 的 `useState`、`useEffect`、`useMemo` 管理；通过浏览器 `fetch` 直接调用 FastAPI；样式集中在一份 CSS 中。

依赖事实见：

- [package.json](../../../minibkn-ui/package.json)
- [页面入口 main.tsx](../../../minibkn-ui/src/main.tsx)
- [全部工作区 App.tsx](../../../minibkn-ui/src/App.tsx)
- [HTTP 客户端 api.ts](../../../minibkn-ui/src/api.ts)
- [样式 styles.css](../../../minibkn-ui/src/styles.css)
- [前端测试 App.test.tsx](../../../minibkn-ui/src/App.test.tsx)

## 页面实际上做了什么

`App.tsx` 包含六个工作区：

| 工作区 | 用户操作 | 调用后端能力 |
| --- | --- | --- |
| 数据源 | 登记 CSV/SQLite 路径、发现字段 | `/sources`、`/discover` |
| AI 建模 | 创建建模会话、审核提案、发布 | `/modeling-sessions` |
| 知识网络 | 查看网络、触发增量构建 | `/networks`、`/builds` |
| 业务问答 | 选择结构化/文档/混合路线并提问 | `/ask-routed` |
| 动作与风险 | 风险模拟、提交动作 | `/risks/simulate`、`/execute` |
| 评测 | 读取真实生成的最近评测 | `/evaluations/latest` |

页面切换不是 URL 路由，而是 `view` 状态决定显示哪个面板。因此工程小、依赖少、容易理解，但刷新后不会保留当前页面，也不适合直接扩展为大型多团队前端。

`MiniBknApi` 只做四件事：拼接后端地址、序列化 JSON、需要时添加 `x-api-key`、把后端错误显示出来。它不会在浏览器里伪造业务答案。

## “轻量”具体体现在哪里

- 生产依赖只有 `react` 与 `react-dom`。
- 组件和六个页面目前都在一个 `App.tsx`，没有复杂目录和状态框架。
- 不维护第二套服务端逻辑，业务规则都在 Python 后端。
- 构建由 Vite 负责，测试由 Vitest + Testing Library 负责。
- API Key 保存在 `localStorage`，输入框使用密码类型；这只适合本地演示，不是生产级密钥管理。

最后一点需要主动说明：浏览器本地保存 API Key 能减少演示操作，但生产环境应改用企业登录、短期会话 Cookie/Token、HTTPS、CSRF 防护和服务端会话，而不是把长期密钥留在浏览器中。

## 面试时可以这样说

> 这个项目的重点是 Python 后端的业务知识网络、混合检索、QueryPlan 和安全动作链路。为了让完整能力可操作、可演示，我使用 React、TypeScript 和 Vite 做了一个轻量控制台。它没有引入复杂状态管理和 BFF，而是用六个工作区直接调用 FastAPI。我在前端经验有限，所以开发中配合了 AI coding 工具完成脚手架、样式和部分组件实现；我自己负责需求拆分、API 契约、权限边界、异常行为、联调和自动化验收，并能够解释数据如何从页面进入后端以及为什么不能在前端做安全判断。

若面试官追问“是不是 AI 写的”，建议如实回答：

> AI 是编码工具，不是需求负责人。我没有把生成代码直接当结果，而是先定义后端接口和验收条件，再检查请求参数、错误显示、API Key 传递、无数据状态和测试。项目的技术取舍和最终验收由我负责。

这比说“前端完全是我手写的”更真实，也比说“我不会前端，都是 AI 做的”更能体现工程能力。

## 当前 UI 的边界

- 问答页当前调用 `/ask-routed`，没有直接展示 `/ask-intelligent` 的歧义追问和 QueryPlan。
- 没有登录页；只提供手动输入 API Key。
- 没有细粒度地根据权限隐藏按钮，真正的拒绝由后端完成。
- 没有文件上传控件，结构化源填写本地路径，非结构化文档主要通过 API/脚本接入。
- 动作页能模拟和提交，但待审批动作的确认目前更适合在 Swagger/API 中操作。

因此正确定位是“覆盖完整后端能力的轻量演示控制台”，不是“已经完成的企业管理前端”。
