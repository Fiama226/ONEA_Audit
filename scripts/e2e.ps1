# Tests e2e (Playwright) sur une base PostgreSQL jetable : jamais la base "onea" de dev.
# Usage : pwsh scripts/e2e.ps1 [arguments Playwright]      (ex. scripts/e2e.ps1 e2e/login.spec.ts)
# Équivalent de scripts/e2e.sh (voir son en-tête) : crée onea_e2e_<horodatage>, migre, lance
# l'API (127.0.0.1:8010) et Vite (5174), exécute Playwright, puis supprime serveurs, base et
# dossier temporaire. Compare les comptes de la base onea avant/après.
# Les comptes de test sont créés par `manage.py creer_comptes_e2e` (mot de passe E2E_PASSWORD).
# Variables : E2E_DB_NAME (doit valoir ^onea_e2e_[0-9]+$, sinon code 2 avant toute écriture),
# E2E_API_PORT, E2E_WEB_PORT, PYTHON, ONEA_VENV. Codes : 2 nom refusé ; 3 pile de dev absente ;
# 4 comptes de la base onea modifiés.
param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$PlaywrightArgs)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$Stamp = [int][double]::Parse((Get-Date -UFormat %s))
$DbName = if ($env:E2E_DB_NAME) { $env:E2E_DB_NAME } else { "onea_e2e_$Stamp" }
$ApiPort = if ($env:E2E_API_PORT) { $env:E2E_API_PORT } else { 8010 }
$WebPort = if ($env:E2E_WEB_PORT) { $env:E2E_WEB_PORT } else { 5174 }

# 1. Garde : avant toute commande qui écrit.
if ($DbName -notmatch '^onea_e2e_[0-9]+$') {
  [Console]::Error.WriteLine("Refus : le nom de base '$DbName' ne correspond pas à ^onea_e2e_[0-9]+`$ (aucune écriture faite).")
  exit 2
}

# .env -> variables locales (sans écraser l'environnement déjà défini).
$EnvFile = Join-Path $Root '.env'
$Dot = @{}
if (Test-Path $EnvFile) {
  foreach ($line in Get-Content $EnvFile) {
    if ($line -match '^\s*([A-Z0-9_]+)=(.*)$') { $Dot[$Matches[1]] = $Matches[2].Trim() }
  }
}
function Cfg($name, $default) {
  $v = [Environment]::GetEnvironmentVariable($name)
  if ($v) { return $v }
  if ($Dot.ContainsKey($name)) { return $Dot[$name] }
  return $default
}
$PgUser = Cfg 'POSTGRES_USER' 'onea'
$PgPass = Cfg 'POSTGRES_PASSWORD' ''
if (-not $PgPass) { throw 'POSTGRES_PASSWORD manquant (voir .env.example)' }
$DevDb = Cfg 'POSTGRES_DB' 'onea'
$DbPort = Cfg 'DB_PORT' '5432'
$RedisPort = Cfg 'REDIS_PORT' '6379'
$Compose = @('compose', '--env-file', $EnvFile, '-f', (Join-Path $Root 'docker\compose.yml'), '-f', (Join-Path $Root 'docker\compose.dev.yml'))

# 2. La pile de dev doit tourner.
$running = & docker @Compose ps --status running --services 2>$null
foreach ($service in 'db') {
  if ($running -notcontains $service) {
    [Console]::Error.WriteLine("Pile de dev absente : le service '$service' ne tourne pas (make up).")
    exit 3
  }
}

$Py = $env:PYTHON
if (-not $Py) {
  $cands = @()
  if ($env:ONEA_VENV) { $cands += Join-Path $env:ONEA_VENV 'Scripts\python.exe' }
  $cands += Join-Path $Root 'backend\.venv\Scripts\python.exe'
  $Py = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $Py) { $Py = 'python' }
}

