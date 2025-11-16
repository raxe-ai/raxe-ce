# Migration Guide: Public API Changes

**Version:** 1.0.0
**Date:** 2025-11-16
**Sprint:** Sprint 5 - Phase 4 CLI Architecture Fixes

## Overview

This document describes the changes made to the Raxe SDK client to provide a public API for CLI commands and diagnostic tools. These changes eliminate the need for private attribute access while maintaining backward compatibility.

## What Changed

### New Public API Methods

The `Raxe` client now exposes the following public methods:

```python
class Raxe:
    # Rule and pack access
    def get_all_rules(self) -> list
    def list_rule_packs(self) -> list[str]

    # Configuration queries
    def has_api_key(self) -> bool
    def get_performance_mode(self) -> str
    def get_telemetry_enabled(self) -> bool

    # Diagnostic access
    def get_profiling_components(self) -> Dict[str, Any]
    def get_pipeline_stats(self) -> Dict[str, Any]
    def validate_configuration(self) -> Dict[str, Any]
```

### Why These Changes Were Made

**Problem:** CLI commands were accessing private attributes like `raxe._pipeline`, `raxe._api_key`, which violates Clean Architecture principles and makes the codebase fragile.

**Solution:** Add public API methods that provide controlled access to internal components, making the API contract explicit and stable.

## Migration Examples

### Example 1: Accessing Rules

**Before (DEPRECATED):**
```python
from raxe.sdk.client import Raxe

raxe = Raxe()
rules = raxe._pipeline.pack_registry.get_all_rules()  # ❌ Private access
```

**After (RECOMMENDED):**
```python
from raxe.sdk.client import Raxe

raxe = Raxe()
rules = raxe.get_all_rules()  # ✅ Public API
```

### Example 2: Listing Rule Packs

**Before (DEPRECATED):**
```python
raxe = Raxe()
packs = raxe._pipeline.pack_registry.list_packs()  # ❌ Private access
```

**After (RECOMMENDED):**
```python
raxe = Raxe()
packs = raxe.list_rule_packs()  # ✅ Public API

# Note: Returns RulePack objects, not just names
pack_ids = [pack.manifest.id for pack in packs]
```

### Example 3: Checking API Key

**Before (DEPRECATED):**
```python
raxe = Raxe()
if hasattr(raxe, "_api_key") and raxe._api_key:  # ❌ Private access
    print("API key configured")
```

**After (RECOMMENDED):**
```python
raxe = Raxe()
if raxe.has_api_key():  # ✅ Public API
    print("API key configured")
```

### Example 4: Profiling Components

**Before (DEPRECATED):**
```python
raxe = Raxe()
executor = raxe._pipeline.rule_executor  # ❌ Private access
l2_detector = raxe._pipeline.l2_detector  # ❌ Private access
rules = raxe._pipeline.pack_registry.get_all_rules()  # ❌ Private access
```

**After (RECOMMENDED):**
```python
raxe = Raxe()
components = raxe.get_profiling_components()  # ✅ Public API

executor = components['executor']
l2_detector = components['l2_detector']
rules = components['rules']
```

### Example 5: Pipeline Statistics

**Before (DEPRECATED):**
```python
raxe = Raxe()
# Multiple private attribute accesses
rules_count = len(raxe._pipeline.pack_registry.get_all_rules())
packs_count = len(raxe._pipeline.pack_registry.list_packs())
has_api_key = bool(raxe._api_key)
```

**After (RECOMMENDED):**
```python
raxe = Raxe()
stats = raxe.get_pipeline_stats()  # ✅ Public API

rules_count = stats['rules_loaded']
packs_count = stats['packs_loaded']
has_api_key = stats['has_api_key']
telemetry_enabled = stats['telemetry_enabled']
```

### Example 6: Configuration Validation

**Before:** No public method available

**After (NEW):**
```python
raxe = Raxe()
validation = raxe.validate_configuration()

if not validation['config_valid']:
    print("Configuration errors:")
    for error in validation['errors']:
        print(f"  - {error}")

if validation['warnings']:
    print("Configuration warnings:")
    for warning in validation['warnings']:
        print(f"  - {warning}")
```

## Affected CLI Commands

The following CLI commands were updated to use the new public API:

1. **`raxe doctor`** - Uses `get_all_rules()`, `list_rule_packs()`
2. **`raxe profiler`** - Uses `get_profiling_components()`
3. **`raxe test`** - Uses `has_api_key()`
4. **`raxe rules`** - Uses `get_all_rules()`
5. **`raxe repl`** - Uses `get_all_rules()`

## Backward Compatibility

**Current Status:** FULLY BACKWARD COMPATIBLE

- The private attributes (`_pipeline`, `_api_key`) are still accessible
- No breaking changes to existing code
- Deprecation warnings will be added in a future release

**Future Plans:**

- **v1.1.0** (Q1 2026): Add deprecation warnings for private attribute access
- **v2.0.0** (Q2 2026): Remove or hide private attributes (breaking change)

## Deprecation Timeline

| Version | Date | Action |
|---------|------|--------|
| v1.0.0 | 2025-11-16 | Public API added, private access still works |
| v1.1.0 | Q1 2026 | Deprecation warnings added for private access |
| v2.0.0 | Q2 2026 | Private attributes removed or hidden |

## Testing Your Code

### Automated Check

