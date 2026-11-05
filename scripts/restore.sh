#!/bin/sh
# Restauration d'un jeu de sauvegarde de la production (lot 9, T18, D8).
#
#   sh scripts/restore.sh <horodatage> --oui [--dossier DIR]   restaure (DESTRUCTIF)
#   sh scripts/restore.sh <horodatage> --verifier [--dossier DIR]   vérifie le jeu, ne modifie rien
#
# <horodatage> : AAAAMMJJ-HHMMSS (nom des fichiers de backup.sh). Sans --oui, rien n'est modifié.
# Copie hors serveur : `restic restore latest --target /srv/onea-restauration`, puis
#   --dossier /srv/onea-restauration/<dossier de sauvegarde d'origine>.
# Déroulement : contrôle du manifeste SHA-256 (refus au moindre écart) ; arrêt de web, des workers et beat ;
# restauration de la base applicative (pg_restore --clean --if-exists --single-transaction) ; ré-installation des déclencheurs de gel et des droits
# (installer_gardes_sql, que pg_restore ne rétablit pas de façon sûre) ; dossier des documents
# déplacé en <dossier>-avant-restauration-<horodatage> puis archive extraite (10001:10001, 0750) ;
# volume onea-fichiers sauvegardé dans <dossier de sauvegarde>/avant-restauration-fichiers-<horodatage>.tar.gz
# puis remplacé ; redémarrage ; réindexation de la recherche ; verifier_documents (code 1 si un fichier
# référencé manque ou est altéré), --orphelins (informatif), verifier_pieces. Code 1 si une vérification
# échoue. Doit être lancé en root, depuis le dépôt du serveur. docs/deploy.md, §7.
set -eu
umask 077

ROOT=$(cd "$(dirname "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT/.env.prod"}
. "$ROOT/scripts/sauvegarde-lib.sh"

STAMP=
DEST=
OUI=0
VERIFIER=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --oui) OUI=1 ;;
    --verifier) VERIFIER=1 ;;
    --dossier) [ "$#" -ge 2 ] || { echo "ERREUR : --dossier attend un chemin." >&2; exit 2; }
               DEST=$2; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    -*) echo "ERREUR : option inconnue : $1" >&2; exit 2 ;;
    *) [ -z "$STAMP" ] || { echo "ERREUR : un seul horodatage." >&2; exit 2; }
       STAMP=$1 ;;
  esac
  shift
done
DEST=${DEST:-"$ROOT/backups"}
case "$STAMP" in
  [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]) ;;
  *) echo "Usage : sh scripts/restore.sh <AAAAMMJJ-HHMMSS> --oui|--verifier [--dossier DIR]" >&2; exit 2 ;;
esac
if [ "$OUI" -eq 0 ] && [ "$VERIFIER" -eq 0 ]; then
  echo "REFUS : la restauration remplace la base et les fichiers. Ajouter --oui pour confirmer" >&2
  echo "        (ou --verifier pour contrôler le jeu $STAMP sans rien modifier)." >&2
  exit 2
fi
[ -f "$ENV_FILE" ] || { echo "ERREUR : $ENV_FILE introuvable." >&2; exit 1; }
[ -d "$DEST" ] || { echo "ERREUR : dossier de sauvegarde introuvable : $DEST" >&2; exit 1; }
DEST=$(cd "$DEST" && pwd -P)
DEBUT=$(date +%s)

# --- 1. Contrôle du jeu : manifeste, empreintes, lisibilité ------------------------------------------
MANIFESTE="$DEST/manifeste-$STAMP.sha256"
[ -f "$MANIFESTE" ] || {
  echo "ERREUR : $MANIFESTE absent : jeu incomplet ou antérieur au manifeste, restauration refusée." >&2
  exit 1; }
for f in "onea-$STAMP.dump" "fichiers-$STAMP.tar.gz" "documents-$STAMP.tar.gz"; do
  grep -q "  $f\$" "$MANIFESTE" || { echo "ERREUR : $f absent du manifeste." >&2; exit 1; }
done
( cd "$DEST" && sha256sum -c "manifeste-$STAMP.sha256" ) || {
  echo "ERREUR : empreinte SHA-256 différente du manifeste : jeu altéré, restauration refusée." >&2
  exit 1; }
for f in "documents-$STAMP.tar.gz" "fichiers-$STAMP.tar.gz"; do
  tar -tzf "$DEST/$f" >/dev/null 2>&1 || { echo "ERREUR : $f illisible (tar -tzf)." >&2; exit 1; }
done
compose up -d --no-deps --wait db
attendre_postgres db
for pair in "db:onea"; do
  compose exec -T "${pair%%:*}" pg_restore --list < "$DEST/${pair##*:}-$STAMP.dump" >/dev/null \
    || { echo "ERREUR : dump ${pair##*:} illisible (pg_restore --list)." >&2; exit 1; }
