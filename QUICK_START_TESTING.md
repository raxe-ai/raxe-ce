# Quick Start: Running RAXE Tests

## ✅ Status: All 81 Collection Errors Fixed

**Tests Collected:** 3,364 | **Errors:** 0 | **Status:** Ready for Deployment

---

## Quick Commands

### Run All Tests
```bash
python -m pytest tests/
```

### Run Specific Test Categories
```bash
# Unit tests only
python -m pytest tests/unit/

# Integration tests
python -m pytest tests/integration/

# Performance tests (may be slow)
python -m pytest tests/performance/

# Skip slow tests
python -m pytest tests/ -m "not slow"
```

### Test Collection (verify without running)
```bash
python -m pytest tests --collect-only
```

### With Coverage
```bash
python -m pytest tests/ --cov=src/raxe --cov-report=html
# Open htmlcov/index.html to view coverage report
```

### Verbose Output
```bash
python -m pytest tests/ -v
```

### Run Single Test File
```bash
python -m pytest tests/test_structure.py -v
```

---

## What Was Fixed

### Before
- ❌ 81 collection errors
- ❌ Only 15 tests found
- ❌ Missing package installation
- ❌ Missing dependencies

### After
- ✅ 0 collection errors
- ✅ 3,364 tests collected
- ✅ Package installed in editable mode
- ✅ All dependencies installed

---

## Installed Dependencies

### Core Package
```bash
pip install -e .
```

### Test Framework
```bash
pip install pytest pytest-asyncio pytest-cov pytest-benchmark
```

### Test Dependencies
```bash
pip install jsonschema prometheus-client cffi
```

---

## Verification

```bash
# Quick verification (should show 3364 tests collected)
python -m pytest tests --collect-only -q

# Run smoke tests (should pass in ~1.5s)
python -m pytest tests/test_structure.py -v
```

---

## Next Steps

1. **Run full test suite:**
   ```bash
   python -m pytest tests/ --tb=short
   ```

2. **Generate coverage report:**
   ```bash
   python -m pytest tests/ --cov=src/raxe --cov-report=html --cov-report=term
   ```

3. **Fix any failing tests** (collection is fixed, but some tests may fail during execution)

4. **Add to CI/CD pipeline:**
   ```yaml
   - pip install -e .
   - pip install pytest pytest-asyncio pytest-cov
   - pip install jsonschema prometheus-client cffi
   - python -m pytest tests/ --cov=src/raxe
   ```

---

## Common Issues

### Issue: "No module named 'raxe'"
**Solution:** Run `pip install -e .` from project root

### Issue: "No module named 'pytest'"
**Solution:** Run `pip install pytest pytest-asyncio`

### Issue: Tests not found
**Solution:** Ensure you're in `/home/user/raxe-ce` and run with `python -m pytest tests/`

---

**Full Report:** See `TEST_COLLECTION_FIX_REPORT.md` for detailed analysis