Use our architecture validation script to check for violations:

```bash
python scripts/check_architecture_violations.py
```

This script will:
- Scan all CLI files for private attribute access
- Report violations with line numbers
- Verify Clean Architecture compliance

### Manual Check

Search your code for private attribute access:

```bash
# Find violations in your custom code
grep -r "\._pipeline\|\._api_key\|\._config" your_code_directory/
```

## API Reference

### `get_all_rules() -> list`

Get all loaded detection rules from all packs.

**Returns:** List of Rule objects

**Example:**
```python
raxe = Raxe()
rules = raxe.get_all_rules()

for rule in rules:
    print(f"{rule.rule_id}: {rule.name}")
```

### `list_rule_packs() -> list[RulePack]`

List all loaded rule packs.

**Returns:** List of RulePack objects

**Example:**
```python
raxe = Raxe()
packs = raxe.list_rule_packs()

for pack in packs:
    print(f"{pack.manifest.id} v{pack.manifest.version}")
```

### `has_api_key() -> bool`

Check if an API key is configured.

**Returns:** True if API key is set, False otherwise

**Example:**
```python
raxe = Raxe()
if raxe.has_api_key():
    print("Cloud features available")
else:
    print("Running in offline mode")
```

### `get_performance_mode() -> str`

Get the current performance mode setting.

**Returns:** 'fast', 'balanced', or 'thorough'

**Example:**
```python
raxe = Raxe()
mode = raxe.get_performance_mode()
print(f"Performance mode: {mode}")
```

### `get_telemetry_enabled() -> bool`

Check if telemetry is enabled.

**Returns:** True if telemetry is enabled

**Example:**
```python
raxe = Raxe()
if raxe.get_telemetry_enabled():
    print("Telemetry active")
```

### `get_profiling_components() -> Dict[str, Any]`

Get internal components for profiling and diagnostics.

**Returns:** Dictionary with:
- `executor`: RuleExecutor instance
- `l2_detector`: L2Detector instance (or None if disabled)
- `rules`: List of all loaded rules

**Example:**
```python
raxe = Raxe()
components = raxe.get_profiling_components()

# Use for profiling
profiler = ScanProfiler(
    rule_executor=components['executor'],
    l2_detector=components['l2_detector']
)
```

### `get_pipeline_stats() -> Dict[str, Any]`

Get pipeline statistics for diagnostics.

**Returns:** Dictionary with:
- `rules_loaded`: Number of rules loaded
- `packs_loaded`: Number of packs loaded
- `performance_mode`: Current performance mode
- `telemetry_enabled`: Whether telemetry is enabled
- `has_api_key`: Whether API key is configured
- `l2_enabled`: Whether L2 detection is enabled
- `preload_time_ms`: Initialization time (if available)
- `patterns_compiled`: Number of patterns compiled (if available)

**Example:**
```python
raxe = Raxe()
stats = raxe.get_pipeline_stats()

print(f"Rules: {stats['rules_loaded']}")
print(f"Packs: {stats['packs_loaded']}")
print(f"L2 enabled: {stats['l2_enabled']}")
```

### `validate_configuration() -> Dict[str, Any]`

Validate the current configuration.

**Returns:** Dictionary with:
- `config_valid`: True if configuration is valid
- `errors`: List of error messages (blocking issues)
- `warnings`: List of warning messages (non-blocking issues)

**Example:**
```python
raxe = Raxe()
validation = raxe.validate_configuration()

if not validation['config_valid']:
    print("Configuration errors found:")
    for error in validation['errors']:
        print(f"  ERROR: {error}")
    sys.exit(1)

if validation['warnings']:
    print("Configuration warnings:")
    for warning in validation['warnings']:
        print(f"  WARNING: {warning}")
```

## FAQ

### Q: Will my existing code break?

**A:** No, existing code will continue to work. Private attributes are still accessible for now.

### Q: When should I migrate to the public API?

**A:** As soon as possible. The public API is more stable and won't change without deprecation warnings.

### Q: What if I need access to something not in the public API?

**A:** Please open an issue on GitHub describing your use case. We'll consider adding it to the public API.

### Q: Are there performance differences?

**A:** No, the public API methods are simple wrappers with no performance overhead.

### Q: Can I still use private attributes after v2.0.0?

**A:** No, they will be removed or hidden in v2.0.0. Migrate to the public API before then.

## Support

If you encounter issues during migration:

1. Check this guide for examples
2. Run the validation script: `python scripts/check_architecture_violations.py`
3. Open an issue: https://github.com/raxe-ai/raxe-ce/issues

## Changes Summary

| What Changed | Old Approach | New Approach |
|-------------|-------------|--------------|
| Rule access | `raxe._pipeline.pack_registry.get_all_rules()` | `raxe.get_all_rules()` |
| Pack listing | `raxe._pipeline.pack_registry.list_packs()` | `raxe.list_rule_packs()` |
| API key check | `raxe._api_key` | `raxe.has_api_key()` |
| Profiling | Multiple `raxe._pipeline.*` | `raxe.get_profiling_components()` |
| Statistics | Multiple private accesses | `raxe.get_pipeline_stats()` |
| Validation | No public method | `raxe.validate_configuration()` |

---

**Last Updated:** 2025-11-16
**Document Version:** 1.0.0
**Maintainer:** RAXE CE Team
