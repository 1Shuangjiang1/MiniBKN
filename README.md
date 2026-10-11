# MiniBKN

English | [中文](README.zh.md)

**Turn business tables, relationships and document knowledge into a queryable, traceable knowledge network with controlled actions.**

MiniBKN is a Python-first learning and portfolio implementation inspired by [BKN Foundry](https://github.com/openbkn-ai/bkn-foundry). It is neither a complete port nor an official OpenBKN product. A FastAPI + SQLite modular monolith replaces the upstream deployment complexity, with a separate React control room. Current version: **0.6.0**.

The default structured workflow needs **no API keys, model downloads or LightRAG server**. Optional OpenAI-compatible LLMs, semantic embeddings and a LightRAG sidecar enable richer planning, modeling assistance and document retrieval.

## 1. What it does

Business questions often require more than finding a paragraph: locate a customer, join orders and line items, calculate totals, check access, and possibly request an action. MiniBKN models objects, relations, actions and risks explicitly. Retrieval supplies evidence; constrained plans handle traversal and aggregation; deterministic permission and risk checks guard execution.

Example: “Which materials are below safety stock, and who supplies them?” The supply-chain demo joins materials to suppliers and returns citations. A replenishment-alert request requires confirmation when its value exceeds the policy threshold. The demo tool returns a local result; it **does not place orders, make payments or send notifications**.

## 2. Features and boundaries

| Area | Implemented |
| --- | --- |
| Sources | Local CSV and SQLite; resource/field profiling; single/composite key and explainable foreign-key candidates |
| BKN modeling | YAML-frontmatter/Markdown object, relation, action and risk definitions; mappings and cross-reference validation |
| Assisted modeling | Natural-language requirements, description enrichment and reviewed proposals; suggested actions are disabled until configured |
| Graph and index | Object/edge materialization; schema/instance/action cards; BM25 + embeddings + RRF; index-version checks |
| QueryPlan | Rules or optional LLM analysis; rewrites, keywords/synonyms, subquestions, ambiguity and clarification; constrained filtering/traversal/aggregation |
| Answers | Three-level context, unified evidence and source citations; deterministic extractive answers by default |
| Access and actions | API key; principal/role/network/resource/collection/action RBAC; allow/confirm/deny risk DSL, idempotency and traces |
| Documents | Optional LightRAG REST sidecar; text ingestion, asynchronous indexing status, structured/document/hybrid routing |
| Updates | Diff-based object/edge/index writes and snapshot restoration on failures |
| Interfaces | REST/OpenAPI, three stdio MCP tools and a six-workspace React control room |
| Evaluation | Unit/API tests; synthetic CRM/procurement/finance/HR data; retrieval, planning, action, Ragas, token and performance scripts |

Read these limitations before using the project:

- Authorization is resource/file and document-collection level, **not row-level, field-level, SSO or production multitenancy**. Employee-specific payroll access is not ready.
- Structured ingestion supports CSV/SQLite. Export spreadsheets to CSV. MiniBKN accepts document text; PDF/Word/OCR parsing requires a preprocessing layer or compatible sidecar facilities.
- Discovered foreign keys are candidates, not guaranteed business semantics; review them.
- `/ask-intelligent` handles planning/clarification, while `/ask-routed` handles knowledge routing. They are **separate entry points**, not one integrated agent. Auto routing is keyword-rule based; the UI uses the routed endpoint.
- Plans do not execute arbitrary SQL or code. Suggested actions are not automatic actions; execution uses a separate endpoint and registered tools.
- Incremental builds still read the full source to compute a diff; this is not CDC or production-grade concurrent transaction orchestration.
- Natural-language action suggestions do not create real business connectors.
- Offline token hashing is a reproducible baseline, **not semantic embedding**. Rebuild indexes after changing models/dimensions.

## 3. Architecture

```text
React / REST clients / MCP
            │
     FastAPI + authentication/RBAC
            │
  ┌─────────┼──────────────────────────┐
CSV/SQLite  Query analysis / QueryPlan  Document text
  │                 │                    │
Profile + reviewed  Constrained       Optional LightRAG
BKN modeling        execution         REST sidecar
  │                 │                    │
Objects/edges/index → Retrieval/subgraph ← Knowledge routing
                    │
          Context / evidence / cited answers
                    │ (separate action request)
          Access → risk → confirmation → allowlisted tool
                    │
                SQLite / traces
```

`domain/` contains models; `application/` orchestrates workflows; `ports/` defines contracts; `adapters/` implements persistence, retrieval, LLM, document and tool integrations. No Neo4j, Redis or Kubernetes is required.

## 4. Quick start

Prerequisites: Python **3.11 or 3.12**, [uv](https://docs.astral.sh/uv/), Node.js **22.12+**, npm. An ASCII checkout path is recommended. Python 3.13+ is unsupported. Start in the downloaded repository root.

```sh
git clone https://github.com/1Shuangjiang1/MiniBKN.git
cd MiniBKN
```

### 4.1 Backend

```sh
cd minibkn
uv sync --frozen --python 3.11 --extra dev --no-editable
```

Optionally copy `.env.example` to `.env`; built-in defaults already work offline:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```sh
# Linux / macOS
cp .env.example .env
```

```sh
uv run --no-sync python -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

Health: <http://127.0.0.1:8000/health>. Interactive API reference: <http://127.0.0.1:8000/docs>.

Non-editable installation avoids some Windows non-ASCII `.pth` encoding issues. After source changes, reinstall with `uv sync --frozen --extra dev --no-editable --reinstall-package minibkn`. Never commit `.env` or credentials.

### 4.2 Load live demo data

Keep the server running. In a second terminal, inside `minibkn`:

```sh
uv run --no-sync python scripts/seed_demo.py --example supply_chain
uv run --no-sync python scripts/seed_demo.py --example crm
```

This HTTP helper imports BKN, registers/discovers CSVs and builds the network in the **local running server's database**. Use it on a fresh demo database; repeated imports may conflict. Rebuild existing networks through the UI/API rather than deleting the database. If authentication is enabled, add `--api-key-file /path/to/private/key.txt`.

For an isolated in-process workflow, without starting a server:

```sh
uv run --no-sync python scripts/demo.py
```

This script creates its own demo database; it does **not** populate the live server.

### 4.3 Frontend

In a new terminal, starting from the repository root:

```sh
cd minibkn-ui
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

Visit <http://127.0.0.1:5173>. Set the API URL to `http://127.0.0.1:8000`; leave the key blank for default local mode. Workspaces cover sources, modeling, networks, questions, actions/risks and evaluation. The UI is in Chinese. Select the supply-chain network and ask the inventory question above.

Source paths refer to files on the **backend machine**, not browser uploads. Use Swagger for BKN import and advanced endpoints. The UI does not expose every API or a complete clarification/action-approval wizard.

## 5. Bring your own tables

Using `/docs`, in order:

1. `POST /api/v1/sources` with `{"id":"my_files","name":"My files","kind":"csv","path":"/absolute/path/to/csv-folder"}`. For SQLite, use `kind: sqlite` and a database path.
2. `POST /api/v1/sources/my_files/discover`; inspect fields and key candidates.
3. Import your BKN or call `POST /api/v1/sources/my_files/generate-network` for a basic model. Consult Swagger for exact request schemas.
4. For reviewed modeling, create `/api/v1/modeling-sessions`, review each `/proposals/{proposal_id}` and explicitly `/publish`. Do not publish unreviewed AI guesses.
5. `POST /api/v1/networks/{network_id}/builds` materializes/updates graph and indexes.
6. Query and inspect citations. Implement/register connectors and test their permission/risk rules before enabling actions.

See [supply-chain BKN](minibkn/examples/supply_chain/bkn/network.bkn) and [CRM BKN](minibkn/examples/crm/bkn/network.bkn). Public examples use synthetic records; do not add real employee/customer data.

## 6. API demo recipes

Submit these bodies using Swagger:

| Endpoint | Body | What to inspect |
| --- | --- | --- |
| `POST /api/v1/networks/supply_chain/ask` | `{"question":"哪些物料库存低于安全库存，它们由谁供应？"}` | Answer, three-level context and citations |
| `POST /api/v1/networks/crm/query-plans/analyze` | `{"question":"查询 CUST-001 的订单"}` | Rewrite, keywords, ambiguity and plan; rule fallback without LLM |
| `POST /api/v1/networks/crm/ask-intelligent` | `{"question":"查询 CUST-001 的订单"}` | Execution or clarification; configure LLM below for richer analysis |
| `POST /api/v1/networks/crm/ask-routed` | `{"question":"客户折扣政策是什么？","route":"document"}` | Document branch; explicit document route returns 503 when disabled; hybrid/auto can degrade |
| `POST /api/v1/networks/supply_chain/actions/create_replenishment_alert/execute` | `{"object_type_id":"material","instance_id":"MAT-001"}` | `pending_confirmation` for high-value request |
| `POST /api/v1/action-executions/{id}/confirm` | `{"approved":true}` | Local tool execution |
| `GET /api/v1/traces/{trace_id}` | No body | Risk and execution events |

The fixture's low-stock materials are MAT-001/MAT-003, supplied by Precision Components; MAT-001 requires confirmation. Default `/ask` summarizes retrieved evidence and can also include normal-stock objects; it does not guarantee precise filtering. For deterministic filtering, submit this to `/api/v1/networks/supply_chain/query-plans/execute`:

```json
{"plan":{"intent":"lookup","object_types":["material"],"filters":[{"field":"current_stock","operator":"lt","value_field":"safety_stock"}]}}
```

Match entity IDs to each fixture; analysis wording can vary by model.

## 7. Optional LLM and semantic embeddings

Configure `minibkn/.env` with your private local key-file paths (or corresponding `*_API_KEY` environment variables):

```dotenv
MINIBKN_LLM_PROVIDER=openai_compatible
MINIBKN_LLM_BASE_URL=https://api.deepseek.com/v1
MINIBKN_LLM_MODEL=deepseek-chat
MINIBKN_LLM_API_KEY_FILE=/path/to/private/deepseek.txt
MINIBKN_EMBEDDING_PROVIDER=siliconflow
MINIBKN_EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
MINIBKN_EMBEDDING_MODEL=BAAI/bge-m3
MINIBKN_EMBEDDING_DIMENSIONS=1024
MINIBKN_EMBEDDING_API_KEY_FILE=/path/to/private/embedding.txt
```

These are integrated configurations with historical validation, not promises of future provider availability/pricing. Calls require network access and may incur charges. Source/schema data will be sent to the provider. Restart and rebuild indexes. Check logs and embedding versions: missing credentials may cause offline fallback; do not count fallback as semantic-model evaluation.

Local sentence transformers are also supported: install `uv sync --frozen --extra dev --extra semantic --no-editable`, set `MINIBKN_EMBEDDING_PROVIDER=sentence_transformers` and configure matching model/dimensions. Initial use downloads a model. The LLM enhances analysis/planning/modeling; default answers remain extractive rather than a general chatbot agent.

## 8. Authorization and LightRAG

### 8.1 Authorization

For a shared local key, set `MINIBKN_API_KEY` and send `x-api-key`. For per-user policies:

```dotenv
MINIBKN_AUTHORIZATION_ENABLED=true
MINIBKN_AUTHORIZATION_POLICY_FILE=./config/access-policy.example.json
```

`demo-sales-key`, `demo-finance-key` and `demo-manager-key` are **public demo credentials**; replace them before real use. Policies store SHA-256 digests and scope networks, resources, document collections, actions and read/model/execute/approve/audit/admin permissions. This does not implement row/field security. Load CRM in local no-auth mode before enabling the example policy; its manager role is not a global admin and may not register sources.

### 8.2 Document branch

Use a separate Python 3.12 sidecar environment. Historical acceptance used **lightrag-hku 1.5.6**:

```sh
uv venv .lightrag-venv --python 3.12
```

```powershell
# Windows, inside minibkn
uv pip install --python .lightrag-venv/Scripts/python.exe "lightrag-hku[api]==1.5.6"
./scripts/start_lightrag.ps1 -DeepSeekKeyFile /path/to/private/deepseek.txt -SiliconFlowKeyFile /path/to/private/embedding.txt -SidecarApiKey YOUR_LOCAL_SIDECAR_KEY
```

Unix users can run `.lightrag-venv/bin/lightrag-server` with OpenAI-compatible LLM/embedding binding variables, matching model/dimension settings and a private `LIGHTRAG_API_KEY`; bind to 127.0.0.1:9621 with workspace crm_public. See the complete [sidecar setup](docs/LIGHTRAG.md).

MiniBKN settings:

```dotenv
MINIBKN_DOCUMENT_KNOWLEDGE_PROVIDER=lightrag
MINIBKN_LIGHTRAG_ENDPOINT_MAP_FILE=./evals/config/lightrag-local.json
MINIBKN_LIGHTRAG_API_KEY_FILE=/path/to/private/sidecar-key.txt
```

Load CRM first. Submit `{"collection":"public","title":"Discount policy","text":"The standard discount is 5%; discounts above 10% require manager approval."}` to `POST /api/v1/networks/crm/documents/text`. Poll `/api/v1/networks/crm/document-collections/public/jobs/{track_id}` until indexing completes. Query `/ask-routed` with route `structured`, `document`, `hybrid` or `auto`.

[Three synthetic policy documents](minibkn/evals/fixtures/documents/crm_public) are included. Sensitive collections require separate endpoints/workspaces; post-filtering a mixed shared graph is not an access boundary. The local map enables public only, not full sales/finance isolation.

## 9. MCP and Docker

Start the HTTP backend, then configure an MCP client to run `minibkn/.venv/Scripts/minibkn-mcp.exe` on Windows or `minibkn/.venv/bin/minibkn-mcp` on Unix using stdio. Set `MINIBKN_API_BASE_URL` and, if required, a user key as `MINIBKN_API_KEY`. Tools: `search_knowledge`, `ask_knowledge`, `request_action`. MCP does not bypass risk checks or human confirmation.

Optional Docker: run `docker compose up --build` inside `minibkn`. Container source paths are `/app/examples/...`, not host paths. Compose runs only the backend, not the UI or sidecar. The Docker dependency installation is not a complete uv-locked reproduction; publication validation uses uv.

## 10. Tests and evaluation

Offline commands (no paid calls):

```sh
# minibkn
uv run --no-sync python -m pytest -q
uv run --no-sync python -m ruff format --check src tests scripts
uv run --no-sync python -m ruff check src tests scripts
uv run --no-sync python -m mypy src/minibkn
uv run --no-sync python scripts/evaluate_offline.py
uv run --no-sync python scripts/evaluate_crm.py --embedding-provider token_hashing
# minibkn-ui
npm test
npm run build
```

For paid evaluations, consult each script's `--help` for explicit key/input/database/output parameters. Install optional metrics with `uv sync --frozen --extra dev --extra evaluation --no-editable` (Ragas 0.4.3). Start small; **do not batch-run all paid suites without estimating cost**. See the [evaluation reproduction guide](docs/EVALUATION.md).

Local publication acceptance (2026-10-11): **77 backend tests and 8 frontend tests passed**, checks/build passed, backend coverage 88.70%; additionally ran 200 offline retrieval questions, 130 frozen-plan executions and 30 risk simulations. Paid model/Ragas results were not rerun. See [verification](docs/PUBLICATION_REPORT.md). Three development-tool dependency findings remain; this is not production-readiness certification. See [security notes](SECURITY.md).

Historical results, not model benchmarks rerun during this publication task:

| Evaluation | Sample/result | Qualification |
| --- | --- | --- |
| CRM retrieval | 200 synthetic questions; BM25/BGE-M3/hybrid Hit@1 = .700/.515/.700 | Hybrid did not beat BM25 |
| QueryPlan | 60 holdout questions; 93.33% exact accuracy | Separate adversarial set: 5/6; not universal correctness |
| Ragas Faithfulness | Stratified 30-question mean: .9261 | Small sample, LLM judge |
| Answer-token comparison | 30 questions: input 844.07→280.40 (-66.78%); total -62.36% | Frozen correct plans; **excludes online planning cost** |
| Action risk | 30 cases (10 per decision), 100% | Policy simulation, not real payment/approval validation |
| LightRAG | Three policies indexed/retrieved, 3/3 | Integration smoke test, not large-scale accuracy |

A 10-question full-metric Ragas diagnostic retains negative results and failures. It is not a 200-question full-metric run. All business data is seeded **synthetic data**, not customer records or NUS research data. See [metric scope](docs/EVALUATION.md), [raw artifacts](minibkn/evals/results) and [historical evaluation report](minibkn/docs/reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md).

## 11. Repository and documentation

```text
README.md / README.zh.md     Bilingual public entry points
docs/                       Current release, evaluation and sidecar guides
minibkn/
  src/minibkn/              Domain / application / ports / adapters / API
  examples/                Small supply-chain and CRM demos
  config/                  Access and collection policy examples
  tests/                   Unit and API integration tests
  scripts/                 Demo loading, generation and evaluation
  evals/                   Frozen datasets, synthetic tables, historical results
  docs/                    Architecture, plans, development reports, deep dives, handoffs
minibkn-ui/                 React + TypeScript + Vite UI and tests
tools/check_release.py      Manifest integrity and common credential-pattern checks
PUBLICATION_MANIFEST.json   Public snapshot file hashes
```

Start with [documentation navigation](docs/README.md), the [full repository handoff](minibkn/docs/handoffs/MINIBKN_COMPLETE_REPOSITORY_HANDOFF_FOR_AI.md), and [technical deep dives](minibkn/docs/technical_deep_dive/README.md). Most detailed historical documents are Chinese. Archive documents reflect their stage, not necessarily current behavior; this README is the current entry point. See [publication verification](docs/PUBLICATION_REPORT.md).

## 12. Troubleshooting and safety

- Missing networks: seed/import/build first; demo.py does not populate the live server.
- Search after changing models: rebuild; do not mix embedding versions.
- Browser/CORS errors: confirm backend connectivity and match `MINIBKN_CORS_ORIGINS` to the frontend origin.
- 401/403: check API key, principal and resource grants; do not disable real access controls to work around failures.
- No document evidence: check sidecar reachability, collection mapping, key and job completion. Disabled-provider fallback is not retrieval success.
- Bind to loopback only. Default authentication is off, APIs accept server-local paths and the UI can store keys in localStorage. **Do not expose this setup directly to the Internet.** Read [SECURITY.md](SECURITY.md).

## 13. Attribution, licensing and contributions

Architecture/BKN concepts reference [openbkn-ai/bkn-foundry](https://github.com/openbkn-ai/bkn-foundry). LightRAG is an optional third-party dependency. This is not an official product, NUS research project or production SaaS.

Original [LICENSE](LICENSE), [NOTICE](NOTICE), [Apache text](LICENSE-APACHE.txt), [OpenBKN text](LICENSE-OPENBKN.txt) and per-file notices are preserved. **This is not uniformly MIT or Apache licensed.** Check each file's notice/origin; the OpenBKN text includes additional conditions. No unrestricted commercial-use claim is added. See [provenance](docs/PROVENANCE.md).

Contributions should include a use case, reproduction and test results; never submit secrets or real customer data. Future priorities include row/field authorization, unified planning/routing, richer document parsing and larger human-reviewed evaluation sets.
