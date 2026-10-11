$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "未找到 .venv，请先按照 README 执行 uv sync。"
}

& ".venv\Scripts\python.exe" "scripts\demo.py"
