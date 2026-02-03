# Description

Please include a summary of the changes and which issue is fixed.

Fixes # (issue)

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring (no functional changes)

## Pre-submission Checklist

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings

## Testing

- [ ] Unit tests added/updated
- [ ] All unit tests pass locally (`pytest tests/unit -v`)
- [ ] Integration tests added/updated (if needed)
- [ ] Coverage remains >80% (`pytest --cov=raxe --cov-fail-under=80`)

### Detection Rule Changes (if applicable)

- [ ] Golden tests pass (`pytest tests/golden -v`)
- [ ] Golden files regenerated if detection behavior changed (`python scripts/generate_golden_files.py`)
- [ ] False positive rate validated

### MSSP/Webhook Changes (if applicable)

- [ ] Webhook signature verification tested
- [ ] Privacy: `_mssp_data` NEVER sent to RAXE backend
- [ ] Privacy: No PII in logs

## Documentation

- [ ] I have made corresponding changes to the documentation
- [ ] Updated docstrings for changed functions
- [ ] Updated `docs/` if behavior changes
- [ ] Updated `raxe-ce-docs/` for user-facing changes

## Domain Layer Purity (if applicable)

- [ ] No I/O operations in domain layer (`src/raxe/domain/`)
- [ ] Domain layer remains pure (functions only)
- [ ] All I/O moved to infrastructure layer

## Telemetry & Privacy (if applicable)

- [ ] No prompt content in telemetry payloads
- [ ] No matched text in telemetry payloads
- [ ] Telemetry tests pass (`pytest tests/*/test_telemetry*.py -v`)

## Screenshots (if applicable)

Add screenshots to help explain your changes.

---

**For Reviewers:**

- [ ] Code quality review
- [ ] Security review (if security-sensitive)
- [ ] Performance impact considered
- [ ] Documentation is adequate
