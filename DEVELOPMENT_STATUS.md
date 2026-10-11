# Public snapshot continuity

Snapshot: MiniBKN 0.6.0, 2026-10-11. Status: prepared locally; publication verification is documented in docs/PUBLICATION_REPORT.md.

## Resume here

Read README.md / README.zh.md for current scope and commands, SECURITY.md for known limits and dependency warnings, docs/PROVENANCE.md for license caveats. Use the detailed module handoff linked in docs/README.md. Do not infer production readiness from historical metrics.

## Architecture and scope

FastAPI/SQLite modular monolith + independent React UI + optional REST LightRAG sidecar. Default offline hashing/extractive mode. QueryPlan and knowledge routing are separate entry points. Resource/collection RBAC is implemented; row/field security is not. Local allowlisted tools are not real payments/orders.

## Recent publication fixes

Public helpers use explicit credential paths. Optional paid evaluation imports no longer prevent offline test collection. Optional sentence-transformers import is isolated from baseline mypy. Added guarded HTTP demo loader with regression coverage. Public docs/results are de-identified; private learner-profile/coaching documents are excluded. Compatible source-map-js patch applied; full dev audit still has three findings requiring reviewed cross-major test-tool upgrade.

## Verification and next steps

See docs/PUBLICATION_REPORT.md for exact commands/results. No credentials or runtime databases are included. GitHub CI requires no API secrets; its result must be verified separately after actual push.

Prioritize reviewed toolchain security fixes, then row/field authorization, unified planning/routing, richer document ingestion and larger human-reviewed evaluations. Update this file before substantive implementation, after each meaningful edit/test and before interruption.
