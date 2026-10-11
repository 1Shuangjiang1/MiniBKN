# MiniBKN backend

The current, portable usage instructions are at the repository root:

- [English README](../README.md)
- [中文 README](../README.zh.md)
- [Documentation](../docs/README.md)

Python 3.11/3.12. From this directory:

```sh
uv sync --frozen --python 3.11 --extra dev --no-editable
uv run --no-sync python -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
```

Offline standalone demo: `uv run --no-sync python scripts/demo.py`.
Load an example into a separately running server: `uv run --no-sync python scripts/seed_demo.py --example supply_chain`.

Historical module documents are under `docs/`; they preserve stage-specific designs and results, not current launch instructions. The top-level README records current capabilities and limitations.
