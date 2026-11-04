#!/bin/sh
# Banc d'essai de la peripherie (nginx) sur la pile de recette.
# Usage : sh scripts/recette/up.sh && sh scripts/recette/tests/edge.sh
. "$(dirname "$0")/../lib.sh"
A="https://$PUBLIC_HOST"

# En-tete present (insensible a la casse) dans la reponse a une URL.
entete() { curl_recette -sI "$1" | grep -i "^$2:" | grep -qi "$3"; }
code() { [ "$(curl_recette -s -o /dev/null -w '%{http_code}' "$1")" = "$2" ]; }
redir() { # url attendu-Location
    r=$(curl_recette -s -o /dev/null -w '%{http_code} %{redirect_url}' "$1")
    [ "$r" = "301 $2" ]
}

affirmer "HTTP app -> HTTPS app (chemin et requete conserves)" \
    redir "http://$PUBLIC_HOST/api/v1/health/?a=1\&b=2" "$A/api/v1/health/?a=1&b=2"
affirmer "hote client inconnu -> hote de l'application" \
    '[ "$(curl_recette -s -o /dev/null -w "%{redirect_url}" -H "Host: evil.example" "http://$PUBLIC_HOST/p?q=1")" = "'"$A"'/p?q=1" ]'

# Defi ACME http-01 : un fichier du webroot est servi en clair (200, sans redirection) ; le reste
# du port 80 redirige toujours ; un fichier absent -> 404 (pas de redirection non plus).
ACME_DIR=$(sed -n 's/^ACME_WEBROOT=//p' "$RECETTE_ENV" | tail -n 1)
if [ -n "$ACME_DIR" ] && [ -d "$ACME_DIR" ]; then
    mkdir -p "$ACME_DIR/.well-known/acme-challenge"
    chmod 0755 "$ACME_DIR/.well-known" "$ACME_DIR/.well-known/acme-challenge"
    printf 'jeton-de-recette' > "$ACME_DIR/.well-known/acme-challenge/essai-t19"
    chmod 0644 "$ACME_DIR/.well-known/acme-challenge/essai-t19"
    affirmer "ACME : fichier du webroot servi en HTTP (200, sans redirection)" \
        '[ "$(curl_recette -s -w " %{http_code}" "http://$PUBLIC_HOST/.well-known/acme-challenge/essai-t19")" = "jeton-de-recette 200" ]'
    affirmer "ACME : fichier absent -> 404" \
        code "http://$PUBLIC_HOST/.well-known/acme-challenge/absent" 404
    rm -f "$ACME_DIR/.well-known/acme-challenge/essai-t19"
else
    affirmer "ACME : webroot defini dans .env.recette (relancer scripts/recette/up.sh apres mise a jour)" false
fi
affirmer "ACME : le webroot n'expose rien hors de .well-known/acme-challenge" \
    code "http://$PUBLIC_HOST/.well-known/autre" 301

affirmer "app : HSTS" entete "$A/" strict-transport-security max-age
affirmer "app : CSP" entete "$A/" content-security-policy "default-src 'self'"
affirmer "app : X-Frame-Options DENY" entete "$A/" x-frame-options DENY
affirmer "app : nosniff" entete "$A/" x-content-type-options nosniff
affirmer "app : Referrer-Policy" entete "$A/" referrer-policy strict-origin
affirmer "app : Permissions-Policy" entete "$A/" permissions-policy camera
affirmer "server_tokens masque (pas de numero de version)" \
    '! curl_recette -sI "$A/" | grep -i "^server:" | grep -q "[0-9]"'

affirmer "/api/v1/health/ -> status ok" \
    'curl_recette -fs "$A/api/v1/health/" | grep -q "\"status\": *\"ok\""'

# Le texte filtre passe par un tube : en argument, grep le prendrait pour un nom de fichier,
# sortirait en erreur et le « ! » ferait toujours passer l'assertion.
affirmer "docs/deploy.md sans recette (sauf chemin scripts/recette/)" \
    '[ -s "$REPO_ROOT/docs/deploy.md" ] && ! grep -v scripts/recette/ "$REPO_ROOT/docs/deploy.md" | grep -qi recette'
affirmer ".env.prod.example sans recette"     '! grep -qiE "recette" "$REPO_ROOT/.env.prod.example"'

bilan
