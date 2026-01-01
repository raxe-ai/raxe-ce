# Documentation Style Guide

Standards for consistent documentation across RAXE.

---

## Command Formatting

### Inline Commands

Use backticks for inline commands: `raxe scan`, `raxe auth`, `pip install raxe`

### Code Blocks

Use fenced code blocks with language hint for commands:

```bash
raxe scan "your prompt here"
```

Use plain code blocks (no language) for terminal output:

```
THREAT DETECTED

Severity: CRITICAL
Confidence: 0.95
```

**Never mix command and output in the same block.**

---

## Terminal Output Standards

Show expected output in a separate block after the command:

```bash
raxe auth status
```

```
API Key Status
==============
Key Type: live
Key ID: key_23cc2f9f21f9
```

---

## Terminology Standards

| Preferred | Avoid | Reason |
|-----------|-------|--------|
| `scan` | `check`, `analyze`, `detect` | Consistent verb |
| `threat` | `attack`, `malicious input` | Product terminology |
| `detection` | `match`, `hit`, `finding` | API terminology |
| `API key` | `token`, `secret` | User-facing term |
| `temporary key` | `temp key`, `trial key` | Full words preferred |
| `L1/L2` | `layer 1/layer 2` | Established shorthand |
| `rule` | `pattern`, `signature` | Product terminology |
| `pack` | `ruleset`, `bundle` | Product terminology |

---

## Code Example Standards

Always include imports, instantiation, and result handling:

```python
# ALWAYS include imports
from raxe import Raxe

# ALWAYS show instantiation
raxe = Raxe()

# ALWAYS show result handling
result = raxe.scan("your prompt")
if result.has_threats:
    print(f"Threat: {result.severity}")
```

### Runnable Examples

All code examples should be runnable without modification (except API keys).

---

## Version References

**Never hardcode versions** in documentation body. Use:
- "current version" or "latest"
- Badge images for version display
- Single source of truth in `pyproject.toml`

---

## Link Standards

### Internal Links (within docs/)

```markdown
[Getting Started](getting-started.md)
[Authentication Guide](authentication.md)
```

### Links to Root Files

```markdown
[README](../README.md)
[Contributing](../CONTRIBUTING.md)
```

### External Links

```markdown
[GitHub Discussions](https://github.com/raxe-ai/raxe-ce/discussions)
[RAXE Console](https://console.raxe.ai)
```

---

## Document Structure

### Standard Sections

1. **Title** - Clear, action-oriented (e.g., "Getting Started", "Authentication Guide")
2. **Introduction** - One paragraph explaining what the doc covers
3. **Prerequisites** (if applicable)
4. **Main Content** - Organized by user goals, not features
5. **Troubleshooting** - Common issues with solutions
6. **Related Documentation** - Links to next steps

### Heading Hierarchy

```markdown
# Document Title (H1 - one per document)

## Major Section (H2)

### Subsection (H3)

#### Detail (H4 - use sparingly)
```

---

## Tables

Use tables for comparisons and reference data:

| Method | Command | Best For |
|--------|---------|----------|
| Browser Auth | `raxe auth` | New users |
| Link Code | `raxe link CODE` | Existing keys |
| Environment | `RAXE_API_KEY=xxx` | CI/CD |

---

## Callouts

Use blockquotes for important notices:

```markdown
> **Note:** Additional helpful information.

> **Warning:** Something the user should be careful about.

> **Tip:** A helpful suggestion.
```

---

## File Organization

| File | Purpose | Audience |
|------|---------|----------|
| `README.md` | GitHub landing, quick hook | Evaluators |
| `docs/getting-started.md` | Canonical onboarding | New users |
| `docs/authentication.md` | Auth deep dive | Power users |
| `docs/configuration.md` | Full config reference | Production |
| `docs/index.md` | Navigation hub | All readers |

---

## Deprecation Notices

When moving or consolidating documentation:

```markdown
> **⚠️ Deprecated:** This document has moved to [new-location.md](new-location.md).
> This file will be removed in v0.5.0. Please update your bookmarks.
```

---

## Review Checklist

Before merging documentation changes:

- [ ] All internal links resolve
- [ ] Code examples are runnable
- [ ] No hardcoded version numbers
- [ ] Follows terminology standards
- [ ] Has appropriate callouts/warnings
- [ ] Includes related documentation links
