# Security boundaries / 安全边界

This repository is a local learning/demo system, not a production security product.
本项目是本地学习与演示系统，不能作为生产安全产品直接部署。

## Dependency audit checkpoint (2026-10-11)

`npm audit --omit=dev` reported zero findings. The full audit still reports **three development-tool findings (one moderate, two critical)** affecting Vitest/@vitest/mocker/tinypool. A compatible source-map-js patch was applied. Npm proposes a cross-major Vitest upgrade for the remaining findings; that change is not silently applied. Restrict tests/dev tooling to trusted local inputs and do not expose test/mock servers. Zero production-dependency findings do not mean the project is vulnerability-free. Before broader use, obtain approval for the toolchain upgrade and rerun tests/build/audit.

- Authentication is off by default. Bind to 127.0.0.1; do not expose unauthenticated services.
- Demo API keys and the default sidecar key are public examples; replace them.
- Policy hashes do not make weak API keys secure. Use high-entropy keys, TLS and controlled rotation.
- RBAC is resource/collection scoped, not row/field/tenant isolation. Never load sensitive salary/customer data expecting those controls.
- APIs accept backend-local paths. A production deployment needs path sandboxing, ingress restrictions and a proper identity system.
- Each sensitive LightRAG collection needs its own endpoint/workspace. Shared graph post-filtering is insufficient.
- AI-generated plans are constrained; model suggestions never authorize actions. Register tools explicitly and apply deterministic risk checks.
- The UI saves connection keys in localStorage. Do not use it on shared computers or an untrusted origin.
- LLM/embedding calls disclose submitted data to the chosen provider and may cost money.
- Snapshot rollback/idempotency are not a production transaction/approval platform.
- `tools/check_release.py` checks common secret formats and manifest integrity; it cannot prove that all possible private information is absent. Review new datasets and diffs before publishing.

If a credential was ever committed, revoke/rotate it first. Removing the current file does not remove Git history. This snapshot deliberately excludes the original repository's history.

如果发现漏洞，使用目标 GitHub 仓库启用的 Private vulnerability reporting 联系维护者；若未启用，请先请求私下联系渠道。不要在公开 Issue 中发布密钥、私人数据或利用细节。现有项目没有承诺安全响应 SLA。
