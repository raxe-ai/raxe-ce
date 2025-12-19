# Suppression System

Manage false positives in your AI security workflow with RAXE's suppression system.

## Overview

When RAXE detects a threat that you've verified as safe, you can suppress it to prevent future alerts. The suppression system provides:

- **YAML-based configuration** for persistent suppressions
- **Inline SDK suppression** for context-specific cases
- **CLI flags** for quick testing
- **Policy action overrides** (FLAG, LOG instead of full suppression)
- **Audit trail** for compliance

## Quick Start

### 1. Create Configuration

```bash
mkdir -p .raxe
```

Create `.raxe/suppressions.yaml`:

```yaml
version: "1.0"

suppressions:
  - pattern: "pi-001"
    reason: "Known false positive in authentication flow"
```

### 2. Verify

```bash
raxe suppress list
```

## Configuration

### File Location

Suppressions are configured in `.raxe/suppressions.yaml`.

### Schema

```yaml
version: "1.0"  # Required

suppressions:
  - pattern: "pi-001"              # Required: Rule ID or wildcard
    reason: "Audit-ready reason"   # Required: Why suppressed
    expires: "2025-06-01"          # Optional: Expiration date
    action: "FLAG"                 # Optional: SUPPRESS, FLAG, or LOG
    created_by: "security-team"    # Optional: Who created this
```

### Required Fields

| Field | Description |
|-------|-------------|
| `pattern` | Rule ID or wildcard (e.g., `pi-001`, `pi-*`) |
| `reason` | Human-readable reason (required for audit) |

### Optional Fields

| Field | Description |
|-------|-------------|
| `expires` | ISO 8601 expiration date |
| `action` | Override action: `SUPPRESS`, `FLAG`, or `LOG` |
| `created_by` | Who created the suppression |

## Patterns

### Wildcards

```yaml
# Exact rule
- pattern: "pi-001"

# Family wildcard (all prompt injection)
- pattern: "pi-*"

# Partial wildcard
- pattern: "jb-00*"

# Suffix wildcard
- pattern: "*-injection"
```

### Valid Family Prefixes

| Prefix | Family |
|--------|--------|
| `pi` | Prompt Injection |
| `jb` | Jailbreak |
| `pii` | PII Leakage |
| `cmd` | Command Injection |
| `hc` | Harmful Content |
| `enc` | Encoding Attacks |
| `rag` | RAG Attacks |

> **Note:** Bare wildcards (`*`) are not allowed. Use a family prefix like `pi-*`.

## Actions

Instead of fully suppressing, you can override the action:

| Action | Behavior |
|--------|----------|
| `SUPPRESS` | Remove from results (default) |
| `FLAG` | Keep in results, mark for human review |
| `LOG` | Keep in results, log only |

```yaml
suppressions:
  - pattern: "hc-*"
    action: FLAG
    reason: "Harmful content requires human review"
```

## SDK Usage

### Inline Suppression

```python
from raxe import Raxe

client = Raxe()

# Simple suppression
result = client.scan(text, suppress=["pi-001", "jb-*"])

# With action override
result = client.scan(text, suppress=[
    {"pattern": "pi-001", "action": "FLAG", "reason": "Review required"}
])
```

### Context Manager

```python
with client.suppressed("pi-*", reason="Testing auth flow"):
    result = client.scan(text)
```

## CLI Usage

### Scan with Suppression

```bash
# Single
raxe scan "text" --suppress pi-001

# Multiple
raxe scan "text" --suppress pi-001 --suppress "jb-*"

# With action
raxe scan "text" --suppress "pi-001:FLAG"
```

### Manage Suppressions

```bash
raxe suppress list                          # List all
raxe suppress add pi-001 --reason "Reason"  # Add
raxe suppress remove pi-001                 # Remove
raxe suppress audit                         # View audit log
raxe suppress stats                         # Statistics
```

## Best Practices

1. **Be specific** - Use exact rule IDs when possible
2. **Set expirations** - Temporary suppressions should expire
3. **Document reasons** - Future you will thank present you
4. **Review quarterly** - Run `raxe suppress audit` regularly
5. **Use FLAG for monitoring** - See detections without blocking

### Good vs Bad Reasons

```yaml
# Bad
- pattern: "pi-001"
  reason: "false positive"

# Good
- pattern: "pi-001"
  reason: "Auth flow uses 'ignore previous' in rate limit messages - verified safe"
```

## Troubleshooting

### Suppression Not Working

1. Check pattern: `raxe suppress list`
2. Check file: `ls -la .raxe/suppressions.yaml`
3. Check expiration: Expired suppressions are skipped

### Invalid Pattern Error

```
Error: Wildcard patterns must have a valid family prefix.
```

Use `pi-*` instead of `*`.

### Missing Reason Error

```
Error: Missing required field: reason
```

All suppressions require a reason.

## Security

- Pattern length limit: 256 characters
- Reason length limit: 500 characters
- Maximum suppressions: 1000
- Audit trail for all operations
