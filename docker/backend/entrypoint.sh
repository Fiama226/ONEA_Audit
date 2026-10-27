#!/bin/sh
# Backend container entrypoint. Migrations and static collection are NOT done here: they run
# once in the one-shot `migrate` service of docker/compose.prod.yml.
set -eu
exec "$@"
