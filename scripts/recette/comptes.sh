#!/bin/sh
# Comptes de la pile de RECETTE, crees par les outils de l'application (aucun mecanisme propre
# aux tests) et fichier .recette/comptes.txt ($RECETTE_COMPTES, 0600, hors Git) :
#   1. `creer_administrateur` dans le conteneur web : mot de passe temporaire lu sur la sortie
#      de `exec` (jamais ecrit dans les journaux) ; si le compte existe deja, la commande le
#      reinitialise (nouveau mot de passe temporaire, sessions fermees, code par courriel coupe) ;
#   2. connexion par le formulaire (/auth/csrf/ puis /auth/login/ : etape CHANGER_MOT_DE_PASSE) ;
#   3. changement impose par l'API (/auth/password/change/) vers un mot de passe aleatoire ;
#   4. ligne `identifiant:mot_de_passe` dans le fichier des comptes (remplace l'ancienne).
# Aucun mot de passe ne passe en argument d'un processus (variables d'environnement d'un seul
# processus, corps JSON sur l'entree standard de curl).
# Usage : sh scripts/recette/up.sh && sh scripts/recette/comptes.sh [identifiant]
# Defaut : $RECETTE_COMPTE_ECRITURE, sinon admin (compte attendu par tests/reseaux.sh).
set -eu
. "$(dirname "$0")/lib.sh"
A="https://$PUBLIC_HOST"
IDENTIFIANT=${1:-${RECETTE_COMPTE_ECRITURE:-admin}}
COURRIEL="$IDENTIFIANT@recette.test"

[ -f "$RECETTE_ENV" ] || { echo "ERREUR : pile de recette absente (scripts/recette/up.sh)." >&2; exit 1; }
umask 077
JAR=$(mktemp)
ENTETES=$(mktemp)
trap 'rm -f "$JAR" "$ENTETES"' EXIT

# corps_json <cle=VARIABLE>... : objet JSON dont chaque valeur est lue dans l'environnement.
corps_json() {
    python3 -c '
import json, os, sys
print(json.dumps({c: os.environ[v] for c, v in (a.split("=", 1) for a in sys.argv[1:])}))
' "$@"
}

# poster <chemin> <jeton> : POST du corps JSON lu sur l'entree standard, avec le jar de session ;
# affiche le corps de la reponse puis, sur la derniere ligne, le code HTTP.
poster() {
    curl_recette -s -D "$ENTETES" -c "$JAR" -b "$JAR" \
        -H "X-CSRFToken: $2" -H "Referer: $A/" -H "Content-Type: application/json" \
        --data-binary @- -w '\n%{http_code}' "$A$1"
}

# champ <nom> : valeur d'un champ du JSON lu sur l'entree standard (vide si absent).
champ() {
    python3 -c 'import json, sys; print(json.load(sys.stdin).get(sys.argv[1]) or "")' "$1"
}

echo "== Compte de recette « $IDENTIFIANT » =="
SORTIE=$(compose_recette exec -T web python manage.py creer_administrateur \
    --identifiant "$IDENTIFIANT" --courriel "$COURRIEL" --desactiver-otp | tr -d '\r')
TEMPORAIRE=$(printf '%s\n' "$SORTIE" | sed -n 's/^Mot de passe temporaire : //p')
[ -n "$TEMPORAIRE" ] || { echo "ERREUR : mot de passe temporaire introuvable dans la sortie de creer_administrateur." >&2; exit 1; }
DEFINITIF=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')

: > "$JAR"
TOK=$(jeton_csrf "$JAR")
REP=$(ONEA_ID=$IDENTIFIANT ONEA_MDP=$TEMPORAIRE corps_json identifiant=ONEA_ID mot_de_passe=ONEA_MDP |
    poster /api/v1/auth/login/ "$TOK")
CODE=$(printf '%s\n' "$REP" | tail -n 1)
ETAPE=$(printf '%s\n' "$REP" | sed '$d' | champ etape)
if [ "$CODE" != 200 ] || [ "$ETAPE" != CHANGER_MOT_DE_PASSE ]; then
    echo "ERREUR : connexion avec le mot de passe temporaire : HTTP $CODE, etape « $ETAPE »." >&2
    grep -i '^retry-after:' "$ENTETES" >&2 || true
    exit 1
fi
TOK=$(jeton_csrf "$JAR")  # Django renouvelle le jeton CSRF a la connexion
REP=$(ONEA_ANCIEN=$TEMPORAIRE ONEA_NOUVEAU=$DEFINITIF corps_json ancien=ONEA_ANCIEN nouveau=ONEA_NOUVEAU |
    poster /api/v1/auth/password/change/ "$TOK")
CODE=$(printf '%s\n' "$REP" | tail -n 1)
ETAPE=$(printf '%s\n' "$REP" | sed '$d' | champ etape)
if [ "$CODE" != 200 ] || [ "$ETAPE" != OK ]; then
    echo "ERREUR : changement du mot de passe temporaire : HTTP $CODE, etape « $ETAPE »." >&2
    exit 1
fi

mkdir -p "$RECETTE_DIR"
touch "$RECETTE_COMPTES"
chmod 0600 "$RECETTE_COMPTES"
awk -v u="$IDENTIFIANT" 'index($0, u ":") != 1' "$RECETTE_COMPTES" > "$RECETTE_COMPTES.tmp"
printf '%s:%s\n' "$IDENTIFIANT" "$DEFINITIF" >> "$RECETTE_COMPTES.tmp"
mv "$RECETTE_COMPTES.tmp" "$RECETTE_COMPTES"
chmod 0600 "$RECETTE_COMPTES"

# Controle : la connexion avec le mot de passe definitif aboutit a l'etape OK.
connexion_session "$JAR" "$IDENTIFIANT" >/dev/null
echo "Compte « $IDENTIFIANT » pret (mot de passe definitif dans $RECETTE_COMPTES)."
