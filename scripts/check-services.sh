#!/usr/bin/env bash
# Probe every infrastructure service; exit 1 if any is down.
# Host ports can be overridden with the same variables as docker/compose.dev.yml.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/docker/compose.yml" -f "$ROOT/docker/compose.dev.yml")
if [ -f "$ROOT/.env" ]; then set -a; . "$ROOT/.env"; set +a; fi

KC_PORT="${KEYCLOAK_PORT:-8080}"
MINIO_API="${MINIO_API_PORT:-9000}"
MEILI="${MEILI_PORT:-7700}"
GOTENBERG="${GOTENBERG_PORT:-3000}"
MAILPIT_UI="${MAILPIT_HTTP_PORT:-8025}"

fail=0
check() { # name, command...
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "$name: OK"; else echo "$name: KO"; fail=1; fi
}

check db "${COMPOSE[@]}" exec -T db pg_isready -U "${POSTGRES_USER:-onea}" -d "${POSTGRES_DB:-onea}"
check redis "${COMPOSE[@]}" exec -T redis valkey-cli ping
check keycloak curl -fsS "http://localhost:${KC_PORT}/realms/onea"
check minio curl -fsS "http://localhost:${MINIO_API}/minio/health/live"
check meilisearch curl -fsS "http://localhost:${MEILI}/health"
check gotenberg curl -fsS "http://localhost:${GOTENBERG}/health"
check mailpit curl -fsS "http://localhost:${MAILPIT_UI}/livez"

exit $fail
