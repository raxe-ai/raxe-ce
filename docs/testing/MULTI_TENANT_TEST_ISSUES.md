# Multi-Tenant Test Issues & Improvements

**Generated:** 2026-01-13
**Test Run:** Full manual testing of MULTI_TENANT_TESTING.md

---

## Summary

| Category | Count | Priority |
|----------|-------|----------|
| Bugs | 3 | P0-P1 |
| Feature Gaps | 2 | P0-P1 |
| UX Improvements | 4 | P2 |
| Documentation Fixes | 3 | P2 |
| Consistency Issues | 2 | P3 |

---

## BUGS (Must Fix)

### BUG-1: CLI `--ci` flag ignores policy mode [P0]

**Location:** `src/raxe/cli/scan.py`

**Problem:**
The `--ci` flag returns exit code 1 for ANY detection, regardless of policy mode. Monitor mode should always return exit code 0 (allow).

**Observed Behavior:**
```bash
# Monitor mode with --ci - WRONG
raxe scan "threat" --tenant test-tenant-c --ci  # Exit code: 1 (should be 0)

# Balanced mode with --ci - might be wrong depending on threshold
raxe scan "threat" --tenant test-tenant-a --ci  # Exit code: 1

# Strict mode with --ci - CORRECT
raxe scan "threat" --tenant test-tenant-b --ci  # Exit code: 1
```

**Expected Behavior:**
| Policy Mode | Has Threats | Exit Code |
|-------------|-------------|-----------|
| monitor | Yes | 0 (allow) |
| monitor | No | 0 |
| balanced | Yes + meets block threshold | 1 (block) |
| balanced | Yes + below threshold | 0 (allow) |
| strict | Yes (HIGH+) | 1 (block) |
| strict | No | 0 |

**Root Cause:** The `--ci` flag likely just checks `has_threats` without consulting the policy decision.

**Fix Required:**
1. In scan.py, check `result.should_block` or `result.policy_decision` instead of just `has_threats`
2. Return exit code 1 only when policy says to block

---

### BUG-2: Balanced mode blocking threshold might be wrong [P1]

**Location:** `src/raxe/domain/tenants/presets.py`

**Problem:**
The balanced mode spec says "block CRITICAL always" but our test shows CRITICAL detections being allowed because confidence is 82.3% (below 85% threshold).

**Question:** Should CRITICAL severity ALWAYS block regardless of confidence?

**Current Behavior:**
```
Detection: pii-058 (CRITICAL, 82.3% confidence)
Policy: balanced (block_severity_threshold=HIGH, block_confidence_threshold=0.85)
Result: ALLOW (because 82.3% < 85%)
```

**Options:**
1. **Option A:** CRITICAL always blocks (regardless of confidence) - matches "CRITICAL" meaning
2. **Option B:** Keep current behavior (confidence threshold applies to all severities)
3. **Option C:** Different thresholds per severity (CRITICAL=0.5, HIGH=0.85)

**Recommendation:** Option A - CRITICAL should mean "always block if detected"

---

### BUG-3: Invalid policy ID silently falls back [P2]

**Location:** `src/raxe/domain/tenants/resolver.py`

**Problem:**
```bash
raxe scan "test" --policy invalid-policy-name
# No error, silently falls back to tenant default
```

**Expected:** Warning or error about invalid policy ID

**Fix Required:**
1. Validate policy_id against known presets + tenant custom policies
2. If invalid, either:
   - Option A: Error with "Unknown policy: invalid-policy-name. Valid: monitor, balanced, strict"
   - Option B: Warn and fall back: "Warning: Unknown policy 'invalid-policy-name', using tenant default"

---

## FEATURE GAPS (Should Implement)

### GAP-1: Tenant suppressions not applied during scans [P0]

**Location:** `src/raxe/cli/scan.py`, `src/raxe/sdk/client.py`

**Problem:**
Suppressions stored in tenant directory are NOT loaded during scans.

**Current State:**
```bash
# Suppression is stored correctly
raxe suppress add pi-022 --tenant test-tenant-a
cat /tmp/raxe-fresh-multitenant/test-tenant-a/suppressions.yaml
# Shows: pattern: pi-022

# But scan doesn't apply it
raxe scan "Ignore all previous instructions" --tenant test-tenant-a
# Still shows pi-022 in detections!
```

**Required Changes:**
1. When `--tenant` is specified, load `{tenant_dir}/suppressions.yaml`
2. Merge tenant suppressions with any `--suppress` flags
3. Apply combined suppressions during scan
4. Document suppression precedence: `--suppress` flag > tenant suppressions > global

---

### GAP-2: Missing `action_taken` in CLI JSON output [P1]

**Location:** `src/raxe/cli/scan.py`

**Problem:**
Telemetry has `action_taken: "block"/"allow"` but CLI JSON output doesn't include this field.

**Telemetry payload:**
```json
{
  "action_taken": "block",
  "policy_id": "strict"
}
```

