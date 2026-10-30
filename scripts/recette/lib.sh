#!/bin/sh
# Fonctions communes de la pile de recette (sh POSIX). A sourcer : . "$(dirname "$0")/lib.sh"
# Hotes fictifs resolus vers 127.0.0.1 par curl --resolve : aucun DNS ni /etc/hosts requis.
RECETTE_LIB_DIR=$(cd "$(dirname "${BASH_SOURCE:-$0}")" && pwd)
REPO_ROOT=$(cd "$RECETTE_LIB_DIR/../.." && pwd)
RECETTE_DIR="$REPO_ROOT/.recette"
RECETTE_ENV="$RECETTE_DIR/.env.recette"
RECETTE_SECRETS="$RECETTE_DIR/secrets"
PUBLIC_HOST=${PUBLIC_HOST:-audit.recette.test}
SSO_HOST=${SSO_HOST:-sso.recette.test}
RECETTE_PROJECT=${RECETTE_PROJECT:-onea-recette}

# compose_recette <args...> : docker compose de la recette (compose.prod.yml sans modification).
compose_recette() {
    docker compose -p "$RECETTE_PROJECT" --env-file "$RECETTE_ENV" \
        -f "$REPO_ROOT/docker/compose.prod.yml" \
        -f "$REPO_ROOT/scripts/recette/compose.override.yml" "$@"
}

# secret_recette <nom> : valeur d un fichier de secret, lue DANS le conteneur web (les fichiers
# appartiennent a 10001 en 0600 : illisibles pour l utilisateur de l hote). Nom parmi ceux de
# oidc_client_secret, keycloak_sync_secret, secret_key... montes dans web.
secret_recette() {
    compose_recette exec -T web cat "/run/secrets/$1" | tr -d "\r\n"
}

# curl_recette <args...> : curl vers la pile (ports 80/443 locaux), CA de recette.
curl_recette() {
    curl -sS --max-time 20 \
        --resolve "$PUBLIC_HOST:443:127.0.0.1" --resolve "$SSO_HOST:443:127.0.0.1" \
        --resolve "$PUBLIC_HOST:80:127.0.0.1" --resolve "$SSO_HOST:80:127.0.0.1" \
        --cacert "$RECETTE_DIR/certs/ca.pem" "$@"
}

PASS=0
FAIL=0
# affirmer <description> <commande sh> : PASS si la commande retourne 0.
affirmer() {
    _desc=$1
    shift
    if (eval "$@") >/dev/null 2>&1; then
        PASS=$((PASS + 1))
        printf 'PASS  %s\n' "$_desc"
    else
        FAIL=$((FAIL + 1))
        printf 'FAIL  %s\n' "$_desc"
    fi
}

# bilan : affiche le total et fixe le code de sortie (0 si aucun FAIL).
bilan() {
    printf '\n%s PASS, %s FAIL\n' "$PASS" "$FAIL"
    [ "$FAIL" -eq 0 ]
}
