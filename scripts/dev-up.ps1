# Starts the ONEA dev stack on Windows: Postgres + Valkey + Mailpit (docker), Django, Vite.
# Needs a repo-root .env (copy .env.example), frontend/.env and $env:ONEA_VENV or backend\.venv (create it with scripts/dev-setup.ps1).
# Logs and pids go to .dev/ (git-ignored). Idempotent: already-listening ports are skipped.
# Ports: API_PORT (8000), WEB_PORT (5173); DB/Redis/Mailpit ports come from .env.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Dev = Join-Path $Root '.dev'
New-Item -ItemType Directory -Force $Dev | Out-Null
$ApiPort = if ($env:API_PORT) { $env:API_PORT } else { 8000 }
$WebPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { 5173 }
$Candidates = @()
if ($env:ONEA_VENV) { $Candidates += Join-Path $env:ONEA_VENV 'Scripts\python.exe' }
$Candidates += Join-Path $Root 'backend\.venv\Scripts\python.exe'
$Py = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Py) {
  Write-Error "No Python venv found (looked in: $($Candidates -join ', ')). Run scripts/dev-setup.ps1 first."
  exit 1
}
if (-not (Test-Path (Join-Path $Root '.env'))) { Write-Error '.env missing: cp .env.example .env'; exit 1 }

function Test-Port($port) {
  $c = New-Object Net.Sockets.TcpClient
  try { $c.Connect('127.0.0.1', $port); return $true } catch { return $false } finally { $c.Dispose() }
}
function Wait-Http($url, $seconds) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 $url).StatusCode -lt 400) { return } } catch { Start-Sleep 2 }
  }
  throw "timeout waiting for $url"
}
function Start-Detached($name, $file, $argList, $workdir, $port) {
  if (Test-Port $port) { Write-Host "$name already listening on $port"; return }
  $p = Start-Process -FilePath $file -ArgumentList $argList -WorkingDirectory $workdir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $Dev "$name.log") -RedirectStandardError (Join-Path $Dev "$name.err.log") -PassThru
  Set-Content (Join-Path $Dev "$name.pid") $p.Id
  Write-Host "$name started (pid $($p.Id))"
}

$compose = @('compose', '--env-file', (Join-Path $Root '.env'), '-f', (Join-Path $Root 'docker\compose.yml'), '-f', (Join-Path $Root 'docker\compose.dev.yml'))
& docker @compose up -d db redis mailpit
if ($LASTEXITCODE) { throw 'docker compose up failed' }

$env:DJANGO_SETTINGS_MODULE = 'config.settings.dev'
Push-Location (Join-Path $Root 'backend')
& $Py manage.py migrate --noinput
if ($LASTEXITCODE) { throw 'migrate failed' }
Pop-Location
Start-Detached 'api' $Py @('manage.py', 'runserver', "127.0.0.1:$ApiPort") (Join-Path $Root 'backend') $ApiPort
Wait-Http "http://127.0.0.1:$ApiPort/api/v1/health/" 60

$Front = Join-Path $Root 'frontend'
# One origin: the browser only talks to Vite, which proxies /api to Django.
$env:VITE_API_URL = "http://localhost:$WebPort"
$env:ONEA_API_URL = "http://127.0.0.1:$ApiPort"
Start-Detached 'web' 'node' @('node_modules\vite\bin\vite.js', '--host', 'localhost', '--port', $WebPort) $Front $WebPort
Wait-Http "http://localhost:$WebPort/" 60
Write-Host "Frontend  http://localhost:$WebPort"
Write-Host "API       http://127.0.0.1:$ApiPort/api/v1/health/"
Write-Host "Mailpit   http://127.0.0.1:8025"
