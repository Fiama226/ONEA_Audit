#!/bin/sh
# Dump the application and Keycloak PostgreSQL databases of the production stack.
#   sh scripts/backup.sh [backup-dir]        (default: ./backups)
# Run from the repository root on the server; reads .env.prod for the database names.
# Restore: see docs/deploy.md ("Sauvegardes et restauration").
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST=${1:-"$ROOT/backups"}
ENV_FILE=${ENV_FILE:-"$ROOT/.env.prod"}
COMPOSE="docker compose --env-file $ENV_FILE -f $ROOT/docker/compose.prod.yml"
STAMP=$(date +%Y%m%d-%H%M%S)

[ -f "$ENV_FILE" ] || { echo "ERREUR : $ENV_FILE introuvable." >&2; exit 1; }
mkdir -p "$DEST"
umask 077

# POSTGRES_USER / POSTGRES_DB are read inside the container, so no secret leaves it.
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "$DEST/onea-$STAMP.dump"
$COMPOSE exec -T keycloak-db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "$DEST/keycloak-$STAMP.dump"

# Keep the 14 most recent dumps of each database.
for prefix in onea keycloak; do
  ls -1t "$DEST"/"$prefix"-*.dump 2>/dev/null | tail -n +15 | while read -r old; do rm -f "$old"; done
done

echo "OK : sauvegardes écrites dans $DEST (onea-$STAMP.dump, keycloak-$STAMP.dump)"
