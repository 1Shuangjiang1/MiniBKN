# MiniBKN Evaluation Assets

## Multi-domain holdout suite

Run `python scripts/generate_enterprise_test_suite.py` to deterministically rebuild the
procurement, finance, HR, and data-quality fixtures under `evals/enterprise/`. Frozen
retrieval, QueryPlan, adversarial, and action cases are stored in `evals/datasets/` with
the `enterprise_` prefix. The generator seed and case counts are recorded in
`evals/enterprise/manifest.json`.

## Frozen CRM benchmark

- Seed: `20260816`
- Data: 500 customers, 2,500 orders, 6,000 order items, 120 products, 20 sales reps
- Questions: 200 (`70 single_entity + 70 multi_hop + 60 filter_aggregate`)
- Action safety cases: 30 (`10 allow + 10 confirm + 10 deny`)

Regenerate the exact same synthetic business data and labels:

```powershell
.venv\Scripts\python.exe scripts\generate_crm_benchmark.py
```

Run the end-to-end benchmark, full ID metrics, stratified Faithfulness, and the compact UI report:

```powershell
.venv\Scripts\python.exe scripts\evaluate_crm.py
uv sync --extra dev --extra evaluation --no-editable --reinstall-package minibkn
.venv\Scripts\python.exe scripts\evaluate_ragas_comprehensive.py --help
.venv\Scripts\python.exe scripts\compile_evaluation_summary.py --help
```

`results/latest.json` is the machine-readable report exposed by
`GET /api/v1/evaluations/latest`. It is a compact UI-facing summary; detailed per-case artifacts
remain under `results/comprehensive/`. The completed 30-case DeepSeek/Ragas Faithfulness run is
stored at `results/comprehensive/ragas/bge_m3_faithfulness_30.json`. Do not treat token-hashing as
a semantic Embedding model, and never store provider keys in this directory.
