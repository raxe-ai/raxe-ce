# RAXE Error Codes Reference

RAXE provides structured error codes for consistent debugging, logging, and programmatic error handling. This document covers both SDK exceptions and CLI exit codes.

---

## Quick Reference

### CLI Exit Codes

| Code | Name | Description |
|------|------|-------------|
| `0` | `EXIT_SUCCESS` | Command completed successfully, no threats detected |
| `1` | `EXIT_THREAT_DETECTED` | Threat(s) detected during scan |
| `2` | `EXIT_INVALID_INPUT` | Invalid command arguments or input |
| `3` | `EXIT_CONFIG_ERROR` | Configuration problem |
| `4` | `EXIT_SCAN_ERROR` | Scan execution failed |

### SDK Error Code Categories

| Category | Range | Description |
|----------|-------|-------------|
| `CFG` | 001-099 | Configuration errors |
| `RULE` | 100-199 | Rule-related errors |
| `SEC` | 200-299 | Security errors |
| `DB` | 300-399 | Database errors |
| `VAL` | 400-499 | Validation errors |
| `INFRA` | 500-599 | Infrastructure errors |

---

## CLI Exit Codes (Detailed)

### EXIT_SUCCESS (0)

**Meaning:** Command completed successfully with no threats detected.

**When it occurs:**
- `raxe scan` finds no threats
- `raxe doctor` passes all health checks
- `raxe rules list` completes successfully

**CI/CD Usage:**
```bash
raxe scan "$PROMPT" --quiet
if [ $? -eq 0 ]; then
    echo "Clean - safe to proceed"
fi
```

---

### EXIT_THREAT_DETECTED (1)

**Meaning:** One or more security threats were detected during scanning.

**When it occurs:**
- `raxe scan` detects prompt injection, jailbreak, PII, or other threats
- Threat severity is HIGH or CRITICAL

**CI/CD Usage:**
```bash
raxe scan "$PROMPT" --quiet
if [ $? -eq 1 ]; then
    echo "BLOCKED: Security threat detected"
    exit 1
fi
```

**Remediation:**
1. Review the scan output with `raxe scan "$PROMPT" --explain`
2. If false positive, add suppression in `.raxe/suppressions.yaml` (see [Suppression System](SUPPRESSIONS.md))
3. If true positive, sanitize or reject the input

---

### EXIT_INVALID_INPUT (2)

**Meaning:** Invalid command arguments or malformed input.

**When it occurs:**
- Missing required arguments
- Invalid flag combinations
- Malformed input text

**Example:**
```bash
raxe scan  # Missing prompt argument
# Exit code: 2
```

**Remediation:**
1. Check command syntax with `raxe --help`
2. Ensure all required arguments are provided
3. Verify input encoding (UTF-8 required)

---

### EXIT_CONFIG_ERROR (3)

**Meaning:** Configuration file missing, invalid, or contains errors.

**When it occurs:**
- Config file not found and required
- Invalid YAML syntax in config
- Missing required configuration fields

**Example:**
```bash
raxe scan "test" --config /nonexistent/config.yaml
# Exit code: 3
```

**Remediation:**
1. Run `raxe init` to create default configuration
2. Validate config with `raxe config validate`
3. Check YAML syntax in `.raxe/config.yaml`

---

### EXIT_SCAN_ERROR (4)

**Meaning:** Internal error during scan execution.

**When it occurs:**
- Rule loading failure
- ML model initialization error
- Database connection failure
- Unexpected runtime exception

**Remediation:**
1. Run `raxe doctor` to diagnose issues
2. Check disk space and permissions
3. Reinstall with `pip install --force-reinstall raxe`
4. Report issue if persistent

---

## SDK Error Codes (Detailed)

All SDK errors follow the format `{CATEGORY}-{NUMBER}` and include:
- **code**: Unique error identifier
- **message**: Human-readable description
- **details**: Additional context (key-value pairs)
- **remediation**: Suggested fix
- **doc_url**: Link to documentation

### Catching Errors

