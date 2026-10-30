#!/bin/sh
# Affiche un jeton d'acces d'un compte de recette (client onea-charge, RECETTE SEULEMENT).
# Usage : sh scripts/recette/token.sh <utilisateur>
set -eu
. "$(dirname "$0")/lib.sh"
pw=$(awk -F '\t' -v u="$1" '$1 == u { print $2 }' "$RECETTE_DIR/comptes.txt")
curl_recette -fs "https://$SSO_HOST/realms/onea/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=onea-charge -d "username=$1" --data-urlencode "password=$pw" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
