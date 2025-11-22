# RAXE CE - Aggressive Pre-Release Cleanup Plan

**Context**: No backwards compatibility needed - product hasn't been released yet
**Goal**: Ship with clean, polished, production-ready APIs
**Time**: 2-3 hours
**Risk**: LOW - comprehensive tests will catch any issues

---

## Phase 1: Auto-Fixable Issues (30 min)

### 1.1 Remove All Unused Imports (10 min)
```bash
cd /Users/mh/github-raxe-ai/raxe-ce
source .venv/bin/activate

# Auto-fix with ruff
ruff check src/raxe --select=F401 --fix

# Verify the changes
git diff src/raxe
```

**Expected Changes**:
- `src/raxe/application/scan_pipeline.py:20` - Remove `Any`
- `src/raxe/cli/l2_formatter.py:20` - Remove `Table`
- `src/raxe/cli/privacy.py:9,11` - Remove `Panel`, `Table`
- `src/raxe/cli/validate.py:11,13` - Remove `Text`, `ValidationIssue`
- `src/raxe/domain/ml/model_registry.py:266-270` - Remove 5 model metadata imports

**Impact**: 11 imports removed, ~12 LOC

### 1.2 Fix Unused Variables (10 min)

**File: `src/raxe/domain/rules/validator.py:223`**
```python
# Before
compiled = re.compile(pattern)

# After - show intent explicitly
_ = re.compile(pattern)  # Validate pattern compiles
```

**File: `src/raxe/sdk/client.py:376`**
```python
# Before
loop = asyncio.get_event_loop()

# After - delete the line entirely
# (no longer needed after refactor)
```

**File: `src/raxe/sdk/integrations/langchain.py:309`**
```python
# Review context and delete if truly unused
```

### 1.3 Add Missing Dependency (10 min)
```bash
# Edit pyproject.toml
# Add to dependencies array:
"jsonschema>=4.17,<5.0",

# Update lock file
uv pip install -e .
```

---

## Phase 2: API Cleanup (60 min)

### 2.1 Remove `performance_mode` Parameter (20 min)

**Rationale**: Not implemented, confuses users, creates API clutter

**Files to modify**:
- `src/raxe/sdk/client.py:67` - Remove param from `__init__`
- `src/raxe/async_sdk/client.py:85` - Remove param from `__init__`
- Update any tests that pass this parameter

**Breaking Change**: YES - but pre-release, so acceptable

**Action**:
1. Search for all uses: `grep -r "performance_mode" src/ tests/`
2. Remove parameter from function signatures
3. Remove parameter from docstrings
4. Update tests
5. Run tests: `pytest tests/unit/sdk/ -v`

### 2.2 Remove `verbose` from Doctor Functions (20 min)

**Rationale**: 5 functions accept but ignore `verbose` - confusing UX

**Files to modify**:
- `src/raxe/cli/doctor.py:126` - `_check_installation`
- `src/raxe/cli/doctor.py:199` - `_check_configuration`
- `src/raxe/cli/doctor.py:268` - `_check_database`
- `src/raxe/cli/doctor.py:346` - `_check_rule_packs`
- `src/raxe/cli/doctor.py:400` - `_check_performance`

**Options**:
A. **REMOVE** the parameter entirely (recommended - clean API)
B. **IMPLEMENT** verbose logging (2-3 hours extra work)

**Recommendation**: REMOVE - you can add verbose mode in v0.2.0 if needed

### 2.3 Clean Achievement Service (20 min)

**File**: `src/raxe/application/analytics/achievement_service.py`

**Issues**:
- Line 262: `days` parameter unused
- Line 300: `limit` parameter unused

**Options**:
A. **IMPLEMENT** - add date filtering and pagination (1-2 hours)
B. **REMOVE** - simplify API for v1.0, add in v0.2.0

**Recommendation**:
- If analytics are core feature: IMPLEMENT
- If analytics are nice-to-have: REMOVE params, add later

---

## Phase 3: Delete Incomplete Features (30 min)

### 3.1 Audit Log System - DELETE

**File**: `src/raxe/infrastructure/suppression/file_repository.py:158-160`

**Current State**: Returns empty list, parameters unused

**Action**: DELETE the entire `get_audit_log` method

```python
def get_audit_log(
    self,
    limit: int = 100,
    pattern: str | None = None,
    action: str | None = None,
) -> list[dict[str, Any]]:
    """Get audit log of suppression actions."""
    # TODO: Implement audit log
    return []
```

**Rationale**:
- Not implemented
- Placeholder code
- Creates false expectations
- Can add in future if needed

**Alternative**: If you want to keep the API, mark as experimental:

```python
def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
    """
    Get audit log of suppression actions.

    Warning: This feature is not yet implemented. Returns empty list.
    Will be implemented in a future release.
    """
    return []
```

