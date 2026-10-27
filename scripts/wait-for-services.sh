#!/usr/bin/env bash
# Wait (default 240 s) until every service answers; used by `make up`.
# Usage: wait-for-services.sh [--with-storage]   (arguments go to check-services.sh)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMEOUT="${WAIT_TIMEOUT:-240}"
end=$((SECONDS + TIMEOUT))
until bash "$ROOT/scripts/check-services.sh" "$@" >/dev/null 2>&1; do
  if [ "$SECONDS" -ge "$end" ]; then
    echo "Timeout waiting for services:" >&2
    bash "$ROOT/scripts/check-services.sh" "$@" >&2
    exit 1
  fi
  sleep 3
done
echo "All services are up."
