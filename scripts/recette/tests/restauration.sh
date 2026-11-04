#!/bin/sh
# Exercice de restauration complet (lot 9, T18) sur la pile de RECETTE : peuplement, sauvegarde,
# destruction totale (down -v, dossiers supprimés), restauration sur pile vide, comparaison.
# DESTRUCTIF pour la recette : toutes ses données sont supprimées puis restaurées.
# Usage : sh scripts/recette/up.sh && sudo bash scripts/recette/tests/restauration.sh
# (bash : lib.sh retrouve son dossier par BASH_SOURCE ; le script se relance seul sous bash si besoin.)
# Doit être lancé en root (sudo) : backup.sh et restore.sh le sont.
# Vérifie : mêmes comptes par table, mêmes SHA-256 de 10 documents lus dans le stockage, volume
# onea-fichiers identique (empreinte de l'arborescence), fichier ajouté entre le dump et l'archive
# signalé comme orphelin (et seulement lui), gel en base rétabli, API prête après restauration,
# connexion réelle d'un compte de recette (scripts/recette/comptes.sh) avant et après restauration,
# manifeste altéré refusé, --hors-serveur refusé sans configuration, copie restic
# restaurable (si restic est installé), durée de remise en service < 30 min.
[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
. "$(dirname "$0")/../lib.sh"

[ "$(id -u)" -eq 0 ] || { echo "ERREUR : lancer en root (sudo)." >&2; exit 1; }
[ -f "$RECETTE_ENV" ] || { echo "ERREUR : pile de recette absente (scripts/recette/up.sh)." >&2; exit 1; }
SAUV="$RECETTE_DIR/sauvegardes"
DOCS=$(sed -n 's/^DOCUMENTS_HOST_DIR=//p' "$RECETTE_ENV")
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export ENV_FILE="$RECETTE_ENV"
export ONEA_COMPOSE_FICHIERS="$REPO_ROOT/scripts/recette/compose.override.yml"
rm -rf "$SAUV" "$DOCS"-avant-restauration-*

web_shell() { compose_recette exec -T web python manage.py shell -c "$1"; }
web_manage() { compose_recette exec -T web python manage.py "$@"; }

# releve_comptes : « modèle nombre », toutes tables (suppressions logiques incluses).
releve_comptes() {
    web_shell "
from django.apps import apps
for m in sorted(apps.get_models(), key=lambda m: m._meta.label):
    if m._meta.app_label in ('contenttypes', 'sessions'):
        continue
    print(m._meta.label, m._base_manager.count())
" | tr -d '\r'
}

# releve_volume : empreinte de l'arborescence du volume des pièces (chemins + SHA-256).
releve_volume() {
    compose_recette run --rm --no-deps -T --entrypoint sh web -c \
        'cd /var/lib/onea/fichiers && find . -type f | sort | xargs -r sha256sum | sha256sum' | tr -d '\r'
}

# empreintes_api <max> : « sha256 id » des versions de document de versions.txt, lues dans le stockage
# des documents par le conteneur web (les fichiers absents ou vides sont ignorés).
empreintes_api() {
    n=0
    for id in $(cat "$TMP/versions.txt"); do
        [ "$n" -lt "$1" ] || break
        sum=$(web_shell "
import hashlib
from apps.documents.models import DocumentVersion
v = DocumentVersion.all_objects.get(pk=$id)
try:
    with v.fichier_docx.open('rb') as f:
        print(hashlib.sha256(f.read()).hexdigest())
except Exception:
    print('')
" | tail -n 1 | tr -d '\r')
        case "$sum" in ''|e3b0c44298fc1c14*) continue ;; esac  # absent ou vide
        printf '%s %s\n' "$sum" "$id"
        n=$((n + 1))
    done
}

echo "== Peuplement (peupler_demo --profil formation, documents Word générés) =="
compose_recette stop beat worker worker-auth >/dev/null 2>&1 || true
# Faute de module de réglages « recette » (le garde de peupler_demo refuse les réglages prod), la
# commande tourne avec les réglages dev sur la base de la recette (rôle applicatif, documents réels).
compose_recette exec -T -e DJANGO_SETTINGS_MODULE=config.settings.dev web python manage.py peupler_demo --profil formation | tail -n 3

# Connexion réelle (formulaire, empreinte Argon2, session en base, droits du rôle applicatif sur
# les tables de l'authentification) : avant la sauvegarde, puis après la restauration. Le compte
# est préparé APRÈS peupler_demo (qui exige une base sans compte « admin ») et AVANT les relevés
# (son changement de mot de passe écrit une entrée d'audit, comprise dans la sauvegarde).
COMPTE=${RECETTE_COMPTE_ECRITURE:-admin}
sh "$REPO_ROOT/scripts/recette/comptes.sh" "$COMPTE"
connexion_et_session() {
    connexion_session "$TMP/session.jar" "$COMPTE" >/dev/null &&
        curl_recette -fs -o /dev/null -b "$TMP/session.jar" "https://$PUBLIC_HOST/api/v1/auth/session/"
}
affirmer "connexion de $COMPTE et session API avant la sauvegarde" 'connexion_et_session'
web_shell "
from apps.documents.models import DocumentVersion
for v in DocumentVersion.all_objects.exclude(fichier_docx='').order_by('-numero_version', 'pk')[:60]:
    print(v.pk)
" | tr -d '\r' > "$TMP/versions.txt"
affirmer "au moins un document Word généré (10 visés)" '[ "$(wc -l <"$TMP/versions.txt")" -ge 1 ]'
# Pièces justificatives : fichiers témoins écrits dans le volume (empreinte de l'arborescence).
compose_recette run --rm --no-deps -T --entrypoint sh web -c \
    'mkdir -p /var/lib/onea/fichiers/t18 && for i in 1 2 3; do head -c 8192 /dev/urandom > /var/lib/onea/fichiers/t18/temoin-$i.bin; done'
empreintes_api 10 > "$TMP/api-avant.txt"
releve_comptes > "$TMP/comptes-avant.txt"
releve_volume > "$TMP/volume-avant.txt"
# Orphelins déjà présents avant la sauvegarde (reliquats d'un essai précédent dans le dossier hôte).
liste_orphelins() {
    web_manage verifier_documents --orphelins 2>/dev/null | tr -d '\r' |
        sed -n '/^Orphelins :/,$p' | grep -v -e '^Orphelins :' -e 'orphelin(s) :' | sort
}
liste_orphelins > "$TMP/orphelins-avant.txt"
affirmer "au moins 3 documents lus dans le stockage (10 visés), empreintes non vides" '[ "$(wc -l <"$TMP/api-avant.txt")" -ge 3 ]'
affirmer "relevé des comptes non vide" '[ "$(wc -l <"$TMP/comptes-avant.txt")" -gt 20 ]'

echo "== Refus de --hors-serveur sans configuration =="
affirmer "backup.sh --hors-serveur sans RESTIC_REPOSITORY : refus, aucun jeu écrit" \
    '! env -u RESTIC_REPOSITORY -u RESTIC_PASSWORD_FILE sh "$REPO_ROOT/scripts/backup.sh" "$SAUV" --hors-serveur &&
     [ -z "$(ls "$SAUV" 2>/dev/null)" ]'

echo "== Sauvegarde (fichier ajouté entre le dump et l'archive) =="
cat > "$TMP/pause.sh" <<EOF
echo "fichier ecrit entre le dump et l'archive" > "$DOCS/orphelin-t18.txt"
chown 10001:10001 "$DOCS/orphelin-t18.txt"
EOF
mkdir -p "$SAUV"
ONEA_SAUVEGARDE_PAUSE="$TMP/pause.sh" sh "$REPO_ROOT/scripts/backup.sh" "$SAUV"
STAMP=$(ls "$SAUV" | sed -n 's/^manifeste-\(.*\)\.sha256$/\1/p' | tail -n 1)
affirmer "jeu de sauvegarde complet (3 fichiers + manifeste)" \
    '[ -n "$STAMP" ] && [ -f "$SAUV/onea-$STAMP.dump" ] &&
     [ -f "$SAUV/fichiers-$STAMP.tar.gz" ] && [ -f "$SAUV/documents-$STAMP.tar.gz" ] &&
     [ "$(wc -l <"$SAUV/manifeste-$STAMP.sha256")" -eq 3 ]'
affirmer "manifeste SHA-256 conforme" '(cd "$SAUV" && sha256sum -c "manifeste-$STAMP.sha256")'

echo "== Altération détectée avant toute modification =="
mkdir -p "$TMP/altere"
cp "$SAUV"/*-"$STAMP".* "$TMP/altere/"
# Un octet modifié au milieu de l'archive des documents.
printf 'X' | dd of="$TMP/altere/documents-$STAMP.tar.gz" bs=1 seek=100 conv=notrunc 2>/dev/null
affirmer "restore.sh refuse un jeu altéré (manifeste)" \
    '! sh "$REPO_ROOT/scripts/restore.sh" "$STAMP" --oui --dossier "$TMP/altere"'
affirmer "restore.sh --verifier signale aussi l'altération" \
    '! sh "$REPO_ROOT/scripts/restore.sh" "$STAMP" --verifier --dossier "$TMP/altere"'
affirmer "restore.sh sans --oui : refus (rien n'est modifié)" \
    '! sh "$REPO_ROOT/scripts/restore.sh" "$STAMP" --dossier "$SAUV"'
affirmer "pile intacte après les refus (API prête)" \
    'curl_recette -fs "https://$PUBLIC_HOST/api/v1/health/ready/"'

echo "== Copie hors serveur restic (dépôt local) =="
if command -v restic >/dev/null 2>&1; then
    export RESTIC_REPOSITORY="$RECETTE_DIR/depot-restic"
    export RESTIC_PASSWORD_FILE="$TMP/restic.pass"
    openssl rand -hex 24 > "$RESTIC_PASSWORD_FILE"
    chmod 0600 "$RESTIC_PASSWORD_FILE"
    affirmer "backup.sh --hors-serveur refuse un dépôt non initialisé" \
        '! sh "$REPO_ROOT/scripts/backup.sh" "$SAUV" --hors-serveur'
    # Le refus ci-dessus a tout de même écrit un jeu local : on le retire pour garder STAMP seul.
    for f in "$SAUV"/*; do
        case "$f" in *"$STAMP"*) ;; *) rm -f "$f" ;; esac
    done
    sh "$REPO_ROOT/scripts/backup.sh" "$SAUV" --hors-serveur --initialiser-depot
    STAMP_RESTIC=$(ls "$SAUV" | sed -n 's/^manifeste-\(.*\)\.sha256$/\1/p' | tail -n 1)
    affirmer "restic check du dépôt" 'restic check'
    affirmer "backup.sh --verifier-hors-serveur" 'sh "$REPO_ROOT/scripts/backup.sh" --verifier-hors-serveur'
    restic restore latest --target "$TMP/depot-restaure" >/dev/null
    COPIE=$(dirname "$(find "$TMP/depot-restaure" -name "manifeste-$STAMP_RESTIC.sha256" | head -n 1)")
    affirmer "instantané restic restauré : manifeste et empreintes conformes" \
        '[ -d "$COPIE" ] && (cd "$COPIE" && sha256sum -c "manifeste-$STAMP_RESTIC.sha256")'
    affirmer "instantané restic : fichiers identiques au jeu local" \
        'cmp "$COPIE/onea-$STAMP_RESTIC.dump" "$SAUV/onea-$STAMP_RESTIC.dump" &&
         cmp "$COPIE/documents-$STAMP_RESTIC.tar.gz" "$SAUV/documents-$STAMP_RESTIC.tar.gz"'
    unset RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
    STAMP=$STAMP_RESTIC
else
    echo "SKIP  restic absent : copie hors serveur non exercée."
fi

echo "== Destruction totale =="
compose_recette down -v --remove-orphans >/dev/null 2>&1
rm -rf "$DOCS"
mkdir -p "$DOCS"
chown 10001:10001 "$DOCS"
chmod 0750 "$DOCS"
affirmer "pile détruite (plus aucun conteneur ni volume)" \
    '[ -z "$(compose_recette ps -a -q)" ] && [ -z "$(docker volume ls -q --filter "label=com.docker.compose.project=$RECETTE_PROJECT")" ]'

echo "== Restauration sur pile vide =="
DEBUT=$(date +%s)
sh "$REPO_ROOT/scripts/restore.sh" "$STAMP" --oui --dossier "$SAUV"
RC=$?
FIN=$(date +%s)
DUREE=$((FIN - DEBUT))
affirmer "restore.sh terminé sans erreur" '[ "$RC" -eq 0 ]'
printf 'Durée de remise en service : %s min %s s\n' "$((DUREE / 60))" "$((DUREE % 60))"
affirmer "durée de remise en service < 30 min" '[ "$DUREE" -lt 1800 ]'

echo "== Comparaison =="
releve_comptes > "$TMP/comptes-apres.txt"
affirmer "mêmes comptes par table" 'diff "$TMP/comptes-avant.txt" "$TMP/comptes-apres.txt"'
releve_volume > "$TMP/volume-apres.txt"
affirmer "volume onea-fichiers : même arborescence et mêmes empreintes" \
    'diff "$TMP/volume-avant.txt" "$TMP/volume-apres.txt"'
# Mêmes versions qu'avant la destruction (liste figée dans api-avant.txt).
cut -d' ' -f2 "$TMP/api-avant.txt" > "$TMP/versions.txt"
empreintes_api 10 > "$TMP/api-apres.txt"
affirmer "mêmes SHA-256 pour les documents lus dans le stockage" 'diff "$TMP/api-avant.txt" "$TMP/api-apres.txt"'
web_manage verifier_documents --orphelins > "$TMP/docs.txt" 2>&1
affirmer "verifier_documents : 0 anomalie, 0 manquant" 'grep -q " 0 anomalie" "$TMP/docs.txt"'
{ cat "$TMP/orphelins-avant.txt"; echo orphelin-t18.txt; } | sort > "$TMP/orphelins-attendus.txt"
liste_orphelins > "$TMP/orphelins-apres.txt"
affirmer "verifier_documents --orphelins : l'orphelin du test et lui seul s'ajoute" \
    'diff "$TMP/orphelins-attendus.txt" "$TMP/orphelins-apres.txt"'
affirmer "l'orphelin n'est pas supprimé" '[ -f "$DOCS/orphelin-t18.txt" ]'
affirmer "dossier documents : 10001:10001, 0750" \
    '[ "$(stat -c "%u:%g %a" "$DOCS")" = "10001:10001 750" ]'
affirmer "ancien dossier des documents conservé (avant-restauration)" \
    '[ -d "$DOCS-avant-restauration-$STAMP" ]'
affirmer "gel en base et droits de onea_app rétablis" \
    'compose_recette run --rm --no-deps -T migrate python manage.py installer_gardes_sql --verifier --exiger-role'
tenter_suppression() {
    web_shell "
from django.db import connection
try:
    connection.cursor().execute('DELETE FROM referentiel_direction')
    print('SUPPRIME')
except Exception as e:
    print('REFUS', str(e).splitlines()[0])
" | tr -d '\r'
}
affirmer "DELETE refusé en base pour le rôle applicatif (gel actif)" \
    'tenter_suppression | grep -qE "^REFUS .*(permission denied|ERREUR ONEA)"'
affirmer "API prête après restauration (/api/v1/health/ready/)" \
    'curl_recette -fs "https://$PUBLIC_HOST/api/v1/health/ready/"'
affirmer "connexion de $COMPTE et session API après restauration (mot de passe sauvegardé)" \
    'connexion_et_session'
affirmer "changement de mot de passe possible après restauration (DELETE des codes par le rôle)" \
    'sh "$REPO_ROOT/scripts/recette/comptes.sh" "$COMPTE" >/dev/null && connexion_et_session'

bilan
