.PHONY: help install install-backend install-frontend install-electron \
        dev dev-backend dev-frontend dev-electron \
        test test-backend test-frontend lint lint-backend lint-frontend \
        build build-frontend clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

install: install-backend install-frontend ## Install backend + frontend deps

install-backend: ## Create backend venv and install deps
	cd backend && python3 -m venv .venv
	cd backend && . .venv/bin/activate && pip install --upgrade pip && pip install -e '.[dev]'

install-frontend: ## Install frontend deps
	cd frontend && pnpm install

install-electron: ## Install Electron shell deps
	cd electron && pnpm install

# ---------------------------------------------------------------------------
# Develop
# ---------------------------------------------------------------------------

dev: ## Run backend + frontend concurrently (requires `concurrently` shell or two terms)
	@echo "Run 'make dev-backend' in one terminal and 'make dev-frontend' in another."
	@echo "For Electron, add 'make dev-electron' in a third."

dev-backend: ## Run the FastAPI server with hot reload
	cd backend && . .venv/bin/activate && LEDGERLINE_DEV_MODE=true python -m app.main

dev-frontend: ## Run the Vite dev server on :5173
	cd frontend && pnpm dev

dev-electron: ## Run the Electron shell against the Vite dev server
	cd electron && NODE_ENV=development pnpm start

# ---------------------------------------------------------------------------
# Test + lint
# ---------------------------------------------------------------------------

test: test-backend test-frontend ## Run all tests

test-backend: ## pytest
	cd backend && . .venv/bin/activate && pytest -ra

test-frontend: ## vitest (runs once)
	cd frontend && pnpm test

lint: lint-backend lint-frontend ## Lint both backend and frontend

lint-backend: ## ruff check backend
	cd backend && . .venv/bin/activate && ruff check app tests

lint-frontend: ## tsc typecheck
	cd frontend && pnpm typecheck

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

build: build-frontend ## Build frontend bundle

build-frontend: ## Compile the frontend to frontend/dist
	cd frontend && pnpm build

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

clean: ## Remove build artifacts and caches
	rm -rf backend/.venv backend/.pytest_cache backend/.ruff_cache backend/**/__pycache__
	rm -rf frontend/node_modules frontend/dist frontend/.vite
	rm -rf electron/node_modules
