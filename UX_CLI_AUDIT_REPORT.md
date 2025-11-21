# RAXE CLI User Experience Audit Report

**Date:** 2025-11-21
**Auditor:** UX Designer Agent
**Scope:** Complete CLI command structure, user flows, help text, and error handling
**Status:** ⚠️ Critical issues found requiring immediate attention

---

## Executive Summary

The RAXE CLI demonstrates strong foundational UX with excellent visual design, clear help text, and privacy-first messaging. However, there are **critical inconsistencies** between implemented commands, registered commands, and documented commands that create broken user flows and discovery issues.

**Key Findings:**
- ✅ **15 working commands** with excellent UX
- ⚠️ **2 broken commands** (not registered but imported/referenced)
- ❌ **1 incomplete command** (stub implementation)
- 🔍 **Multiple discovery issues** (commands mentioned but not accessible)

**Overall Score:** 7.5/10 (Strong foundation, needs consistency fixes)

---

## 1. Command Inventory & Status

### ✅ Working Commands (15)

| Command | Status | Help Text | Error Handling | User Flow |
|---------|--------|-----------|----------------|-----------|
| `raxe` | ✅ | Excellent | ✅ | Perfect welcome screen |
| `raxe init` | ✅ | Excellent | ✅ | Clear onboarding |
| `raxe scan` | ✅ | Excellent | ✅ | Excellent visual output |
| `raxe batch` | ✅ | Excellent | ✅ | Good progress indicators |
| `raxe test` | ✅ | Excellent | ✅ | Clear health checks |
| `raxe stats` | ✅ | Excellent | ✅ | Engaging metrics display |
| `raxe doctor` | ✅ | Excellent | ✅ | Helpful diagnostics |
| `raxe export` | ✅ | Good | ✅ | Clear options |
| `raxe repl` | ✅ | Excellent | ⚠️ | (Not tested live) |
| `raxe rules` | ✅ | Excellent | ✅ | Comprehensive subcommands |
| `raxe models` | ✅ | Excellent | ✅ | Well-structured management |
| `raxe pack` | ✅ | Good | ⚠️ | Stub implementation |
| `raxe plugins` | ✅ | Good | ✅ | Clear status display |
| `raxe privacy` | ✅ | Excellent | ✅ | Strong privacy messaging |
| `raxe profile` | ✅ | Good | ✅ | Performance insights |
| `raxe suppress` | ✅ | Good | ⚠️ | (Not tested live) |
| `raxe tune` | ✅ | Good | ⚠️ | (Not tested live) |
| `raxe validate-rule` | ✅ | Excellent | ✅ | Comprehensive validation |
| `raxe completion` | ✅ | Good | ✅ | Multi-shell support |

### ⚠️ Broken Commands (2)

#### 1. `raxe history` - BROKEN
**File:** `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/history.py:17`
**Issue:** Command implemented but not imported or registered in main.py
**Impact:** HIGH - Command is referenced in REPL help but doesn't work
**Error Message:**
```
Error: No such command 'history'.
```

**Fix Required:**
```python
# File: src/raxe/cli/main.py:13-25
# ADD THIS IMPORT:
from raxe.cli.history import history

# ADD THIS REGISTRATION (line ~903):
cli.add_command(history)
```

**Evidence:**
- Command defined: `src/raxe/cli/history.py:17` (`@click.group()`)
- Missing import: `src/raxe/cli/main.py` (no history import)
- Missing registration: `src/raxe/cli/main.py:892-903` (history not added)
- Referenced in REPL: `src/raxe/cli/repl.py` mentions "history" command

#### 2. `raxe config` - BROKEN
**File:** `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/config.py:16`
**Issue:** Command implemented but not imported or registered in main.py
**Impact:** MEDIUM - Users cannot view/manage configuration via CLI
**Error Message:**
```
Error: No such command 'config'.
```

**Fix Required:**
```python
# File: src/raxe/cli/main.py:13-25
# ADD THIS IMPORT:
from raxe.cli.config import config

# ADD THIS REGISTRATION (line ~903):
cli.add_command(config)
```

**Evidence:**
- Command defined: `src/raxe/cli/config.py:16` (`@click.group()`)
- Has subcommands: `show`, `set`, `reset`
- Missing import: `src/raxe/cli/main.py` (no config import)
- Missing registration: `src/raxe/cli/main.py:892-903` (config not added)

