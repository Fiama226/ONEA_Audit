# ONEA backend image (Django + gunicorn / celery). Build context: repository root.
#   docker build -f docker/backend.Dockerfile -t onea-backend .
FROM ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 AS uv

FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY --from=uv /uv /usr/local/bin/uv
COPY backend/pyproject.toml backend/uv.lock ./
# Runtime dependencies only (no dev group), installed exactly as locked: versions and
# hashes come from uv.lock; pip refuses anything whose hash does not match.
RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt -o requirements.txt \
    && pip install --require-hashes -r requirements.txt

FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    STATIC_ROOT=/app/staticfiles \
    WEB_CONCURRENCY=3

RUN groupadd --gid 10001 onea \
    && useradd --uid 10001 --gid onea --home-dir /app --shell /usr/sbin/nologin onea

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# Code stays owned by root and not writable by the app user (image immutability); only
# /app/staticfiles (a volume shared with nginx) belongs to `onea`.
COPY backend/ /app/
COPY docker/backend/entrypoint.sh docker/backend/healthcheck.py /usr/local/bin/
RUN chmod 0555 /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.py \
    && rm -rf /app/.venv /app/tests /app/.pytest_cache /app/.coverage \
    && chmod -R go-w /app \
    && mkdir -p /app/staticfiles

# Collect static files at build time (admin, DRF, Swagger sidecar). Build-only settings:
# production settings need runtime secrets that do not exist at build time. The one-shot
# `migrate` service refreshes the shared static volume at every deployment.
RUN DJANGO_SETTINGS_MODULE=config.settings.base python manage.py collectstatic --noinput \
    && chown -R onea:onea /app/staticfiles

USER onea
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "/usr/local/bin/healthcheck.py"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120", "--max-requests", "1000", "--max-requests-jitter", "100", "-c", "gunicorn_conf.py"]
