#!/bin/sh
# Gitea + act_runner jetables pour verifier la compatibilite du workflow CI (lot 9, T28).
# Usage : sh scripts/ci/gitea-local.sh [up|push|logs|down]     (defaut : up puis push)
#   up    demarre Gitea (SQLite) et act_runner, cree l'administrateur et le depot "onea-audit"
#   push  pousse la branche courante VERS LE GITEA JETABLE uniquement (jamais vers un autre depot)
#   logs  affiche l'etat des executions (API Gitea) et les journaux du runner
#   down  supprime conteneurs et reseau jetables
# Prerequis : docker, git, curl, openssl. Port : GITEA_PORT (defaut 3300 ; 8000 et 5173 restent libres).
# Images epinglees par etiquette : verifier les empreintes avant un usage durable.
# Le runner monte le socket Docker de l'hote (necessaire aux services et aux builds d'images) :
# usage local jetable uniquement. Les commandes push/logs exigent GITEA_ADMIN_PASSWORD si elles
# sont lancees dans un autre appel que "up" (le mot de passe jetable n'est jamais ecrit sur disque).
set -eu

GITEA_IMAGE=${GITEA_IMAGE:-gitea/gitea:1.22.6}
RUNNER_IMAGE=${RUNNER_IMAGE:-gitea/act_runner:0.2.11}
GITEA_PORT=${GITEA_PORT:-3300}
NET=gitea-ci-local-net
GITEA=gitea-ci-local-server
RUNNER=gitea-ci-local-runner
ADMIN=ci-admin
ADMIN_PASS=${GITEA_ADMIN_PASSWORD:-$(openssl rand -hex 12)}
API="http://127.0.0.1:$GITEA_PORT/api/v1"
ROOT=$(cd "$(dirname "$0")/../.." && pwd)

up() {
    docker network create "$NET" >/dev/null 2>&1 || true
    docker run -d --name "$GITEA" --network "$NET" -p "127.0.0.1:$GITEA_PORT:3000" \
        -e GITEA__security__INSTALL_LOCK=true -e GITEA__database__DB_TYPE=sqlite3 \
        -e GITEA__actions__ENABLED=true -e GITEA__server__ROOT_URL="http://$GITEA:3000/" \
        -e GITEA__server__DISABLE_SSH=true "$GITEA_IMAGE" >/dev/null
    i=0
    until curl -fsS "$API/version" >/dev/null 2>&1; do
        i=$((i + 1))
        [ "$i" -gt 60 ] && { echo "Gitea ne demarre pas" >&2; exit 1; }
        sleep 2
    done
    docker exec -u git "$GITEA" gitea admin user create --admin --username "$ADMIN" \
        --password "$ADMIN_PASS" --email ci@example.invalid --must-change-password=false >/dev/null
    curl -fsS -u "$ADMIN:$ADMIN_PASS" -H 'Content-Type: application/json' \
        -d '{"name":"onea-audit","private":false}' "$API/user/repos" >/dev/null
    token=$(docker exec -u git "$GITEA" gitea actions generate-runner-token)
    docker run -d --name "$RUNNER" --network "$NET" -v /var/run/docker.sock:/var/run/docker.sock \
        -e GITEA_INSTANCE_URL="http://$GITEA:3000" -e GITEA_RUNNER_REGISTRATION_TOKEN="$token" \
        -e GITEA_RUNNER_NAME=ci-local \
        -e GITEA_RUNNER_LABELS=ubuntu-latest:docker://catthehacker/ubuntu:act-22.04 \
        "$RUNNER_IMAGE" >/dev/null
    echo "Gitea : http://127.0.0.1:$GITEA_PORT  (utilisateur $ADMIN, mot de passe jetable : $ADMIN_PASS)"
}

push() {
    branch=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)
    url="http://$ADMIN:$ADMIN_PASS@127.0.0.1:$GITEA_PORT/$ADMIN/onea-audit.git"
    # URL explicite : aucun remote du depot reel n'est utilise ni modifie.
    git -C "$ROOT" push "$url" "HEAD:refs/heads/$branch"
    echo "Executions : http://127.0.0.1:$GITEA_PORT/$ADMIN/onea-audit/actions"
}

logs() {
    curl -fsS -u "$ADMIN:$ADMIN_PASS" "$API/repos/$ADMIN/onea-audit/actions/tasks" || true
    docker logs --tail 100 "$RUNNER"
}

down() {
    docker rm -f "$RUNNER" "$GITEA" >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
}

case "${1:-all}" in
    up) up ;;
    push) push ;;
    logs) logs ;;
    down) down ;;
    all) up; push ;;
    *) echo "Usage : $0 [up|push|logs|down]" >&2; exit 2 ;;
esac
