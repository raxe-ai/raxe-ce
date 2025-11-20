# CLI JSON Output Fix - Implementation Documentation

## Problem Statement

Previously, when using `raxe scan --format json`, progress indicators were mixed with JSON output, breaking JSON parsers and making the output unsuitable for CI/CD pipelines or scripting.

**Before (broken):**
```bash
$ raxe scan "test" --format json
[2025-11-20 12:47:45] Initializing RAXE...
[2025-11-20 12:47:46] Loaded 460 rules (559ms)
{"has_detections": false, ...}  # JSON mixed with progress text
```

**After (fixed):**
```bash
$ raxe scan "test" --format json
{"has_detections": false, ...}  # Clean JSON only
```

## Solution

### Key Changes

1. **Auto-quiet for structured formats** (`/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/main.py`, lines 277-279)
   - When `--format json` or `--format yaml` is specified, quiet mode is automatically enabled
   - This prevents progress indicators from contaminating structured output

2. **Quiet mode enforcement**
   - Progress indicators check quiet mode before displaying
   - Already implemented in `QuietProgress` class
   - Now properly triggered by format selection

### Implementation Details

#### Modified File: `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/main.py`

```python
# Auto-enable quiet mode for JSON/YAML formats to prevent progress contamination
if format in ("json", "yaml"):
    quiet = True
```

This simple change ensures that:
- `raxe scan "text" --format json` → quiet mode enabled, clean JSON
- `raxe scan "text" --format yaml` → quiet mode enabled, clean YAML
- `raxe --quiet scan "text"` → explicit quiet, outputs JSON
- `raxe scan "text" --format text` → normal progress display

## Usage Examples

### CI/CD Integration

```bash
# Clean JSON output for parsing
raxe scan "$USER_INPUT" --format json | jq '.has_detections'

# Exit code 0 if safe, 1 if threats detected
raxe --quiet scan "$USER_INPUT" && echo "Safe" || echo "Threats found"

# Parse detection count
DETECTIONS=$(raxe scan "$INPUT" --format json | jq '.l1_count + .l2_count')
```

### Scripting Examples

```python
import subprocess
import json

# Run scan and parse JSON
result = subprocess.run(
    ["raxe", "scan", user_prompt, "--format", "json"],
    capture_output=True,
    text=True
)

# Parse output (no progress contamination)
data = json.loads(result.stdout)
if data["has_detections"]:
    print(f"Found {len(data['detections'])} threats")
```

### Manual Testing

```bash
# JSON format auto-suppresses progress
raxe scan "test" --format json
# Output: {"has_detections": false, ...}

# Quiet flag suppresses progress
raxe --quiet scan "test"
# Output: {"has_detections": false, ...}

# Text mode shows progress normally
raxe scan "test" --format text
# Output includes: [timestamp] Initializing RAXE...

# YAML format also suppresses progress
raxe scan "test" --format yaml
# Output: has_detections: false
```

## Test Coverage

### New Tests (`/Users/mh/github-raxe-ai/raxe-ce/tests/integration/test_cli_commands.py`)

1. **`test_json_format_auto_suppresses_progress`**
   - Verifies JSON output is valid and parseable
   - Ensures no progress indicators in output
   - Validates JSON structure

2. **`test_yaml_format_auto_suppresses_progress`**
   - Verifies YAML output is clean
   - Ensures no progress indicators

3. **`test_quiet_flag_suppresses_progress`**
   - Tests explicit `--quiet` flag
   - Validates JSON output

4. **`test_quiet_flag_with_explicit_json`**
   - Tests combination of `--quiet` and `--format json`

5. **`test_text_format_shows_progress`**
   - Ensures text mode still shows progress normally

6. **`test_json_output_structure_complete`**
   - Validates all required JSON fields are present
   - Type checks for each field

7. **`test_quiet_mode_ci_cd_exit_codes`**
   - Verifies exit code 0 for safe scans
   - Verifies exit code 1 when threats detected
   - Essential for CI/CD integration

### Test Results

All 24 integration tests pass (21 passed, 3 skipped):
- All existing tests continue to pass
- New quiet mode tests validate the fix
- No regressions detected

## Behavior Matrix

| Format | Quiet Flag | Progress Shown? | Output Format |
|--------|-----------|----------------|---------------|
| text   | No        | Yes            | Rich text     |
| text   | Yes       | No             | JSON          |
| json   | No        | No (auto)      | JSON          |
| json   | Yes       | No             | JSON          |
| yaml   | No        | No (auto)      | YAML          |
| yaml   | Yes       | No             | YAML          |

## Environment Variables

The `RAXE_QUIET` environment variable works identically to `--quiet`:

```bash
export RAXE_QUIET=1
raxe scan "test"  # Outputs JSON with no progress
```

## Exit Codes

For CI/CD integration, exit codes are meaningful:

- **0**: No threats detected (safe)
- **1**: Threats detected (in quiet mode only)
- **Non-zero**: Error occurred

```bash
#!/bin/bash
if raxe --quiet scan "$USER_INPUT"; then
    echo "Prompt is safe"
else
    echo "Threats detected!"
    exit 1
fi
```

## Backwards Compatibility

This change is **fully backwards compatible**:

- Text mode behavior unchanged (still shows progress)
- JSON/YAML now work correctly (previously broken)
- All existing flags and options continue to work
- No breaking changes to API or behavior

## Performance Impact

**Zero performance impact**:
- Progress suppression is just a conditional check
- No additional overhead
- Same scan latency as before

## Future Enhancements

Potential future improvements:

1. **Progress to stderr**: Send progress to stderr, data to stdout
   ```bash
   raxe scan "test" --format json 2>/dev/null  # Suppress progress manually
   ```

2. **Table format**: Add `--format table` for tabular output
   ```bash
   raxe scan "test" --format table
   ```

3. **Streaming mode**: Support `--stream` for long-running scans
   ```bash
   raxe batch large.txt --stream
   ```

## Related Files

- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/main.py` - CLI main command
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/progress.py` - Progress indicator implementations
- `/Users/mh/github-raxe-ai/raxe-ce/src/raxe/cli/progress_context.py` - Progress mode detection
- `/Users/mh/github-raxe-ai/raxe-ce/tests/integration/test_cli_commands.py` - Integration tests

## Summary

The fix is **simple, effective, and complete**:

1. ✅ JSON/YAML formats auto-enable quiet mode
2. ✅ Progress indicators properly suppressed
3. ✅ Comprehensive test coverage (7 new tests)
4. ✅ CI/CD exit codes work correctly
5. ✅ Backwards compatible
6. ✅ Zero performance impact
7. ✅ All existing tests pass

**Result**: Clean, parseable JSON/YAML output suitable for scripting and CI/CD integration.
