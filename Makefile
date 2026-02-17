# Makefile for m8tes Python SDK
# Provides common development commands following backend patterns

.PHONY: help install test lint format type-check check clean build publish dev

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "Development:"
	@echo "  install            - Install development dependencies"
	@echo "  dev                - Set up development environment"
	@echo "  pre-commit-install - Install pre-commit hooks"
	@echo ""
	@echo "Testing:"
	@echo "  test               - Run all tests"
	@echo "  test-unit          - Run unit tests only"
	@echo "  test-e2e           - Run E2E tests (requires services)"
	@echo "  test-smoke         - Run smoke tests with real APIs (costs money!)"
	@echo "  test-cov           - Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint               - Check code style with ruff"
	@echo "  format             - Format code with ruff"
	@echo "  type-check         - Run type checking with mypy"
	@echo "  check              - Run all quality checks"
	@echo "  pre-commit         - Run pre-commit checks"
	@echo ""
	@echo "CI/CD:"
	@echo "  ci-test            - Run tests exactly as CI does"
	@echo "  ci-e2e             - Run E2E tests for CI"
	@echo "  quick-check        - Fast check (< 10 seconds)"
	@echo "  quick              - Quick development workflow"
	@echo ""
	@echo "Build & Release:"
	@echo "  clean              - Clean build artifacts"
	@echo "  build              - Build package"
	@echo "  publish            - Publish to PyPI (requires PYPI_TOKEN)"
	@echo "  version            - Show current version"

# Development setup
install:
	uv sync

upgrade:
	uv sync --upgrade

dev: install
	@echo "Development environment ready!"
	@echo "Run 'make check' to verify everything works."

# Testing
test:
	uv run pytest

test-unit:
	uv run pytest -m unit

test-integration:
	uv run pytest -m integration

test-e2e:
	@echo "🚀 Running E2E tests (requires FastAPI backend running)"
	@echo "   Backend: http://localhost:8000 (cd ../../fastapi && uv run uvicorn main:app --reload --port 8000)"
	uv run pytest tests/e2e/ -v -m "e2e and not smoke"

test-e2e-all:
	@echo "🚀 Running ALL E2E tests including smoke tests (requires FastAPI backend)"
	uv run pytest tests/e2e/ -v -m e2e

test-smoke:
	@echo "💰 Running SMOKE tests with REAL APIs (costs money!)"
	@echo "   Set E2E_USE_REAL_APIS=true to enable"
	E2E_USE_REAL_APIS=true uv run pytest tests/e2e/ -v -m smoke

test-cov:
	uv run pytest --cov=m8tes --cov-report=html --cov-report=term

test-verbose:
	uv run pytest -v

# Code quality
format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .

type-check:
	uv run mypy m8tes/


# Package management
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -delete
	find . -name "*.pyc" -delete

build: clean
	uv run python -m build

# Publishing — use GitHub Actions workflow (.github/workflows/publish-sdk.yml)
# which handles PyPI upload via OIDC trusted publishing (no tokens needed).
publish:
	@echo "Publishing is handled by GitHub Actions (OIDC trusted publishing)."
	@echo "Create a GitHub release to trigger the publish workflow."

# Verification commands
verify-install:
	python -c "import m8tes; print(f'✅ m8tes SDK v{m8tes.__version__} imported successfully')"

# Development helpers
watch-tests:
	@echo "👀 Watching for changes and running tests..."
	@which entr > /dev/null || (echo "Install entr: brew install entr" && exit 1)
	find . -name "*.py" | entr -c make test

# CI/CD helpers
ci-install:
	uv sync

check: format lint type-check test-cov
	@echo "✅ CI checks completed"

# Release helpers
version:
	@python -c "import m8tes; print(f'Current version: {m8tes.__version__}')"

# Quick development workflow
quick: format lint test-unit
	@echo "⚡ Quick checks completed"

# Pre-commit hooks
pre-commit-install:
	@echo "📌 Installing pre-commit hooks..."
	uv run pip install pre-commit
	uv run pre-commit install
	@echo "✅ Pre-commit hooks installed"

pre-commit:
	@echo "🔍 Running pre-commit checks..."
	uv run pre-commit run --all-files

# CI/CD helpers
ci-test: format lint type-check
	@echo "🧪 Running tests exactly as CI does..."
	uv run pytest -m unit --cov=m8tes --cov-report=term
	@echo "✅ CI test checks completed"

ci-e2e:
	@echo "🚀 Running E2E tests (requires FastAPI backend running)..."
	@echo "   Make sure FastAPI backend is started:"
	@echo "   cd ../../fastapi && uv run uvicorn main:app --reload --port 8000"
	uv run pytest -m "e2e and not smoke" -v --tb=short

quick-check:
	@echo "⚡ Quick check (< 10 seconds)..."
	uv run ruff check . --fix
	uv run pytest -m unit -x --maxfail=1 -q
	@echo "✅ Quick check passed!"
