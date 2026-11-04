#!/bin/sh
# Fonctions communes de la pile de recette (sh POSIX). A sourcer : . "$(dirname "$0")/lib.sh"
# Hotes fictifs resolus vers 127.0.0.1 par curl --resolve : aucun DNS ni /etc/hosts requis.
RECETTE_LIB_DIR=$(cd "$(dirname "${BASH_SOURCE:-$0}")" && pwd)
REPO_ROOT=$(cd "$RECETTE_LIB_DIR/../.." && pwd)
RECETTE_DIR="$REPO_ROOT/.recette"
RECETTE_ENV="$RECETTE_DIR/.env.recette"
RECETTE_SECRETS="$RECETTE_DIR/secrets"
PUBLIC_HOST=${PUBLIC_HOST:-audit.recette.test}
RECETTE_PROJECT=${RECETTE_PROJECT:-onea-recette}

# compose_recette <args...> : docker compose de la recette (compose.prod.yml sans modification).
compose_recette() {
    docker compose -p "$RECETTE_PROJECT" --env-file "$RECETTE_ENV" \
        -f "$REPO_ROOT/docker/compose.prod.yml" \
        -f "$REPO_ROOT/scripts/recette/compose.override.yml" "$@"
}

# secret_recette <nom> : valeur d un fichier de secret, lue DANS le conteneur web (les fichiers
# appartiennent a 10001 en 0600 : illisibles pour l utilisateur de l hote). Nom parmi ceux de
# secret_key, postgres_app_password... montes dans web.
secret_recette() {
    compose_recette exec -T web cat "/run/secrets/$1" | tr -d "\r\n"
}

# curl_recette <args...> : curl vers la pile (ports 80/443 locaux), CA de recette.
curl_recette() {
    curl -sS --max-time 20 \
        --resolve "$PUBLIC_HOST:443:127.0.0.1" \
        --resolve "$PUBLIC_HOST:80:127.0.0.1" \
        --cacert "$RECETTE_DIR/certs/ca.pem" "$@"
}

# --- Connexion par session (plus de jetons Bearer) -----------------------------------------
# Comptes de recette : fichier .recette/comptes.txt (ou $RECETTE_COMPTES), une ligne
# `identifiant:mot_de_passe` par compte (le mot de passe commence apres le premier « : »).
RECETTE_COMPTES=${RECETTE_COMPTES:-$RECETTE_DIR/comptes.txt}

# mdp_compte <identifiant> : mot de passe du compte dans le fichier des comptes de recette.
mdp_compte() {
    awk -v u="$1" 'index($0, u ":") == 1 { print substr($0, length(u) + 2); exit }' "$RECETTE_COMPTES"
}

# jeton_csrf <jar> : GET /api/v1/auth/csrf/ (pose le cookie CSRF dans le jar) et affiche le jeton.
jeton_csrf() {
    curl_recette -fs -c "$1" -b "$1" "https://$PUBLIC_HOST/api/v1/auth/csrf/" |
        python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])'
}

# connexion_session <jar> <identifiant> : ouvre une session (csrf puis POST /auth/login/) et affiche
# le jeton CSRF a joindre (en-tete X-CSRFToken) aux requetes d'ecriture. Code 1 si la connexion echoue.
# Django renouvelle le jeton CSRF a la connexion : il est relu apres le login.
connexion_session() {
    _jar=$1
    _id=$2
    : > "$_jar"
    _tok=$(jeton_csrf "$_jar") || return 1
    _corps=$(python3 -c 'import json,sys; print(json.dumps({"identifiant": sys.argv[1], "mot_de_passe": sys.argv[2]}))'         "$_id" "$(mdp_compte "$_id")") || return 1
    curl_recette -fs -o /dev/null -c "$_jar" -b "$_jar" -H "X-CSRFToken: $_tok"         -H "Referer: https://$PUBLIC_HOST/" -H "Content-Type: application/json"         -d "$_corps" "https://$PUBLIC_HOST/api/v1/auth/login/" || return 1
    jeton_csrf "$_jar"
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
