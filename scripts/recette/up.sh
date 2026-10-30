#!/bin/sh
# Lance la pile de recette (compose.prod.yml + surcouche) : sh scripts/recette/up.sh
# Prerequis : docker compose v2, openssl, curl ; ports 80 et 443 libres sur la machine.
set -eu
. "$(dirname "$0")/lib.sh"

mkdir -p "$RECETTE_DIR" "$RECETTE_DIR/acme"
chmod 0755 "$RECETTE_DIR/acme"
sh "$RECETTE_LIB_DIR/certs.sh"

rand() { openssl rand -hex 24; }

if [ ! -f "$RECETTE_ENV" ]; then
    docs="$RECETTE_DIR/documents"
    mkdir -p "$docs"
    # Dossier des documents : 10001:10001, 0750 (utilisateur du conteneur applicatif).
    if ! chown 10001:10001 "$docs" 2>/dev/null; then
        docker run --rm -v "$docs:/d" alpine:3.20 chown 10001:10001 /d
    fi
    chmod 0750 "$docs" 2>/dev/null || docker run --rm -v "$docs:/d" alpine:3.20 chmod 0750 /d
    # Secrets applicatifs : fichiers (T17), exactement comme en production. Compose monte les
    # fichiers tels quels : ils doivent appartenir a 10001 (utilisateur des conteneurs applicatifs).
    sh "$REPO_ROOT/scripts/generer-secrets.sh" --dossier "$RECETTE_SECRETS" --sans-proprietaire
    if ! chown 10001:10001 "$RECETTE_SECRETS"/* 2>/dev/null; then
        docker run --rm -v "$RECETTE_SECRETS:/s" alpine:3.20 sh -c "chown 10001:10001 /s/*"
    fi
    # Les deux secrets de Keycloak restent des variables (Keycloak ne lit pas de fichier).
    sed -e "s|@SECRETS_DIR@|$RECETTE_SECRETS|" \
        -e "s|@KC_ADMIN_PASSWORD@|$(rand)|" \
        -e "s|@KC_DB_PASSWORD@|$(rand)|" \
        -e "s|@DOCUMENTS_HOST_DIR@|$docs|" \
        -e "s|@TLS_CERT_DIR@|$RECETTE_DIR/certs|" \
        -e "s|@ACME_WEBROOT@|$RECETTE_DIR/acme|" \
        "$REPO_ROOT/.env.recette.example" > "$RECETTE_ENV"
    chmod 0600 "$RECETTE_ENV"
fi

compose_recette up -d --build

echo "Attente de /api/v1/health/ (max 10 min)..."
i=0
until curl_recette -fs "https://$PUBLIC_HOST/api/v1/health/" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 120 ]; then
        echo "Delai depasse. Voir : docker compose -p $RECETTE_PROJECT logs" >&2
        exit 1
    fi
    sleep 5
done
echo "Pile de recette prete : https://$PUBLIC_HOST (SSO : https://$SSO_HOST)."
echo "Etape suivante : sh scripts/recette/realm.sh"
