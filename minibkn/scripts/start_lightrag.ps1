param(
    [int]$Port = 9621,
    [string]$Workspace = "crm_public",
    [string]$WorkingDirectory = ".\data\lightrag\crm-public",
    [string]$InputDirectory = ".\data\lightrag\crm-public-inputs",
    [Parameter(Mandatory = $true)][string]$DeepSeekKeyFile,
    [Parameter(Mandatory = $true)][string]$SiliconFlowKeyFile,
    [string]$SidecarApiKey = "minibkn-lightrag-local"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$server = Join-Path $projectRoot ".lightrag-venv\Scripts\lightrag-server.exe"
if (-not (Test-Path -LiteralPath $server)) {
    throw "LightRAG environment is missing. Run: uv venv .lightrag-venv --python 3.12; uv pip install --python .lightrag-venv\Scripts\python.exe 'lightrag-hku[api]'"
}

$resolvedWorking = [IO.Path]::GetFullPath((Join-Path $projectRoot $WorkingDirectory))
$resolvedInput = [IO.Path]::GetFullPath((Join-Path $projectRoot $InputDirectory))
New-Item -ItemType Directory -Force -Path $resolvedWorking, $resolvedInput | Out-Null

$env:LLM_BINDING = "openai"
$env:LLM_MODEL = "deepseek-chat"
$env:LLM_BINDING_HOST = "https://api.deepseek.com/v1"
$env:LLM_BINDING_API_KEY = (Get-Content -LiteralPath $DeepSeekKeyFile -Raw).Trim()
$env:EMBEDDING_BINDING = "openai"
$env:EMBEDDING_MODEL = "BAAI/bge-m3"
$env:EMBEDDING_DIM = "1024"
$env:EMBEDDING_BINDING_HOST = "https://api.siliconflow.cn/v1"
$env:EMBEDDING_BINDING_API_KEY = (Get-Content -LiteralPath $SiliconFlowKeyFile -Raw -Encoding UTF8).Trim()
$env:LIGHTRAG_API_KEY = $SidecarApiKey
$env:SUMMARY_LANGUAGE = "Chinese"

& $server --host 127.0.0.1 --port $Port --working-dir $resolvedWorking --input-dir $resolvedInput --workspace $Workspace --log-level INFO
