#!/bin/sh
# Banc d'essai TLS de la peripherie sur la pile de recette (sslyze, conteneur epingle).
# Usage : sh scripts/recette/up.sh && sh scripts/recette/tests/tls.sh
# sslyze (AGPL-3.0 : outil d'essai uniquement, jamais livre) s'execute dans un conteneur
# lance sur le reseau de l'hote, avec l'AC de recette montee en lecture seule.
. "$(dirname "$0")/../lib.sh"
SSLYZE_IMAGE=${SSLYZE_IMAGE:-python:3.12-slim}
SSLYZE_VERSION=${SSLYZE_VERSION:-6.0.0}

# sslyze <hote> : rapport JSON sur la sortie standard. --network host + --resolve impossible :
# l'hote fictif est resolu vers 127.0.0.1 via --add-host.
sslyze_json() {
    docker run --rm --network host --add-host "$1:127.0.0.1" \
        -v "$RECETTE_DIR/certs/ca.pem:/ca.pem:ro" "$SSLYZE_IMAGE" sh -c \
        "pip install -q --disable-pip-version-check sslyze==$SSLYZE_VERSION >/dev/null 2>&1 && \
         sslyze --json_out=- --certinfo --sslv2 --sslv3 --tlsv1 --tlsv1_1 --tlsv1_2 --tlsv1_3 \
         --http_headers $1:443 2>/dev/null"
}

mkdir -p "$RECETTE_DIR/tmp"
for h in "$PUBLIC_HOST" "$SSO_HOST"; do
    j="$RECETTE_DIR/tmp/sslyze-$h.json"
    sslyze_json "$h" > "$j" || true
    # Les assertions lisent le JSON avec python (present dans l'image sslyze, pas sur l'hote).
    q() { docker run --rm -v "$j:/r.json:ro" "$SSLYZE_IMAGE" python -c "$1"; }
    affirmer "$h : rapport sslyze exploitable" '[ -s "$j" ]'
    for v in ssl_2_0 ssl_3_0 tls_1_0 tls_1_1; do
        affirmer "$h : $v refuse" q "import json;r=json.load(open('/r.json'));t=r['server_scan_results'][0]['scan_result']['${v}_cipher_suites'];assert t['result']['accepted_cipher_suites']==[]"
    done
    affirmer "$h : TLS 1.2 et 1.3 acceptes" q "import json;r=json.load(open('/r.json'));s=r['server_scan_results'][0]['scan_result'];assert s['tls_1_2_cipher_suites']['result']['accepted_cipher_suites'] and s['tls_1_3_cipher_suites']['result']['accepted_cipher_suites']"
    affirmer "$h : aucune suite faible (RC4, 3DES, NULL, EXPORT, CBC, anonyme)" q "import json,re;r=json.load(open('/r.json'));s=r['server_scan_results'][0]['scan_result'];n=[c['cipher_suite']['name'] for k in ('tls_1_2_cipher_suites','tls_1_3_cipher_suites') for c in s[k]['result']['accepted_cipher_suites']];assert n and not [x for x in n if re.search('RC4|3DES|NULL|EXPORT|_CBC_|anon|MD5',x)],n"
    affirmer "$h : chaine valide avec l'AC de recette" \
        curl_recette -s -o /dev/null "https://$h/"
    affirmer "$h : HSTS (max-age >= 1 an)" \
        'curl_recette -sI "https://$h/" | grep -i "^strict-transport-security:" | grep -Eq "max-age=([3-9][0-9]{7}|[1-9][0-9]{8,})"'
done
# Un client TLS 1.1 est refuse par la poignee de main (openssl de l'hote, si disponible).
affirmer "poignee de main TLS 1.1 refusee" \
    '! openssl s_client -connect 127.0.0.1:443 -servername "$PUBLIC_HOST" -tls1_1 </dev/null 2>&1 | grep -q "BEGIN CERTIFICATE"'
affirmer "poignee de main TLS 1.2 acceptee" \
    'openssl s_client -connect 127.0.0.1:443 -servername "$PUBLIC_HOST" -tls1_2 -CAfile "$RECETTE_DIR/certs/ca.pem" -verify_return_error </dev/null 2>&1 | grep -q "Verification: OK"'

bilan