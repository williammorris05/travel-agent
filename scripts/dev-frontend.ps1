param([string]$Pnpm = 'pnpm')
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $projectDir 'frontend')
try {
    & $Pnpm dev
    $resultCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $resultCode
