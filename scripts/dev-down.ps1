# Stops what dev-up.ps1 started: Vite, Django, then the docker services (data is kept).
# Add -Purge to also delete the Postgres/Valkey volumes (platform back to empty).
param([switch]$Purge)
$Root = Split-Path -Parent $PSScriptRoot
$Dev = Join-Path $Root '.dev'
foreach ($name in 'web', 'api') {
  $f = Join-Path $Dev "$name.pid"
  if (Test-Path $f) {
    $id = [int](Get-Content $f)
    & taskkill /PID $id /T /F 2>$null | Out-Null
    Remove-Item $f
    Write-Host "$name stopped"
  }
}
$compose = @('compose', '--env-file', (Join-Path $Root '.env'), '-f', (Join-Path $Root 'docker\compose.yml'), '-f', (Join-Path $Root 'docker\compose.dev.yml'))
if ($Purge) { & docker @compose down -v } else { & docker @compose stop db redis mailpit }
