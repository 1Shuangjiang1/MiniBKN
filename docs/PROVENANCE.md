# Provenance and license inventory / 来源与许可证清单

MiniBKN is a local Python-first implementation inspired by BKN Foundry's Business Knowledge Network architecture. This snapshot exports the MiniBKN modules, not the complete Foundry services, deployment stack or upstream Git history. It retains the original module layout.

## Retained notices

- Root `LICENSE`, `NOTICE`, `LICENSE-APACHE.txt`, `LICENSE-OPENBKN.txt` are copied from the development checkout without rewriting terms.
- Twelve backend files already bear `Copyright openbkn.ai` / OpenBKN License headers. Those headers remain unchanged: application answer_generator/build_service/query_plan_service; ports/planner; adapters llm/query_planner and search/remote; domain base/build/evidence/modeling/policy/query.
- Other project files do not all have explicit individual license headers. This publication task does not invent authorship, relicense them as MIT, or claim universal commercial rights. The repository owner should confirm licensing for independently authored, unmarked files before granting downstream reuse rights.
- Foundry's root license overview describes the upstream multi-license model; it is retained for provenance, not a claim that every Foundry component is present in this export.
- Third-party runtime dependencies keep their own licenses. LightRAG is installed separately and is not vendored here.

## Publication transformations

The exporter excludes private learner profiles/interview coaching, local keys, virtual environments, logs, databases, caches and build outputs. Historical document/result paths are de-identified. Historical documents receive an archive banner. Public PowerShell helpers require explicit credential paths. Root bilingual instructions override old machine-specific instructions. No benchmark scores are fabricated or recalculated by this transformation.

## Scope of claims

The project is not an official OpenBKN distribution, NUS research result, commercial certification or production SaaS. Metrics use synthetic data and explicitly scoped samples. Model-assisted implementation is not evidence of academic affiliation or enterprise deployment.
