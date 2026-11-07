# RecallOps Makefile — Common Development Commands
# Usage: make <target>

.PHONY: help install dev-install test lint format typecheck clean \
        backend frontend docker-up docker-down docker-logs \
        seed-memory check-env

# Default target
help:
	@echo "RecallOps — Available Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install production dependencies"
	@echo "  make dev-install    Install with dev dependencies"
	@echo "  make check-env      Verify .env configuration"
	@echo ""
	@echo "Development:"
	@echo "  make backend        Run backend (FastAPI) with hot reload"
	@echo "  make frontend       Run frontend (Streamlit)"
	@echo "  make test           Run all tests"
	@echo "  make lint           Run ruff linter"
	@echo "  make format         Format code with black/ruff"
	@echo "  make typecheck      Run mypy type checking"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up      Start all services with docker-compose"
	@echo "  make docker-down    Stop all services"
	@echo "  make docker-logs    View docker-compose logs"
	@echo "  make docker-build   Build docker images"
	@echo ""
	@echo "Memory:"
	@echo "  make seed-memory    Seed Hindsight with demo incidents"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          Remove cache and build artifacts"

# ============================================================================
# Setup
# ============================================================================

install:
	pip install -e ".[backend,frontend]"

dev-install:
	pip install -e ".[backend,frontend,dev]"
	pre-commit install || true

check-env:
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found. Copy .env.example to .env and configure."; \
		exit 1; \
	fi
	@echo "✅ .env file exists"
	@grep -E "^(GROQ_API_KEY|HINDSIGHT_API_KEY|HINDSIGHT_BANK_ID)=" .env | while read line; do \
		key=$$(echo $$line | cut -d= -f1); \
		val=$$(echo $$line | cut -d= -f2); \
		if [ "$$val" = "your_"*"_here" ] || [ -z "$$val" ]; then \
			echo "⚠️  $$key appears to be unset or using placeholder"; \
		else \
			echo "✅ $$key is set"; \
		fi; \
	done

# ============================================================================
# Development
# ============================================================================

backend:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0

# Run both backend and frontend (requires two terminals)
# Use: make backend in one terminal, make frontend in another

test:
	pytest -v

test-agent:
	pytest tests/test_agent.py -v

test-api:
	pytest tests/test_api.py -v

test-memory:
	pytest tests/test_memory.py -v

lint:
	ruff check backend/ frontend/ scripts/ tests/

format:
	ruff format backend/ frontend/ scripts/ tests/
	ruff check --fix backend/ frontend/ scripts/ tests/

typecheck:
	mypy backend/ frontend/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/ 2>/dev/null || true

# ============================================================================
# Docker
# ============================================================================

docker-build:
	docker-compose build

docker-up:
	docker-compose up --build -d
	@echo ""
	@echo "Services starting..."
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:8501"
	@echo "  API Docs: http://localhost:8000/docs"

docker-down:
	docker-compose down -v

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

docker-ps:
	docker-compose ps

# ============================================================================
# Memory Seeding
# ============================================================================

seed-memory:
	@if [ ! -f .env ]; then \
		echo "❌ .env not found. Run 'make check-env' first."; \
		exit 1; \
	fi
	python scripts/seed_memory.py

# ============================================================================
# CI Helpers
# ============================================================================

ci-test: lint typecheck test
	@echo "✅ All CI checks passed"

ci-build: docker-build
	@echo "✅ Docker build successful"