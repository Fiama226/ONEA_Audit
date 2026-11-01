#!/bin/sh
# Banc d'essai du realm de recette (lot 9, T29 : SEC-03, SEC-06) : les URI de redirection de
# onea-frontend correspondent a la route de la SPA, et la politique de mots de passe cible est posee.
# Usage : sh scripts/recette/up.sh && sh scripts/recette/realm.sh && sh scripts/recette/tests/realm.sh
. "$(dirname "$0")/../lib.sh"

KCADM="/opt/keycloak/bin/kcadm.sh"
kc() { compose_recette exec -T keycloak "$KCADM" "$@"; }
envv() { sed -n "s/^$1=//p" "$RECETTE_ENV"; }

kc config credentials --server http://localhost:8080 --realm master \
    --user admin --password "$(envv KEYCLOAK_ADMIN_PASSWORD)" >/dev/null

REALM=$(kc get realms/onea)
CLIENT=$(kc get clients -r onea -q clientId=onea-frontend)
ROUTE=$(sed -n 's#.*path: *"/callback".*#callback#p' "$REPO_ROOT/frontend/src/routes.tsx" | head -1)

affirmer "route /callback presente dans la SPA" '[ "$ROUTE" = callback ]'
affirmer "onea-frontend : redirectUris contient https://$PUBLIC_HOST/callback" \
    'printf "%s" "$CLIENT" | grep -q "\"https://$PUBLIC_HOST/callback\""'
affirmer "onea-frontend : aucune URI /auth/callback ni joker" \
    '! printf "%s" "$CLIENT" | grep -q "auth/callback\|\*"'
affirmer "politique de mots de passe : longueur 12 minimum" \
    'printf "%s" "$REALM" | grep -q "length(12)"'
affirmer "politique de mots de passe : historique et nom d utilisateur" \
    'printf "%s" "$REALM" | grep -q "passwordHistory(5)" && printf "%s" "$REALM" | grep -q "notUsername"'
affirmer "protection force brute : 5 echecs" \
    'printf "%s" "$REALM" | grep -q "\"failureFactor\" *: *5"'
affirmer "politique OTP : totp a 6 chiffres" \
    'printf "%s" "$REALM" | grep -q "\"otpPolicyType\" *: *\"totp\"" && printf "%s" "$REALM" | grep -q "\"otpPolicyDigits\" *: *6"'

bilan
