#!/usr/bin/env bash
# Probe the infrastructure services; exit 1 if any is down.
# Usage: check-services.sh
# Reads the repo-root .env (KEY=VALUE lines, parsed, never sourced).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for arg in "$@"; do
  echo "unknown argument: $arg" >&2; exit 2
done

# Safe .env loader: only KEY=VALUE lines, optional surrounding quotes, no expansion.
# Variables already set in the environment win.
ENV_ARGS=()
if [ -f "$ROOT/.env" ]; then
  ENV_ARGS=(--env-file "$ROOT/.env")
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}"; val="${BASH_REMATCH[2]}"
    if [[ "$val" =~ ^\"(.*)\"$ || "$val" =~ ^\'(.*)\'$ ]]; then val="${BASH_REMATCH[1]}"; fi
    [ -z "${!key+x}" ] && export "$key=$val"
  done < "$ROOT/.env"
fi

COMPOSE=(docker compose "${ENV_ARGS[@]}" -f "$ROOT/docker/compose.yml" -f "$ROOT/docker/compose.dev.yml")

KC_PORT="${KEYCLOAK_PORT:-8080}"
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
check meilisearch curl -fsS "http://localhost:${MEILI}/health"
check gotenberg curl -fsS "http://localhost:${GOTENBERG}/health"
check mailpit curl -fsS "http://localhost:${MAILPIT_UI}/livez"
# Documents folder (dev): created on demand by the storage layer, so only report its state.
DOCS_DIR="${DOCUMENTS_ROOT:-$ROOT/.dev/documents}"
if [ -d "$DOCS_DIR" ] && [ -w "$DOCS_DIR" ]; then echo "documents: OK"; else echo "documents: absent (créé à la première écriture)"; fi

exit $fail
