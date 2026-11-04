#!/bin/sh
# Banc d'essai des secrets (lot 9, T17) sur la pile de recette : aucune valeur de secret ne figure
# dans la configuration des conteneurs (docker inspect), ni dans .env.recette, et les fichiers de
# secrets ont les droits attendus.
# Usage : sh scripts/recette/up.sh && sh scripts/recette/tests/secrets.sh
# Les valeurs ne sont jamais affichees : elles transitent par un fichier temporaire 0600.
. "$(dirname "$0")/../lib.sh"
umask 077

MOTIFS=$(mktemp)
trap 'rm -f "$MOTIFS"' EXIT
# Lecture en root dans un conteneur jetable (les fichiers appartiennent a 10001, en 0600).
# Un fichier vide (email_password) est ignore : un motif vide correspondrait a tout.
docker run --rm -v "$RECETTE_SECRETS:/s:ro" alpine:3.20 \
    sh -c 'for f in /s/*; do [ -s "$f" ] && { cat "$f"; echo; }; done' | sed '/^$/d' >"$MOTIFS"

affirmer "fichiers de secrets lus (au moins 8 valeurs)" '[ "$(wc -l <"$MOTIFS")" -ge 8 ]'
affirmer "secrets : dossier 0700, fichiers 0600, non vides, sans CHANGE_ME" \
    'sh "$REPO_ROOT/scripts/generer-secrets.sh" --verifier --dossier "$RECETTE_SECRETS"'
affirmer ".env.recette ne contient aucune valeur de secret applicatif" \
    '! grep -qFf "$MOTIFS" "$RECETTE_ENV"'

# docker inspect : Config.Env, Cmd, Entrypoint, Healthcheck, Labels... (tout le JSON).
for service in web worker beat migrate db redis meilisearch; do
    ids=$(compose_recette ps -a -q "$service")
    affirmer "$service : conteneur trouve" '[ -n "$ids" ]'
    for id in $ids; do
        affirmer "$service : docker inspect sans valeur de secret" \
            '! docker inspect "$id" | grep -qFf "$MOTIFS"'
    done
done

# Les variables *_FILE pointent vers /run/secrets ; aucune variable de secret en clair.
affirmer "web : SECRET_KEY_FILE present, SECRET_KEY absent de l'environnement" \
    'env_web=$(docker inspect "$(compose_recette ps -q web)" --format "{{range .Config.Env}}{{println .}}{{end}}");
     echo "$env_web" | grep -q "^SECRET_KEY_FILE=/run/secrets/secret_key$" &&
     ! echo "$env_web" | grep -q "^SECRET_KEY="'
affirmer "db : POSTGRES_PASSWORD_FILE present, POSTGRES_PASSWORD absent" \
    'env_db=$(docker inspect "$(compose_recette ps -q db)" --format "{{range .Config.Env}}{{println .}}{{end}}");
     echo "$env_db" | grep -q "^POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password$" &&
     ! echo "$env_db" | grep -q "^POSTGRES_PASSWORD="'

# Valkey refuse les connexions sans mot de passe et accepte celle qui le fournit.
affirmer "redis : refuse sans mot de passe" \
    '! compose_recette exec -T redis valkey-cli ping | grep -q PONG'
affirmer "redis : repond avec le mot de passe du fichier" \
    'compose_recette exec -T redis sh -c "REDISCLI_AUTH=\"\$(cat /run/secrets/redis_password)\" valkey-cli --no-auth-warning ping" | grep -q PONG'
affirmer "meilisearch : refuse sans cle" \
    '[ "$(compose_recette exec -T meilisearch curl -s -o /dev/null -w "%{http_code}" http://localhost:7700/keys)" = 401 ]'

# L'application fonctionne avec les secrets en fichiers (base, Redis, Meilisearch).
affirmer "API prete (/api/v1/health/ready/)" \
    'curl_recette -fs "https://$PUBLIC_HOST/api/v1/health/ready/"'

# Le role applicatif n'est ni superutilisateur ni proprietaire (T10) : connexion par mot de passe de fichier.
affirmer "web se connecte a la base avec le role applicatif" \
    '[ "$(compose_recette exec -T web python manage.py shell -c "from django.db import connection as c; cur=c.cursor(); cur.execute(\"select current_user\"); print(cur.fetchone()[0])" | tr -d "\r\n")" = onea_app ]'

bilan
