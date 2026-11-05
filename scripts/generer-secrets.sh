#!/bin/sh
# Génère les fichiers de secrets de la production (lot 9, T17, D16). Aucune dépendance : sh POSIX
# + /dev/urandom. JAMAIS d'écrasement : un fichier existant est conservé tel quel (rotation :
# docs/deploy.md, §3bis — on déplace l'ancien fichier, puis on relance le script).
#
#   sh scripts/generer-secrets.sh [--dossier DIR] [--proprietaire UID:GID]
#   sh scripts/generer-secrets.sh --verifier [--dossier DIR]
#   --sans-proprietaire : ne change pas le propriétaire (le recette le fait elle-même, via Docker).
#
# DIR vaut $ONEA_SECRETS_DIR par défaut (pas d'emplacement implicite). Dossier créé en 0700, fichiers
# en 0600 dès leur création (umask 077). Les fichiers appartiennent à --proprietaire (par défaut
# 10001:10001, l'utilisateur des conteneurs applicatifs, quand le script est lancé en root) : Compose
# monte les fichiers tels quels, sans pouvoir changer leur propriétaire ni leur mode.
# Les valeurs ne sont jamais affichées.
set -eu
umask 077

# Fichiers attendus. Deux sont créés VIDES : `email_password` (à renseigner seulement si le relais SMTP
# exige un mot de passe ; vide = mot de passe de EMAIL_URL, s'il y en a un) et `secret_key_fallbacks`
# (anciennes clés Django acceptées pendant une rotation, une par ligne ; vide = aucune).
SECRETS="secret_key secret_key_fallbacks postgres_password postgres_app_password redis_password meili_master_key metrics_token email_password"

usage() {
  echo "Usage : sh scripts/generer-secrets.sh [--verifier] [--dossier DIR] [--proprietaire UID:GID | --sans-proprietaire]" >&2
  exit 2
}

DOSSIER=${ONEA_SECRETS_DIR:-}
PROPRIETAIRE=
SANS_PROPRIETAIRE=0
VERIFIER=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dossier) [ $# -ge 2 ] || usage; DOSSIER=$2; shift 2 ;;
    --proprietaire) [ $# -ge 2 ] || usage; PROPRIETAIRE=$2; shift 2 ;;
    --verifier) VERIFIER=1; shift ;;
    --sans-proprietaire) SANS_PROPRIETAIRE=1; shift ;;
    *) usage ;;
  esac
done

if [ -z "$DOSSIER" ]; then
  echo "ERREUR : indiquer --dossier ou définir ONEA_SECRETS_DIR (ex. /etc/onea/secrets)." >&2
  exit 2
fi
case "$DOSSIER" in
  /*) ;;
  *) echo "ERREUR : le dossier des secrets doit être un chemin absolu." >&2; exit 2 ;;
esac
if [ -z "$PROPRIETAIRE" ] && [ "$SANS_PROPRIETAIRE" -eq 0 ] && [ "$(id -u)" -eq 0 ]; then
  PROPRIETAIRE=10001:10001
fi
case "$PROPRIETAIRE" in
  ""|[0-9]*:[0-9]*) ;;
  *) echo "ERREUR : --proprietaire attend UID:GID numériques." >&2; exit 2 ;;
esac

if [ "$VERIFIER" -eq 1 ]; then
  [ -d "$DOSSIER" ] || { echo "ERREUR : dossier $DOSSIER introuvable." >&2; exit 1; }
  statut=0
  if [ -n "$(find "$DOSSIER" -maxdepth 0 -perm /077 2>/dev/null)" ]; then
    echo "ERREUR : $DOSSIER est accessible au groupe ou aux autres (attendu 0700)." >&2
    statut=1
  fi
  for nom in $SECRETS; do
    f="$DOSSIER/$nom"
    if [ ! -f "$f" ] || [ -L "$f" ]; then
      echo "ERREUR : $nom absent (ou lien symbolique)." >&2
      statut=1
      continue
    fi
    if [ -n "$(find "$f" -maxdepth 0 -perm /077 2>/dev/null)" ]; then
      echo "ERREUR : $nom est accessible au groupe ou aux autres (attendu 0600)." >&2
      statut=1
    fi
    if [ "$nom" != email_password ] && [ "$nom" != secret_key_fallbacks ] && [ ! -s "$f" ]; then
      echo "ERREUR : $nom est vide." >&2
      statut=1
    fi
    if grep -qi '^CHANGE_ME' "$f" 2>/dev/null; then
      echo "ERREUR : $nom contient une valeur de modèle (CHANGE_ME)." >&2
      statut=1
    fi
  done
  [ "$statut" -eq 0 ] && echo "OK : secrets conformes dans $DOSSIER."
  exit "$statut"
fi

if [ ! -d "$DOSSIER" ]; then
  mkdir -p "$DOSSIER"
  chmod 0700 "$DOSSIER"
fi
[ -d "$DOSSIER" ] && [ ! -L "$DOSSIER" ] || { echo "ERREUR : $DOSSIER n'est pas un dossier ordinaire." >&2; exit 1; }

# Valeur aléatoire hexadécimale : $1 octets (2 caractères chacun), sans dépendance externe.
aleatoire() {
  od -An -tx1 -N "$1" /dev/urandom | tr -d ' \n'
}

crees=0
conserves=0
for nom in $SECRETS; do
  f="$DOSSIER/$nom"
  if [ -e "$f" ] || [ -L "$f" ]; then
    echo "conservé : $nom"
    conserves=$((conserves + 1))
    continue
  fi
  case "$nom" in
    secret_key) octets=48 ;;
    email_password | secret_key_fallbacks) octets=0 ;;
    *) octets=32 ;;
  esac
  # set -C (noclobber) : échec plutôt qu'écrasement si le fichier apparaît entre-temps.
  if [ "$octets" -eq 0 ]; then
    (set -C; : > "$f")
  else
    valeur=$(aleatoire "$octets")
    [ "${#valeur}" -eq $((octets * 2)) ] || { echo "ERREUR : /dev/urandom illisible." >&2; exit 1; }
    (set -C; printf '%s\n' "$valeur" > "$f")
    valeur=
  fi
  chmod 0600 "$f"
  if [ -n "$PROPRIETAIRE" ]; then
    chown "$PROPRIETAIRE" "$f"
  fi
  echo "créé     : $nom"
  crees=$((crees + 1))
done

echo "Terminé : $crees créé(s), $conserves conservé(s) dans $DOSSIER (aucun écrasement)."
if [ -z "$PROPRIETAIRE" ] && [ "$SANS_PROPRIETAIRE" -eq 0 ]; then
  echo "Attention : propriétaire non modifié ; les conteneurs (uid 10001) ne pourront lire ces fichiers" >&2
  echo "qu'après : chown 10001:10001 $DOSSIER/*  (ou relancer en root)." >&2
fi
