#!/bin/sh
# Test de charge de la recette (lot 9, T26) : 40 utilisateurs, montee 2/s, 20 min, seuils D10.
# Usage : sh scripts/recette/charge.sh   (apres up.sh et peupler_demo --profil volumetrie)
# Code de sortie : 0 si tous les seuils D10 sont tenus ET la file Celery est vide 2 min apres la fin.
# Variables : CHARGE_USERS (40), CHARGE_RATE (2), CHARGE_DUREE (20m), CHARGE_ATTENTE_FILE (120 s),
#             SEUIL_* (voir loadtest/locustfile.py). Tout seuil releve doit etre consigne.
# Sorties : .recette/charge/<horodatage>/ (CSV Locust, resume.json, docker-stats.csv, locust.log).
set -eu
. "$(dirname "$0")/lib.sh"

CHARGE_USERS=${CHARGE_USERS:-40}
CHARGE_RATE=${CHARGE_RATE:-2}
CHARGE_DUREE=${CHARGE_DUREE:-20m}
CHARGE_ATTENTE_FILE=${CHARGE_ATTENTE_FILE:-120}
OUT="$RECETTE_DIR/charge/$(date +%Y%m%d-%H%M%S)"
VENV="$RECETTE_DIR/venv-charge"
mkdir -p "$OUT"

[ -f "$RECETTE_DIR/comptes.txt" ] || { echo "comptes.txt absent : comptes de charge (session) a provisionner, voir loadtest/locustfile.py" >&2; exit 2; }
[ -f "$RECETTE_DIR/certs/ca.pem" ] || { echo "ca.pem absent : lancer certs.sh" >&2; exit 2; }

# Locust (MIT) dans un environnement isole, installe avec empreintes (aucune dependance non verifiee).
if [ ! -x "$VENV/bin/locust" ]; then
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --require-hashes -r "$REPO_ROOT/loadtest/requirements.txt"
fi

# Releves de CPU et de memoire par service, toutes les 30 s (docker stats).
echo "horodatage,service,cpu,memoire" > "$OUT/docker-stats.csv"
(
    while :; do
        ids=$(compose_recette ps -q 2>/dev/null || true)
        # shellcheck disable=SC2086
        [ -n "$ids" ] && docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' $ids |
            while IFS= read -r ligne; do printf '%s,%s\n' "$(date +%H:%M:%S)" "$ligne"; done >> "$OUT/docker-stats.csv"
        sleep 30
    done
) &
STATS_PID=$!
trap 'kill $STATS_PID 2>/dev/null || true' EXIT INT TERM

# Les noms d'hote de recette sont fictifs : resolution locale sans DNS ni /etc/hosts.
set +e
CHARGE_COMPTES="$RECETTE_DIR/comptes.txt" CHARGE_PREFIXE=charge \
CHARGE_RESOLVE="$PUBLIC_HOST=127.0.0.1" CHARGE_RESULTATS="$OUT" \
REQUESTS_CA_BUNDLE="$RECETTE_DIR/certs/ca.pem" \
    "$VENV/bin/locust" -f "$REPO_ROOT/loadtest/locustfile.py" --headless \
    --host "https://$PUBLIC_HOST" -u "$CHARGE_USERS" -r "$CHARGE_RATE" -t "$CHARGE_DUREE" \
    --csv "$OUT/locust" --only-summary > "$OUT/locust.log" 2>&1
RC=$?
set -e
tail -n 40 "$OUT/locust.log"

# File Celery videe 2 min apres la fin (liste Redis `celery` : taches en attente).
echo "Attente de ${CHARGE_ATTENTE_FILE} s avant de controler la file Celery..."
sleep "$CHARGE_ATTENTE_FILE"
FILE=$(compose_recette exec -T redis sh -c \
    'redis-cli -a "$(cat /run/secrets/redis_password)" --no-auth-warning llen celery' | tr -d '\r\n')
echo "File Celery : $FILE tache(s) en attente."
if [ "$FILE" != "0" ]; then
    echo "ECHEC : la file Celery n'est pas vide." >&2
    RC=1
fi
echo "Resultats : $OUT"
exit "$RC"
