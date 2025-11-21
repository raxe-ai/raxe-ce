# RAXE CE - Quick Cleanup Checklist

**Generated**: 2025-11-21
**Status**: Ready for Implementation
**Estimated Time**: 50 minutes

---

## Immediate Actions (< 1 hour)

### 1. Remove Unused Imports (15 min)

```bash
# Run these commands to auto-fix:
cd /Users/mh/github-raxe-ai/raxe-ce
source .venv/bin/activate
ruff check src/raxe --select=F401 --fix
```

**Files to verify after auto-fix**:
- [ ] `src/raxe/application/scan_pipeline.py` - Remove `from typing import Any`
- [ ] `src/raxe/cli/l2_formatter.py` - Remove `from rich.table import Table`
- [ ] `src/raxe/cli/privacy.py` - Remove Panel and Table imports
- [ ] `src/raxe/cli/validate.py` - Remove Text and ValidationIssue imports
- [ ] `src/raxe/domain/ml/model_registry.py` - Remove 5 unused imports (lines 266-270)

**Test**: `pytest tests/ -x --tb=short`

---

### 2. Fix Unused Variables (30 min)

#### File: `src/raxe/domain/rules/validator.py`
**Line 223**:
```python
# BEFORE:
compiled = re.compile(pattern)

# AFTER (option 1 - show intent):
_ = re.compile(pattern)  # Test pattern compilation

# AFTER (option 2 - use result):
re.compile(pattern)  # Raises exception if invalid
```

#### File: `src/raxe/sdk/client.py`
**Line 376**:
```python
# BEFORE:
loop = asyncio.get_event_loop()

# AFTER (if not needed):
# Remove the line entirely

# OR (if needed):
loop = asyncio.get_event_loop()
# Use loop for something...
```

#### File: `src/raxe/sdk/integrations/langchain.py`
**Line 309**:
```python
# BEFORE:
inputs = something

# AFTER:
# Remove if truly unused, or rename to _ if needed for unpacking
```

**Test**: `pytest tests/unit/ -k "validator or client or langchain"`

---

### 3. Add Missing Dependency (5 min)

Edit `/Users/mh/github-raxe-ai/raxe-ce/pyproject.toml`:

```toml
dependencies = [
    "click>=8.0,<9.0",
    "pydantic>=2.0,<3.0",
    "httpx>=0.24,<1.0",
    "structlog>=23.0,<25.0",
    "sqlalchemy>=2.0,<3.0",
    "pyyaml>=6.0,<7.0",
    "rich>=13.0,<14.0",
    "tomli>=2.0,<3.0; python_version < '3.11'",
    "jsonschema>=4.17,<5.0",  # ADD THIS LINE
]
```

**Test**:
```bash
uv pip install -e .
pytest tests/unit/infrastructure/schemas/ -v
```

---

## Verification Commands

After each section:

```bash
# Check for regressions
ruff check src/raxe --select=F401,F841,ARG
pytest tests/unit/ -v --tb=short

# Verify no new issues
mypy src/raxe --strict
```

---

## Git Commits

```bash
# After completing all fixes:
git add src/raxe
git commit -m "chore: remove unused imports and fix unused variables"

git add pyproject.toml
git commit -m "fix: add missing jsonschema dependency"

# Push when tests pass
git push origin main
```

---

## Success Criteria

- [ ] All unused imports removed
- [ ] All unused variables fixed
- [ ] jsonschema dependency added
- [ ] All unit tests passing
- [ ] Ruff shows 11 fewer F401 errors
- [ ] Ruff shows 3 fewer F841 errors
- [ ] No test collection errors for schema tests

---

## Next Steps (Future)

See `DEAD_CODE_ANALYSIS_REPORT.md` for:
- Medium priority cleanup tasks
- Feature implementation recommendations
- Long-term technical debt items
