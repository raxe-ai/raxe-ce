# RAXE CLI Technical Audit Report

**Date:** November 21, 2025
**Auditor:** Tech Lead
**Scope:** Complete CLI implementation audit with focus on dead code, missing features, and technical debt

## Executive Summary

The RAXE CLI has significant issues with unregistered commands, stale code references, and inconsistent implementation patterns. While core functionality (scan, init, models) works, there are missing command registrations and references to deprecated features that need immediate cleanup.

## 1. Command Registration Audit

### ✅ Registered Commands (Working)
- `init` - Configuration initialization
- `scan` - Text scanning
- `batch` - Batch scanning
- `test` - Configuration testing
- `stats` - Statistics display
- `export` - Export functionality
- `repl` - Interactive shell
- `rules` - Rule management
- `doctor` - System health checks
- `models` - L2 model management
- `profile` - Performance profiling
- `privacy` - Privacy information
- `suppress` - Suppression management
- `tune` - Detection tuning
- `validate-rule` - Rule validation
- `pack` - Pack management (inline in main.py)
- `plugins` - Plugin listing (inline in main.py)
- `completion` - Shell completions (inline in main.py)

### ❌ Unregistered Commands (Dead Code)
- **`config.py`** - Complete config management CLI exists but not registered
- **`custom_rules.py`** - Custom rule management exists but not exposed
- **`history.py`** - Scan history management exists but not exposed

### 🔧 Support Files (Not Commands)
- `branding.py` - UI/branding utilities
- `output.py` - Output formatting
- `l2_formatter.py` - L2 result formatting
- `progress.py` - Progress indicators
- `progress_context.py` - Progress context management

## 2. Code Cleanliness Issues

### Critical Issues (Priority: HIGH)

#### 1. Missing Command Registrations
**Files:** `/src/raxe/cli/main.py`
- `config` command group not imported or registered
- `history` command group not imported or registered
- `custom_rules` integrated into rules but separate file exists

**Fix Required:**
```python
# Add to imports
from raxe.cli.config import config
from raxe.cli.history import history

# Add to registrations
cli.add_command(config)
cli.add_command(history)
```

#### 2. Bundle References (Deprecated)
**Files with bundle references:**
- `/src/raxe/cli/l2_formatter.py` - Comments about "bundle schema fields"
- `/src/raxe/cli/doctor.py` - References to "bundled packs"
- `/src/raxe/cli/models.py` - Example mentions "v1.0_bundle"
- `/src/raxe/cli/main.py` - Comments about "bundle metadata"

**Action:** Remove all bundle references, update to folder-based model terminology

### Medium Issues (Priority: MEDIUM)

#### 3. Inconsistent Error Handling
- Some commands use `display_error()` + `sys.exit(1)`
- Others use `raise click.Abort()`
- No consistent pattern for error codes

#### 4. Incomplete Command Options
- `rules list` doesn't accept `--limit` despite user expectation
- `batch` mentions `--parallel` but doesn't implement parallelization
- Several commands have placeholder implementations

### Low Issues (Priority: LOW)

#### 5. Documentation Inconsistencies
- Help text references features not fully implemented
- Examples show commands that don't exist
- Completion scripts list commands differently than actual implementation

## 3. Models Command Assessment

### ✅ Working Features
- `models list` - Lists available models correctly
- `models info` - Shows model details
- `models compare` - Compares models
- `models set-default` - Sets default model

### ⚠️ Issues Found
- Models show "unknown" for latency/accuracy (metadata not populated)
- Example still references "v1.0_bundle" format
- No integration with actual model performance metrics

## 4. Configuration Commands Assessment

### ❌ Config Command Not Available
The entire `config` command group exists but isn't registered:
- `config show` - Would display configuration
- `config set` - Would update configuration
- `config reset` - Would reset to defaults
- `config validate` - Would validate config
- `config edit` - Would open in editor

**Impact:** Users must manually edit `~/.raxe/config.yaml`

## 5. Stale Code Analysis

### Files to Remove/Refactor
1. **`custom_rules.py`** - Duplicate functionality with rules.py
2. Bundle-related comments throughout codebase
3. Unused telemetry endpoints referenced in init command

### Dead Functions/Imports
- No systematic unused import detection possible (AST analysis failed)
- Manual review shows most imports are used
- Some redundant imports in test files

## 6. Priority Action Items

### 🔴 Critical (Fix Immediately)
1. **Register missing commands** - Add config and history to main.py
2. **Remove bundle references** - Clean up all deprecated terminology
3. **Fix model metadata** - Populate performance metrics correctly

### 🟡 High (Fix This Sprint)
1. **Standardize error handling** - Use consistent patterns
2. **Complete partial implementations** - Finish placeholder commands
3. **Update documentation** - Fix help text and examples

### 🟢 Medium (Next Sprint)
1. **Consolidate custom_rules.py** - Merge with rules.py
2. **Add missing command options** - Implement expected flags
3. **Improve test coverage** - Add CLI command tests

### 🔵 Low (Backlog)
1. **Optimize imports** - Remove redundant imports
2. **Enhance completion scripts** - Make them dynamic
3. **Add telemetry for CLI usage** - Track command usage patterns

## 7. Specific Files to Modify

### Files to Update (High Priority)
```
src/raxe/cli/main.py - Add config, history commands
src/raxe/cli/l2_formatter.py - Remove bundle comments (lines 194, 204, 233, 244, 267, 282, 311)
src/raxe/cli/doctor.py - Remove bundled packs check (lines 371-386)
src/raxe/cli/models.py - Update example (line 301)
```

### Files to Consider Removing
```
src/raxe/cli/custom_rules.py - Redundant with rules.py functionality
```

### Files to Keep As-Is
```
src/raxe/cli/branding.py - Working utility file
src/raxe/cli/output.py - Working utility file
src/raxe/cli/progress*.py - Working progress indicators
```

## 8. Testing Results

| Command | Status | Issues |
|---------|---------|---------|
| `raxe init` | ✅ Works | None |
| `raxe scan` | ✅ Works | None |
| `raxe models list` | ✅ Works | Missing performance data |
| `raxe config` | ❌ Not Found | Command not registered |
| `raxe rules list` | ✅ Works | Missing --limit option |
| `raxe doctor` | Not Tested | Likely works |
| `raxe stats` | Not Tested | Likely works |

## 9. Recommendations

1. **Immediate Action:** Register config and history commands to unlock functionality
2. **Quick Win:** Remove all bundle references (30 min task)
3. **User Impact:** Fix models to show actual performance metrics
4. **Tech Debt:** Consolidate duplicate rule management code
5. **Documentation:** Update all help text to match actual implementation

## 10. Compliance Check

### Clean Architecture Violations
- None found in CLI layer
- Proper separation of concerns maintained

### Performance Concerns
- Batch command claims parallel support but doesn't implement it
- No rate limiting on API calls in config

### Security Issues
- API key properly masked in display
- No PII leakage detected
- Telemetry properly optional

## Conclusion

The RAXE CLI is functional but has significant technical debt. The most critical issue is unregistered commands that exist but users cannot access. Bundle terminology cleanup and command registration should be prioritized for immediate fixes. The codebase is well-structured but needs consistency improvements and removal of deprecated references.

**Recommended Next Steps:**
1. Register config and history commands (5 min fix)
2. Remove bundle references globally (30 min fix)
3. Populate model performance metrics (1 hour task)
4. Consolidate custom rules functionality (2 hour refactor)