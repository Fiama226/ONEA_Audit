#!/bin/sh
# Verify that the committed frontend/src/api/schema.d.ts matches the backend OpenAPI schema.
# Regenerates it with gen-api.sh, then fails if the working copy differs from the index.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
FILE=frontend/src/api/schema.d.ts

sh "$ROOT/scripts/gen-api.sh"

cd "$ROOT"
if ! git diff --exit-code -- "$FILE"; then
  echo "ERREUR : $FILE n'est pas à jour avec le schéma OpenAPI du backend." >&2
  echo "Lancez « sh scripts/gen-api.sh » puis commitez le fichier régénéré." >&2
  exit 1
fi
echo "OK : $FILE est à jour."
