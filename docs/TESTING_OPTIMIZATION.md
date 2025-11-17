# Test Execution Optimization Guide

## Overview

RAXE has 3,364 tests across 114 test files. This guide shows how to run tests efficiently during development.

## Quick Commands

```bash
# Fast tests only (~30 seconds)
pytest -m "not slow"

# Fast tests in parallel (~10 seconds)
pytest -m "not slow" -n auto

# Unit tests only (~15 seconds)
pytest tests/unit/

# Specific test file
pytest tests/unit/domain/test_threat_detector.py

# Single test
pytest tests/unit/sdk/test_client.py::test_scan_basic -v
```

## Test Categories

### By Speed

| Category | Marker | Count | Duration | Command |
|----------|--------|-------|----------|---------|
| Fast | `not slow` | ~2500 | 30s | `pytest -m "not slow"` |
| Unit | `tests/unit/` | ~2000 | 15s | `pytest tests/unit/` |
| Integration | `integration` | ~300 | 60s | `pytest -m integration` |
| Performance | `benchmark` | ~50 | 120s | `pytest -m benchmark` |
| Golden | `golden` | 428 | 45s | `pytest tests/golden/` |

### By Component

```bash
# Domain layer (pure logic)
pytest tests/unit/domain/

# SDK/Client
pytest tests/unit/sdk/

# CLI commands
pytest tests/unit/cli/

# Infrastructure
pytest tests/unit/infrastructure/

# Async functionality
pytest tests/unit/async_sdk/
```

## Parallel Execution

### Install pytest-xdist

```bash
pip install pytest-xdist
```

### Run Tests in Parallel

```bash
# Auto-detect CPU cores
pytest -n auto

# Specific number of workers
pytest -n 4

# Fast tests in parallel (best for development)
pytest -m "not slow" -n auto
```

**Expected Speedup**: 3-6x on multi-core machines

## Makefile Shortcuts

```bash
# Install make if needed
sudo apt-get install make  # Linux
brew install make          # macOS

# Run fast tests
make test-fast

# Run with parallel execution
make test-parallel

# Run with coverage
make test-coverage

# Full CI simulation
make ci
```

## Pytest Configuration

### Custom Markers

Add markers to your tests:

```python
import pytest

@pytest.mark.fast
def test_quick_operation():
    """Runs in <100ms."""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Takes >1 second."""
    pass

@pytest.mark.integration
def test_full_pipeline():
    """Tests multiple components."""
    pass
```

### Run by Marker

```bash
# Fast tests only
pytest -m fast

# Skip slow tests
pytest -m "not slow"

# Integration tests only
pytest -m integration

# Combine markers
pytest -m "integration and not slow"
```

## Selective Testing

### Test Specific Functionality

```bash
# All detection tests
pytest -k "detection"

# Specific rule family tests
pytest -k "prompt_injection"

# Async tests only
pytest -k "async"

# Exclude specific tests
pytest -k "not integration"
```

### Last Failed Tests

```bash
# Run only tests that failed last time
pytest --lf

# Run failed tests first, then others
pytest --ff
```

## Coverage-Driven Testing

### Run with Coverage

```bash
# Basic coverage
pytest --cov=src/raxe

# HTML coverage report
pytest --cov=src/raxe --cov-report=html

# Terminal + HTML
pytest --cov=src/raxe --cov-report=html --cov-report=term
```

### View Coverage Report

```bash
# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage by Module

```bash
# Domain coverage only
pytest --cov=src/raxe/domain tests/unit/domain/

# SDK coverage
pytest --cov=src/raxe/sdk tests/unit/sdk/
```

## Development Workflows

### Quick Iteration (< 10 seconds)

```bash
# Test only what you changed
pytest tests/unit/domain/test_my_module.py -v

# Or use watch mode (requires pytest-watch)
pip install pytest-watch
ptw tests/unit/domain/ -- -v
```

### Pre-commit Check (< 30 seconds)

```bash
# Fast tests + linting
make pre-commit

# Or manually
pytest -m "not slow" -n auto
ruff check src/ tests/
mypy src/raxe
```

### Full Local CI (< 5 minutes)

```bash
# Simulate CI pipeline
make ci

# Or manually
pytest --cov=src/raxe --cov-report=term
ruff check src/ tests/
mypy src/raxe
bandit -r src/raxe
```

## Golden File Tests

### What are Golden Files?

Golden file tests compare output against known-good "golden" files to catch regressions.

**Location**: `tests/golden/`
**Count**: 428 parameterized test cases

### Run Golden Tests

```bash
# All golden tests
pytest tests/golden/

