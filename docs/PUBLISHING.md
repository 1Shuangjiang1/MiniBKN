# Uploading this snapshot / 上传此版本

Upload the contents of **the generated `MiniBKN` directory**, not the original Foundry workspace and not both directories together. The zip has one MiniBKN top-level folder. No old `.git` history is included. Do not rename/remove original notices.

本次整理不会修改原仓库 origin，也不会推送到 openbkn-ai/bkn-foundry。新建你自己账号下的空仓库，选择公开/私有；README 中没有猜测你的用户名或仓库地址。以下命令的 URL 必须由你替换。

## Review first

1. Review both READMEs, SECURITY and PROVENANCE; confirm ownership/licensing of unmarked independent files.
2. Run `python tools/check_release.py` and inspect newly added files yourself; pattern scanning is not a complete secret audit.
3. Never copy `.env`, secrets, `.venv`, `.lightrag-venv`, node_modules or real data into the public commit.
4. Create an **empty repository** on your GitHub account (no automatically generated README/license). Do not use the Foundry URL.

## New local repository

Inside the released MiniBKN folder, after review:

```sh
git init -b main
git add .
git status --short
git diff --cached --stat
git diff --cached --check
# Inspect the staged content, then:
git commit -m "feat: publish MiniBKN 0.6.0 portfolio snapshot"
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

Requires your own GitHub authentication. If the remote already contains files, stop and inspect it; do not force-push. A web upload is possible for small selections but Git preserves the complete layout reliably.

## After upload

Confirm root README, source/tests/examples, public synthetic results and Actions checks are visible. Local checks do not mean cloud CI has run. Add a short repository description and topics such as `python`, `fastapi`, `rag`, `knowledge-graph`, `lightrag`, `mcp` if desired. The Actions file tests offline only and does not need provider secrets. Public release does not deploy a live application.

## Future changes

`PUBLICATION_MANIFEST.json` is a reproducible snapshot inventory. After legitimate content edits, regenerate its file hashes before running the publication check; do not silently disable the check. Avoid adding runtime assets to the inventory. The export tool maintained in the original development workspace can create a fresh, non-overwriting snapshot.
