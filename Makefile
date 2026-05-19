SHELL := /bin/bash
COMPOSE := docker compose

.DEFAULT_GOAL := help

.PHONY: help
help:
	@awk 'BEGIN{FS=":.*##"; printf "targets:\n"} /^[a-zA-Z_-]+:.*##/ {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: env
env: ## create .env from example if missing
	@test -f .env || cp .env.example .env

.PHONY: build
build: env ## build all images
	$(COMPOSE) build

.PHONY: up
up: env ## start full stack (detached)
	$(COMPOSE) up -d

.PHONY: up-fg
up-fg: env ## start full stack (foreground)
	$(COMPOSE) up

.PHONY: down
down: ## stop stack
	$(COMPOSE) down

.PHONY: nuke
nuke: ## stop and wipe volumes
	$(COMPOSE) down -v

.PHONY: logs
logs: ## tail all logs
	$(COMPOSE) logs -f --tail=200

.PHONY: ps
ps: ## list services
	$(COMPOSE) ps

.PHONY: db-shell
db-shell: ## psql into postgres
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-reviewly} -d $${POSTGRES_DB:-reviewly}

.PHONY: backend-shell
backend-shell: ## shell into backend container
	$(COMPOSE) exec backend bash

.PHONY: redis-shell
redis-shell: ## redis-cli into redis
	$(COMPOSE) exec redis redis-cli

.PHONY: migrate
migrate: ## run alembic upgrade head
	$(COMPOSE) exec backend alembic upgrade head

.PHONY: migration
migration: ## create new migration (m="message")
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

.PHONY: downgrade
downgrade: ## downgrade one revision
	$(COMPOSE) exec backend alembic downgrade -1

.PHONY: test
test: ## run backend tests
	$(COMPOSE) exec backend pytest -q

.PHONY: fmt
fmt: ## format backend (black + ruff)
	$(COMPOSE) exec backend bash -lc "black app tests && ruff check --fix app tests"

.PHONY: lint
lint: ## lint backend
	$(COMPOSE) exec backend bash -lc "ruff check app tests && black --check app tests"

.PHONY: fe-install
fe-install: ## install frontend deps
	$(COMPOSE) exec frontend npm install --legacy-peer-deps

.PHONY: fe-lint
fe-lint: ## lint frontend
	$(COMPOSE) exec frontend npm run lint

.PHONY: fe-fmt
fe-fmt: ## prettier write
	$(COMPOSE) exec frontend npm run format

.PHONY: clean
clean: ## remove build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache backend/htmlcov backend/.coverage
	rm -rf frontend/dist
