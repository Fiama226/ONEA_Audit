#!/bin/sh
# Obtention et renouvellement du certificat TLS par Let's Encrypt (defi ACME http-01, webroot).
# Voie B de docs/deploy.md section 2. Prerequis : DNS public pour PUBLIC_HOST et SSO_HOST,
# port 80 joignable depuis Internet. Un seul certificat (deux noms) est emis.
#
#   sh scripts/tls/certbot.sh --dry-run      essai a blanc (serveur de test Let's Encrypt, rien n'est ecrit)
#   sh scripts/tls/certbot.sh --staging      certificat de TEST reel (non reconnu par les navigateurs)
#   sh scripts/tls/certbot.sh --production   certificat reel (emission ou renouvellement si < 30 jours)
# Aucun mode par defaut : un appel sans option affiche cette aide et ne contacte personne.
#
# Variables (fichier ENV_FILE, defaut ./.env.prod, ou environnement) :
#   PUBLIC_HOST, SSO_HOST, TLS_CERT_DIR, ACME_WEBROOT (obligatoires)
#   LETSENCRYPT_EMAIL (obligatoire, alertes d'expiration) ; CERTBOT_DIR (defaut /etc/onea/letsencrypt)
#   CERTBOT_IMAGE (defaut certbot/certbot:v2.11.0)
# Apres emission, fullchain.pem et privkey.pem sont copies dans TLS_CERT_DIR (remplacement
# atomique) puis nginx est recharge. Le renouvellement automatique : docker/ops/onea-certificat.timer.
set -eu
umask 077

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT/.env.prod"}
MODE=""
for a in "$@"; do
    case "$a" in
        --dry-run | --staging | --production) MODE=$a ;;
        *) echo "Option inconnue : $a" >&2; MODE="" ; break ;;
    esac
done
if [ -z "$MODE" ]; then
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
fi

lire() { # lire NOM : valeur de l'environnement, sinon du fichier d'environnement
    eval "_v=\${$1:-}"
    if [ -z "$_v" ] && [ -f "$ENV_FILE" ]; then
        _v=$(sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1 | tr -d '"\r')
    fi
    printf '%s' "$_v"
}
PUBLIC_HOST=$(lire PUBLIC_HOST)
SSO_HOST=$(lire SSO_HOST)
TLS_CERT_DIR=$(lire TLS_CERT_DIR)
ACME_WEBROOT=$(lire ACME_WEBROOT)
EMAIL=$(lire LETSENCRYPT_EMAIL)
CERTBOT_DIR=$(lire CERTBOT_DIR); CERTBOT_DIR=${CERTBOT_DIR:-/etc/onea/letsencrypt}
CERTBOT_IMAGE=$(lire CERTBOT_IMAGE); CERTBOT_IMAGE=${CERTBOT_IMAGE:-certbot/certbot:v2.11.0}

for v in PUBLIC_HOST SSO_HOST TLS_CERT_DIR ACME_WEBROOT EMAIL; do
    eval "val=\$$v"
    [ -n "$val" ] || { echo "Variable obligatoire absente : $v (LETSENCRYPT_EMAIL pour EMAIL ; voir $ENV_FILE)" >&2; exit 1; }
done
case "$EMAIL" in *@*.*) ;; *) echo "LETSENCRYPT_EMAIL invalide." >&2; exit 1 ;; esac

mkdir -p "$ACME_WEBROOT" "$CERTBOT_DIR"
chmod 0755 "$ACME_WEBROOT"   # nginx (autre utilisateur) doit lire le defi

set -- certonly --webroot -w /webroot -d "$PUBLIC_HOST" -d "$SSO_HOST" \
    --cert-name onea --email "$EMAIL" --agree-tos --no-eff-email \
    --keep-until-expiring --non-interactive
case "$MODE" in
    --dry-run) set -- "$@" --dry-run ;;
    --staging) set -- "$@" --staging ;;
esac

echo "Certbot ($MODE) pour $PUBLIC_HOST et $SSO_HOST..."
docker run --rm -v "$CERTBOT_DIR:/etc/letsencrypt" -v "$ACME_WEBROOT:/webroot" \
    "$CERTBOT_IMAGE" "$@"

if [ "$MODE" = "--dry-run" ]; then
    echo "Essai a blanc reussi : rien n'a ete ecrit dans $TLS_CERT_DIR."
    exit 0
fi

live="$CERTBOT_DIR/live/onea"
[ -f "$live/fullchain.pem" ] || { echo "Certificat introuvable dans $live" >&2; exit 1; }
if cmp -s "$live/fullchain.pem" "$TLS_CERT_DIR/fullchain.pem" 2>/dev/null; then
    echo "Certificat inchange : pas de rechargement."
    exit 0
fi
mkdir -p "$TLS_CERT_DIR"
cp "$live/fullchain.pem" "$TLS_CERT_DIR/fullchain.pem.new"
cp "$live/privkey.pem" "$TLS_CERT_DIR/privkey.pem.new"
chmod 0644 "$TLS_CERT_DIR/fullchain.pem.new"
chmod 0600 "$TLS_CERT_DIR/privkey.pem.new"
mv "$TLS_CERT_DIR/privkey.pem.new" "$TLS_CERT_DIR/privkey.pem"
mv "$TLS_CERT_DIR/fullchain.pem.new" "$TLS_CERT_DIR/fullchain.pem"
docker compose --env-file "$ENV_FILE" -f "$ROOT/docker/compose.prod.yml" exec -T nginx nginx -s reload
echo "Certificat installe dans $TLS_CERT_DIR et nginx recharge."
