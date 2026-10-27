#!/bin/sh
# Generate frontend/src/api/schema.d.ts from the Django OpenAPI schema.
# Can be run from anywhere: the script resolves the repository root itself.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

if [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/backend/.venv/Scripts/python.exe"
elif [ -x "$ROOT/backend/.venv/bin/python" ]; then
  PY="$ROOT/backend/.venv/bin/python"
else
  PY=python
fi

# No query runs during schema generation; the URL is only needed to load settings.
DATABASE_URL=${DATABASE_URL:-postgres://onea:onea@127.0.0.1:5432/onea}
export DATABASE_URL

# Note: field descriptions come from Django translations (settings are fr). The committed
# schema.d.ts must be regenerated with the pinned Django/DRF versions to stay reproducible.

# A Windows-native python needs a native path for --file.
OUT="$TMP/schema.yml"
if command -v cygpath >/dev/null 2>&1; then
  OUT=$(cygpath -m "$OUT")
fi

(cd "$ROOT/backend" && "$PY" manage.py spectacular --file "$OUT" --settings=config.settings.test --urlconf=config.urls)
(cd "$ROOT/frontend" && npx --no-install openapi-typescript "$TMP/schema.yml" -o src/api/schema.d.ts)
echo "Generated frontend/src/api/schema.d.ts"
