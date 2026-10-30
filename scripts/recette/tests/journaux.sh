#!/bin/sh
# Verifie les journaux de la pile apres un parcours e2e : chaque ligne est un JSON valide
# et aucune ne contient de courriel @onea, de jeton Bearer ni de chaine de requete.
# Usage : sh scripts/recette/tests/journaux.sh
. "$(dirname "$0")/../lib.sh"

LOGS=$(mktemp)
trap 'rm -f "$LOGS"' EXIT
compose_recette logs --no-log-prefix web worker beat nginx >"$LOGS" 2>&1

affirmer "journaux non vides" '[ -s "$LOGS" ]'
affirmer "chaque ligne est un JSON valide" \
    'python3 -c "import json,sys
for l in open(sys.argv[1], encoding=\"utf-8\"):
    l = l.strip()
    if l: json.loads(l)" "$LOGS"'
affirmer "aucun courriel @onea" '! grep -q "@onea" "$LOGS"'
affirmer "aucun jeton Bearer" '! grep -q "Bearer " "$LOGS"'
affirmer "aucune chaine de requete" '! grep -qE "\?[^ \"]" "$LOGS"'

bilan
