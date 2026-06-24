.PHONY: install test lint clean all format

# Auto-detect Python from venv or system
PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
PIP := $(shell command -v pip3 2>/dev/null || command -v pip 2>/dev/null)

install:
	@echo "==> Installing repomapper in editable mode..."
	$(PIP) install -e ".[dev]"
	@echo "==> Done. Run 'make test' to verify."

test:
	@echo "==> Running test suite..."
	$(PYTHON) -m pytest tests/ -v --tb=short
	@echo "==> All tests passed."

test-cov:
	@echo "==> Running tests with coverage..."
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=repomapper --cov-report=term-missing --cov-report=html
	@echo "==> Coverage report: htmlcov/index.html"

lint:
	@echo "==> Running ruff..."
	$(PYTHON) -m ruff check repomapper/ tests/
	@echo "==> Running mypy..."
	$(PYTHON) -m mypy repomapper/ --ignore-missing-imports
	@echo "==> Lint clean."

format:
	@echo "==> Auto-formatting with ruff..."
	$(PYTHON) -m ruff format repomapper/ tests/

clean:
	@echo "==> Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "==> Clean."

all: clean install test lint
	@echo "==> Full pipeline complete."
