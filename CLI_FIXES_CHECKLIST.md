# RAXE CLI - Critical Fixes Checklist

**Priority:** 🔴 CRITICAL
**Estimated Time:** 30-45 minutes
**Impact:** Fixes broken user flows and command discovery

---

## ✅ Checklist

### 🔴 Critical Fixes (Must Do Before Next Release)

#### 1. Register `history` command

**File:** `src/raxe/cli/main.py`

**Step 1:** Add import (around line 23)
```python
from raxe.cli.history import history
```

**Step 2:** Register command (around line 903)
```python
cli.add_command(history)
```

**Test:**
```bash
raxe history --help
# Should show help instead of "No such command"
```

- [ ] Import added
- [ ] Command registered
- [ ] Tested `raxe history --help`
- [ ] Tested `raxe history list`

---

#### 2. Register `config` command

**File:** `src/raxe/cli/main.py`

**Step 1:** Add import (around line 23)
```python
from raxe.cli.config import config
```

**Step 2:** Register command (around line 903)
```python
cli.add_command(config)
```

**Test:**
```bash
raxe config --help
raxe config show
```

- [ ] Import added
- [ ] Command registered
- [ ] Tested `raxe config --help`
- [ ] Tested `raxe config show`

---

#### 3. Update bash completion

**File:** `src/raxe/cli/main.py` (line 821)

**Change from:**
```bash
opts="init scan batch test stats export repl rules doctor pack plugins privacy profile suppress tune validate-rule completion --help --version"
```

**Change to:**
```bash
opts="init scan batch test stats export repl rules models doctor pack plugins privacy profile suppress tune validate-rule history config completion --help --version"
```

- [ ] Added `models`
- [ ] Added `history`
- [ ] Added `config`
- [ ] Tested bash completion

---

#### 4. Update zsh completion

**File:** `src/raxe/cli/main.py` (lines 833-850)

**Add to commands array:**
```zsh
'models:Manage L2 detection models'
'history:View and manage scan history'
'config:Manage RAXE configuration'
```

- [ ] Added all three commands
- [ ] Tested zsh completion

---

#### 5. Update fish completion

**File:** `src/raxe/cli/main.py` (lines 859-876)

**Update command list:**
```fish
complete -c raxe -f -a "init scan batch test stats export repl rules models doctor pack plugins privacy profile suppress tune validate-rule history config completion"
```

**Add descriptions:**
```fish
complete -c raxe -f -a "models" -d "Manage L2 models"
complete -c raxe -f -a "history" -d "View scan history"
complete -c raxe -f -a "config" -d "Manage configuration"
```

- [ ] Updated command list
- [ ] Added descriptions
- [ ] Tested fish completion

---

#### 6. Update PowerShell completion

**File:** `src/raxe/cli/main.py` (lines 880-886)

**Update commands array:**
```powershell
$commands = @('init', 'scan', 'batch', 'test', 'stats', 'export', 'repl', 'rules', 'models', 'doctor', 'pack', 'plugins', 'privacy', 'profile', 'suppress', 'tune', 'validate-rule', 'history', 'config', 'completion')
```

- [ ] Added `models`, `history`, `config`
- [ ] Tested PowerShell completion

---

### 🟡 High Priority (Should Fix Soon)

#### 7. Add `models` to welcome banner

**File:** `src/raxe/cli/branding.py` (lines 164-168)

**Change from:**
```python
config_commands = [
    ("raxe rules", "Manage detection rules"),
    ("raxe tune", "Fine-tune detection settings"),
    ("raxe doctor", "Diagnose issues"),
]
```

**Change to:**
```python
config_commands = [
    ("raxe rules", "Manage detection rules"),
    ("raxe models", "Manage L2 models"),
    ("raxe tune", "Fine-tune detection settings"),
    ("raxe doctor", "Diagnose issues"),
]
```

**Test:**
```bash
raxe
# Should show 'raxe models' in configuration commands section
```

- [ ] Added to config_commands
- [ ] Tested welcome banner displays it

---

#### 8. Add `history` to welcome banner

**File:** `src/raxe/cli/branding.py` (lines 156-161)

