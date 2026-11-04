#!/bin/sh
# Sauvegarde de la pile de production (lot 9, T18, D8) : dumps PostgreSQL (application),
# archive du volume des pièces justificatives (onea-fichiers), archive du dossier des documents,
# manifeste SHA-256, vérification de chaque artefact, copie hors serveur chiffrée (restic).
#
#   sh scripts/backup.sh [dossier]                         (défaut : ./backups)
#   sh scripts/backup.sh [dossier] --hors-serveur          (+ restic backup et restic forget)
#   sh scripts/backup.sh --hors-serveur --initialiser-depot (1re fois : crée le dépôt restic)
#   sh scripts/backup.sh --verifier-hors-serveur           (restic snapshots + restic check)
#
# Ordre : bases d'abord, fichiers ensuite. Un fichier écrit entre le dump et l'archive est donc un
# orphelin inoffensif (écriture unique), signalé par `verifier_documents --orphelins`, jamais supprimé.
# Chaque artefact est écrit en .tmp puis renommé ; le manifeste est écrit en dernier : un jeu sans
# manifeste est incomplet et refusé par restore.sh. En cas d'échec, les fichiers du jeu en cours
# sont retirés. Doit être lancé en root (sudo) : le dossier des documents appartient à 10001 (0750).
# Copie hors serveur : RESTIC_REPOSITORY et RESTIC_PASSWORD_FILE sont obligatoires (aucune valeur
# par défaut) ; le mot de passe n'est jamais passé en argument. docs/deploy.md, §7.
# Test uniquement : ONEA_SAUVEGARDE_PAUSE = chemin d'un script lancé entre les dumps et les archives.
set -eu
umask 077

ROOT=$(cd "$(dirname "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT/.env.prod"}
. "$ROOT/scripts/sauvegarde-lib.sh"

DEST=
HORS_SERVEUR=0
INITIALISER=0
VERIFIER_DEPOT=0
for arg in "$@"; do
  case "$arg" in
    --hors-serveur) HORS_SERVEUR=1 ;;
    --initialiser-depot) INITIALISER=1 ;;
    --verifier-hors-serveur) VERIFIER_DEPOT=1 ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    -*) echo "ERREUR : option inconnue : $arg" >&2; exit 2 ;;
    *) [ -z "$DEST" ] || { echo "ERREUR : un seul dossier de destination." >&2; exit 2; }
       DEST=$arg ;;
  esac
done
DEST=${DEST:-"$ROOT/backups"}
[ "$INITIALISER" -eq 0 ] || [ "$HORS_SERVEUR" -eq 1 ] || {
  echo "ERREUR : --initialiser-depot s'utilise avec --hors-serveur." >&2; exit 2; }

# --- Copie hors serveur : configuration exigée AVANT toute sauvegarde -------------------------------
exiger_restic() {
  command -v restic >/dev/null 2>&1 || {
    echo "ERREUR : restic est introuvable (apt install restic)." >&2; exit 1; }
  [ -n "${RESTIC_REPOSITORY:-}" ] || {
    echo "ERREUR : RESTIC_REPOSITORY est vide : la copie hors serveur exige un dépôt (docs/deploy.md, §7)." >&2
    exit 1; }
  [ -n "${RESTIC_PASSWORD_FILE:-}" ] || {
    echo "ERREUR : RESTIC_PASSWORD_FILE est vide : la copie hors serveur exige un fichier de mot de passe." >&2
    exit 1; }
  [ -f "$RESTIC_PASSWORD_FILE" ] && [ -s "$RESTIC_PASSWORD_FILE" ] || {
    echo "ERREUR : $RESTIC_PASSWORD_FILE est introuvable ou vide." >&2; exit 1; }
  [ -z "$(find "$RESTIC_PASSWORD_FILE" -maxdepth 0 -perm /077)" ] || {
    echo "ERREUR : $RESTIC_PASSWORD_FILE doit être en 0600 (chmod 600)." >&2; exit 1; }
  export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
}

if [ "$VERIFIER_DEPOT" -eq 1 ]; then
  exiger_restic
  restic snapshots --tag onea-sauvegarde --group-by host,tags --compact
  restic check --read-data-subset=10%
  echo "OK : dépôt restic vérifié."
  exit 0
fi
[ "$HORS_SERVEUR" -eq 0 ] || exiger_restic

