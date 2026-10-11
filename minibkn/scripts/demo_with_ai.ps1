param(
    [Parameter(Mandatory = $true)][string]$DeepSeekKeyFile,
    [Parameter(Mandatory = $true)][string]$SiliconFlowKeyFile
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $DeepSeekKeyFile)) {
    throw "DeepSeek key file does not exist: $DeepSeekKeyFile"
}
if (-not (Test-Path -LiteralPath $SiliconFlowKeyFile)) {
    throw "SiliconFlow key file does not exist: $SiliconFlowKeyFile"
}

$env:MINIBKN_LLM_PROVIDER = "openai_compatible"
$env:MINIBKN_LLM_API_KEY_FILE = $DeepSeekKeyFile
$env:MINIBKN_LLM_BASE_URL = "https://api.deepseek.com/v1"
$env:MINIBKN_LLM_MODEL = "deepseek-chat"
$env:MINIBKN_EMBEDDING_PROVIDER = "siliconflow"
$env:MINIBKN_EMBEDDING_API_KEY_FILE = $SiliconFlowKeyFile
$env:MINIBKN_EMBEDDING_API_BASE = "https://api.siliconflow.cn/v1"
$env:MINIBKN_EMBEDDING_MODEL = "BAAI/bge-m3"
$env:MINIBKN_EMBEDDING_DIMENSIONS = "1024"

try {
    & .venv\Scripts\python.exe -m uvicorn minibkn.main:app --host 127.0.0.1 --port 8000
}
finally {
    Remove-Item Env:MINIBKN_LLM_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:MINIBKN_LLM_API_KEY_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:MINIBKN_LLM_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:MINIBKN_LLM_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:MINIBKN_EMBEDDING_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:MINIBKN_EMBEDDING_API_KEY_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:MINIBKN_EMBEDDING_API_BASE -ErrorAction SilentlyContinue
    Remove-Item Env:MINIBKN_EMBEDDING_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:MINIBKN_EMBEDDING_DIMENSIONS -ErrorAction SilentlyContinue
}
