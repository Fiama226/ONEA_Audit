#!/bin/sh
# Dump the application and Keycloak PostgreSQL databases of the production stack, then
# archive the documents folder (DOCUMENTS_HOST_DIR). Databases first: the archive then holds
# every file referenced by the dump.
#   sh scripts/backup.sh [backup-dir]        (default: ./backups)
# Run from the repository root on the server. Dumps are written to a .tmp file first and
# renamed only when pg_dump succeeded, so a failed run never leaves a truncated dump.
# Restore: see docs/deploy.md ("Sauvegardes et restauration").
set -eu
umask 077

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST=${1:-"$ROOT/backups"}
ENV_FILE=${ENV_FILE:-"$ROOT/.env.prod"}
STAMP=$(date +%Y%m%d-%H%M%S)

[ -f "$ENV_FILE" ] || { echo "ERREUR : $ENV_FILE introuvable." >&2; exit 1; }
mkdir -p "$DEST"

compose() {
  docker compose --env-file "$ENV_FILE" -f "$ROOT/docker/compose.prod.yml" "$@"
}

dump() { # <service> <output-prefix>
  tmp="$DEST/$2-$STAMP.dump.tmp"
  # POSTGRES_USER / POSTGRES_DB are read inside the container: no secret leaves it.
  if compose exec -T "$1" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$tmp"; then
    mv "$tmp" "$DEST/$2-$STAMP.dump"
  else
    rm -f "$tmp"
    echo "ERREUR : la sauvegarde de $1 a échoué." >&2
    exit 1
  fi
}

dump db onea
dump keycloak-db keycloak

# Documents folder: read DOCUMENTS_HOST_DIR from the env file (parsed, never sourced).
DOCUMENTS_HOST_DIR=$(sed -n 's/^DOCUMENTS_HOST_DIR=//p' "$ENV_FILE" | tail -n 1 \
  | tr -d '\r' | tr -d "\"'")
[ -n "$DOCUMENTS_HOST_DIR" ] && [ -d "$DOCUMENTS_HOST_DIR" ] || {
  echo "ERREUR : DOCUMENTS_HOST_DIR absent de $ENV_FILE ou dossier introuvable." >&2
  exit 1
}
tmp="$DEST/documents-$STAMP.tar.gz.tmp"
if tar -czf "$tmp" -C "$DOCUMENTS_HOST_DIR" .; then
  mv "$tmp" "$DEST/documents-$STAMP.tar.gz"
else
  rm -f "$tmp"
  echo "ERREUR : l'archive des documents a échoué." >&2
  exit 1
fi

# Keep the 14 most recent dumps of each database and 14 document archives.
for prefix in onea keycloak; do
  ls -1t "$DEST"/"$prefix"-*.dump 2>/dev/null | tail -n +15 | while read -r old; do rm -f "$old"; done
done
ls -1t "$DEST"/documents-*.tar.gz 2>/dev/null | tail -n +15 | while read -r old; do rm -f "$old"; done

echo "OK : sauvegardes écrites dans $DEST (onea-$STAMP.dump, keycloak-$STAMP.dump, documents-$STAMP.tar.gz)"