### ❌ Incomplete Commands (1)

#### `raxe pack info` - STUB
**File:** `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/main.py:729-732`
**Issue:** Placeholder implementation with TODO message
**Impact:** LOW - Command exists but provides no useful information
**Output:**
```
Pack: core
  (Full pack info coming in next sprint)
```

**Recommendation:** Either implement or remove from help text until ready

---

## 2. Command Discovery Issues

### Issue 2.1: Inconsistent Command Listing

**Problem:** Different places list different commands, creating confusion

**Evidence:**

1. **Welcome Screen** (`raxe` with no args):
   - Lists: scan, init, test, stats, batch, repl, export, rules, tune, doctor, profile
   - Missing: models, pack, plugins, privacy, suppress, validate-rule, completion, **history**, **config**

2. **Help Output** (`raxe --help`):
   - Lists all registered commands correctly
   - Missing: **history**, **config** (because they're broken)

3. **Completion Script** (`raxe completion bash`):
   ```bash
   opts="init scan batch test stats export repl rules doctor pack plugins privacy profile suppress tune validate-rule completion --help --version"
   ```
   - Missing: **models**, **history**, **config**

4. **REPL Help** (`src/raxe/cli/repl.py`):
   - References `history` command (which doesn't work)
   - Lists `config` command (which doesn't work)

**Fix Priority:** HIGH
**Files to Update:**
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/branding.py:149-175`
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/main.py:821` (bash completion)
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/main.py:830-854` (zsh completion)
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/main.py:859-876` (fish completion)
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/main.py:880-886` (powershell completion)

### Issue 2.2: Missing `models` Command in Welcome Screen

**Problem:** `raxe models` is fully implemented and working but not shown in welcome banner

**File:** `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/branding.py:149-175`

**Current State:**
```python
config_commands = [
    ("raxe rules", "Manage detection rules"),
    ("raxe tune", "Fine-tune detection settings"),
    ("raxe doctor", "Diagnose issues"),
]
```

**Recommended Addition:**
```python
config_commands = [
    ("raxe rules", "Manage detection rules"),
    ("raxe models", "Manage L2 models"),  # ADD THIS
    ("raxe tune", "Fine-tune detection settings"),
    ("raxe doctor", "Diagnose issues"),
]
```

---

## 3. User Flow Analysis

### Flow 3.1: First-Time User Experience ✅ EXCELLENT

**Journey:** Install → First Scan

**Steps:**
1. User runs `raxe` → Beautiful welcome banner with clear next steps
2. User runs `raxe scan "test"` → Works perfectly with privacy messaging
3. Time to value: **< 10 seconds** ✅

**Strengths:**
- Gorgeous ASCII art logo (on-brand, memorable)
- Clear "Quick Start" section in welcome banner
- Privacy messaging reinforced throughout
- No required setup (works out of box)

**Recommendation:** Keep this flow unchanged - it's excellent!

### Flow 3.2: Configuration & Setup ⚠️ GOOD (with issues)

**Journey:** First scan → Customize settings

**Current Path:**
1. User runs `raxe init` → Creates config file
2. User wants to view config → ❌ `raxe config` doesn't work
3. User has to manually edit `~/.raxe/config.yaml`

**Expected Path:**
1. User runs `raxe init` → Creates config file
2. User runs `raxe config show` → Views current settings
3. User runs `raxe config set detection.mode fast` → Updates setting
4. User runs `raxe models list` → Picks L2 model
5. User runs `raxe models set-default <model>` → Updates default

**Fix:** Register `config` command to enable this flow

### Flow 3.3: Rule Management ✅ EXCELLENT

**Journey:** Discover rules → Test rule → Create custom rule

**Path:**
1. `raxe rules list` → Browse available rules ✅
2. `raxe rules search "injection"` → Find relevant rules ✅
3. `raxe rules show pi-001` → Learn about specific rule ✅
4. `raxe rules test pi-001 "test"` → Validate behavior ✅
5. `raxe rules custom create` → Build custom rule ✅

**Strengths:**
- Comprehensive subcommand structure
- Excellent help text with examples
- Educational focus (explains WHY rules exist)
- Clear visual hierarchy in output

**Recommendation:** Showcase this in README - it's a killer feature!

### Flow 3.4: Model Management ✅ GOOD

**Journey:** List models → Compare → Set default

**Path:**
1. `raxe models list` → See available models ✅
2. `raxe models info <id>` → View detailed metrics ✅
3. `raxe models compare` → Side-by-side comparison ✅
4. `raxe models set-default <id>` → Update config ✅

**Strengths:**
- Clear performance metrics (P95 latency, accuracy)
- Visual indicators (⚡ for fast, 🎯 for accurate)
- Helpful error messages when model not found

**Minor Issue:** Not listed in welcome banner (see Issue 2.2)

### Flow 3.5: History & Analytics ❌ BROKEN

**Journey:** View past scans → Export data

**Current Path:**
1. User runs scans → Data stored in `~/.raxe/scan_history.db`
2. User runs `raxe history list` → ❌ Command doesn't exist
3. User runs `raxe export` → Works, but no way to preview first

**Expected Path:**
1. User runs `raxe history list` → View recent scans
2. User runs `raxe history show <id>` → View scan details
3. User runs `raxe history clear` → Clean up old data
4. User runs `raxe export --days 30` → Export to file

**Fix:** Register `history` command to enable this flow

---

## 4. Error Handling Assessment

### Excellent Error Handling ✅

**Example 1: Missing scan argument**
```bash
$ raxe scan
```
**Output:**
```
╭───────────────────────────────╮
│ ❌ ERROR                      │
╰───────────────────────────────╯

No text provided

Details:
Provide text as argument or use --stdin
```

**Strengths:**
- Clear visual structure (panel with emoji)
- Specific error message
- Actionable next step (use --stdin)

**Example 2: Invalid model**
```bash
$ raxe models info fake-model
```
**Output:**
```
Model not found: fake-model

Available models:
  • threat_classifier_fp16_deploy
  • threat_classifier_int8_deploy
```

**Strengths:**
- Clear error message
- Helpful recovery path (list of valid options)
- No stack traces in user-facing output

### Command Not Found (Broken Commands) ❌

**Example:**
```bash
$ raxe history
```
**Output:**
```
Error: No such command 'history'.
Try 'raxe --help' for help.
```

**Problem:** Generic Click error, not user-friendly
**Impact:** User doesn't know if command is:
- Typo in their input
- Not installed
- Not yet implemented
- Renamed/deprecated

**Recommendation:** Add custom error handler for common misspellings:
```python
# In main.py cli() function
@cli.result_callback()
def handle_command_error(ctx, *args, **kwargs):
    if ctx.invoked_subcommand is None:
        # Suggest similar commands
        pass
```

---

## 5. Help Text Quality Assessment

### Overall Quality: ✅ EXCELLENT

**Strengths:**
- Every command has clear docstring with examples
- Examples use realistic scenarios
- Options have helpful descriptions
- Command groups are well-organized

**Example - `raxe scan --help`:**
```
Usage: raxe scan [OPTIONS] [TEXT]

  Scan text for security threats.

  Examples:
    raxe scan "Ignore all previous instructions"
    echo "test" | raxe scan --stdin
    raxe scan "prompt" --format json
    raxe scan "text" --l1-only --mode fast
    raxe scan "text" --confidence 0.8 --explain
    raxe --quiet scan "text"  # CI/CD mode (JSON output)

Options:
  --stdin               Read text from stdin instead of argument
  --format [text|json|yaml|table]
                        Output format (default: text)
  --profile             Enable performance profiling
  --l1-only             Use L1 (regex) detection only
  --l2-only             Use L2 (ML) detection only
  --mode [fast|balanced|thorough]
                        Performance mode (default: balanced)
  --confidence FLOAT    Minimum confidence threshold (0.0-1.0)
  --explain             Show detailed explanation of detections
  --dry-run             Test scan without saving to database
  --help                Show this message and exit.
```

**Why This is Excellent:**
- Real-world examples
- Shows multiple use cases (stdin, CI/CD, profiling)
- Clear option descriptions
- Logical grouping of related options

### Minor Improvement Opportunities

1. **Add "See Also" sections** to connect related commands:
   ```
   See Also:
     raxe batch       Scan multiple prompts
     raxe history     View past scans
     raxe rules test  Test specific rules
   ```

2. **Add exit code documentation** for CI/CD users:
   ```
   Exit Codes:
     0  No threats detected
     1  Threats detected (in --quiet mode)
     2  Error during scan
   ```

---

## 6. Visual Design Assessment

### Overall Design: ✅ EXCELLENT

**Strengths:**
- Consistent ASCII art logo across all commands
- Rich color palette (cyan primary, color-coded severity)
- Clear visual hierarchy (panels, tables, borders)
- Privacy messaging always visible
- Progress indicators for long operations

**Example - Scan Result:**
```
┌──────────────────────┐
│  █▀▀▄ ▄▀▄ ▀▄▀ █▀▀    │
│  █ ▀█ █▀█ ▄▀▄ █▄▄    │
└──────────────────────┘

╭──────────────────────────────────────────────────────────╮
│ 🔴 THREAT DETECTED                                       │
╰──────────────────────────────────────────────────────────╯

 Rule      Severity    Confidence  Description
 pi-001    CRITICAL         79.8%  Detects attempts to...
 pi-022    HIGH             77.4%  Detects obfuscated...

Summary: 5 detection(s) • Severity: CRITICAL • Scan time: 164.66ms

🔒 Privacy-First: Prompt hashed locally (SHA256) • Never stored or transmitted
```

**Why This Works:**
- Emotional impact (🔴 emoji + color coding)
- Scannable table format
- Summary line with key metrics
- Privacy reassurance at bottom

### Accessibility Considerations

**Currently Good:**
- `--no-color` flag for terminal compatibility
- Color choices work for most color blindness types (cyan/red/yellow)
- Emoji usage is supplemental (also has text)

**Recommendations:**
1. Add `--simple` flag for terminals without Unicode support
2. Test with screen readers (Rich library generally works well)
3. Ensure all tables have clear headers

---

## 7. CI/CD Integration Assessment

### Current Support: ✅ EXCELLENT

**Features:**
- `--quiet` flag suppresses visual output
- JSON/YAML output formats
- Exit codes for automation
- `--stdin` for piping data

**Example CI/CD Usage:**
```yaml
# .github/workflows/security.yml
- name: Scan prompts
  run: |
    raxe --quiet scan "${{ github.event.comment.body }}" --format json
  # Exits with code 1 if threats detected
```

**Strengths:**
- Machine-readable output (JSON)
- No progress bars/spinners in quiet mode
- Consistent exit codes
- Environment variable support (`RAXE_QUIET`, `RAXE_NO_COLOR`)

**Recommendation:** Document this more prominently in README

---

## 8. Consistency Issues

### Issue 8.1: Command Naming Inconsistency

**Problem:** Mix of singular/plural and verb/noun patterns

**Examples:**
- `raxe models` (plural noun) ✅
- `raxe rules` (plural noun) ✅
- `raxe pack` (singular noun) ⚠️ - Should be `packs`?
- `raxe plugins` (plural noun) ✅
- `raxe privacy` (abstract noun) ✅
- `raxe profile` (verb/noun ambiguous) ⚠️
- `raxe suppress` (verb) ⚠️ - Should be `suppressions`?

**Recommendation:** Establish naming convention:
- **Resource management:** Plural nouns (`models`, `rules`, `packs`)
- **Actions:** Verbs (`scan`, `export`, `init`)
- **Info display:** Singular nouns (`stats`, `privacy`, `doctor`)

### Issue 8.2: Subcommand Structure Inconsistency

**Observation:** Some commands are groups, others are standalone

**Groups (with subcommands):**
- `raxe rules` → `list`, `show`, `search`, `test`, `stats`, `custom`
- `raxe models` → `list`, `info`, `compare`, `set-default`
- `raxe suppress` → `add`, `list`, `remove`, `show`, `stats`, `audit`, `clear`
- `raxe tune` → `threshold`, `benchmark`
- `raxe pack` → `list`, `info`
- `raxe rules custom` → `create`, `validate`, `install`, `list`, `package`, `uninstall`

**Standalone commands:**
- `raxe scan`
- `raxe init`
- `raxe test`
- `raxe stats`
- `raxe doctor`
- `raxe export`
- `raxe privacy`
- `raxe profile`
- `raxe validate-rule`

**Assessment:** This is actually good! Follows common CLI patterns:
- Complex features → groups with subcommands
- Simple actions → standalone commands
- Consistent with git, docker, kubectl

**Recommendation:** Keep current structure

---

## 9. Priority Fixes

### 🔴 Critical (Must Fix Before Next Release)

1. **Register `history` command**
   - File: `src/raxe/cli/main.py`
   - Lines: Add import at ~line 23, add registration at ~line 903
   - Impact: Broken user flow (REPL references it)
   - Effort: 5 minutes

2. **Register `config` command**
   - File: `src/raxe/cli/main.py`
   - Lines: Add import at ~line 23, add registration at ~line 903
   - Impact: No way to view/manage config via CLI
   - Effort: 5 minutes

3. **Update completion scripts to include all commands**
   - File: `src/raxe/cli/main.py`
   - Lines: 821, 833-850, 859-875, 880-886
   - Impact: Tab completion incomplete
   - Effort: 10 minutes

### 🟡 High Priority (Should Fix Soon)

4. **Add `models` command to welcome banner**
   - File: `src/raxe/cli/branding.py`
   - Lines: 149-175
   - Impact: Users don't discover this feature
   - Effort: 2 minutes

5. **Implement or remove `pack info` stub**
   - File: `src/raxe/cli/main.py`
   - Lines: 729-732
   - Impact: Confusing placeholder message
   - Effort: 30 minutes OR remove command

6. **Update README examples to match actual commands**
   - File: `README.md`
   - Impact: Documentation doesn't match implementation
   - Effort: 15 minutes

### 🟢 Medium Priority (Nice to Have)

7. **Add "See Also" sections to help text**
   - Files: Multiple CLI files
   - Impact: Better command discovery
   - Effort: 1-2 hours

8. **Document exit codes in help text**
   - Files: `scan`, `validate-rule`, `batch`
   - Impact: Better CI/CD integration clarity
   - Effort: 30 minutes

9. **Add `--simple` flag for basic terminals**
   - Files: Multiple CLI files
   - Impact: Better accessibility
   - Effort: 2-3 hours

---

## 10. Recommendations Summary

### Immediate Actions (Before Next Release)

```bash
# 1. Fix broken commands
# File: src/raxe/cli/main.py

# Add imports (line ~23):
from raxe.cli.history import history
from raxe.cli.config import config

# Add registrations (line ~903):
cli.add_command(history)
cli.add_command(config)
```

```bash
# 2. Update completion scripts
# File: src/raxe/cli/main.py:821

# Change this line:
opts="init scan batch test stats export repl rules doctor pack plugins privacy profile suppress tune validate-rule completion --help --version"

# To this:
opts="init scan batch test stats export repl rules models doctor pack plugins privacy profile suppress tune validate-rule history config completion --help --version"

# Update all shells (bash, zsh, fish, powershell) similarly
```

```python
# 3. Update welcome banner
# File: src/raxe/cli/branding.py:164-168

config_commands = [
    ("raxe rules", "Manage detection rules"),
    ("raxe models", "Manage L2 models"),  # ADD THIS LINE
    ("raxe tune", "Fine-tune detection settings"),
    ("raxe doctor", "Diagnose issues"),
]
```

### Quality of Life Improvements

1. **Add command aliases for common typos:**
   ```python
   @cli.command("model")  # Singular alias
   def model_alias():
       """Alias for 'models' command."""
       click.echo("Did you mean 'raxe models'? Try 'raxe models --help'")
   ```

2. **Add "Recently Added" section to welcome banner:**
   ```
   🆕 Recently Added:
     raxe models       Manage L2 detection models (NEW!)
     raxe suppress     Manage false positive suppressions
   ```

3. **Add command recommendations after errors:**
   ```
   Error: No such command 'model'.

   Did you mean one of these?
     • raxe models
     • raxe doctor
   ```

---

## 11. Testing Recommendations

### Manual Testing Checklist

**Priority 1: Critical Path**
- [ ] `raxe` → Welcome banner displays
- [ ] `raxe init` → Config file created
- [ ] `raxe scan "test"` → Scan completes
- [ ] `raxe scan "ignore all"` → Detects threat
- [ ] `raxe --quiet scan "test"` → JSON output only
- [ ] `echo "test" | raxe scan --stdin` → Reads from stdin

**Priority 2: All Commands Work**
- [ ] `raxe history list` → Shows history (AFTER FIX)
- [ ] `raxe config show` → Displays config (AFTER FIX)
- [ ] `raxe models list` → Lists models
- [ ] `raxe rules list` → Lists rules
- [ ] `raxe pack list` → Lists packs
- [ ] `raxe doctor` → Health check passes
- [ ] `raxe stats` → Statistics display
- [ ] `raxe test` → Configuration test passes

**Priority 3: Error Handling**
- [ ] `raxe scan` → Clear error (no text provided)
- [ ] `raxe models info fake` → Shows available models
- [ ] `raxe rules show fake` → Rule not found
- [ ] `raxe batch missing.txt` → File not found error

**Priority 4: CI/CD Mode**
- [ ] `raxe --quiet scan "test"` → Exit code 0
- [ ] `raxe --quiet scan "ignore all"` → Exit code 1
- [ ] `raxe scan "test" --format json` → Valid JSON
- [ ] `RAXE_NO_COLOR=1 raxe scan "test"` → No ANSI codes

### Automated Testing Gaps

**Current Coverage:** Good unit test coverage
**Missing:** End-to-end CLI tests

**Recommendation:** Add CLI integration tests:
```python
# tests/integration/test_cli_flows.py

def test_first_time_user_flow():
    """Test: Install -> First Scan -> View Stats"""
    result = runner.invoke(cli, ["scan", "test"])
    assert result.exit_code == 0
    assert "SAFE" in result.output

def test_broken_commands_work():
    """Test: history and config commands are registered"""
    result = runner.invoke(cli, ["history", "--help"])
    assert result.exit_code == 0
    assert "No such command" not in result.output

    result = runner.invoke(cli, ["config", "--help"])
    assert result.exit_code == 0
    assert "No such command" not in result.output
```

---

## 12. Competitive Comparison

### How RAXE CLI Compares

**Compared to:** git, docker, kubectl, npm, poetry, ruff

| Aspect | RAXE | Industry Standard |
|--------|------|-------------------|
| Help text quality | ✅ Excellent | ✅ Excellent |
| Error messages | ✅ Excellent | ✅ Excellent |
| Visual design | ⭐ Outstanding | 🟢 Good |
| Consistency | ⚠️ Good (issues) | ✅ Excellent |
| Completion | ⚠️ Incomplete | ✅ Complete |
| First-time UX | ⭐ Outstanding | 🟢 Good |
| Documentation | 🟢 Good | ✅ Excellent |

**Standout Features:**
- 🎨 Visual design (logo, colors, panels) - **best in class**
- 🔒 Privacy messaging - **unique differentiator**
- 📚 Educational focus - **unique approach**
- ⚡ Time to value (<60s) - **excellent**

**Areas to Match Industry Leaders:**
- Consistency (all commands work, all listed)
- Comprehensive testing (end-to-end CLI tests)
- Command aliases (handle common typos)

---

## 13. Final Recommendations

### Short Term (This Week)

1. ✅ Fix broken commands (history, config)
2. ✅ Update completion scripts
3. ✅ Add models to welcome banner
4. ✅ Test all command flows manually
5. ✅ Update README with actual commands

### Medium Term (This Sprint)

1. Implement or remove `pack info` stub
2. Add end-to-end CLI tests
3. Add "See Also" sections to help text
4. Document exit codes for CI/CD
5. Add command aliases for common typos

### Long Term (Next Quarter)

1. Create comprehensive CLI documentation site
2. Add interactive tutorials (in REPL)
3. Build command recommendation system
4. Add `--simple` mode for basic terminals
5. Create video walkthrough of CLI features

---

## Appendix A: Command Reference

### Complete Command Tree

```
raxe
├── init                 Initialize configuration
├── scan [TEXT]          Scan for threats
│   ├── --stdin
│   ├── --format [text|json|yaml|table]
│   ├── --profile
│   ├── --l1-only
│   ├── --l2-only
│   ├── --mode [fast|balanced|thorough]
│   ├── --confidence FLOAT
│   ├── --explain
│   └── --dry-run
├── batch FILE           Batch scan from file
│   ├── --format [text|json|csv]
│   ├── --output PATH
│   ├── --fail-fast
│   └── --parallel INT
├── test                 Test configuration
├── stats                Show statistics
├── export               Export scan history
│   ├── --format [json|csv]
│   ├── --output PATH
│   └── --days INT
├── repl                 Interactive mode
├── rules                Manage rules
│   ├── list
│   │   ├── --family [PI|JB|PII|SEC|QUAL|CUSTOM]
│   │   ├── --severity [critical|high|medium|low|info]
│   │   └── --format [table|tree|json]
│   ├── show RULE_ID
│   ├── search QUERY
│   │   └── --in [name|description|all]
│   ├── test RULE_ID TEXT
│   ├── stats
│   └── custom
│       ├── create
│       ├── validate FILE
│       ├── install FILE
│       ├── list
│       ├── package
│       └── uninstall RULE_ID
├── models               Manage L2 models
│   ├── list
│   │   ├── --status [active|experimental|deprecated|all]
│   │   └── --runtime [pytorch|onnx|onnx_int8|all]
│   ├── info MODEL_ID
│   ├── compare [MODEL_IDS...]
│   └── set-default MODEL_ID
├── doctor               Run health checks
│   ├── --fix
│   ├── --export PATH
│   └── --verbose
├── pack                 Manage rule packs
│   ├── list
│   └── info PACK_ID     [STUB - not implemented]
├── plugins              List plugins
├── privacy              Show privacy guarantees
├── profile TEXT         Profile performance
│   ├── --l2 / --no-l2
│   └── --format [tree|table|json]
├── suppress             Manage suppressions
│   ├── add
│   ├── list
│   ├── remove ID
│   ├── show ID
│   ├── stats
│   ├── audit
│   └── clear
├── tune                 Tune parameters
│   ├── threshold
│   └── benchmark
├── validate-rule FILE   Validate rule file
│   ├── --strict
│   └── --json
├── history              [BROKEN] View scan history
│   ├── list
│   │   ├── --limit INT
│   │   └── --severity SEVERITY
│   ├── show ID
│   ├── clear
│   └── stats
├── config               [BROKEN] Manage configuration
│   ├── show
│   │   └── --path PATH
│   ├── set KEY VALUE
│   └── reset
├── completion SHELL     Generate completions
│   └── [bash|zsh|fish|powershell]
└── [GLOBAL FLAGS]
    ├── --version
    ├── --no-color
    ├── --verbose
    ├── --quiet
    └── --help
```

---

## Appendix B: File Locations

### CLI Command Files

```
src/raxe/cli/
├── __init__.py                  CLI module initialization
├── main.py                      Main CLI entry point + core commands
├── branding.py                  Logo, welcome banner, help menu
├── output.py                    Output formatting utilities
├── models.py                    L2 model management commands
├── rules.py                     Rule management commands
├── custom_rules.py              Custom rule creation/management
├── doctor.py                    Health check diagnostics
├── test.py                      Configuration testing
├── stats.py                     Statistics display
├── export.py                    History export
├── repl.py                      Interactive REPL mode
├── privacy.py                   Privacy information
├── profiler.py                  Performance profiling
├── suppress.py                  Suppression management
├── tune.py                      Parameter tuning
├── validate.py                  Rule validation
├── history.py                   [BROKEN] Scan history
├── config.py                    [BROKEN] Config management
├── progress.py                  Progress indicators
├── progress_context.py          Progress context detection
└── l2_formatter.py              L2 result formatting
```

### Configuration Files

```
~/.raxe/
├── config.yaml                  User configuration
├── custom_rules/                Custom rule directory
├── scan_history.db             Scan history database
└── logs/                       Log files
    └── latest.log
```

---

## Conclusion

The RAXE CLI demonstrates **excellent foundational UX** with standout visual design, clear messaging, and strong privacy focus. The critical issues (broken commands, incomplete discovery) are **easily fixable** and should be addressed before the next release.

**Overall Assessment:** 7.5/10
- Would be **9/10** after fixing broken commands
- Would be **9.5/10** after improving consistency
- Has potential to be **best-in-class** CLI for security tools

**Key Strengths to Preserve:**
- Beautiful visual design (logo, colors, tables)
- Privacy-first messaging
- Educational approach
- Excellent help text with examples
- Fast time-to-value (<60 seconds)

**Critical Fixes Required:**
1. Register `history` command
2. Register `config` command
3. Update completion scripts
4. Add `models` to welcome banner
5. Implement or remove `pack info` stub

**Estimated Time to Fix Critical Issues:** 30-45 minutes

---

**Report Generated:** 2025-11-21
**Next Review:** After critical fixes are implemented
**Reviewer:** UX Designer Agent
