# Compose reads the repo-root .env (when present) through --env-file.
ENV_FILE := $(wildcard .env)
COMPOSE := docker compose $(if $(ENV_FILE),--env-file .env) -f docker/compose.yml -f docker/compose.dev.yml

.PHONY: up down logs backend frontend test test-backend test-frontend e2e lint gen-api check

up:
	$(COMPOSE) up -d
	bash scripts/wait-for-services.sh

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
	sh scripts/e2e.sh

lint:
	cd backend && ruff check . && ruff format --check . && mypy .
	cd frontend && npm run lint && npx prettier --check .

gen-api:
	sh scripts/gen-api.sh

check:
	bash scripts/check-services.sh

.PHONY: worker
worker:
	$(COMPOSE) up -d worker beat

.PHONY: check-api images prod-config
check-api:
	sh scripts/check-api-fresh.sh

images:
	docker build -f docker/backend.Dockerfile -t onea-backend:local .
	docker build -f docker/frontend.Dockerfile -t onea-frontend:local --build-arg VITE_API_URL=https://audit.example.org .

# Validate the production compose file against the placeholder env file.
prod-config:
	docker compose --env-file .env.prod.example -f docker/compose.prod.yml config -q
