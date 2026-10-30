#!/usr/bin/env bash
# Tests e2e (Playwright) sur une base PostgreSQL jetable : jamais la base "onea" de dev.
# Usage : scripts/e2e.sh [arguments Playwright]      (ex. scripts/e2e.sh e2e/login.spec.ts)
#
# Exige la pile de dev (services db et keycloak du compose). Crée onea_e2e_<horodatage>, la
# migre, lance l'API sur 127.0.0.1:8010 (documents dans un dossier temporaire) et Vite sur 5174,
# exécute Playwright, puis (trap) arrête les serveurs, supprime la base et le dossier temporaire.
# La pile de dev (8000/5173, base onea) continue de tourner. Compare les comptes de
# missions_mission et referentiel_cartographieversion de la base onea avant/après.
#
# Variables : E2E_DB_NAME (doit valoir ^onea_e2e_[0-9]+$, sinon code 2 avant toute écriture),
# E2E_API_PORT (8010), E2E_WEB_PORT (5174), PYTHON (interpréteur), ONEA_VENV, DB_PORT, REDIS_PORT.
# Codes : 2 nom de base refusé ; 3 pile de dev absente ; 4 comptes de la base onea modifiés.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
STAMP="$(date +%s)"
DB_NAME="${E2E_DB_NAME:-onea_e2e_${STAMP}}"
API_PORT="${E2E_API_PORT:-8010}"
WEB_PORT="${E2E_WEB_PORT:-5174}"

# 1. Garde : avant toute commande qui écrit (création de base, dossiers, processus).
if ! printf '%s' "$DB_NAME" | grep -Eq '^onea_e2e_[0-9]+$'; then
  echo "Refus : le nom de base '$DB_NAME' ne correspond pas à ^onea_e2e_[0-9]+\$ (aucune écriture faite)." >&2
  exit 2
fi

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi
PGUSER_="${POSTGRES_USER:-onea}"
PGPASS_="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD manquant (voir .env.example)}"
DEV_DB="${POSTGRES_DB:-onea}"
DB_HOST_PORT="${DB_PORT:-5432}"
REDIS_HOST_PORT="${REDIS_PORT:-6379}"
KC_PORT="${KEYCLOAK_PORT:-8080}"

compose() {
  docker compose --env-file "$ROOT/.env" -f "$ROOT/docker/compose.yml" -f "$ROOT/docker/compose.dev.yml" "$@"
}

# 2. La pile de dev doit tourner.
running="$(compose ps --status running --services 2>/dev/null)"
for service in db keycloak; do
  if ! printf '%s\n' "$running" | grep -qx "$service"; then
    echo "Pile de dev absente : le service '$service' ne tourne pas (make up)." >&2
    exit 3
  fi
done

# Interpréteur Python.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for candidate in \
    "${ONEA_VENV:-/nonexistent}/Scripts/python.exe" "${ONEA_VENV:-/nonexistent}/bin/python" \
    "$ROOT/backend/.venv/Scripts/python.exe" "$ROOT/backend/.venv/bin/python"; do
    if [ -x "$candidate" ]; then PY="$candidate"; break; fi
  done
fi
PY="${PY:-python}"

psql_dev() { compose exec -T db psql -v ON_ERROR_STOP=1 -At -U "$PGUSER_" -d "$DEV_DB" -c "$1"; }

counts() {
  printf 'missions_mission=%s referentiel_cartographieversion=%s' \
    "$(psql_dev 'SELECT count(*) FROM missions_mission' | tr -d '\r')" \
    "$(psql_dev 'SELECT count(*) FROM referentiel_cartographieversion' | tr -d '\r')"
}

TMP="$(mktemp -d)"
CREATED=0
API_PID=""
WEB_PID=""
STATUS=1

