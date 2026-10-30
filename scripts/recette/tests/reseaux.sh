#!/bin/sh
# Banc d'essai du cloisonnement reseau et de la peripherie sur la pile de recette.
# Usage : sh scripts/recette/up.sh && sh scripts/recette/realm.sh && sh scripts/recette/tests/reseaux.sh
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

for s in web worker; do
    affirmer "$s : keycloak:8080 injoignable" '! tcp '"$s"' keycloak 8080'
    affirmer "$s : keycloak:9000 injoignable" '! tcp '"$s"' keycloak 9000'
done
affirmer "frontend : keycloak:8080 injoignable" \
    '! compose_recette exec -T frontend sh -c "nc -z -w 3 keycloak 8080"'
affirmer "frontend : keycloak:9000 injoignable" \
    '! compose_recette exec -T frontend sh -c "nc -z -w 3 keycloak 9000"'
affirmer "frontend : web:8000 injoignable" \
    '! compose_recette exec -T frontend sh -c "nc -z -w 3 web 8000"'
affirmer "web : realm onea joignable via nginx (https://SSO_HOST)" \
    "compose_recette exec -T web python -c \"import os,urllib.request as u; u.urlopen('https://$SSO_HOST/realms/onea', timeout=10)\""
affirmer "web : aucune sortie vers Internet" '! sortie web'
affirmer "gotenberg : aucune sortie vers Internet" \
    '! compose_recette exec -T gotenberg sh -c "curl -s -m 3 -o /dev/null https://1.1.1.1"'

# Adresse du client : X-Forwarded-For / X-Real-IP usurpes ne doivent jamais etre enregistres.
affirmer "adresse usurpee 6.6.6.6 absente du journal d'audit, adresse reelle presente" '
    tok=$(sh "$RECETTE_LIB_DIR/token.sh" admin 2>/dev/null) &&
    code="Z$(date +%s | tail -c 6)" &&
    curl_recette -fs -o /dev/null -H "Authorization: Bearer $tok" -H "X-Forwarded-For: 6.6.6.6" \
        -H "X-Real-IP: 6.6.6.6" -H "Content-Type: application/json" -X POST \
        -d "{\"code\":\"$code\",\"libelle\":\"Recette reseau\",\"type\":\"DIRECTION\"}" "$A/api/v1/directions/" &&
    adr=$(compose_recette exec -T web python manage.py shell -c "
from auditlog.models import LogEntry
e = LogEntry.objects.filter(object_repr__contains=\"$code\").order_by(\"-pk\").first()
print(e.remote_addr if e else \"AUCUNE\")" | tail -n 1 | tr -d "\r") &&
    [ -n "$adr" ] && [ "$adr" != "AUCUNE" ] && [ "$adr" != "6.6.6.6" ]'

# API admin Keycloak : joignable depuis web (sync de comptes), console et realm master non.
affirmer "web : API admin Keycloak du realm onea atteinte (401 sans jeton, pas 404)" '
    c=$(compose_recette exec -T web python -c "
import urllib.request as u, urllib.error as e
try:
    u.urlopen(\"https://$SSO_HOST/admin/realms/onea/users\", timeout=10)
except e.HTTPError as x:
    print(x.code)" | tail -n 1 | tr -d "\r"); [ "$c" = 401 ]'
affirmer "console Keycloak /admin/master/console/ -> 404 pour un client externe" \
    '[ "$(curl_recette -s -o /dev/null -w "%{http_code}" "https://$SSO_HOST/admin/master/console/")" = 404 ]'
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