[ -f "$ENV_FILE" ] || { echo "ERREUR : $ENV_FILE introuvable." >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || {
  echo "ERREUR : la sauvegarde des documents doit être lancée en root (sudo)." >&2; exit 1; }
DOCS_REAL=$(dossier_documents)
mkdir -p "$DEST"
STAMP=$(date +%Y%m%d-%H%M%S)

SUCCES=0
nettoyer() {
  [ "$SUCCES" -eq 1 ] && return 0
  rm -f "$DEST"/*-"$STAMP".*
  echo "ERREUR : sauvegarde $STAMP interrompue ; les fichiers du jeu ont été retirés." >&2
}
trap nettoyer EXIT

# --- Bases PostgreSQL -------------------------------------------------------------------------------
dump() { # <service> <préfixe>
  _tmp="$DEST/$2-$STAMP.dump.tmp"
  # POSTGRES_USER / POSTGRES_DB sont lus dans le conteneur : aucun secret ne le quitte.
  compose exec -T "$1" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$_tmp" \
    || { rm -f "$_tmp"; echo "ERREUR : la sauvegarde de $1 a échoué." >&2; exit 1; }
  [ -s "$_tmp" ] || { rm -f "$_tmp"; echo "ERREUR : dump de $1 vide." >&2; exit 1; }
  # Vérification : le sommaire du dump doit se relire (pg_restore --list, dans le conteneur).
  compose exec -T "$1" pg_restore --list < "$_tmp" >/dev/null \
    || { rm -f "$_tmp"; echo "ERREUR : le dump de $1 est illisible (pg_restore --list)." >&2; exit 1; }
  mv "$_tmp" "$DEST/$2-$STAMP.dump"
}
dump db onea

# Crochet de test : écrire un fichier entre les dumps et les archives (devient un orphelin).
if [ -n "${ONEA_SAUVEGARDE_PAUSE:-}" ] && [ -f "$ONEA_SAUVEGARDE_PAUSE" ]; then
  sh "$ONEA_SAUVEGARDE_PAUSE"
fi

# --- Archives de fichiers ---------------------------------------------------------------------------
archiver() { # <préfixe> <code de sortie tar> <fichier .tmp>
  tar_tolerant "$2" || { rm -f "$3"; echo "ERREUR : l'archive $1 a échoué (code $2)." >&2; exit 1; }
  [ -s "$3" ] || { rm -f "$3"; echo "ERREUR : archive $1 vide." >&2; exit 1; }
  tar -tzf "$3" >/dev/null 2>&1 \
    || { rm -f "$3"; echo "ERREUR : l'archive $1 est illisible (tar -tzf)." >&2; exit 1; }
  mv "$3" "$DEST/$1-$STAMP.tar.gz"
}

# Volume des pièces justificatives (FICHIERS_RACINE) : lu par un conteneur jetable de l'image web,
# en 10001 (propriétaire). Aucune dépendance aux chemins internes de Docker.
rc=0
compose run --rm --no-deps -T --entrypoint tar web -czf - -C /var/lib/onea/fichiers . \
  > "$DEST/fichiers-$STAMP.tar.gz.tmp" || rc=$?
archiver fichiers "$rc" "$DEST/fichiers-$STAMP.tar.gz.tmp"

# Dossier des documents (bind mount hôte).
rc=0
tar -czf "$DEST/documents-$STAMP.tar.gz.tmp" -C "$DOCS_REAL" . || rc=$?
archiver documents "$rc" "$DEST/documents-$STAMP.tar.gz.tmp"

# --- Manifeste SHA-256 (écrit en dernier) et contre-vérification ------------------------------------
(
  cd "$DEST"
  sha256sum "onea-$STAMP.dump" "fichiers-$STAMP.tar.gz" \
    "documents-$STAMP.tar.gz" > "manifeste-$STAMP.sha256.tmp"
  sha256sum -c "manifeste-$STAMP.sha256.tmp" >/dev/null
  mv "manifeste-$STAMP.sha256.tmp" "manifeste-$STAMP.sha256"
)
SUCCES=1

# --- Conservation locale : 14 jeux ------------------------------------------------------------------
for prefix in onea; do
  ls -1t "$DEST"/"$prefix"-*.dump 2>/dev/null | tail -n +15 | while read -r old; do rm -f "$old"; done
done
for prefix in documents fichiers; do
  ls -1t "$DEST"/"$prefix"-*.tar.gz 2>/dev/null | tail -n +15 | while read -r old; do rm -f "$old"; done
done
ls -1t "$DEST"/manifeste-*.sha256 2>/dev/null | tail -n +15 | while read -r old; do rm -f "$old"; done

echo "OK : sauvegarde $STAMP écrite et vérifiée dans $DEST (manifeste-$STAMP.sha256)."

# --- Copie hors serveur chiffrée --------------------------------------------------------------------
if [ "$HORS_SERVEUR" -eq 1 ]; then
  if ! restic cat config >/dev/null 2>&1; then
    if [ "$INITIALISER" -eq 1 ]; then
      restic init
    else
      echo "ERREUR : dépôt restic absent ou inaccessible (restic init, ou --initialiser-depot)." >&2
      echo "         La sauvegarde locale $STAMP est conservée." >&2
      exit 1
    fi
  fi
  # Les archives « avant-restauration » de restore.sh restent sur le serveur ; ne pas les copier.
  restic backup --tag onea-sauvegarde --host onea \
    --exclude '*.tmp' --exclude 'avant-restauration-*' "$DEST"
  # group-by host,tags : le dossier est le même d'un jour à l'autre, mais ne jamais regrouper par chemin.
  restic forget --tag onea-sauvegarde --host onea --group-by host,tags \
    --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune
  echo "OK : copie hors serveur chiffrée (restic) terminée."
fi