### 3.2 Parallel Processing - REMOVE or DOCUMENT

**File**: `src/raxe/cli/main.py:535`

**Issue**: `parallel` parameter unused

**Options**:
A. REMOVE - clean API
B. IMPLEMENT - add parallel scanning (4-6 hours)
C. DOCUMENT - mark as "coming soon"

**Recommendation**: REMOVE - add in v0.2.0 as performance feature

---

## Phase 4: Modern Python Patterns (30 min)

### 4.1 Add Future Annotations

Add to ALL SDK files with forward references:

```python
from __future__ import annotations
```

**Files**:
- `src/raxe/sdk/decorator.py`
- `src/raxe/sdk/wrappers/__init__.py`
- `src/raxe/sdk/wrappers/anthropic.py`
- `src/raxe/sdk/wrappers/openai.py`
- `src/raxe/sdk/wrappers/vertexai.py`
- `src/raxe/domain/ml/model_registry.py`

**Then remove string quotes from type hints**:

```python
# Before
def wrap(client: "Raxe") -> "ScanResult":
    pass

# After
from __future__ import annotations

def wrap(client: Raxe) -> ScanResult:
    pass
```

**Benefits**:
- Cleaner code
- Better IDE autocomplete
- Modern Python style
- No flake8 F821 warnings

---

## Phase 5: Testing & Verification (30 min)

### 5.1 Run Full Test Suite
```bash
# Run all tests
pytest tests/ -v --tb=short

# Check for failures
# Fix any breakages from API changes
```

### 5.2 Run All Quality Checks
```bash
# Linting
ruff check src/raxe
pylint src/raxe --exit-zero

# Type checking
mypy src/raxe --ignore-missing-imports

# Dead code check (should be clean now!)
vulture src/raxe --min-confidence=80
```

### 5.3 Integration Smoke Test
```bash
# Test CLI works
.venv/bin/raxe --help
.venv/bin/raxe doctor
.venv/bin/raxe scan --prompt "test prompt"

# Test SDK
python -c "from raxe import Raxe; print('SDK imports OK')"
```

---

## Phase 6: Documentation Updates (20 min)

### 6.1 Update CHANGELOG
Document removed parameters as "cleaned up unused API parameters"

### 6.2 Update SDK Documentation
Remove references to:
- `performance_mode` parameter
- `parallel` parameter
- Any other removed features

### 6.3 Update Examples
Ensure all examples work with cleaned APIs

---

## Summary of Changes

### Will Remove:
1. ✅ 11 unused imports (~12 LOC)
2. ✅ 3 unused variables (~3 LOC)
3. ✅ `performance_mode` parameter from SDK
4. ✅ `verbose` parameter from 5 doctor functions
5. ✅ `parallel` parameter from CLI
6. ✅ `days`, `limit` from achievement service
7. ✅ `get_audit_log` method (or mark as unimplemented)
8. ✅ Forward reference string quotes (add __future__ imports)

### Will Add:
1. ✅ `jsonschema>=4.17,<5.0` dependency
2. ✅ `from __future__ import annotations` to 6+ files

### Net Result:
- **Removed**: ~50-100 LOC of dead/unused code
- **Cleaner APIs**: No confusing unused parameters
- **Modern Python**: PEP 563 style annotations
- **Production Ready**: No half-implemented features
- **Great First Impression**: Clean, professional codebase

---

## Execution Checklist

- [ ] Phase 1: Auto-fixes (30 min)
  - [ ] Remove unused imports with ruff
  - [ ] Fix unused variables manually
  - [ ] Add jsonschema dependency
- [ ] Phase 2: API cleanup (60 min)
  - [ ] Remove performance_mode
  - [ ] Remove verbose from doctor
  - [ ] Clean achievement service
- [ ] Phase 3: Delete incomplete features (30 min)
  - [ ] Delete or document audit log
  - [ ] Remove parallel parameter
- [ ] Phase 4: Modern Python (30 min)
  - [ ] Add __future__ annotations
  - [ ] Remove string type hints
- [ ] Phase 5: Testing (30 min)
  - [ ] Run full test suite
  - [ ] Run quality checks
  - [ ] Smoke test CLI and SDK
- [ ] Phase 6: Documentation (20 min)
  - [ ] Update CHANGELOG
  - [ ] Update docs
  - [ ] Update examples

**Total Time**: 2-3 hours
**Risk**: LOW (comprehensive tests will catch issues)
**Benefit**: Production-ready, professional codebase for launch

---

## Alternative: Conservative Approach

If you prefer to be more conservative:

1. **Do Phase 1 only** (30 min) - Safe, obvious wins
2. **Leave API changes for post-release** - Less risk
3. **Document incomplete features** - Set expectations

But my recommendation: **Go aggressive**. You have one chance to make a first impression. Ship with clean, polished APIs that you're proud of.
