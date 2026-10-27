# Compose reads the repo-root .env (when present) through --env-file.
# Object storage is opt-in: `make up WITH_STORAGE=1` (see docs/infra-minio.md).
ENV_FILE := $(wildcard .env)
COMPOSE := docker compose $(if $(ENV_FILE),--env-file .env) -f docker/compose.yml -f docker/compose.dev.yml $(if $(WITH_STORAGE),--profile storage)
STORAGE_FLAG := $(if $(WITH_STORAGE),--with-storage)

.PHONY: up down logs backend frontend test test-backend test-frontend e2e lint gen-api check

up:
	$(COMPOSE) up -d
	bash scripts/wait-for-services.sh $(STORAGE_FLAG)

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

backend:
	cd backend && python manage.py runserver

frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && pytest

test-frontend:
	cd frontend && npm test -- --run

e2e:
	cd frontend && npx playwright test

lint:
	cd backend && ruff check . && ruff format --check . && mypy .
	cd frontend && npm run lint && npx prettier --check .

gen-api:
	sh scripts/gen-api.sh

check:
	bash scripts/check-services.sh $(STORAGE_FLAG)

.PHONY: worker
worker:
	$(COMPOSE) up -d worker beat
