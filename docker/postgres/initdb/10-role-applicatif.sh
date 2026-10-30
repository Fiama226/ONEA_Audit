#!/bin/sh
# Rôle applicatif sans privilèges (lot 9, T10, D6). Exécuté UNE SEULE FOIS par l'image postgres,
# à l'initialisation d'un volume vide. Pour une base existante : docs/deploy.md, § « Base de données ».
#
# `onea_app` : LOGIN, ni superutilisateur, ni création de base ou de rôle, sans héritage, et jamais
# propriétaire des tables (le propriétaire est POSTGRES_USER, réservé à `migrate` et aux sauvegardes).
# Les droits sur les tables sont posés après chaque migration par `manage.py migrate`
# (récepteur post_migrate) ou `manage.py installer_gardes_sql`.
set -eu

APP_USER="${POSTGRES_APP_USER:-onea_app}"
if [ -z "${POSTGRES_APP_PASSWORD:-}" ]; then
  echo "10-role-applicatif.sh : POSTGRES_APP_PASSWORD absent, rôle applicatif non créé." >&2
  exit 1
fi
if [ "$APP_USER" = "$POSTGRES_USER" ]; then
  echo "10-role-applicatif.sh : POSTGRES_APP_USER doit différer de POSTGRES_USER." >&2
  exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_user="$APP_USER" -v app_password="$POSTGRES_APP_PASSWORD" -v app_db="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %L',
              :'app_user', :'app_password') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'app_db', :'app_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'app_user') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO %I',
              :'app_user') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I',
              :'app_user') \gexec
SQL
