# MarsGIS — task entrypoint. Wraps `docker compose` (v2 plugin) and per-service
# tooling. NOTE: uses `docker compose` (plugin), never the legacy docker-compose.
COMPOSE      ?= docker compose
GHCR_OWNER   ?= marsgis
TAG          ?= dev
# Version derives from git tags (SemVer); falls back to the compose TAG.
VERSION      := $(shell git describe --tags --always --dirty 2>/dev/null || echo $(TAG))
ENGINE_IMAGE := ghcr.io/$(GHCR_OWNER)/marsgis-engine:$(TAG)

export GHCR_OWNER
export TAG

.DEFAULT_GOAL := help

.PHONY: help dev-install up dev down logs ps build-images \
        test test-backend test-frontend test-engine \
        lint typecheck fmt db-upgrade seed engine-run-sample precommit clean

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

dev-install: ## Install host dev tooling notes (deps install is per service; see docs/DEVELOPMENT.md)
	@echo "Containerized path needs only Docker + the compose plugin:  cp .env.example .env && make up"
	@echo "Non-Docker dev: Python 3.12 venv for backend/engine, Node 24 for frontend (docs/DEVELOPMENT.md)."

up: ## Build + start the default stack (db + backend + frontend), detached
	$(COMPOSE) up -d --build

dev: ## Start the stack with the dev overlay and follow logs (backend --reload)
	$(COMPOSE) up --build

down: ## Stop and remove the stack (keeps named volumes)
	$(COMPOSE) down

logs: ## Follow logs for all services
	$(COMPOSE) logs -f

ps: ## Show service status
	$(COMPOSE) ps

build-images: ## Build all three images (engine, backend, frontend)
	$(COMPOSE) --profile engine build

test: test-backend test-frontend test-engine ## Run every test suite

test-backend: ## Run backend pytest inside the backend image
	$(COMPOSE) run --rm --no-deps --entrypoint pytest backend -q

test-engine: ## Run engine pytest inside the engine image
	$(COMPOSE) --profile engine run --rm --entrypoint pytest engine -q

test-frontend: ## Run frontend unit tests on the host (Node 24+)
	cd frontend && npm ci && npm run test

lint: ## Lint backend + engine (ruff) and frontend (eslint)
	$(COMPOSE) run --rm --no-deps --entrypoint ruff backend check .
	cd frontend && npm run lint

typecheck: ## Type-check backend (mypy) and frontend (tsc --noEmit)
	$(COMPOSE) run --rm --no-deps --entrypoint mypy backend app
	cd frontend && npm run typecheck

fmt: ## Format backend/engine (ruff format) and frontend (prettier)
	$(COMPOSE) run --rm --no-deps --entrypoint ruff backend format .
	cd frontend && npx prettier -w src

db-upgrade: ## Apply Alembic migrations (PostgreSQL path)
	$(COMPOSE) run --rm --no-deps --entrypoint alembic backend -c alembic.ini upgrade head

seed: ## (Re)seed the catalogue — the backend seeds idempotently on startup
	SEED_ON_STARTUP=true $(COMPOSE) up -d --no-deps backend
	@echo "Backend (re)started; the catalogue seed runs idempotently on startup."

engine-run-sample: ## Run SAM on the bundled SYNTHETIC sample cube (offline; flagged SYNTHETIC)
	$(COMPOSE) --profile engine run --rm engine run \
		--cube /work/sample/sample_crism_nili.img \
		--mineral carbonate \
		--out /data/results/sample \
		--engine-image $(ENGINE_IMAGE)
	@echo "SYNTHETIC sample result written under the shared storage volume (/data/results/sample)."

engine-image: ## Build only the standalone engine image, tagged by VERSION
	docker build -t ghcr.io/$(GHCR_OWNER)/marsgis-engine:$(VERSION) ./engine

precommit: ## Run all pre-commit hooks against the whole tree
	pre-commit run --all-files

clean: ## Stop the stack, drop volumes, and prune local caches
	$(COMPOSE) down -v
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache frontend/dist frontend/.vite 2>/dev/null || true