cleanup() {
  trap - EXIT INT TERM
  for pid in "$WEB_PID" "$API_PID"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null
  done
  # Windows (Git Bash) : l'arbre de processus survit au kill simple.
  for pid in "$WEB_PID" "$API_PID"; do
    [ -n "$pid" ] && command -v taskkill >/dev/null 2>&1 && taskkill //PID "$pid" //T //F >/dev/null 2>&1
  done
  if [ "$CREATED" = 1 ] && printf '%s' "$DB_NAME" | grep -Eq '^onea_e2e_[0-9]+$'; then
    compose exec -T db dropdb --if-exists --force -U "$PGUSER_" "$DB_NAME" >/dev/null 2>&1 \
      || echo "Échec de suppression de la base $DB_NAME : à supprimer à la main." >&2
  fi
  rm -rf "$TMP"
  exit "$STATUS"
}
trap cleanup EXIT INT TERM

wait_http() { # url secondes
  end=$((SECONDS + $2))
  until curl -fsS -o /dev/null "$1" 2>/dev/null; do
    if [ "$SECONDS" -ge "$end" ]; then echo "Délai dépassé : $1" >&2; return 1; fi
    sleep 2
  done
}

# Orpheline du lot 3 T10 : supprimée si elle existe (aucun autre nom n'est touché).
compose exec -T db dropdb --if-exists --force -U "$PGUSER_" onea_e2e3 >/dev/null 2>&1 || true

BEFORE="$(counts)" || { echo "Lecture des comptes de $DEV_DB impossible." >&2; STATUS=3; exit 3; }
echo "Base $DEV_DB avant : $BEFORE"

compose exec -T db createdb -U "$PGUSER_" "$DB_NAME" || { STATUS=3; exit 3; }
CREATED=1
echo "Base jetable : $DB_NAME"

mkdir -p "$TMP/documents" "$TMP/fichiers"
export DJANGO_SETTINGS_MODULE=config.settings.dev
export DATABASE_URL="postgres://${PGUSER_}:${PGPASS_}@localhost:${DB_HOST_PORT}/${DB_NAME}"
export DOCUMENTS_ROOT="$TMP/documents"
export FICHIERS_RACINE="$TMP/fichiers"
export CORS_ALLOWED_ORIGINS="http://localhost:${WEB_PORT}"
# Isolation des services partagés : aucun index de recherche ni file Celery de la pile de dev.
export MEILI_URL="http://127.0.0.1:9"
export REDIS_URL="redis://localhost:${REDIS_HOST_PORT}/14"
export OIDC_OP_BASE_URL="http://localhost:${KC_PORT}/realms/onea"

(cd "$ROOT/backend" && "$PY" manage.py migrate --noinput) || { STATUS=1; exit 1; }

(cd "$ROOT/backend" && exec "$PY" manage.py runserver "127.0.0.1:${API_PORT}" --noreload) \
  >"$TMP/api.log" 2>&1 &
API_PID=$!
wait_http "http://127.0.0.1:${API_PORT}/api/v1/health/" 90 || { cat "$TMP/api.log" >&2; STATUS=1; exit 1; }

(cd "$ROOT/frontend" && VITE_API_URL="http://localhost:${API_PORT}" \
  VITE_OIDC_AUTHORITY="http://localhost:${KC_PORT}/realms/onea" \
  exec node node_modules/vite/bin/vite.js --host localhost --port "$WEB_PORT" --strictPort) \
  >"$TMP/web.log" 2>&1 &
WEB_PID=$!
wait_http "http://localhost:${WEB_PORT}/" 90 || { cat "$TMP/web.log" >&2; STATUS=1; exit 1; }

export E2E_API_URL="http://localhost:${API_PORT}"
export E2E_OIDC_AUTHORITY="http://localhost:${KC_PORT}/realms/onea"
export E2E_RUN_ID="$STAMP"
export E2E_WEB_EXTERNAL=1
export WEB_PORT
(cd "$ROOT/frontend" && npx playwright test "$@")
STATUS=$?

AFTER="$(counts)"
echo "Base $DEV_DB après : $AFTER"
if [ "$BEFORE" != "$AFTER" ]; then
  echo "ERREUR : les comptes de la base $DEV_DB ont changé (avant : $BEFORE ; après : $AFTER)." >&2
  [ "$STATUS" = 0 ] && STATUS=4
fi
exit "$STATUS"