**CLI JSON output:**
```json
{
  "policy": {
    "effective_policy_id": "strict",
    "effective_policy_mode": "strict",
    "resolution_source": "tenant"
  }
  // No action_taken field!
}
```

**Fix Required:**
Add `action_taken` to scan JSON output for consistency with telemetry.

---

## UX IMPROVEMENTS

### UX-1: `--output json` vs `--format json` inconsistency [P2]

**Problem:**
- `raxe scan` uses `--format json`
- `raxe tenant list`, `raxe app list`, `raxe policy list` use `--output json`

**Recommendation:** Standardize on one flag name across all commands.

**Options:**
1. Use `--format` everywhere (more descriptive)
2. Use `--output` everywhere (more common in CLI tools)
3. Support both as aliases

**Suggested:** Option 3 - support both `--format` and `--output` as aliases

---

### UX-2: Policy explain output formatting [P3]

**Current:**
```
Resolution Path
  • request:None
  • app:trading
  • tenant:test-tenant-a
```

**Better (shows what each resolved to):**
```
Resolution Path
  • request: (none specified)
  • app: trading → strict
  • tenant: test-tenant-a → balanced
  • system_default: balanced
```

---

### UX-3: No visual indicator of blocking status in human output [P2]

**Current output:**
```
🔴 THREAT DETECTED
... detections ...
Summary: 8 detection(s) • Severity: CRITICAL
```

**Better output (shows policy decision):**
```
🔴 THREAT DETECTED
... detections ...
Summary: 8 detection(s) • Severity: CRITICAL • Action: ✅ ALLOWED (monitor mode)

# Or for blocking:
Summary: 8 detection(s) • Severity: CRITICAL • Action: 🛑 BLOCKED (strict mode)
```

---

### UX-4: Tenant not found warning [P2]

**Current:** Silently falls back to system default

**Better:**
```
⚠️ Tenant 'nonexistent' not found, using system default policy (balanced)
```

---

## DOCUMENTATION FIXES

### DOC-1: Field name mismatches [P2]

**File:** `docs/testing/MULTI_TENANT_TESTING.md`

| Location | Doc Says | Actual Field |
|----------|----------|--------------|
| Journey 3.1 | `has_threats` | `has_detections` |
| Journey 3.1 | `action_taken` | (not present in CLI JSON) |
| Journey 6.1 | `has_threats`, `severity`, `total_detections` | `has_detections`, (severity in detections), `l1_count`+`l2_count` |

---

### DOC-2: SDK attribute paths [P2]

**File:** `docs/testing/MULTI_TENANT_TESTING.md` (Journey 8)

**Doc shows:**
```python
result.metadata.get('effective_policy_id')
```

**Should also document:**
```python
# Direct attributes
result.has_threats  # bool
result.should_block  # bool
result.policy_decision  # BlockAction.ALLOW or BlockAction.BLOCK
result.severity  # str

# Metadata dict
result.metadata['effective_policy_id']
result.metadata['effective_policy_mode']
result.metadata['resolution_source']
result.metadata['resolution_path']
result.metadata['tenant_id']
```

---

### DOC-3: Quick reference needs update [P2]

**File:** `docs/testing/MULTI_TENANT_QUICK_REF.md`

- Update BigQuery queries to use correct field paths (`policy_id` not `effective_policy_id`)
- Update expected JSON structure

---

## CONSISTENCY ISSUES

### CONSISTENCY-1: Telemetry vs CLI field naming [P3]

| Field | CLI JSON | Telemetry |
|-------|----------|-----------|
| Policy ID | `effective_policy_id` | `policy_id` |
| Policy Mode | `effective_policy_mode` | `policy_mode` |
| Resolution Source | `resolution_source` | (not present) |

**Recommendation:** Add `resolution_source` to telemetry payload.

---

### CONSISTENCY-2: `app_id` only present with `--app` flag [P3]

**Observation:** CLI JSON only includes `app_id` when `--app` is specified.

**Recommendation:** Always include `app_id` field, set to `null` if not specified.

---

## IMPLEMENTATION PRIORITY

### Phase 1: Critical Fixes (This Sprint)
1. BUG-1: CLI --ci respects policy mode
2. GAP-1: Tenant suppressions applied during scans
3. DOC-1: Fix field name documentation

### Phase 2: Important Improvements
4. BUG-2: Clarify balanced mode CRITICAL handling
5. GAP-2: Add action_taken to CLI JSON
6. UX-3: Visual blocking indicator

### Phase 3: Polish
7. BUG-3: Invalid policy validation
8. UX-1: Standardize --output/--format
9. UX-2: Better policy explain output
10. UX-4: Tenant not found warning
11. DOC-2, DOC-3: SDK and quick ref docs
12. CONSISTENCY-1, CONSISTENCY-2: Field alignment

---

## Test Validation Required

After fixes, re-run:
1. Full MULTI_TENANT_TESTING.md guide
2. Unit tests for changed files
3. BigQuery telemetry verification