done
echo "Jeu $STAMP : manifeste et empreintes conformes, dumps et archives lisibles."
[ "$VERIFIER" -eq 0 ] || exit 0

[ "$(id -u)" -eq 0 ] || { echo "ERREUR : la restauration doit être lancée en root (sudo)." >&2; exit 1; }
DOCS_REAL=$(dossier_documents)
DOCS_AVANT="$DOCS_REAL-avant-restauration-$STAMP"
[ ! -e "$DOCS_AVANT" ] || { echo "ERREUR : $DOCS_AVANT existe déjà." >&2; exit 1; }

# --- 2. Arrêt des services qui écrivent -------------------------------------------------------------
echo "Arrêt de web, worker, worker-auth, beat..."
compose stop web worker worker-auth beat

# --- 3. Bases PostgreSQL ----------------------------------------------------------------------------
restaurer_base() { # <service> <préfixe>
  echo "Restauration de $2..."
  compose exec -T "$1" sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --single-transaction --no-owner' \
    < "$DEST/$2-$STAMP.dump"
}
restaurer_base db onea || {
  echo "ERREUR : restauration de la base applicative échouée (rôle applicatif absent ? voir docs/deploy.md, §7bis)." >&2
  exit 1
}

# Déclencheurs de gel et droits de onea_app : rétablis par le code (jamais par confiance dans le dump).
compose run --rm --no-deps -T migrate python manage.py installer_gardes_sql

# --- 4. Dossier des documents -----------------------------------------------------------------------
echo "Restauration du dossier des documents..."
if mv "$DOCS_REAL" "$DOCS_AVANT" 2>/dev/null; then
  mkdir "$DOCS_REAL"
else
  # Le dossier est un point de montage : on déplace son contenu.
  mkdir "$DOCS_AVANT"
  find "$DOCS_REAL" -mindepth 1 -maxdepth 1 -exec mv {} "$DOCS_AVANT"/ \;
fi
tar -xzf "$DEST/documents-$STAMP.tar.gz" -C "$DOCS_REAL"
chown 10001:10001 "$DOCS_REAL"
chown -R 10001:10001 "$DOCS_REAL"
chmod 0750 "$DOCS_REAL"
chmod 0750 "$DOCS_AVANT"

# --- 5. Volume des pièces justificatives ------------------------------------------------------------
echo "Restauration du volume onea-fichiers (copie de sûreté préalable)..."
AVANT_FICHIERS="$DEST/avant-restauration-fichiers-$STAMP.tar.gz"
compose run --rm --no-deps -T --entrypoint tar web -czf - -C /var/lib/onea/fichiers . > "$AVANT_FICHIERS"
compose run --rm --no-deps -T --entrypoint sh web -c \
  'find /var/lib/onea/fichiers -mindepth 1 -delete && tar -xzf - -C /var/lib/onea/fichiers' \
  < "$DEST/fichiers-$STAMP.tar.gz"

# --- 6. Redémarrage ---------------------------------------------------------------------------------
echo "Redémarrage..."
compose up -d --wait --wait-timeout 600

# --- 7. Vérifications -------------------------------------------------------------------------------
ECHEC=0
echo "Gel en base et droits :"
compose run --rm --no-deps -T migrate python manage.py installer_gardes_sql --verifier --exiger-role \
  || ECHEC=1
echo "Réindexation de la recherche (reconstructible, non sauvegardée) :"
compose exec -T web python manage.py reindexer \
  || echo "AVERTISSEMENT : réindexation impossible ; relancer 'manage.py reindexer' (non bloquant)." >&2
echo "Documents (empreintes) :"
compose exec -T web python manage.py verifier_documents || ECHEC=1
echo "Documents orphelins (informatif, rien n'est supprimé) :"
compose exec -T web python manage.py verifier_documents --orphelins || true
echo "Pièces justificatives (empreintes ; un orphelin seul est informatif) :"
ECARTS=$(mktemp)
trap 'rm -f "$ECARTS"' EXIT
compose exec -T web python manage.py verifier_pieces 2>"$ECARTS" || true
cat "$ECARTS" >&2
if grep '^ECART' "$ECARTS" | grep -qv 'fichier orphelin'; then
  echo "ERREUR : pièce absente ou altérée." >&2
  ECHEC=1
fi

DUREE=$(( $(date +%s) - DEBUT ))
echo "Durée de la restauration : $((DUREE / 60)) min $((DUREE % 60)) s."
if [ "$ECHEC" -ne 0 ]; then
  echo "ERREUR : restauration terminée mais au moins une vérification a échoué." >&2
  exit 1
fi
echo "OK : jeu $STAMP restauré. Dossier des documents d'avant : $DOCS_AVANT (à supprimer après contrôle)."
