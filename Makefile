COMPOSE := docker compose -f docker/compose.yml -f docker/compose.dev.yml

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
	cd frontend && npx playwright test

lint:
	cd backend && ruff check . && ruff format --check . && mypy .
	cd frontend && npm run lint && npx prettier --check .

gen-api:
	cd backend && python manage.py spectacular --file ../frontend/openapi.yaml
	cd frontend && npm run gen-api

check:
	bash scripts/check-services.sh
