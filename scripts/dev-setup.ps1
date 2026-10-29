# One-time (idempotent) Windows dev setup: Python venv via uv + frontend deps via npm ci.
# The venv lives OUTSIDE the repo (OneDrive sync, spaces in paths): $env:ONEA_VENV,
# default $env:LOCALAPPDATA\oneaenv. Needs uv and Node.js on PATH. Run before scripts/dev-up.ps1.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Venv = if ($env:ONEA_VENV) { $env:ONEA_VENV } else { Join-Path $env:LOCALAPPDATA 'oneaenv' }
foreach ($tool in 'uv', 'npm') {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Write-Error "$tool not found on PATH"; exit 1 }
}
if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) {
  New-Item -ItemType Directory -Force (Split-Path -Parent $Venv) | Out-Null
  & uv venv $Venv
  if ($LASTEXITCODE) { throw 'uv venv failed' }
}
$env:UV_PROJECT_ENVIRONMENT = $Venv
Push-Location (Join-Path $Root 'backend')
try {
  & uv sync --frozen
  if ($LASTEXITCODE) { throw 'uv sync failed' }
} finally { Pop-Location }
Push-Location (Join-Path $Root 'frontend')
try {
  & npm ci
  if ($LASTEXITCODE) { throw 'npm ci failed' }
} finally { Pop-Location }
Write-Host "Setup done. venv: $Venv"
Write-Host "Persist it with:  setx ONEA_VENV `"$Venv`"   (new shells), then scripts/dev-up.ps1"
