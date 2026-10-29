#!/bin/sh
# Supprime conteneurs, volumes et dossier .recette/ : sh scripts/recette/down.sh
set -eu
. "$(dirname "$0")/lib.sh"
if [ -f "$RECETTE_ENV" ]; then
    compose_recette down -v --remove-orphans
else
    docker compose -p "$RECETTE_PROJECT" down -v --remove-orphans 2>/dev/null || true
fi
# Le dossier documents appartient a 10001 : suppression via un conteneur si necessaire.
if [ -d "$RECETTE_DIR/documents" ]; then
    rm -rf "$RECETTE_DIR/documents" 2>/dev/null ||
        docker run --rm -v "$RECETTE_DIR:/r" alpine:3.20 rm -rf /r/documents
fi
rm -rf "$RECETTE_DIR"
rm -f "$REPO_ROOT/certs/recette-ca.pem"
echo "Recette supprimee."