function Invoke-DevPsql($sql) {
  $out = & docker @Compose exec -T db psql -v ON_ERROR_STOP=1 -At -U $PgUser -d $DevDb -c $sql
  if ($LASTEXITCODE) { throw "psql a échoué : $sql" }
  return ($out | Out-String).Trim()
}
function Get-Counts {
  'missions_mission={0} referentiel_cartographieversion={1}' -f `
    (Invoke-DevPsql 'SELECT count(*) FROM missions_mission'),
    (Invoke-DevPsql 'SELECT count(*) FROM referentiel_cartographieversion')
}
function Wait-Http($url, $seconds) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 $url).StatusCode -lt 400) { return } } catch { Start-Sleep 2 }
  }
  throw "Délai dépassé : $url"
}

$Tmp = Join-Path ([IO.Path]::GetTempPath()) "onea-e2e-$Stamp"
$Created = $false
$Procs = @()
$Status = 1
try {
  New-Item -ItemType Directory -Force (Join-Path $Tmp 'documents'), (Join-Path $Tmp 'fichiers') | Out-Null

  # Orpheline du lot 3 T10 : supprimée si elle existe (aucun autre nom n'est touché).
  & docker @Compose exec -T db dropdb --if-exists --force -U $PgUser onea_e2e3 *> $null

  $Before = Get-Counts
  Write-Host "Base $DevDb avant : $Before"
  & docker @Compose exec -T db createdb -U $PgUser $DbName
  if ($LASTEXITCODE) { $Status = 3; throw "createdb a échoué" }
  $Created = $true
  Write-Host "Base jetable : $DbName"

  $env:DJANGO_SETTINGS_MODULE = 'config.settings.dev'
  $env:DATABASE_URL = "postgres://${PgUser}:${PgPass}@localhost:${DbPort}/${DbName}"
  $env:DOCUMENTS_ROOT = Join-Path $Tmp 'documents'
  $env:FICHIERS_RACINE = Join-Path $Tmp 'fichiers'
  $env:MEILI_URL = 'http://127.0.0.1:9'
  $env:REDIS_URL = "redis://localhost:$RedisPort/14"

  Push-Location (Join-Path $Root 'backend')
  & $Py manage.py migrate --noinput
  $migrated = $LASTEXITCODE
  Pop-Location
  if ($migrated) { throw 'migrate a échoué' }

  # Limites de débit relevées : la suite se connecte des dizaines de fois par minute depuis la même
  # IP (seaux de l'authentification, backend/apps/users/auth_throttles.py). E2e jetable uniquement.
  $env:THROTTLE_RATE_CONNEXION = '10000/min'
  $env:THROTTLE_RATE_CONNEXION_CODE = '10000/min'
  $env:THROTTLE_RATE_MOT_DE_PASSE_OUBLIE_IP = '10000/min'
  $env:THROTTLE_RATE_REINITIALISATION = '10000/min'
  $env:THROTTLE_RATE_ECHECS_CONNEXION = '10000/min'
  $env:THROTTLE_RATE_ECHECS_REINITIALISATION = '10000/min'
  $env:THROTTLE_RATE_CHANGEMENT_MOT_DE_PASSE = '10000/min'
  $env:THROTTLE_RATE_MOT_DE_PASSE_OUBLIE = '10000/hour'

  # Comptes de test avec un mot de passe connu (e2e uniquement : la commande refuse tout hors
  # DEBUG et hors base onea_e2e_<nombre>). Les specs se connectent par le vrai formulaire.
  if (-not $env:E2E_PASSWORD) { $env:E2E_PASSWORD = 'Onea-e2e-2026-pwd' }
  Push-Location (Join-Path $Root 'backend')
  & $Py manage.py creer_comptes_e2e
  $seeded = $LASTEXITCODE
  Pop-Location
  if ($seeded) { throw 'creer_comptes_e2e a échoué' }

  $Procs += Start-Process -FilePath $Py -ArgumentList @('manage.py', 'runserver', "127.0.0.1:$ApiPort", '--noreload') `
    -WorkingDirectory (Join-Path $Root 'backend') -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $Tmp 'api.log') -RedirectStandardError (Join-Path $Tmp 'api.err.log')
  Wait-Http "http://127.0.0.1:$ApiPort/api/v1/health/" 90

  # Même origine : le navigateur parle à Vite, qui relaie /api vers Django (ONEA_API_URL).
  $env:VITE_API_URL = "http://localhost:$WebPort"
  $env:ONEA_API_URL = "http://127.0.0.1:$ApiPort"
  $Procs += Start-Process -FilePath 'node' `
    -ArgumentList @('node_modules\vite\bin\vite.js', '--host', 'localhost', '--port', $WebPort, '--strictPort') `
    -WorkingDirectory (Join-Path $Root 'frontend') -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $Tmp 'web.log') -RedirectStandardError (Join-Path $Tmp 'web.err.log')
  Wait-Http "http://localhost:$WebPort/" 90

  $env:E2E_API_URL = "http://localhost:$ApiPort"
  $env:E2E_RUN_ID = "$Stamp"
  $env:E2E_WEB_EXTERNAL = '1'
  $env:WEB_PORT = "$WebPort"
  Push-Location (Join-Path $Root 'frontend')
  & npx playwright test @PlaywrightArgs
  $Status = $LASTEXITCODE
  Pop-Location

  $After = Get-Counts
  Write-Host "Base $DevDb après : $After"
  if ($Before -ne $After) {
    [Console]::Error.WriteLine("ERREUR : les comptes de la base $DevDb ont changé (avant : $Before ; après : $After).")
    if ($Status -eq 0) { $Status = 4 }
  }
}
catch {
  [Console]::Error.WriteLine($_.Exception.Message)
  if ($Status -eq 0) { $Status = 1 }
}
finally {
  foreach ($p in $Procs) { if ($p -and -not $p.HasExited) { & taskkill /PID $p.Id /T /F 2>$null | Out-Null } }
  if ($Created -and $DbName -match '^onea_e2e_[0-9]+$') {
    & docker @Compose exec -T db dropdb --if-exists --force -U $PgUser $DbName 2>$null
    if ($LASTEXITCODE) { [Console]::Error.WriteLine("Échec de suppression de la base $DbName : à supprimer à la main.") }
  }
  Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
exit $Status
