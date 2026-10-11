# LightRAG sidecar setup / 可选文档分支

Keep LightRAG in a separate Python 3.12 environment. Historical testing used lightrag-hku 1.5.6; this integration is a REST adapter, not vendored LightRAG source. External credentials and provider availability are required. These commands are optional and potentially paid.

## Windows

From `minibkn`:

```powershell
uv venv .lightrag-venv --python 3.12
uv pip install --python .lightrag-venv/Scripts/python.exe "lightrag-hku[api]==1.5.6"
./scripts/start_lightrag.ps1 -DeepSeekKeyFile /path/to/private/deepseek.txt -SiliconFlowKeyFile /path/to/private/embedding.txt -SidecarApiKey YOUR_LOCAL_SIDECAR_KEY
```

The script requires explicit key files, binds loopback and defaults to port 9621 / workspace crm_public. Its built-in default sidecar key is a public example, not a secret. Pass your own key and put the same value in a private file for MiniBKN.

## Linux/macOS

```sh
uv venv .lightrag-venv --python 3.12
uv pip install --python .lightrag-venv/bin/python "lightrag-hku[api]==1.5.6"
export LLM_BINDING=openai
export LLM_MODEL=deepseek-chat
export LLM_BINDING_HOST=https://api.deepseek.com/v1
export EMBEDDING_BINDING=openai
export EMBEDDING_MODEL=BAAI/bge-m3
export EMBEDDING_DIM=1024
export EMBEDDING_BINDING_HOST=https://api.siliconflow.cn/v1
export SUMMARY_LANGUAGE=Chinese
# Inject LLM_BINDING_API_KEY, EMBEDDING_BINDING_API_KEY and LIGHTRAG_API_KEY
# via your private environment/secret manager, not this repository.
.lightrag-venv/bin/lightrag-server --host 127.0.0.1 --port 9621 --working-dir ./data/lightrag/crm-public --input-dir ./data/lightrag/crm-public-inputs --workspace crm_public
```

## Connect, index and query

Set `MINIBKN_DOCUMENT_KNOWLEDGE_PROVIDER=lightrag`, `MINIBKN_LIGHTRAG_ENDPOINT_MAP_FILE=./evals/config/lightrag-local.json` and `MINIBKN_LIGHTRAG_API_KEY_FILE` to your private sidecar key file, then restart MiniBKN. Seed the small CRM example first.

`POST /api/v1/networks/crm/documents/text` accepts collection/title/text. It returns an asynchronous job reference. Poll `/api/v1/networks/crm/document-collections/public/jobs/{track_id}`. Only after completion query `/ask-routed` with route `document` or `hybrid`.

The real integration script uses the frozen benchmark network; it sets up its own test app/data. Consult `scripts/evaluate_lightrag_integration.py --help` for its endpoint map and key parameters instead of assuming the small CRM example and benchmark share IDs.

Example source texts are under `evals/fixtures/documents/crm_public/`. They are synthetic, not real internal policies. The script's 3/3 historical result is a smoke test.

For confidential collections, isolate endpoint/workspace per security domain and map them in `config/lightrag-endpoints.example.json`. The public-only map is intentionally limited. MiniBKN's collection checks cannot protect an external shared graph whose contents were already mixed. No PDF/Word upload/OCR feature is implied by this text-ingestion interface.
