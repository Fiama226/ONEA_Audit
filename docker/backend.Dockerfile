# ONEA backend image (Django + gunicorn / celery). Build context: repository root.
#   docker build -f docker/backend.Dockerfile -t onea-backend .
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY backend/pyproject.toml ./
# Runtime dependencies only (the dev group is not installed in the image).
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
    && pip install -r requirements.txt

FROM python:3.12-slim AS runtime

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
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120", "--max-requests", "1000", "--max-requests-jitter", "100", "--access-logfile", "-"]