**Change from:**
```python
analysis_commands = [
    ("raxe batch <file>", "Scan multiple prompts from file"),
    ("raxe repl", "Interactive scanning mode"),
    ("raxe export", "Export scan history"),
]
```

**Change to:**
```python
analysis_commands = [
    ("raxe batch <file>", "Scan multiple prompts from file"),
    ("raxe repl", "Interactive scanning mode"),
    ("raxe history", "View scan history"),
    ("raxe export", "Export scan history"),
]
```

- [ ] Added to analysis_commands
- [ ] Tested welcome banner

---

#### 9. Implement or remove `pack info` stub

**File:** `src/raxe/cli/main.py` (lines 729-732)

**Option A: Quick Fix (Remove the message)**
```python
@pack.command("info")
@click.argument("pack_id")
def pack_info(pack_id: str):
    """Show information about a specific pack."""
    # TODO: Implement pack info display
    click.echo(f"Pack: {pack_id}")
    click.echo("  Status: Active")
    click.echo("  Rules: (querying...)")
    click.echo()
    click.echo("Full pack details coming soon.")
    click.echo("Use 'raxe rules list' to see all rules in the meantime.")
```

**Option B: Full Implementation**
- Query pack registry
- Display pack metadata
- Show rule count
- List authors/contributors

- [ ] Decided on approach
- [ ] Implemented fix
- [ ] Tested `raxe pack info core`

---

## 🧪 Testing Checklist

### After Implementing Fixes

**Core Commands:**
- [ ] `raxe --help` - Lists all commands including history, config, models
- [ ] `raxe` - Welcome banner shows models and history
- [ ] `raxe history --help` - Shows help instead of error
- [ ] `raxe history list` - Lists scan history
- [ ] `raxe config --help` - Shows help instead of error
- [ ] `raxe config show` - Displays current configuration
- [ ] `raxe models list` - Lists available models

**Completion Scripts:**
- [ ] `raxe completion bash | grep models` - Includes models
- [ ] `raxe completion bash | grep history` - Includes history
- [ ] `raxe completion bash | grep config` - Includes config
- [ ] `raxe completion zsh | grep models` - Has models description
- [ ] `raxe completion fish | grep models` - Has models in list

**Error Handling:**
- [ ] `raxe history` (no subcommand) - Shows appropriate error
- [ ] `raxe config` (no subcommand) - Shows appropriate error
- [ ] `raxe models` (no subcommand) - Shows appropriate error

**User Flows:**
- [ ] First-time user: `raxe` → `raxe scan "test"` → works
- [ ] View config: `raxe config show` → displays settings
- [ ] View history: `raxe history list` → shows past scans
- [ ] Manage models: `raxe models list` → `raxe models info <id>` → works

---

## 📊 Impact Assessment

### Before Fixes

**Broken Commands:** 2 (history, config)
**Incomplete Discovery:** 3+ commands missing from various locations
**User Confusion:** HIGH (commands referenced but don't work)

### After Fixes

**Broken Commands:** 0
**Incomplete Discovery:** 0
**User Confidence:** HIGH (everything works as expected)

---

## 🎯 Success Criteria

All items checked = Ready for release

- [ ] All critical fixes implemented
- [ ] All tests passing
- [ ] Manual testing completed
- [ ] Welcome banner updated
- [ ] Completion scripts updated
- [ ] Documentation updated (if needed)

---

## 📝 Notes

**Time Required:**
- Critical fixes (1-6): ~20 minutes
- High priority (7-9): ~15 minutes
- Testing: ~10 minutes
- **Total: ~45 minutes**

**Risk Level:** LOW
- Changes are additive (registering existing commands)
- No breaking changes
- Easy to verify with manual testing

**Dependencies:**
- None - all fixes are independent
- Can be done in any order
- Can be split across multiple people

---

## 🚀 Deployment Steps

1. Create branch: `git checkout -b fix/cli-command-registration`
2. Implement fixes 1-6 (critical)
3. Test manually
4. Implement fixes 7-9 (high priority)
5. Run full test suite
6. Create PR with this checklist
7. Review and merge
8. Verify on main branch

---

**Checklist Created:** 2025-11-21
**Target Completion:** ASAP (before next release)
**Assigned To:** [TBD]
**Status:** 🟡 Ready to Start
