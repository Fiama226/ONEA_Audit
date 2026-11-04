#!/bin/sh
# Banc d'essai du cloisonnement reseau et de la peripherie sur la pile de recette.
# Usage : sh scripts/recette/up.sh && sh scripts/recette/tests/reseaux.sh
. "$(dirname "$0")/../lib.sh"
A="https://$PUBLIC_HOST"

# tcp <service> <hote> <port> : 0 si la connexion TCP aboutit (python du conteneur applicatif,
# sinon wget/nc selon l'image).
tcp() {
    compose_recette exec -T "$1" python -c \
        "import socket,sys; socket.create_connection(('$2',$3),3).close()" 2>/dev/null
}
# sortie <service> : 0 si une connexion vers Internet aboutit.
sortie() {
    compose_recette exec -T "$1" python -c \
        "import socket; socket.create_connection(('1.1.1.1',443),3).close()" 2>/dev/null
}

affirmer "frontend : web:8000 injoignable" \
    '! compose_recette exec -T frontend sh -c "nc -z -w 3 web 8000"'
affirmer "web : aucune sortie vers Internet" '! sortie web'
affirmer "gotenberg : aucune sortie vers Internet" \
    '! compose_recette exec -T gotenberg sh -c "curl -s -m 3 -o /dev/null https://1.1.1.1"'

# Adresse du client : X-Forwarded-For / X-Real-IP usurpes ne doivent jamais etre enregistres.
# Connexion par session avec un compte de recette habilite a creer une direction (defaut : admin,
# $RECETTE_COMPTE_ECRITURE), puis une ecriture portant les en-tetes usurpes ; l'adresse enregistree
# par le journal d'audit doit etre celle vue par nginx, pas 6.6.6.6.
JAR="$RECETTE_DIR/session-reseaux.jar"
affirmer "adresse usurpee 6.6.6.6 absente du journal d'audit, adresse reelle presente" '
    tok=$(connexion_session "$JAR" "${RECETTE_COMPTE_ECRITURE:-admin}") && [ -n "$tok" ] &&
    code="Z$(date +%s | tail -c 6)" &&
    curl_recette -fs -o /dev/null -b "$JAR" -H "X-CSRFToken: $tok" -H "Referer: $A/"         -H "X-Forwarded-For: 6.6.6.6" -H "X-Real-IP: 6.6.6.6" -H "Content-Type: application/json" -X POST         -d "{\"code\":\"$code\",\"libelle\":\"Recette reseau\",\"type\":\"DIRECTION\"}" "$A/api/v1/directions/" &&
    adr=$(compose_recette exec -T web python manage.py shell -c "
from auditlog.models import LogEntry
e = LogEntry.objects.filter(object_repr__contains=\"$code\").order_by(\"-pk\").first()
print(e.remote_addr if e else \"AUCUNE\")" | tail -n 1 | tr -d "\r") &&
    [ -n "$adr" ] && [ "$adr" != "AUCUNE" ] && [ "$adr" != "6.6.6.6" ]'
rm -f "$JAR"

# Debit : 300 requetes en une seconde depuis une adresse -> au moins une 429.
affirmer "300 requetes/s -> au moins une 429" '
    n=$(seq 1 300 | xargs -P 100 -I{} curl -sk -o /dev/null -w "%{http_code}\n" \
        --resolve "$PUBLIC_HOST:443:127.0.0.1" "$A/api/v1/health/" | grep -c 429); [ "$n" -ge 1 ]'

# Tailles de corps.
head -c 2097152 /dev/zero > "$RECETTE_DIR/2mo.bin"
head -c 58720256 /dev/zero > "$RECETTE_DIR/56mo.bin"
affirmer "2 Mo hors /api/ -> 413" \
    '[ "$(curl_recette -s -o /dev/null -w "%{http_code}" -X POST --data-binary @"$RECETTE_DIR/2mo.bin" "$A/")" = 413 ]'
affirmer "56 Mo sur /api/ -> 413" \
    '[ "$(curl_recette -s -o /dev/null -w "%{http_code}" -X POST --data-binary @"$RECETTE_DIR/56mo.bin" "$A/api/v1/health/")" = 413 ]'
rm -f "$RECETTE_DIR/2mo.bin" "$RECETTE_DIR/56mo.bin"

# Journal d'acces : JSON valide, sans "?".
affirmer "journal d'acces : chaque ligne JSON valide, sans '?'" '
    curl_recette -s -o /dev/null "$A/api/v1/health/?secret=abc";
    compose_recette logs --no-log-prefix --tail 50 nginx 2>/dev/null > "$RECETTE_DIR/acces.log";
    [ -s "$RECETTE_DIR/acces.log" ] && ! grep -q "?" "$RECETTE_DIR/acces.log" &&
    python3 -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" "$RECETTE_DIR/acces.log"'

bilan