```python
from raxe import Raxe, RaxeException
from raxe.sdk.exceptions import (
    ConfigurationError,
    ValidationError,
    RuleError,
    DatabaseError,
    InfrastructureError,
    SecurityException,
    RaxeBlockedError,
    ErrorCode,
)

try:
    raxe = Raxe()
    result = raxe.scan(prompt)
except RaxeBlockedError as e:
    # Request blocked by policy
    print(f"Blocked: {e.result.severity}")
except SecurityException as e:
    # Threat detected
    print(f"Threat: {e.error.code} - {e.error.message}")
except ConfigurationError as e:
    # Config issue
    print(f"Config: {e.error.remediation}")
except RaxeException as e:
    # Any RAXE error
    if e.error:
        print(f"Error {e.error.code}: {e.error.message}")
        print(f"Fix: {e.error.remediation}")
```

---

## Configuration Errors (CFG-001 to CFG-099)

### CFG-001: Configuration Not Found

**Message:** Configuration file not found

**Causes:**
- Config file doesn't exist at expected path
- Path typo or permission issue

**Remediation:**
```bash
raxe init  # Create default configuration
```

---

### CFG-002: Invalid Configuration Format

**Message:** Invalid configuration format (YAML parse error)

**Causes:**
- Invalid YAML syntax
- Incorrect indentation
- Special characters not quoted

**Remediation:**
```bash
raxe config validate  # Check for syntax errors
```

---

### CFG-003: Missing Required Field

**Message:** Required configuration field missing

**Causes:**
- Required field not present in config
- Field name typo

**Remediation:**
```bash
raxe config show  # View current configuration
# Add missing field to .raxe/config.yaml
```

---

### CFG-004: Invalid Configuration Value

**Message:** Invalid value for configuration field

**Causes:**
- Value type mismatch (string instead of number)
- Value out of allowed range
- Invalid enum value

**Remediation:**
Check documentation for valid values for the specific field.

---

### CFG-005: Permission Denied

**Message:** Permission denied accessing configuration

**Causes:**
- File permissions too restrictive
- Directory not writable

**Remediation:**
```bash
chmod 644 ~/.raxe/config.yaml
chmod 755 ~/.raxe
```

---

### CFG-006: Initialization Failed

**Message:** Configuration initialization failed

**Causes:**
- Corrupted config file
- Incompatible version

**Remediation:**
```bash
rm -rf ~/.raxe  # Remove old config
raxe init       # Reinitialize
```

---

## Rule Errors (RULE-100 to RULE-199)

### RULE-100: Rule Not Found

**Message:** Detection rule not found

**Causes:**
- Typo in rule ID
- Rule not loaded from pack

**Remediation:**
```bash
raxe rules list           # See available rules
raxe rules show pi-001    # Verify rule exists
```

---

### RULE-101: Invalid Rule Syntax

**Message:** Invalid rule syntax in YAML

**Causes:**
- Malformed rule definition
- Missing required fields

**Remediation:**
```bash
raxe validate-rule path/to/rule.yaml
```

---

### RULE-102: Invalid Pattern

**Message:** Invalid regex pattern in rule

**Causes:**
- Regex syntax error
- Catastrophic backtracking pattern
- Unsupported regex feature

