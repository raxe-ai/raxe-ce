# RAXE Suppression System Guide

## Overview

The RAXE Suppression System provides a comprehensive way to manage false positives in security scans. It supports:

- **File-based suppressions** via `.raxeignore` (like `.gitignore`)
- **Programmatic suppressions** via API
- **SQLite audit logging** for compliance and debugging
- **Wildcard patterns** for flexible rule matching
- **CLI commands** for easy management

---

## Quick Start

### 1. Create a `.raxeignore` file

```bash
# Copy the example file
cp .raxeignore.example .raxeignore

# Or create your own
cat > .raxeignore <<EOF
# Suppress specific rule
pi-001  # False positive in documentation

# Suppress all prompt injection rules
pi-*  # Too sensitive for our use case
EOF
```

### 2. Add a suppression via CLI

```bash
# Add a suppression
raxe suppress add pi-001 "False positive in documentation"

# Add with wildcard
raxe suppress add "pi-*" "Suppress all prompt injection rules"

# Add with expiration
raxe suppress add jb-001 "Temporary fix" --expires 2025-12-31T23:59:59Z

# Save to .raxeignore
raxe suppress add pi-002 "Another false positive" --save
```

### 3. List suppressions

```bash
# List all active suppressions
raxe suppress list

# List in JSON format
raxe suppress list --format json

# List in plain text (for .raxeignore)
raxe suppress list --format text
```

### 4. View audit log

```bash
# Show recent suppression activity
raxe suppress audit

# Show only applied suppressions
raxe suppress audit --action applied

# Show specific pattern
raxe suppress audit --pattern "pi-*"
```

---

## `.raxeignore` File Format

### Basic Syntax

```gitignore
# Comments start with #
pi-001  # Inline reason after pattern

# Blank lines are ignored

# Pattern matching
pi-*         # Wildcard: all PI rules
*-injection  # Wildcard: all injection rules
pi-00*       # Wildcard: pi-001, pi-002, etc.
```

### Pattern Matching

| Pattern | Matches | Example Rules |
|---------|---------|---------------|
| `pi-001` | Exact match | `pi-001` |
| `pi-*` | All PI rules | `pi-001`, `pi-002`, `pi-advanced-001` |
| `*-injection` | All injection rules | `pi-injection`, `cmd-injection`, `jb-injection` |
| `jb-regex-*` | All regex jailbreak rules | `jb-regex-basic`, `jb-regex-advanced` |
| `*-00*` | Rules ending in 00x | `pi-001`, `jb-002`, `pii-003` |

### Example File

```gitignore
# RAXE Suppression File

# Specific false positives
pi-001  # Documentation examples contain instruction patterns
jb-regex-basic  # Support docs use common phrases

# Disable entire families (use with caution!)
# pi-*  # All prompt injection rules

# Temporary suppressions (add expiration in CLI)
# Use: raxe suppress add <pattern> <reason> --expires <date>

# Context-specific
jb-dan-prompt  # Used in red-team testing environment
```

---

## CLI Commands

### `raxe suppress add`

Add a new suppression rule.

```bash
# Basic usage
raxe suppress add <pattern> <reason>

# Examples
raxe suppress add pi-001 "False positive in docs"
raxe suppress add "pi-*" "Disable all PI rules"
raxe suppress add jb-001 "Known safe pattern"

# With options
raxe suppress add pi-002 "Temporary fix" --expires 2025-12-31T23:59:59Z
raxe suppress add pi-003 "Safe in test env" --save  # Save to .raxeignore
```

**Options:**
- `--config PATH`: Path to .raxeignore file (default: `./.raxeignore`)
- `--expires DATE`: Expiration date (ISO format: `2025-12-31T23:59:59Z`)
- `--save`: Save to .raxeignore file

### `raxe suppress list`

List all active suppressions.

```bash
# Table format (default)
raxe suppress list

# JSON format
raxe suppress list --format json

# Plain text (for .raxeignore)
raxe suppress list --format text
```

**Options:**
- `--format FORMAT`: Output format (`table`, `json`, `text`)
- `--config PATH`: Path to .raxeignore file

### `raxe suppress remove`

Remove a suppression.

```bash
# Remove suppression
raxe suppress remove <pattern>

# Examples
raxe suppress remove pi-001
raxe suppress remove "pi-*"

# Save changes to .raxeignore
raxe suppress remove pi-002 --save
```

**Options:**
- `--config PATH`: Path to .raxeignore file
- `--save`: Save changes to .raxeignore file

### `raxe suppress show`

Show details of a specific suppression.

```bash
# Show suppression details
raxe suppress show <pattern>

# Examples
raxe suppress show pi-001
raxe suppress show "pi-*"
```

