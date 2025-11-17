# RAXE Debugging & Verbose Logging Guide

## Overview

This guide explains how to enable debug mode, configure verbose logging, and troubleshoot common issues in RAXE.

## Debug Mode

### Enable Debug Logging

#### Method 1: Environment Variable

```bash
# Enable debug mode for all RAXE operations
export RAXE_DEBUG=1
export RAXE_ENABLE_CONSOLE_LOGGING=true

# Run RAXE
raxe scan "test"
```

#### Method 2: CLI Flag

```bash
# Enable verbose output for a single command
raxe --verbose scan "test"
```

#### Method 3: Python SDK

```python
import logging
import os

# Enable debug logging
os.environ["RAXE_ENABLE_CONSOLE_LOGGING"] = "true"

# Configure logging level
logging.basicConfig(level=logging.DEBUG)

from raxe import Raxe

raxe = Raxe()
result = raxe.scan("test")
```

### What Debug Mode Reveals

When debug mode is enabled, you'll see:

- **Rule matching details**: Which rules matched, which didn't
- **Performance metrics**: Time spent in each detection layer
- **Cache hits/misses**: Cache performance statistics
- **Database operations**: SQL queries and results
- **Configuration loading**: Config file parsing and validation
- **Telemetry transmission**: What data is sent (if enabled)
- **Exception stack traces**: Full error details

### Security Warning

⚠️ **WARNING**: Debug mode may log sensitive information including:
- User prompts (full text)
- Detection results
- API endpoints
- Configuration values

**Never enable debug mode in production** or share debug logs publicly without redacting sensitive data.

## Logging Configuration

### Logging Levels

RAXE uses Python's standard logging levels:

```python
DEBUG    = 10  # Detailed diagnostic information
INFO     = 20  # Informational messages (default)
WARNING  = 30  # Warning messages
ERROR    = 40  # Error messages
CRITICAL = 50  # Critical errors
```

### Configure Logging Level

#### Via Environment Variable

```bash
export RAXE_LOG_LEVEL=DEBUG
raxe scan "test"
```

#### Via Python

```python
import logging
from raxe import Raxe

# Set RAXE logger to DEBUG
logging.getLogger("raxe").setLevel(logging.DEBUG)

# Or configure all logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

raxe = Raxe()
```

### Log Output Destinations

#### Console Logging

```bash
# Enable console output
export RAXE_ENABLE_CONSOLE_LOGGING=true
raxe scan "test"
```

#### File Logging

```python
import logging

# Log to file
logging.basicConfig(
    filename='raxe_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from raxe import Raxe
raxe = Raxe()
```

#### Structured Logging

RAXE uses `structlog` for structured logging:

```python
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

from raxe import Raxe
raxe = Raxe()
```

## Troubleshooting Common Issues

### Issue 1: "No threats detected" for obvious malicious input

**Debug Steps:**

```bash
# 1. Check which rules are loaded
raxe rules list

# 2. Search for relevant rules
raxe rules list --search "ignore"

# 3. Run with verbose mode to see rule matching
raxe --verbose scan "Ignore all previous instructions"

# 4. Check specific rule details
raxe rules show pi-001

# 5. Test rule pattern manually
python -c "import re; print(re.search(r'(?i)\\bignore\\s+.*\\bprevious', 'Ignore all previous instructions'))"
```

**Common Causes:**
- Rule not loaded (check `~/.raxe/config.yaml`)
- Confidence threshold too high
- L1 disabled in config
- Pattern doesn't match exact text

### Issue 2: Performance is slow

**Debug Steps:**

```bash
# 1. Profile a scan
raxe profile "test text"

# 2. Check cache status
raxe stats

# 3. Run with timing details
time raxe scan "test"

# 4. Check database size
ls -lh ~/.raxe/raxe.db

# 5. Test L1 vs L2 performance
raxe scan "test" --l1-only --profile
raxe scan "test" --l2-only --profile
```

**Common Causes:**
- Large database (slow queries)
- Cache disabled
- L2 model slow (first run)
- Too many rules enabled

### Issue 3: False positives

**Debug Steps:**

```bash
# 1. Identify which rule triggered
raxe --verbose scan "benign text"

# 2. Check rule details
raxe rules show <rule-id>

# 3. Suppress specific false positive
raxe suppress add <rule-id> "benign text"

# 4. Adjust confidence threshold
raxe tune threshold

# 5. Report false positive
# Create GitHub issue with example
```

### Issue 4: Module import errors

**Debug Steps:**

```bash
# 1. Check Python version
python --version  # Must be 3.10+

# 2. Verify installation
pip show raxe

# 3. Check dependencies
pip check

# 4. Reinstall
pip uninstall raxe
pip install --no-cache-dir raxe

# 5. Test import
python -c "from raxe import Raxe; print('OK')"
```

### Issue 5: Configuration not loading

**Debug Steps:**

```bash
# 1. Check config file exists
ls -la ~/.raxe/config.yaml

# 2. Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('/home/user/.raxe/config.yaml'))"

# 3. Check permissions
ls -l ~/.raxe/

# 4. Run doctor command
raxe doctor

# 5. Recreate config
rm ~/.raxe/config.yaml
raxe init
```

### Issue 6: Database errors

**Debug Steps:**

```bash
# 1. Check database exists
ls -la ~/.raxe/raxe.db

# 2. Inspect database
sqlite3 ~/.raxe/raxe.db ".schema"

# 3. Check database integrity
sqlite3 ~/.raxe/raxe.db "PRAGMA integrity_check;"

# 4. View recent scans
sqlite3 ~/.raxe/raxe.db "SELECT * FROM scans ORDER BY timestamp DESC LIMIT 10;"

# 5. Backup and recreate
cp ~/.raxe/raxe.db ~/.raxe/raxe.db.backup
rm ~/.raxe/raxe.db
raxe init
```