**Remediation:**
Test patterns at [regex101.com](https://regex101.com) before adding to rules.

---

### RULE-103: Rule Load Failed

**Message:** Failed to load detection rules

**Causes:**
- Corrupted rule pack
- Permission issues
- Disk full

**Remediation:**
```bash
raxe doctor  # Diagnose rule loading issues
```

---

### RULE-104: Rule Pack Not Found

**Message:** Rule pack not found

**Causes:**
- Pack not installed
- Pack name typo

**Remediation:**
```bash
# Reinstall RAXE to restore default packs
pip install --force-reinstall raxe
```

---

### RULE-105: Invalid Rule Pack

**Message:** Invalid rule pack format

**Causes:**
- Corrupted pack manifest
- Invalid pack structure

**Remediation:**
Validate pack structure matches expected schema.

---

### RULE-106: Version Mismatch

**Message:** Rule version mismatch

**Causes:**
- Rule requires newer RAXE version
- Incompatible rule format

**Remediation:**
```bash
pip install --upgrade raxe
```

---

### RULE-107: Duplicate Rule ID

**Message:** Duplicate rule ID detected

**Causes:**
- Multiple rules with same ID
- Custom rule conflicts with built-in

**Remediation:**
Ensure all custom rule IDs are unique and don't conflict with built-in rules.

---

## Security Errors (SEC-200 to SEC-299)

### SEC-200: Threat Detected

**Message:** Security threat detected

**Causes:**
- Prompt injection attempt
- Jailbreak pattern detected
- PII in prompt

**Remediation:**
```bash
raxe scan "prompt" --explain  # Get detailed threat info
```

---

### SEC-201: Blocked by Policy

**Message:** Request blocked by security policy

**Causes:**
- Policy configured to block this threat type
- Severity exceeds threshold

**Remediation:**
Review policy configuration or add suppression rule if false positive.

---

### SEC-202: Critical Threat

**Message:** Critical security threat detected

**Causes:**
- High-confidence critical severity threat
- Multiple threat indicators

**Remediation:**
Investigate immediately - this indicates a likely attack.

---

### SEC-203: Invalid Signature

**Message:** Invalid signature on rule pack

**Causes:**
- Tampered rule pack
- Corrupted download

**Remediation:**
```bash
pip install --force-reinstall raxe
```

---

### SEC-204: Authentication Failed

**Message:** Authentication failed

**Causes:**
- Invalid API key
- Expired credentials

**Remediation:**
```bash
raxe config set api_key YOUR_KEY
```

---

### SEC-205: Permission Denied

**Message:** Permission denied for operation

**Causes:**
- API key lacks required permissions
- Rate limited

**Remediation:**
Contact administrator for access or wait before retrying.

---

## Database Errors (DB-300 to DB-399)

### DB-300: Connection Failed

**Message:** Database connection failed

**Causes:**
- Database file corrupted
- Disk full
- Permission denied

**Remediation:**
```bash
raxe doctor  # Check database health
# If corrupted:
rm ~/.raxe/scan_history.db
```

---

### DB-301: Query Failed

**Message:** Database query failed

**Causes:**
- Malformed query
- Database locked

**Remediation:**
```bash
raxe doctor  # Diagnose database issues
```

---

### DB-302: Migration Failed

**Message:** Database migration failed

**Causes:**
- Interrupted upgrade
- Incompatible schema

**Remediation:**
```bash
# Backup and reinitialize
cp ~/.raxe/scan_history.db ~/.raxe/scan_history.db.backup
rm ~/.raxe/scan_history.db
raxe init
```

---

### DB-303: Integrity Error

**Message:** Database integrity error

**Causes:**
- Corrupted database file
- Constraint violation

**Remediation:**
Restore from backup or reinitialize database.

---

### DB-304: Not Initialized

**Message:** Database not initialized

**Causes:**
- First run without initialization
- Database deleted

**Remediation:**
```bash
raxe init
```

---

### DB-305: Lock Timeout

**Message:** Database lock timeout

**Causes:**
- Multiple RAXE instances
- Long-running transaction

**Remediation:**
Close other RAXE instances and retry.

---

## Validation Errors (VAL-400 to VAL-499)

### VAL-400: Empty Input

**Message:** Empty input provided

**Causes:**
- Empty string passed to scan()
- Whitespace-only input

**Remediation:**
Provide non-empty text for scanning.

---

### VAL-401: Input Too Long

**Message:** Input exceeds maximum length

**Causes:**
- Text longer than allowed limit
- No chunking applied

**Remediation:**
Split input into smaller chunks or increase limit.

---

### VAL-402: Invalid Format

**Message:** Invalid input format

**Causes:**
- Unexpected data type
- Invalid encoding

**Remediation:**
Ensure input is valid UTF-8 string.

---

### VAL-403: Missing Field

**Message:** Required field missing

**Causes:**
- API call missing required parameter

**Remediation:**
Check API documentation for required fields.

---

### VAL-404: Type Mismatch

**Message:** Type mismatch

**Causes:**
- Wrong data type for parameter

**Remediation:**
Verify parameter types match API specification.

---

### VAL-405: Out of Range

**Message:** Value out of allowed range

**Causes:**
- Numeric value outside bounds
- Invalid threshold

**Remediation:**
Use value within documented range.

---

### VAL-406: Invalid Regex

**Message:** Invalid regular expression

**Causes:**
- Malformed regex pattern
- Unsupported regex syntax

**Remediation:**
Test regex at regex101.com before use.

---

### VAL-407: Invalid Policy

**Message:** Invalid policy configuration

**Causes:**
- Malformed policy YAML
- Invalid policy action

**Remediation:**
```bash
# Validate policy file
raxe config validate
```

---

## Infrastructure Errors (INFRA-500 to INFRA-599)

### INFRA-500: Network Error

**Message:** Network error

**Causes:**
- No internet connection
- DNS resolution failure
- Firewall blocking

**Remediation:**
Check network connectivity. RAXE works 100% offline by default.

---

### INFRA-501: Timeout

**Message:** Operation timed out

**Causes:**
- Slow disk I/O
- Overloaded system

**Remediation:**
Retry or increase timeout setting.

---

### INFRA-502: Service Unavailable

**Message:** Service unavailable

**Causes:**
- Cloud service down (Enterprise only)
- Rate limiting

**Remediation:**
Retry later or use offline mode.

---

### INFRA-503: Rate Limited

**Message:** Rate limit exceeded

**Causes:**
- Too many requests

**Remediation:**
Implement exponential backoff.

---

### INFRA-504: Disk Full

**Message:** Disk space exhausted

**Causes:**
- No space for database or logs

**Remediation:**
Free up disk space.

---

### INFRA-505: Model Load Failed

**Message:** Failed to load ML model

**Causes:**
- Missing ONNX runtime
- Corrupted model file
- Insufficient memory

**Remediation:**
```bash
pip install raxe[ml]  # Install ML dependencies
```

---

### INFRA-506: Circuit Breaker Open

**Message:** Circuit breaker is open

**Causes:**
- Service experiencing repeated failures
- Automatic protection activated

**Remediation:**
Wait a few minutes for circuit breaker to reset.

---

## Programmatic Error Handling

### Creating Errors

```python
from raxe.sdk.exceptions import (
    from_error_code,
    ErrorCode,
    config_not_found_error,
    validation_empty_input_error,
)

# Using factory function
error = config_not_found_error("/path/to/config.yaml")
raise ConfigurationError(error)

# Using from_error_code helper
exc = from_error_code(
    ErrorCode.VAL_EMPTY_INPUT,
    message="Prompt cannot be empty",
    details={"field": "prompt"},
)
raise exc
```

### Error Serialization

```python
try:
    result = raxe.scan(prompt)
except RaxeException as e:
    # Convert to dict for logging/API response
    error_dict = e.to_dict()
    # {
    #     "code": "VAL-400",
    #     "category": "VAL",
    #     "message": "Empty input provided",
    #     "details": {"field": "prompt"},
    #     "remediation": "Provide non-empty input",
    #     "doc_url": "https://docs.raxe.ai/errors/VAL-400"
    # }
```

---

## CI/CD Integration Examples

### GitHub Actions

```yaml
name: Security Scan
on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install RAXE
        run: pip install raxe

      - name: Scan PR Description
        run: |
          raxe scan "${{ github.event.pull_request.body }}" --quiet
        continue-on-error: false

      - name: Handle Scan Result
        if: failure()
        run: |
          echo "::error::Security threat detected in PR"
          exit 1
```

### GitLab CI

```yaml
security_scan:
  image: python:3.11
  script:
    - pip install raxe
    - raxe scan "$CI_COMMIT_MESSAGE" --quiet
  rules:
    - if: $CI_PIPELINE_SOURCE == "push"
  allow_failure: false
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    stages {
        stage('Security Scan') {
            steps {
                sh 'pip install raxe'
                script {
                    def exitCode = sh(
                        script: 'raxe scan "${PROMPT}" --quiet',
                        returnStatus: true
                    )
                    if (exitCode == 1) {
                        error('Security threat detected')
                    } else if (exitCode != 0) {
                        error("Scan failed with code ${exitCode}")
                    }
                }
            }
        }
    }
}
```

---

## Troubleshooting

### Common Issues

**Q: Getting CFG-001 but config file exists**
A: Check file permissions and ensure path is absolute.

**Q: RULE-103 on first run**
A: Run `raxe init` to initialize rule packs.

**Q: DB-305 lock timeout**
A: Close other terminal sessions running RAXE.

**Q: INFRA-505 model load failed**
A: Install ML dependencies: `pip install raxe[ml]`

### Getting Help

- **Issues**: [github.com/raxe-ai/raxe-ce/issues](https://github.com/raxe-ai/raxe-ce/issues)
- **Discussions**: [github.com/raxe-ai/raxe-ce/discussions](https://github.com/raxe-ai/raxe-ce/discussions)
- **Email**: community@raxe.ai

---

## Version History

| Version | Changes |
|---------|---------|
| v0.2.0 | Initial error code system (35 codes across 6 categories) |
| v0.2.0 | Standardized CLI exit codes (0-4) |
