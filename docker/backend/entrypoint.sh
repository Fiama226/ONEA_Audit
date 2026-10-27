#!/bin/sh
# Backend container entrypoint.
#   RUN_MIGRATIONS=true  apply migrations before starting (set on the `web` service only)
#   COLLECT_STATIC=true  refresh the shared static volume served by nginx (`web` only)
set -eu

if [ "${COLLECT_STATIC:-false}" = "true" ]; then
  python manage.py collectstatic --noinput --clear >/dev/null
fi

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
