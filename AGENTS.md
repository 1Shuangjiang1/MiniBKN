# MiniBKN contributor entry point

Read root README.md / README.zh.md, SECURITY.md and docs/PROVENANCE.md before making changes.
The current system is 0.6.0, a local portfolio implementation, not upstream Foundry.

- Work independently unless the user explicitly requests delegation.
- Preserve license/copyright notices and existing unrelated edits. Do not invent blanket MIT licensing.
- No credentials or real customer/employee data; `.env` and runtime data are excluded.
- Treat detailed minibkn/docs reports as historical evidence; verify current source and scoped evaluation artifacts.
- Maintain DEVELOPMENT_STATUS.md for substantive changes, recording current state, exact next action and verification.
- Add regression coverage for bugs. Run offline pytest, Ruff/mypy and UI tests/build before handoff.
- Do not run paid evaluations without explicit authorization and cost awareness.
- Do not commit/push/create repositories/PRs or make production/security/toolchain-major changes without user authorization.
- Update public instructions when behavior changes. Refresh PUBLICATION_MANIFEST.json hashes after reviewed edits; never disable integrity checks to hide changes.
