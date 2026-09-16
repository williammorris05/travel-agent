$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectDir '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install backend/requirements.lock first. See README.md.' }
& $pythonPath -m uvicorn travel_agent.main:app --app-dir (Join-Path $projectDir 'backend\src') --host 127.0.0.1 --port 8000 --reload --reload-dir (Join-Path $projectDir 'backend\src')
exit $LASTEXITCODE