# Specific family
pytest tests/golden/test_golden.py -k "PI"

# Update golden files (when intentionally changing output)
pytest tests/golden/ --update-golden
```

## Performance Benchmarking

### Run Benchmarks

```bash
# All benchmarks
pytest tests/performance/ --benchmark-only

# Specific benchmark
pytest tests/performance/test_detection_performance.py --benchmark-only

# Save baseline
pytest tests/performance/ --benchmark-save=baseline

# Compare against baseline
pytest tests/performance/ --benchmark-compare=baseline
```

### Benchmark Output

```
----------------------- benchmark: 10 tests -----------------------
Name (time in ms)              Min      Max     Mean    StdDev
------------------------------------------------------------------
test_l1_detection_speed      0.30     0.50     0.37     0.05
test_l2_detection_speed      0.80     1.20     0.95     0.10
test_full_pipeline_speed     1.20     1.80     1.45     0.15
------------------------------------------------------------------
```

## Optimizing Slow Tests

### Profile Test Execution

```bash
# Show slowest 20 tests
pytest --durations=20

# Show all durations
pytest --durations=0
```

### Common Slow Test Patterns

#### 1. Database Setup (Slow)

```python
# ❌ Slow: Create database per test
def test_scan_history():
    db = Database()  # Initializes SQLite
    # ...

# ✅ Fast: Use session-scoped fixture
@pytest.fixture(scope="session")
def shared_db():
    return Database()

def test_scan_history(shared_db):
    # ...
```

#### 2. Rule Loading (Slow)

```python
# ❌ Slow: Load all rules per test
def test_detection():
    raxe = Raxe()  # Loads 460 rules
    # ...

# ✅ Fast: Use session-scoped client
@pytest.fixture(scope="session")
def raxe_client():
    return Raxe()

def test_detection(raxe_client):
    # ...
```

#### 3. Async Sleep (Slow)

```python
# ❌ Slow: Long sleep
async def test_async_operation():
    await asyncio.sleep(1.0)  # 1 second
    # ...

# ✅ Fast: Minimal sleep
async def test_async_operation():
    await asyncio.sleep(0.01)  # 10ms, often sufficient
    # ...
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run fast tests in parallel
        run: |
          pytest -m "not slow" -n auto --cov=src/raxe --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-fast
        name: pytest-fast
        entry: pytest
        args: ["-m", "not slow", "--tb=short"]
        language: system
        pass_filenames: false
        always_run: true
```

## Tips & Best Practices

### 1. Run Fast Tests First

```bash
# Fail fast on quick tests
pytest -m "not slow" -n auto -x  # -x stops on first failure
```

### 2. Use Test-Driven Development

```bash
# Watch mode for TDD
pip install pytest-watch
ptw tests/unit/domain/ -- -v
```

### 3. Cache Test Results

```bash
# Use pytest cache
pytest --cache-show  # View cache
pytest --cache-clear  # Clear cache
```

### 4. Isolate Flaky Tests

```bash
# Run flaky test multiple times
pytest tests/unit/test_flaky.py --count=10
```

### 5. Debug Failing Tests

```bash
# Verbose output
pytest tests/unit/test_failing.py -vv

# Drop into debugger on failure
pytest tests/unit/test_failing.py --pdb

# Show local variables
pytest tests/unit/test_failing.py -l
```

## Performance Targets

| Test Suite | Target | Actual | Status |
|------------|--------|--------|--------|
| Fast tests (sequential) | <60s | 30s | ✅ 2x better |
| Fast tests (parallel) | <15s | 10s | ✅ 1.5x better |
| Unit tests | <30s | 15s | ✅ 2x better |
| Full suite | <300s | ~600s | ⚠️ Needs optimization |
| Single test | <100ms | ~10ms | ✅ 10x better |

## Troubleshooting

### Tests Running Slow

```bash
# Identify slow tests
pytest --durations=50

# Profile test execution
pytest --profile

# Check for database locks
lsof ~/.raxe/raxe.db
```

### Out of Memory

```bash
# Reduce parallel workers
pytest -n 2  # Instead of -n auto

# Run test subsets
pytest tests/unit/ -n auto
pytest tests/integration/  # Sequential
```

### Import Errors

```bash
# Ensure development install
pip install -e ".[dev]"

# Verify PYTHONPATH
python -c "import raxe; print(raxe.__file__)"
```

## See Also

- [QUICK_START_TESTING.md](QUICK_START_TESTING.md) - Testing basics
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [Makefile](../Makefile) - Development commands
- [pytest.ini](../pyproject.toml) - Pytest configuration
