# ============================================================
# HITL Gateway — Project Makefile
# ============================================================

.PHONY: help install install-backend install-frontend \
        run-backend run-frontend run-all run-agent \
        test test-unit test-integration lint clean deploy activate-demo

PYTHON   ?= python
PIP      ?= pip
NPM      ?= npm

# ── Help ─────────────────────────────────────────────────────
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Install ──────────────────────────────────────────────────
install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install Python dependencies (gateway + backend)
	$(PIP) install -r requirements.txt
	$(PIP) install -r backend/requirements.txt

install-frontend: ## Install frontend npm dependencies
	cd frontend && $(NPM) install

# ── Run ──────────────────────────────────────────────────────
run-backend: ## Start the FastAPI backend server
	$(PYTHON) backend/server.py

run-frontend: ## Start the React frontend dev server
	cd frontend && $(NPM) start

run-agent: ## Start the mock AI agent
	$(PYTHON) -m agents.agent_mock

run-all: ## Start backend, frontend, and activate demo
	bash scripts/start-everything.sh

# ── Test ─────────────────────────────────────────────────────
test: test-unit ## Run all tests

test-unit: ## Run pytest unit tests
	$(PYTHON) -m pytest tests/ -v --tb=short

test-integration: ## Run backend API integration tests
	$(PYTHON) tests/backend_test.py

# ── Quality ──────────────────────────────────────────────────
lint: ## Run flake8 linter on Python source
	$(PYTHON) -m flake8 function_app.py gateway/ agents/ backend/ tests/ \
		--max-line-length=120 --exclude=__pycache__

# ── Deploy ───────────────────────────────────────────────────
deploy: ## Deploy frontend to Vercel
	bash scripts/deploy-vercel.sh

activate-demo: ## Run the demo activation script
	bash scripts/activate-demo.sh

# ── Clean ────────────────────────────────────────────────────
clean: ## Remove caches, build artifacts, and logs
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
	rm -f *.log
	rm -rf frontend/build
