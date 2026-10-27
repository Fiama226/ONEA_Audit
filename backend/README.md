# Backend

Django 5 / DRF. Settings are split in `config/settings/{base,dev,test,prod}.py`.

## Environment

Variables are read from the repository-root `.env` (shared with docker compose),
or from the process environment:

| Variable | Notes |
|---|---|
| `SECRET_KEY` | required in prod |
| `ALLOWED_HOSTS` | comma-separated |
| `CORS_ALLOWED_ORIGINS` | comma-separated |
| `DATABASE_URL` | e.g. `postgres://onea:onea@localhost:5432/onea` (tests need PostgreSQL) |
| `REDIS_URL` | e.g. `redis://localhost:6379/0` (Celery broker and result backend) |
| `EMAIL_URL` | default `smtp://mailpit:1025` (compose network); `smtp://localhost:1025` on the host |
| `OIDC_OP_BASE_URL` | Keycloak realm URL, default `http://localhost:8080/realms/onea`; auth/token/userinfo/JWKS endpoints derive from it |
| `OIDC_RP_CLIENT_ID` | default `onea-backend` |
| `OIDC_ALLOWED_AZP` | comma-separated Keycloak clients whose tokens are accepted (`azp`), default `onea-frontend` (`onea-dev-cli` added in dev/test) |
| `OIDC_RP_CLIENT_SECRET` | unused by the Bearer path (userinfo + JWKS); only required because mozilla-django-oidc reads it at init (empty default in dev/test, mandatory in prod) |
| `OIDC_VERIFY_SSL` | default `true`; prod refuses `false` |

In prod, `OIDC_OP_BASE_URL` is required and must start with `https://`.

If Keycloak is unreachable or answers 5xx, protected endpoints answer 503 (not 401), so
clients do not drop their session during an outage.

The API accepts `Authorization: Bearer <Keycloak access token>` (verified via the userinfo
endpoint). The local role comes only from the `roles` claim (ADMIN > RAI > AUDITEUR > DG >
AUDITE, default AUDITE) and is re-synced on every request.

API schema and docs (`/api/schema/`, `/api/docs/`) are anonymous in dev/test and admin-only in prod.

## Celery and email

`send_mail_task.delay(...)` raises `kombu.exceptions.OperationalError` to the caller when
the broker (Redis) is down. Callers (services) must catch it and decide: fail the business
action or log and continue. Plain-text email parts are rendered without HTML escaping; HTML
parts stay autoescaped.
