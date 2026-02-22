# Makefile for m8tes Python SDK
# Provides common development commands following backend patterns

.PHONY: help install test lint format type-check check clean build publish dev \
       bump-patch bump-minor bump-major release-patch release-minor release-major

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
	@echo "  publish            - Publish to PyPI (via CI)"
	@echo "  version            - Show current version"
	@echo "  bump-patch         - Bump patch version (0.2.0 → 0.2.1)"
	@echo "  bump-minor         - Bump minor version (0.2.0 → 0.3.0)"
	@echo "  bump-major         - Bump major version (0.2.0 → 1.0.0)"
	@echo "  release-patch      - Bump, check, commit, and push (patch)"
	@echo "  release-minor      - Bump, check, commit, and push (minor)"
	@echo "  release-major      - Bump, check, commit, and push (major)"

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
	uv run pytest -m "integration and not runtime"

test-integration-full:
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

# Publishing — automated via CI on push to main.
publish:
	@echo "Publish is automated via CI on push to main."
	@echo "To release: make release-patch (or release-minor/release-major)."

# Version bumping — updates pyproject.toml and CHANGELOG.md in one step.
# __init__.py reads version from package metadata at runtime (no update needed).
define BUMP_SCRIPT
import re, sys, datetime, subprocess
part = sys.argv[1]
with open("pyproject.toml") as f: toml = f.read()
m = re.search(r'version = "(\d+)\.(\d+)\.(\d+)"', toml)
major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
old = f"{major}.{minor}.{patch}"
if part == "patch": patch += 1
elif part == "minor": minor += 1; patch = 0
elif part == "major": major += 1; minor = 0; patch = 0
new = f"{major}.{minor}.{patch}"
with open("pyproject.toml", "w") as f: f.write(toml.replace(m.group(0), f'version = "{new}"'))
# Draft changelog from recent commits
try:
    log = subprocess.check_output(["git", "log", "--oneline", "--no-decorate", f"v{old}..HEAD", "--", "."], stderr=subprocess.DEVNULL).decode().strip()
except Exception:
    try:
        log = subprocess.check_output(["git", "log", "--oneline", "--no-decorate", "-20", "--", "."], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        log = ""
draft = "\n".join(f"- {line}" for line in log.splitlines()) if log else "- "
with open("CHANGELOG.md") as f: cl = f.read()
today = datetime.date.today().isoformat()
header = f"## [{new}] - {today}\n\n### Added\n\n### Changed\n{draft}\n\n### Fixed\n\n"
with open("CHANGELOG.md", "w") as f: f.write(cl.replace("\n## [", f"\n{header}## [", 1))
print(f"Bumped to {new}")
endef
export BUMP_SCRIPT

bump-patch:
	@python3 -c "$$BUMP_SCRIPT" patch

bump-minor:
	@python3 -c "$$BUMP_SCRIPT" minor

bump-major:
	@python3 -c "$$BUMP_SCRIPT" major

# Release targets — bump, check, confirm, commit, push.
define DO_RELEASE
	$(MAKE) check
	@NEW_VER=$$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	echo ""; \
	echo "Ready to release v$$NEW_VER. Review CHANGELOG.md, then confirm."; \
	printf "Commit and push? [y/N] "; \
	read ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
		git add pyproject.toml CHANGELOG.md && \
		git commit -m "release: v$$NEW_VER" && \
		git push && \
		echo "Released v$$NEW_VER"; \
	else \
		echo "Aborted. Files are bumped but not committed."; \
	fi
endef

release-patch: bump-patch
	$(DO_RELEASE)

release-minor: bump-minor
	$(DO_RELEASE)

release-major: bump-major
	$(DO_RELEASE)

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
	@python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"

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
