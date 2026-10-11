# Evaluation scope and reproduction / 评测口径与复现

## Data

- CRM benchmark: seed 20260816, 500 customers + 2,500 orders + 6,000 line items + 120 products + 20 sales reps; 9,140 objects and 9,150 indexed documents; 200 questions (70 single-entity, 70 multi-hop, 60 filtering/aggregation); 30 action-policy cases.
- Enterprise fixtures: procurement, finance and HR, plus data-quality cases; 120 retrieval holdouts, 60 planner holdouts, 6 adversarial cases and 45 action cases. Earlier 15-case planner artifacts remain for history.
- Supply-chain baseline: earlier 200-question templated regression suite, not an independent real-world benchmark.
- LightRAG: three synthetic Chinese business-policy texts; real integration smoke and mocked API regression tests are different evidence.

All data is synthetic/seeded. This is not a standard external benchmark, human-audited production corpus or customer deployment.

## Reproduce without a key

Inside `minibkn`, after the README setup:

```sh
uv run --no-sync python -m pytest -q
uv run --no-sync python scripts/evaluate_offline.py
uv run --no-sync python scripts/evaluate_crm.py --embedding-provider token_hashing
```

Optional generators (`generate_crm_benchmark.py`, `generate_enterprise_test_suite.py`, `generate_query_planner_holdout.py`) rewrite synthetic fixtures; run them in a scratch copy if you want to keep the publication manifest unchanged. Evaluations also write local databases and new output artifacts, which must be reviewed before committing.

## Paid semantic / planning / Ragas evaluations

First inspect help and estimate cost. These calls send data to external providers; this publication task does not rerun them.

```sh
uv run --no-sync python scripts/evaluate_crm.py --embedding-provider siliconflow --embedding-key-file /path/to/private/embedding.txt
uv run --no-sync python scripts/evaluate_query_planner.py --help
uv sync --frozen --extra dev --extra evaluation --no-editable
uv run --no-sync python scripts/evaluate_ragas_comprehensive.py --help
uv run --no-sync python scripts/evaluate_rag_vs_bkn.py --help
uv run --no-sync python scripts/evaluate_performance.py --help
uv run --no-sync python scripts/evaluate_lightrag_integration.py --help
```

Retrieve `--input` and `--database` from the **new retrieval run** you generated. Historical published paths are de-identified and old databases are intentionally absent. Do not assume an old absolute path can run on your machine. `evaluate_ragas.py` is an older ID-metric helper expecting a per-case retrieval report, not the compact `latest.json` summary; prefer the comprehensive scripts.

## Evidence map

| Result | Path (relative to minibkn) | Meaning |
| --- | --- | --- |
| Compact historical dashboard | `evals/results/latest.json` | A snapshot summary; not a new run on each UI refresh |
| Semantic retrieval | `evals/results/comprehensive/retrieval/latest-siliconflow.json` | BM25/BGE-M3/hybrid ranks and full cases |
| Planner 60 cases | `evals/results/comprehensive/query_planner_holdout_60_v1.json` | Exact 93.33%; component 97.52%; planning token costs recorded |
| Adversarial | `evals/results/comprehensive/query_planner_adversarial_v2.json` | 5/6; missing field-level authorization remains a gap |
| Faithfulness 30 | `evals/results/comprehensive/ragas/bge_m3_faithfulness_30.json` | LLM-judged mean .9261 |
| Full metrics 10 | `evals/results/comprehensive/ragas/rag_vs_bkn_full_metrics_10.json` | Diagnostic; includes non-improvements |
| Token comparison 30 | `evals/results/comprehensive/token/rag_vs_bkn_token_30.json` | Frozen correct plans vs traditional RAG answering |
| Performance | `evals/results/comprehensive/performance/bge_m3_after_numpy.json` | Local process/concurrency measurement, not production SLA |
| LightRAG integration | `evals/results/lightrag/` | Small real-sidecar ingestion/retrieval run |

## Fair interpretation

- ID-based precision/recall is calculated against labeled document IDs. It is not the same as LLM-judged Context Precision/Recall.
- 200-question retrieval does not mean all Ragas metrics were run on all 200 questions. Faithfulness used 30; the broader diagnostic used 10.
- The RAG token baseline uses the same retrieval embeddings and answering model. The frozen-plan comparison isolates answering/context assembly. It **excludes online planner cost**, and is not full-system cost savings.
- Correct frozen plans remove planner errors. They do not establish natural-language end-to-end accuracy.
- Hybrid Hit@1 equals BM25 on this corpus. Report this negative result rather than claiming universal gains.
- Ten-case Faithfulness is not uniformly improved by MiniBKN; reference-answer formatting also affected Factual Correctness and prompted a separate rescore artifact.
- LLM judges are imperfect and stochastic. Small samples need human review, confidence intervals and larger held-out data before strong claims.
- Historical summary files can lag later specialist reports. Use the per-run artifacts and their report dates, not a single aggregate number stripped of its setup.

See [full evaluation report](../minibkn/docs/reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md) and [LightRAG report](../minibkn/docs/reports/MINIBKN_LIGHTRAG_INTEGRATION_AND_EVALUATION_REPORT.md) for detailed historical context.
