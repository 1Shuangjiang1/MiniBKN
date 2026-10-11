> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN Acceptance Guide

## Automated acceptance

```powershell
uv sync --python <local-path> --extra dev --extra evaluation --no-editable --reinstall-package minibkn
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff format --check src tests scripts
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m mypy src
.\scripts\demo.ps1
.venv\Scripts\python.exe scripts\generate_crm_benchmark.py
.venv\Scripts\python.exe scripts\evaluate_crm.py
.venv\Scripts\python.exe scripts\evaluate_ragas.py
```

Real-provider acceptance is opt-in and reads one-line local key files without printing them:

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python.exe scripts\verify_ai_demo.py `
  --deepseek-key-file <local-path> `
  --siliconflow-key-file <local-path>
```

It must report DeepSeek planner `ready`, BGE-M3 dimension `1024`, aggregate result `136600.5`,
clarification status `needs_clarification`, and top CRM entity `CUST-001`.

The supply-chain demo must report two resources, five objects, three relations, nine indexed
documents, a domain-neutral evidence answer with row citations, `pending_confirmation` before
approval, `succeeded` after approval, and a trace ending in `tool.succeeded`. The automated CRM
integration test must additionally materialize seven objects and four relations, then answer the
customer-to-order question with instance and relation evidence.

## API acceptance

Start the application and open <http://127.0.0.1:8000/docs>. Execute the endpoints in the order
listed in the root README. Confirm that every response contains an `x-trace-id`, expected failures
use the unified error envelope, and source citations point to BKN documents or exact resource rows.

## Docker acceptance

```powershell
docker compose up --build
```

Check <http://127.0.0.1:8000/health> and <http://127.0.0.1:8000/docs>. The named volume preserves
the SQLite database across container recreation.

If Docker Desktop is not running, the image build cannot be verified locally; this does not affect the
native Python acceptance commands above.

## Optional semantic-model acceptance

```powershell
uv sync --extra dev --extra semantic --no-editable --reinstall-package minibkn
$env:MINIBKN_EMBEDDING_PROVIDER="sentence_transformers"
.venv\Scripts\python.exe -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

The first run downloads the configured model. The default token-hashing provider remains available for
offline and deterministic CI runs.

## MCP acceptance

The automated test starts the MCP 2.x client and server in memory, lists all three tools, and calls
`ask_knowledge`. For a manual stdio check, start the HTTP API and configure an MCP client to execute
`.venv\Scripts\minibkn-mcp.exe` with `MINIBKN_API_BASE_URL` and, if enabled, `MINIBKN_API_KEY`.

## Evaluation interpretation

The CRM result contains all 200 cases and complete top-5 rankings plus 30 side-effect-free action
simulations. The comprehensive suite adds a fresh 60-case DeepSeek QueryPlan holdout and a six-case
adversarial set. `evaluate_ragas_comprehensive.py` applies ID-based Precision/Recall to all 200 cases
and can run stratified DeepSeek Faithfulness. The completed 30-case run scored 0.9261 with zero judge
failures. Detailed artifacts stay under `evals/results/comprehensive/`; the compact UI response is
generated as `evals/results/latest.json`. The UI must pass `npm run lint`, `npm run test`, and
`npm run build` in the sibling `minibkn-ui` product. Current verified totals are 67 backend tests and
8 frontend tests.
