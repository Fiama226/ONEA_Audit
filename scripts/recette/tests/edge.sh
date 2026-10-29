#!/bin/sh
# Banc d'essai de la peripherie (nginx) sur la pile de recette.
# Usage : sh scripts/recette/up.sh && sh scripts/recette/realm.sh && sh scripts/recette/tests/edge.sh
. "$(dirname "$0")/../lib.sh"
A="https://$PUBLIC_HOST"
S="https://$SSO_HOST"

# En-tete present (insensible a la casse) dans la reponse a une URL.
entete() { curl_recette -sI "$1" | grep -i "^$2:" | grep -qi "$3"; }
code() { [ "$(curl_recette -s -o /dev/null -w '%{http_code}' "$1")" = "$2" ]; }
redir() { # url attendu-Location
    r=$(curl_recette -s -o /dev/null -w '%{http_code} %{redirect_url}' "$1")
    [ "$r" = "301 $2" ]
}

affirmer "HTTP app -> HTTPS app (chemin et requete conserves)" \
    redir "http://$PUBLIC_HOST/api/v1/health/?a=1\&b=2" "$A/api/v1/health/?a=1&b=2"
affirmer "HTTP SSO -> HTTPS SSO (chemin et requete conserves)" \
    redir "http://$SSO_HOST/realms/onea/account?x=y" "$S/realms/onea/account?x=y"
affirmer "hote client inconnu -> hote de l'application" \
    '[ "$(curl_recette -s -o /dev/null -w "%{redirect_url}" -H "Host: evil.example" "http://$PUBLIC_HOST/p?q=1")" = "'"$A"'/p?q=1" ]'

affirmer "app : HSTS" entete "$A/" strict-transport-security max-age
affirmer "app : CSP" entete "$A/" content-security-policy "default-src 'self'"
affirmer "app : X-Frame-Options DENY" entete "$A/" x-frame-options DENY
affirmer "app : nosniff" entete "$A/" x-content-type-options nosniff
affirmer "app : Referrer-Policy" entete "$A/" referrer-policy strict-origin
affirmer "app : Permissions-Policy" entete "$A/" permissions-policy camera
affirmer "SSO : HSTS" entete "$S/realms/onea/" strict-transport-security max-age
affirmer "SSO : nosniff" entete "$S/realms/onea/" x-content-type-options nosniff
affirmer "server_tokens masque (pas de numero de version)" \
    '! curl_recette -sI "$A/" | grep -i "^server:" | grep -q "[0-9]"'

for p in /admin/ /realms/master/ /metrics /health; do
    affirmer "SSO $p -> 404" code "$S$p" 404
done
affirmer "decouverte OIDC du realm onea -> 200" \
    code "$S/realms/onea/.well-known/openid-configuration" 200
affirmer "/api/v1/health/ -> status ok" \
    'curl_recette -fs "$A/api/v1/health/" | grep -q "\"status\": *\"ok\""'

affirmer "docs/deploy.md sans onea-charge ni recette" \
    '! grep -qiE "onea-charge|recette" "$REPO_ROOT/docs/deploy.md"'
affirmer ".env.prod.example sans onea-charge ni recette" \
    '! grep -qiE "onea-charge|recette" "$REPO_ROOT/.env.prod.example"'

bilan