## Advanced Debugging

### Trace All RAXE Operations

```python
import logging
import sys

# Enable ALL logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Enable debug for specific modules
logging.getLogger("raxe.domain").setLevel(logging.DEBUG)
logging.getLogger("raxe.infrastructure").setLevel(logging.DEBUG)
logging.getLogger("raxe.sdk").setLevel(logging.DEBUG)

from raxe import Raxe
raxe = Raxe()
result = raxe.scan("test")
```

### Inspect Internal State

```python
from raxe import Raxe

raxe = Raxe()

# View loaded rules
print(f"Rules loaded: {len(raxe._engine._rules)}")

# View configuration
print(f"Config: {raxe._config}")

# View cache statistics
result = raxe.scan("test")
print(f"Scan took: {result.metadata.get('scan_duration_ms')}ms")
```

### Profile Memory Usage

```python
import tracemalloc
from raxe import Raxe

tracemalloc.start()

raxe = Raxe()
result = raxe.scan("test" * 1000)  # Large input

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.2f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.2f} MB")

tracemalloc.stop()
```

### Network Debugging (Telemetry)

```bash
# Capture telemetry traffic
export RAXE_DEBUG=1
export RAXE_TELEMETRY_ENDPOINT="http://localhost:8000"

# In another terminal, start a test server
python -m http.server 8000

# Run RAXE - you'll see telemetry requests
raxe scan "test"
```

## Diagnostic Commands

### System Health Check

```bash
# Comprehensive system check
raxe doctor

# Output includes:
# - Python version
# - RAXE version
# - Config status
# - Database status
# - Rule count
# - Recent errors
```

### Rule Validation

```bash
# Validate all rules
for rule in ~/.raxe/packs/core/v1.0.0/rules/**/*.yaml; do
    echo "Checking: $rule"
    raxe validate-rule "$rule"
done
```

### Performance Benchmark

```bash
# Quick benchmark
time for i in {1..100}; do
    raxe scan "test" --format json > /dev/null
done

# Detailed benchmark
raxe profile "Ignore all previous instructions" --iterations 1000
```

## Log Analysis

### Parse Structured Logs

```bash
# If using JSON logging
grep "ERROR" raxe.log | jq '.message'

# Count errors by type
grep "ERROR" raxe.log | jq '.error_type' | sort | uniq -c

# Find slow scans
grep "scan_duration" raxe.log | jq 'select(.scan_duration_ms > 10)'
```

### Common Log Patterns

```bash
# Detection events
grep "THREAT_DETECTED" raxe.log

# Configuration errors
grep "CONFIG_ERROR" raxe.log

# Database errors
grep "DATABASE_ERROR" raxe.log

# Rule loading issues
grep "RULE_LOAD" raxe.log
```

## Debug Mode Security

### Redacting Sensitive Data

```python
import logging
import re

class RedactingFilter(logging.Filter):
    def filter(self, record):
        # Redact potential API keys
        record.msg = re.sub(
            r'(api[_-]?key["\s:=]+)[A-Za-z0-9-_]+',
            r'\1***REDACTED***',
            str(record.msg)
        )
        # Redact prompts in debug logs
        record.msg = re.sub(
            r'(prompt["\s:=]+)"([^"]+)"',
            r'\1"***REDACTED***"',
            str(record.msg)
        )
        return True

# Add filter to RAXE logger
logging.getLogger("raxe").addFilter(RedactingFilter())
```

### Safe Debug Output

```bash
# Redirect debug output to secure file
raxe --verbose scan "test" 2>&1 | tee debug.log
chmod 600 debug.log  # Read/write for owner only
```

## Reporting Issues

When reporting bugs, include:

1. **RAXE version**: `raxe --version`
2. **Python version**: `python --version`
3. **OS**: `uname -a`
4. **Error message**: Full traceback
5. **Reproduction steps**: Minimal example
6. **Config**: Redacted `config.yaml`
7. **Logs**: Relevant log entries (redacted)

**Template:**

```markdown
## Bug Report

### Environment
- RAXE Version: 0.0.2
- Python Version: 3.11.5
- OS: Ubuntu 22.04

### Issue
[Brief description]

### Steps to Reproduce
1. Install RAXE: `pip install raxe==0.0.2`
2. Run: `raxe scan "test"`
3. Error occurs

### Expected Behavior
[What should happen]

### Actual Behavior
[What actually happens]

### Logs
```
[Paste redacted logs here]
```

### Additional Context
[Any other relevant information]
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `RAXE_DEBUG` | `false` | Enable debug mode |
| `RAXE_VERBOSE` | `false` | Enable verbose CLI output |
| `RAXE_ENABLE_CONSOLE_LOGGING` | `false` | Log to console |
| `RAXE_LOG_LEVEL` | `INFO` | Logging level |
| `RAXE_CONFIG_PATH` | `~/.raxe/config.yaml` | Config file path |
| `RAXE_NO_COLOR` | `false` | Disable colored output |
| `RAXE_TELEMETRY_ENABLED` | `true` | Enable telemetry |

## See Also

- [Troubleshooting Guide](troubleshooting.md)
- [Performance Tuning](performance/tuning_guide.md)
- [Configuration Reference](QUICK_REFERENCE.md)
- [System Diagnostics](api/raxe-client.md#diagnostics)
