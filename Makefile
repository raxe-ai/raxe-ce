# RAXE Development Makefile

.PHONY: help install test test-fast test-all lint format clean docs serve-docs

help:  ## Show this help message
	@echo "RAXE Development Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install development dependencies
	pip install -e ".[dev,repl,config-tools,wrappers,all]"
	pre-commit install

test-fast:  ## Run fast tests only (unit tests, <30s)
	pytest -m "not slow" -v

test-unit:  ## Run unit tests only
	pytest tests/unit/ -v

test-integration:  ## Run integration tests only
	pytest -m "integration" -v

test-parallel:  ## Run fast tests in parallel (requires pytest-xdist)
	pytest -m "not slow" -n auto -v

test-all:  ## Run all tests including slow ones
	pytest -v

test-coverage:  ## Run tests with coverage report
	pytest --cov=src/raxe --cov-report=html --cov-report=term -v

test-benchmark:  ## Run performance benchmarks only
	pytest -m "benchmark" --benchmark-only -v

lint:  ## Run linting checks
	ruff check src/ tests/
	mypy src/raxe

format:  ## Format code with black and ruff
	ruff format src/ tests/
	ruff check --fix src/ tests/

security:  ## Run security checks
	bandit -r src/raxe

clean:  ## Clean build artifacts and cache
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	rm -rf htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

docs:  ## Build documentation with MkDocs
	mkdocs build --strict

serve-docs:  ## Serve documentation locally at http://127.0.0.1:8000
	mkdocs serve

deploy-docs:  ## Deploy documentation to GitHub Pages
	mkdocs gh-deploy --force

build:  ## Build distribution packages
	python -m build

validate-rules:  ## Validate all detection rules
	@echo "Validating detection rules..."
	@find src/raxe/packs -name "*.yaml" -type f | while read rule; do \
		echo "Checking: $$rule"; \
		raxe validate-rule "$$rule" || exit 1; \
	done
	@echo "All rules validated successfully!"

stats:  ## Show project statistics
	@echo "=== RAXE Project Statistics ==="
	@echo "Python files: $$(find src/raxe -name '*.py' | wc -l)"
	@echo "Lines of code: $$(find src/raxe -name '*.py' -exec wc -l {} + | tail -1 | awk '{print $$1}')"
	@echo "Test files: $$(find tests -name 'test_*.py' | wc -l)"
	@echo "Detection rules: $$(find src/raxe/packs -name '*.yaml' | wc -l)"
	@echo "Documentation files: $$(find docs -name '*.md' | wc -l)"

# Quick development workflow
dev: install test-fast lint  ## Install, test (fast), and lint

# Full CI simulation
ci: install test-all lint security  ## Run full CI pipeline locally

# Quick commit check
pre-commit: format test-fast lint  ## Format, test, and lint before commit
