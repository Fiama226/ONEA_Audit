#!/bin/sh
# Cree le realm `onea` de RECETTE via kcadm.sh (dans le conteneur Keycloak).
# Usage : sh scripts/recette/realm.sh   (apres up.sh). Mots de passe : .recette/comptes.txt
# Rappel D20 : onea-charge (acces direct par mot de passe) n'existe qu'en recette.
set -eu
. "$(dirname "$0")/lib.sh"

KCADM="/opt/keycloak/bin/kcadm.sh"
kc() { compose_recette exec -T keycloak "$KCADM" "$@"; }
envv() { sed -n "s/^$1=//p" "$RECETTE_ENV"; }
rand() { openssl rand -hex 12; }

COMPTES="$RECETTE_DIR/comptes.txt"
: > "$COMPTES"
chmod 0600 "$COMPTES"

kc config credentials --server http://localhost:8080 --realm master \
    --user admin --password "$(envv KEYCLOAK_ADMIN_PASSWORD)" >/dev/null

kc create realms -s realm=onea -s enabled=true -s sslRequired=external \
    -s registrationAllowed=false -s loginWithEmailAllowed=true -s duplicateEmailsAllowed=false \
    -s bruteForceProtected=true -s failureFactor=5 -s permanentLockout=false     -s waitIncrementSeconds=60 -s maxFailureWaitSeconds=900     -s 'passwordPolicy=length(12) and notUsername and passwordHistory(5)'     -s otpPolicyType=totp -s otpPolicyDigits=6 -s otpPolicyPeriod=30     -s internationalizationEnabled=true \
    -s 'supportedLocales=["fr"]' -s defaultLocale=fr \
    -s 'attributes.unmanagedAttributePolicy=ADMIN_EDIT' >/dev/null

for r in ADMIN RAI AUDITEUR AUDITE DG; do
    kc create roles -r onea -s name="$r" >/dev/null
done

# Mappers communs (roles, direction, fonction), poses sur chaque client.
add_mappers() { # $1 = id interne du client
    kc create "clients/$1/protocol-mappers/models" -r onea -s name=realm-roles \
        -s protocol=openid-connect -s protocolMapper=oidc-usermodel-realm-role-mapper \
        -s 'config."claim.name"=roles' -s 'config.multivalued=true' \
        -s 'config."jsonType.label"=String' -s 'config."access.token.claim"=true' \
        -s 'config."id.token.claim"=true' -s 'config."userinfo.token.claim"=true' >/dev/null
    for a in direction fonction; do
        kc create "clients/$1/protocol-mappers/models" -r onea -s name="$a" \
            -s protocol=openid-connect -s protocolMapper=oidc-usermodel-attribute-mapper \
            -s "config.\"user.attribute\"=$a" -s "config.\"claim.name\"=$a" \
            -s 'config."jsonType.label"=String' -s 'config."access.token.claim"=true' \
            -s 'config."id.token.claim"=true' -s 'config."userinfo.token.claim"=true' >/dev/null
    done
}
client_id() { kc get clients -r onea -q "clientId=$1" --fields id --format csv --noquotes; }

# onea-frontend : public, PKCE S256, URI exactes (pas de joker).
kc create clients -r onea -s clientId=onea-frontend -s publicClient=true \
    -s standardFlowEnabled=true -s directAccessGrantsEnabled=false \
    -s "redirectUris=[\"https://$PUBLIC_HOST/callback\",\"https://$PUBLIC_HOST/\"]" \
    -s "webOrigins=[\"https://$PUBLIC_HOST\"]" \
    -s 'attributes."pkce.code.challenge.method"=S256' \
    -s "attributes.\"post.logout.redirect.uris\"=https://$PUBLIC_HOST/" >/dev/null
add_mappers "$(client_id onea-frontend)"

# onea-backend : confidentiel, secret = fichier oidc_client_secret (relu dans le conteneur web).
kc create clients -r onea -s clientId=onea-backend -s publicClient=false \
    -s secret="$(secret_recette oidc_client_secret)" -s standardFlowEnabled=true \
    -s directAccessGrantsEnabled=false >/dev/null
add_mappers "$(client_id onea-backend)"

# onea-admin-sync : compte de service view-users + manage-users, portee restreinte.
kc create clients -r onea -s clientId=onea-admin-sync -s publicClient=false \
    -s secret="$(secret_recette keycloak_sync_secret)" -s serviceAccountsEnabled=true \
    -s standardFlowEnabled=false -s directAccessGrantsEnabled=false \
    -s fullScopeAllowed=false >/dev/null
kc add-roles -r onea --uusername service-account-onea-admin-sync \
    --cclientid realm-management --rolename view-users --rolename manage-users
SYNC_ID=$(client_id onea-admin-sync)
RM_ID=$(client_id realm-management)
for role in view-users manage-users; do
    RID=$(kc get "clients/$RM_ID/roles/$role" -r onea --fields id --format csv --noquotes)
    kc create "clients/$SYNC_ID/scope-mappings/clients/$RM_ID" -r onea \
        -b "[{\"id\":\"$RID\",\"name\":\"$role\"}]" >/dev/null
done

# onea-charge (D20) : acces direct par mot de passe, pour les essais de charge. RECETTE SEULEMENT.
kc create clients -r onea -s clientId=onea-charge -s publicClient=true \
    -s standardFlowEnabled=false -s directAccessGrantsEnabled=true >/dev/null
add_mappers "$(client_id onea-charge)"

# Comptes de test : utilisateur role direction fonction. Ajouter ici ceux de T4 et T26.
creer_compte() {
    pw=$(rand)
    kc create users -r onea -s username="$1" -s enabled=true -s emailVerified=true \
        -s email="$1@recette.test" -s firstName="$1" -s lastName=Recette \
        -s "attributes.direction=$3" -s "attributes.fonction=$4" >/dev/null
    kc set-password -r onea --username "$1" --new-password "$pw"
    kc add-roles -r onea --uusername "$1" --rolename "$2"
    # D19 : second facteur obligatoire des comptes ADMIN (action requise a la prochaine connexion).
    # Desactive par defaut en recette, car token.sh (acces direct par mot de passe) ne sait pas
    # enrôler un OTP ; RECETTE_ADMIN_OTP=1 l'active pour verifier le parcours au navigateur.
    if [ "$2" = ADMIN ] && [ "${RECETTE_ADMIN_OTP:-0}" = 1 ]; then
        kc update "users/$(kc get users -r onea -q "username=$1" --fields id --format csv --noquotes)"             -r onea -s 'requiredActions=["CONFIGURE_TOTP"]'
    fi
    printf '%s\t%s\t%s\n' "$1" "$pw" "$2" >> "$COMPTES"
}
creer_compte rai RAI DAI "Responsable de l'audit interne"
creer_compte auditeur1 AUDITEUR DAI "Auditeur senior"
creer_compte auditeur2 AUDITEUR DAI "Auditeur"
creer_compte audite1 AUDITE DEX "Chef de service"
creer_compte dg DG DG "Directeur general"
creer_compte admin ADMIN DSI "Administrateur plateforme"

echo "Realm onea de recette cree. Comptes : $COMPTES (utilisateur, mot de passe, role)."
