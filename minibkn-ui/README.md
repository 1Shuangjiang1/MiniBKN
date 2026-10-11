# MiniBKN Control Room

React 19 + TypeScript + Vite. A separate lightweight UI, with no page-scoped backend.
See [English usage](../README.md) / [中文使用说明](../README.zh.md).

Use Node.js 22.12+ and the committed lockfile:

```sh
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
npm test
npm run build
```

Start `../minibkn` separately. The UI talks directly to `http://127.0.0.1:8000`.
Six Chinese-language workspaces: sources, modeling, networks, questions, actions/risks and evaluation.
Local source paths belong to the backend host, not browser file upload.
This UI does not expose all APIs; Swagger provides advanced query clarification and confirmation calls.