**Output includes:**
- Pattern and reason
- Created date and author
- Expiration status
- Example rule matches
- Recent activity from audit log

### `raxe suppress audit`

View suppression audit log.

```bash
# Show recent activity
raxe suppress audit

# Filter by pattern
raxe suppress audit --pattern "pi-*"

# Filter by action
raxe suppress audit --action applied
raxe suppress audit --action added
raxe suppress audit --action removed

# Limit results
raxe suppress audit --limit 100
```

**Options:**
- `--limit N`: Maximum entries to show (default: 50)
- `--pattern PATTERN`: Filter by pattern
- `--action ACTION`: Filter by action (`added`, `removed`, `applied`)

### `raxe suppress stats`

Show suppression statistics.

```bash
# View statistics
raxe suppress stats
```

**Shows:**
- Active suppressions
- Total added/removed
- Total applied
- Recent activity (last 30 days)

### `raxe suppress clear`

Clear all suppressions.

```bash
# Clear all suppressions (prompts for confirmation)
raxe suppress clear

# Save cleared state to .raxeignore
raxe suppress clear --save
```

---

## Programmatic API

### Using SuppressionManager in Code

```python
from pathlib import Path
from raxe.domain.suppression import SuppressionManager

# Initialize manager
manager = SuppressionManager(
    config_path=Path(".raxeignore"),
    db_path=Path.home() / ".raxe" / "suppressions.db",
    auto_load=True,  # Load from file on init
)

# Add suppression
manager.add_suppression(
    pattern="pi-001",
    reason="False positive in documentation",
    created_by="api",
)

# Add with expiration
manager.add_suppression(
    pattern="jb-001",
    reason="Temporary fix",
    created_by="api",
    expires_at="2025-12-31T23:59:59Z",
)

# Check if rule is suppressed
is_suppressed, reason = manager.is_suppressed("pi-001")
if is_suppressed:
    print(f"Rule suppressed: {reason}")

# Get all suppressions
suppressions = manager.get_suppressions()
for s in suppressions:
    print(f"{s.pattern}: {s.reason}")

# Remove suppression
manager.remove_suppression("pi-001", created_by="api")

# Save to file
manager.save_to_file()

# Load from file
manager.load_from_file()

# Get audit log
audit_log = manager.get_audit_log(limit=50)
for entry in audit_log:
    print(f"{entry['created_at']}: {entry['action']} - {entry['pattern']}")

# Get statistics
stats = manager.get_statistics()
print(f"Active: {stats['total_active']}")
print(f"Applied (30d): {stats['recent_applications_30d']}")
```

### Integration with ScanPipeline

```python
from raxe.application.scan_pipeline import ScanPipeline
from raxe.domain.suppression import SuppressionManager

# Create suppression manager
suppression_manager = SuppressionManager()

# Add some suppressions
suppression_manager.add_suppression(
    pattern="pi-001",
    reason="False positive in test suite",
)

# Create scan pipeline with suppression manager
pipeline = ScanPipeline(
    pack_registry=registry,
    rule_executor=executor,
    l2_detector=detector,
    scan_merger=merger,
    suppression_manager=suppression_manager,  # NEW
)

# Scan text - suppressions will be applied automatically
result = pipeline.scan("Some text to scan")

# Check suppression count
suppressed = result.metadata.get("suppressed_count", 0)
print(f"Suppressions applied: {suppressed}")
```

---

## SQLite Database Schema

### Suppression Audit Table

The suppression system logs all activity to SQLite for audit compliance.

```sql
CREATE TABLE suppression_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    reason TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'added', 'removed', 'applied'
    scan_id INTEGER,       -- NULL for add/remove, set for applied
    rule_id TEXT,          -- Rule that was suppressed (for applied)
    created_at TEXT NOT NULL,
    created_by TEXT,       -- Who performed the action
    metadata TEXT          -- JSON for additional context
);
```

### Scan History Integration

Suppressions are also logged in the scan history database:

```sql
CREATE TABLE suppressions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER,
    rule_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    suppression_pattern TEXT,
    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);
```

### Querying the Database

```python
from raxe.domain.suppression import SuppressionManager

manager = SuppressionManager()

# Get audit log
audit_log = manager.get_audit_log(limit=100)

# Filter by action
added = manager.get_audit_log(action="added")
removed = manager.get_audit_log(action="removed")
applied = manager.get_audit_log(action="applied")

# Filter by pattern
pi_suppressions = manager.get_audit_log(pattern="pi-*")

# Get statistics
stats = manager.get_statistics()
```

---

## Best Practices

### 1. Be Specific

