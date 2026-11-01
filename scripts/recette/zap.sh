#!/bin/sh
# Analyse dynamique OWASP ZAP (lot 9, T27) : « baseline » passive sur l'application et sur le SSO,
# puis « api-scan » sur le schéma OpenAPI avec le jeton d'un compte de recette.
# Usage : sh scripts/recette/zap.sh [compte]   (défaut : auditeur1 ; pile de recette démarrée)
# Rapports (HTML, JSON, Markdown) : .recette/zap/. Outil : image zaproxy/zap-stable (Apache-2.0).
#
# Variables (pour viser une autre instance jetable que la recette) :
#   ZAP_RESEAU     réseau Docker où se trouve le nginx visé (défaut : <projet>_edge de la recette)
#   ZAP_NGINX      conteneur nginx visé (défaut : <projet>-nginx-1)
#   ZAP_SCHEMA     fichier OpenAPI déjà produit (défaut : généré par `manage.py spectacular`)
#   ZAP_JETON      jeton porteur déjà obtenu (défaut : scripts/recette/token.sh <compte>)
#   ZAP_SORTIE     dossier des rapports (défaut : .recette/zap)
#   ZAP_ACTIF=1    ajoute l'analyse ACTIVE de l'API (requêtes d'attaque : instance jetable seulement)
# Code de sortie : celui des scans ZAP (0 aucun avertissement, 1 échec, 2 avertissements seuls).
set -eu
. "$(dirname "$0")/lib.sh"

COMPTE=${1:-auditeur1}
SORTIE=${ZAP_SORTIE:-$RECETTE_DIR/zap}
RESEAU=${ZAP_RESEAU:-${RECETTE_PROJECT}_edge}
NGINX=${ZAP_NGINX:-${RECETTE_PROJECT}-nginx-1}
IMAGE=${ZAP_IMAGE:-zaproxy/zap-stable}
mkdir -p "$SORTIE"
chmod 0777 "$SORTIE" 2>/dev/null || true   # ZAP écrit sous l'utilisateur « zap » du conteneur

IP=$(docker inspect -f "{{(index .NetworkSettings.Networks \"$RESEAU\").IPAddress}}" "$NGINX")
[ -n "$IP" ] || { echo "nginx $NGINX introuvable sur le réseau $RESEAU" >&2; exit 2; }

if [ -n "${ZAP_SCHEMA:-}" ]; then
    cp "$ZAP_SCHEMA" "$SORTIE/openapi.json"
else
    compose_recette exec -T web python manage.py spectacular --format openapi-json \
        > "$SORTIE/openapi.json"
fi
JETON=${ZAP_JETON:-$(sh "$(dirname "$0")/token.sh" "$COMPTE")}

# zap <script> <args...> : conteneur ZAP jetable, noms de la recette résolus vers nginx.
zap() {
    MSYS_NO_PATHCONV=1 docker run --rm --network "$RESEAU" \
        --add-host "$PUBLIC_HOST:$IP" --add-host "$SSO_HOST:$IP" \
        -e ZAP_AUTH_HEADER=Authorization -e "ZAP_AUTH_HEADER_VALUE=Bearer $JETON" \
        -e "ZAP_AUTH_HEADER_SITE=$PUBLIC_HOST" \
        -v "$SORTIE:/zap/wrk:rw" "$IMAGE" "$@"
}

code=0
echo "== ZAP baseline : https://$PUBLIC_HOST/"
zap zap-baseline.py -t "https://$PUBLIC_HOST/" -I -j \
    -r app-baseline.html -J app-baseline.json -w app-baseline.md || code=$?
echo "== ZAP baseline : https://$SSO_HOST/realms/onea/account/"
zap zap-baseline.py -t "https://$SSO_HOST/realms/onea/account/" -I \
    -r sso-baseline.html -J sso-baseline.json -w sso-baseline.md || code=$?
# Le schéma annonce l'URL relative /api/... : -O fixe l'hôte de recette.
echo "== ZAP api-scan (passif$( [ "${ZAP_ACTIF:-0}" = 1 ] && echo ' + actif')) : OpenAPI"
if [ "${ZAP_ACTIF:-0}" = 1 ]; then
    zap zap-api-scan.py -t /zap/wrk/openapi.json -f openapi -O "https://$PUBLIC_HOST" -I \
        -r api-scan.html -J api-scan.json -w api-scan.md || code=$?
else
    zap zap-api-scan.py -t /zap/wrk/openapi.json -f openapi -O "https://$PUBLIC_HOST" -I -S \
        -r api-scan.html -J api-scan.json -w api-scan.md || code=$?
fi
echo "Rapports : $SORTIE"
exit "$code"
