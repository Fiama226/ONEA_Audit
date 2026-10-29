#!/bin/sh
# Genere .recette/certs : ca.pem (AC de recette) + fullchain.pem/privkey.pem couvrant
# audit.recette.test et sso.recette.test. Usage : sh scripts/recette/certs.sh
set -eu
. "$(dirname "$0")/lib.sh"
d="$RECETTE_DIR/certs"
mkdir -p "$d"
cat > "$d/openssl.cnf" <<CNF
[req]
distinguished_name = dn
prompt = no
[dn]
CN = ONEA recette
[ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
[srv]
basicConstraints = CA:FALSE
keyUsage = digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:$PUBLIC_HOST,DNS:$SSO_HOST
CNF
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -keyout "$d/ca.key" -out "$d/ca.pem" \
    -config "$d/openssl.cnf" -extensions ca >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -keyout "$d/privkey.pem" -out "$d/srv.csr" \
    -config "$d/openssl.cnf" >/dev/null 2>&1
openssl x509 -req -in "$d/srv.csr" -CA "$d/ca.pem" -CAkey "$d/ca.key" -CAcreateserial \
    -days 30 -out "$d/srv.pem" -extfile "$d/openssl.cnf" -extensions srv >/dev/null 2>&1
cat "$d/srv.pem" "$d/ca.pem" > "$d/fullchain.pem"
chmod 0644 "$d"/*.pem
chmod 0600 "$d/ca.key"
# L'AC est aussi deposee dans ./certs (monte dans web/worker, voir docs/deploy.md) pour que
# le backend fasse confiance au certificat du SSO de recette. Ignore par git (certs/*.pem).
mkdir -p "$REPO_ROOT/certs"
cp "$d/ca.pem" "$REPO_ROOT/certs/recette-ca.pem"
echo "Certificats de recette generes dans $d"