❌ **Bad:** Suppress entire families without investigation
```gitignore
pi-*  # Disable all PI rules
```

✅ **Good:** Suppress specific rules with detailed reasons
```gitignore
pi-001  # False positive: documentation uses "ignore previous instructions" as example
pi-007  # Safe pattern: CLI help text contains instruction keywords
```

### 2. Document Context

❌ **Bad:** Vague reasons
```gitignore
pi-001  # Doesn't work
jb-002  # False positive
```

✅ **Good:** Detailed explanations
```gitignore
pi-001  # Documentation examples contain instruction patterns - verified safe
jb-002  # Support knowledge base uses "ignore" in troubleshooting steps
```

### 3. Use Expiration Dates

❌ **Bad:** Permanent suppressions for temporary issues
```gitignore
pi-advanced-001  # Bug in new template
```

✅ **Good:** Time-limited suppressions
```bash
raxe suppress add pi-advanced-001 "Bug in template" --expires 2025-12-31T23:59:59Z
```

### 4. Regular Reviews

Set up periodic reviews of suppressions:

```bash
# Monthly review
raxe suppress audit --limit 1000 > monthly_review.txt

# Check for expired suppressions
raxe suppress list

# Remove unnecessary suppressions
raxe suppress remove <pattern>
```

### 5. Audit Trail

Use the audit log for compliance and debugging:

```bash
# Who added suppressions?
raxe suppress audit --action added

# What rules are being suppressed most?
raxe suppress audit --action applied

# When was a suppression added?
raxe suppress show pi-001
```

### 6. Environment-Specific

Use different `.raxeignore` files for different environments:

```bash
# Development
cp .raxeignore.dev .raxeignore

# Production (minimal suppressions)
cp .raxeignore.prod .raxeignore

# Testing (more permissive)
cp .raxeignore.test .raxeignore
```

---

## Common Patterns

### Suppress Documentation Examples

```gitignore
# Documentation contains security examples
pi-001  # "Ignore previous instructions" used in examples
jb-dan-prompt  # DAN prompt documented for awareness
pii-email  # Example email addresses in docs
```

### Suppress Test Data

```gitignore
# Test suite uses attack patterns intentionally
pi-*-test  # All test-related PI rules
jb-test-*  # All test jailbreak patterns
```

### Suppress Known Safe Patterns

```gitignore
# CLI argument parsing
cmd-injection-001  # CLI uses expected flag patterns

# Knowledge base content
pi-system-override  # KB troubleshooting uses system commands

# Code review comments
jb-roleplay  # Code reviews discuss roleplay scenarios
```

### Temporary Migration Suppressions

```bash
# During template migration
raxe suppress add pi-advanced-001 "Old template migration" --expires 2025-12-31T23:59:59Z

# During refactoring
raxe suppress add jb-regex-basic "Refactoring prompt system" --expires 2026-01-15T00:00:00Z
```

---

## Troubleshooting

### Suppression Not Working

1. **Check pattern syntax**
   ```bash
   raxe suppress show "pi-*"  # Verify pattern matches
   ```

2. **Check if suppression is expired**
   ```bash
   raxe suppress list  # Look for expired suppressions
   ```

3. **Verify suppression loaded**
   ```bash
   raxe suppress list --format text
   ```

4. **Check audit log**
   ```bash
   raxe suppress audit --action applied
   ```

### Too Many False Positives

1. **Review detection results**
   ```bash
   raxe scan "text" --format json
   ```

2. **Add targeted suppressions**
   ```bash
   raxe suppress add pi-001 "Specific reason"
   ```

3. **Avoid broad patterns**
   - Don't suppress entire families unless necessary
   - Use specific rule IDs when possible

### Audit Compliance

1. **Export audit log**
   ```bash
   raxe suppress audit --limit 10000 > suppressions_audit.txt
   ```

2. **Review suppressions regularly**
   ```bash
   # Monthly audit
   raxe suppress stats
   raxe suppress list
   ```

3. **Track who added what**
   ```bash
   raxe suppress audit --action added
   ```

---

## Security Considerations

### ⚠️ Risks of Suppressions

1. **Hiding Real Threats**: Suppressions can mask actual security issues
2. **Compliance Gaps**: Suppressed rules may be required by security policies
3. **Drift Over Time**: Suppressions can accumulate and become stale

### ✅ Mitigation Strategies

1. **Require Justification**: Always document why a rule is suppressed
2. **Regular Reviews**: Audit suppressions monthly or quarterly
3. **Approval Process**: Require security team approval for suppressions
4. **Expiration Dates**: Use time-limited suppressions when possible
5. **Audit Logging**: Monitor who adds/removes suppressions
6. **Environment Isolation**: Use different suppressions for dev/prod

