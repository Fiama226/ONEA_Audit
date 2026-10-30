#!/bin/sh
# Alerte par courriel, par curl et SMTP (lot 9, T18) : aucun outil supplémentaire. Appelé par
# docker/ops/onea-alerte@.service lorsqu'une minuterie de sauvegarde échoue.
#
#   sh scripts/alerte-mail.sh "<sujet>" ["<texte>"]     (le texte peut aussi venir de l'entrée standard)
#
# Configuration par l'environnement (fichier /etc/onea/sauvegarde.env, 0600, chargé par systemd) :
#   ALERTE_SMTP_URL                smtp://relais:587 (STARTTLS exigé) ou smtps://relais:465 ;
#                                  smtp://… sans chiffrement uniquement avec ALERTE_SMTP_CLAIR=1 (relais interne)
#   ALERTE_MAIL_DE, ALERTE_MAIL_A  expéditeur ; destinataires (séparés par des virgules)
#   ALERTE_SMTP_UTILISATEUR        facultatif
#   ALERTE_SMTP_MOT_DE_PASSE_FILE  facultatif : fichier contenant le mot de passe (jamais en argument)
#   ALERTE_CA_FILE                 facultatif : autorité de certification interne (PEM)
# Le mot de passe passe à curl par un fichier de configuration temporaire (0600, supprimé à la sortie) :
# ni dans les arguments (ps) ni dans l'environnement de curl.
set -eu
umask 077

SUJET=${1:-}
[ -n "$SUJET" ] || { echo "Usage : sh scripts/alerte-mail.sh \"<sujet>\" [\"<texte>\"]" >&2; exit 2; }
if [ "$#" -ge 2 ]; then CORPS=$2; elif [ ! -t 0 ]; then CORPS=$(cat); else CORPS=; fi

for v in ALERTE_SMTP_URL ALERTE_MAIL_DE ALERTE_MAIL_A; do
  eval "val=\${$v:-}"
  [ -n "$val" ] || { echo "ERREUR : $v est vide (alerte non envoyée)." >&2; exit 1; }
done
command -v curl >/dev/null 2>&1 || { echo "ERREUR : curl est introuvable." >&2; exit 1; }

case "$ALERTE_SMTP_URL" in
  smtps://*) SECU="" ;;
  smtp://*) if [ "${ALERTE_SMTP_CLAIR:-0}" = 1 ]; then SECU=""; else SECU="--ssl-reqd"; fi ;;
  *) echo "ERREUR : ALERTE_SMTP_URL doit commencer par smtp:// ou smtps://." >&2; exit 1 ;;
esac

# Aucune fin de ligne dans les en-têtes (injection) ; sujet encodé RFC 2047 (UTF-8).
propre() { printf '%s' "$1" | tr -d '\r\n'; }
DE=$(propre "$ALERTE_MAIL_DE")
A=$(propre "$ALERTE_MAIL_A")
SUJET_B64=$(printf '%s' "$(propre "$SUJET")" | base64 | tr -d '\r\n')
# Valeur entre guillemets du fichier de configuration de curl : \ et " échappés.
cfg() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
HOTE=$(hostname 2>/dev/null || echo serveur)

MSG=$(mktemp)
CFG=$(mktemp)
trap 'rm -f "$MSG" "$CFG"' EXIT
{
  printf 'From: %s\n' "$DE"
  printf 'To: %s\n' "$A"
  printf 'Subject: =?UTF-8?B?%s?=\n' "$SUJET_B64"
  printf 'Date: %s\n' "$(LC_ALL=C date -R)"
  printf 'MIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n\n'
  printf 'Serveur : %s\n\n%s\n' "$HOTE" "$CORPS"
} > "$MSG"

{
  printf 'url = "%s"\n' "$ALERTE_SMTP_URL"
  printf 'mail-from = "%s"\n' "$DE"
  # Un destinataire par ligne mail-rcpt.
  printf '%s' "$A" | tr ',' '\n' | while IFS= read -r r; do
    r=$(printf '%s' "$r" | tr -d ' ')
    [ -z "$r" ] || printf 'mail-rcpt = "%s"\n' "$r"
  done
  printf 'upload-file = "%s"\ncrlf\nsilent\nshow-error\nmax-time = 30\n' "$MSG"
  [ -z "$SECU" ] || printf 'ssl-reqd\n'
  [ -z "${ALERTE_CA_FILE:-}" ] || printf 'cacert = "%s"\n' "$ALERTE_CA_FILE"
  if [ -n "${ALERTE_SMTP_UTILISATEUR:-}" ]; then
    mdp=
    [ -z "${ALERTE_SMTP_MOT_DE_PASSE_FILE:-}" ] || mdp=$(tr -d '\r\n' < "$ALERTE_SMTP_MOT_DE_PASSE_FILE")
    printf 'user = "%s:%s"\n' "$(cfg "$ALERTE_SMTP_UTILISATEUR")" "$(cfg "$mdp")"
  fi
} > "$CFG"

curl --config "$CFG" && echo "Alerte envoyée à $A."
