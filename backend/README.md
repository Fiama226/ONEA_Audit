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
| `REDIS_URL` | e.g. `redis://localhost:6379/0` |

API schema and docs (`/api/schema/`, `/api/docs/`) are anonymous in dev/test and admin-only in prod.