### 🔒 Compliance

For compliance-sensitive environments:

1. **Track All Changes**
   ```bash
   # Export full audit log
   raxe suppress audit --limit 100000 > audit_$(date +%Y%m%d).log
   ```

2. **Require Approvals**
   - Implement approval workflow before adding suppressions
   - Log approver information in `created_by` field

3. **Periodic Recertification**
   - Review all suppressions quarterly
   - Remove outdated suppressions
   - Update reasons with current context

4. **Separation of Duties**
   - Different roles for adding vs. approving suppressions
   - Track who performs each action

---

## Examples

### Example 1: False Positive in Documentation

```bash
# Identify the false positive
raxe scan "docs/security.md"
# Output: pi-001 detected in "ignore previous instructions" example

# Add suppression
raxe suppress add pi-001 "Documentation security examples" --save

# Verify
raxe suppress show pi-001

# Scan again - should be suppressed
raxe scan "docs/security.md"
```

### Example 2: Testing Environment

```bash
# Add test-specific suppressions
raxe suppress add "jb-dan-prompt" "Red team testing environment"
raxe suppress add "pi-system-override" "Test suite for system prompts"

# Save for test environment
raxe suppress list --format text > .raxeignore.test

# Use in tests
cp .raxeignore.test .raxeignore
raxe scan test_prompts.txt
```

### Example 3: Temporary Migration

```bash
# Add temporary suppression with expiration
raxe suppress add pi-advanced-001 "Migrating to new template system" \
  --expires 2025-12-31T23:59:59Z

# Check status
raxe suppress show pi-advanced-001

# After migration, remove
raxe suppress remove pi-advanced-001 --save
```

### Example 4: Audit Compliance

```bash
# Monthly audit workflow
echo "=== Monthly Suppression Audit ===" > audit_report.txt
date >> audit_report.txt

# Current statistics
raxe suppress stats >> audit_report.txt

# All active suppressions
echo "\n=== Active Suppressions ===" >> audit_report.txt
raxe suppress list >> audit_report.txt

# Recent activity
echo "\n=== Recent Activity ===" >> audit_report.txt
raxe suppress audit --limit 100 >> audit_report.txt

# Review and approve
cat audit_report.txt
```

---

## Migration Guide

### From Manual Filtering

If you're currently filtering results manually:

```python
# Before: Manual filtering
results = raxe.scan(text)
filtered = [r for r in results if r.rule_id not in ["pi-001", "jb-002"]]

# After: Use suppressions
# Add suppressions once
raxe suppress add pi-001 "Documented false positive"
raxe suppress add jb-002 "Known safe pattern"

# Scans automatically filter
results = raxe.scan(text)  # Suppressions applied automatically
```

### From Config Files

If you're using custom config for exclusions:

```python
# Before: Config-based
config = {
    "excluded_rules": ["pi-001", "jb-002"]
}

# After: Use .raxeignore
# .raxeignore file:
pi-001  # Documented false positive
jb-002  # Known safe pattern

# Load automatically
manager = SuppressionManager(auto_load=True)
```

---

## FAQ

**Q: Do suppressions affect all scans?**
A: Yes, once a suppression is active, it applies to all scans that load the SuppressionManager.

**Q: Can I have different suppressions for different projects?**
A: Yes, use different `.raxeignore` files or config paths for each project.

**Q: Are suppressions logged?**
A: Yes, all suppressions are logged to SQLite for audit compliance.

**Q: Can suppressions expire?**
A: Yes, use `--expires` flag when adding suppressions via CLI.

**Q: How do I review what was suppressed?**
A: Use `raxe suppress audit --action applied` to see all applied suppressions.

**Q: Can I suppress rules in code?**
A: Yes, use the SuppressionManager API in your code.

**Q: Are suppressions reversible?**
A: Yes, use `raxe suppress remove <pattern>` to remove suppressions.

**Q: Do wildcards work everywhere?**
A: Yes, patterns support `*` wildcards like `pi-*` or `*-injection`.

---

## Support

For issues or questions:

1. Check audit log: `raxe suppress audit`
2. Review statistics: `raxe suppress stats`
3. Verify patterns: `raxe suppress show <pattern>`
4. Documentation: https://docs.raxe.ai/suppressions
5. GitHub Issues: https://github.com/raxe-ai/raxe-ce/issues

---

## Changelog

### Version 1.0.0 (Initial Release)

- `.raxeignore` file support
- CLI commands for suppression management
- SQLite audit logging
- Wildcard pattern matching
- Expiration date support
- Scan pipeline integration
- Programmatic API
