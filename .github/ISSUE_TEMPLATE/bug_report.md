---
name: Bug Report
about: Report a bug in RAXE CE
title: '[BUG] '
labels: bug, needs-triage
assignees: ''
---

## Pre-submission Checklist

- [ ] I have searched existing issues to ensure this bug hasn't been reported
- [ ] I am using a supported Python version (3.10+)
- [ ] I have tried the latest version of RAXE

## Bug Summary

A clear and concise one-line description of the bug.

## Component

Where does this bug occur?

- [ ] CLI (`raxe scan`, `raxe doctor`, etc.)
- [ ] Python SDK (`raxe.scan()`, wrappers)
- [ ] Framework Integration (LangChain, CrewAI, etc.)
- [ ] Detection Rules (false positive/negative)
- [ ] ML Model (L2 classifier)
- [ ] Configuration
- [ ] Other: ___________

## Severity

How severe is this bug?

- [ ] **Critical** - System crash, data loss, security vulnerability
- [ ] **High** - Major feature broken, no workaround
- [ ] **Medium** - Feature impaired, workaround exists
- [ ] **Low** - Minor issue, cosmetic

## To Reproduce

Steps to reproduce the behavior:

1. Install RAXE: `pip install raxe`
2. Run command: `raxe ...`
3. See error: ...

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened. Include the full error message if applicable.

## Environment

- **OS:** [e.g., Ubuntu 22.04, macOS 14.0, Windows 11]
- **Python version:** [e.g., 3.10.5, 3.11.2]
- **RAXE version:** [e.g., 0.9.1] (run `raxe --version`)
- **Installation method:** [pip, pip with extras, source]

## Minimal Reproducible Example

```python
# Paste minimal code that reproduces the issue
from raxe import Raxe

raxe = Raxe()
result = raxe.scan("...")  # This fails
```

## Error Output

```
# Paste full error output / stack trace here
```

## Additional Context

Any other context, screenshots, or logs that help explain the problem.

## Possible Solution (optional)

If you have ideas on how to fix this bug, share them here.
