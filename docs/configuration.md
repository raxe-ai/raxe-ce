<p align="center">
  <img src="https://github.com/raxe-ai/raxe-ce/blob/main/docs/assets/logo-square.png?raw=true" alt="RAXE" width="100"/>
</p>

# RAXE Configuration Guide

Complete configuration reference for RAXE Community Edition v0.1.0.

## Quick Start

### Initialize Configuration

```bash
raxe init
```

This creates `~/.raxe/config.yaml` with sensible defaults. You can start using RAXE immediately without any configuration - it works out of the box.

### Configuration Priority

RAXE uses configuration from multiple sources in this priority order (highest to lowest):

1. **Explicit parameters** - Passed directly to `Raxe()` or `raxe.scan()`
2. **Environment variables** - `RAXE_*` prefixed variables
3. **Config file** - `~/.raxe/config.yaml` or custom path
4. **Built-in defaults** - Sensible defaults for all settings

---

## Configuration File

### Default Configuration

When you run `raxe init`, it creates this configuration:

```yaml
# RAXE Configuration
version: 1.0.0

# API Key (optional - for cloud features)
# api_key: your_api_key_here

# Telemetry (privacy-preserving, only hashes sent)
telemetry:
  enabled: true
  # endpoint: auto-detected based on environment (see Endpoint Configuration section)

# Performance
performance:
  mode: balanced  # fast, balanced, accurate
  l2_enabled: true
  max_latency_ms: 10

# Pack precedence (custom > community > core)
packs:
  precedence:
    - custom
    - community
    - core

# Policy source
policies:
  source: local_file  # local_file, api, inline
  path: .raxe/policies.yaml
```

### Full Configuration Reference

For advanced use cases, you can use the full `ScanConfig` format:

```yaml
# Scan settings
scan:
  packs_root: ~/.raxe/packs
  enable_l2: true
  use_production_l2: true
  l2_confidence_threshold: 0.5
  fail_fast_on_critical: false
  min_confidence_for_skip: 0.7
  enable_schema_validation: false
  schema_validation_mode: log_only
  api_key: null
  customer_id: null

# Policy settings
policy:
  block_on_critical: true
  block_on_high: false
  allow_on_low_confidence: true
  confidence_threshold: 0.7

# Performance settings
performance:
  mode: fail_open  # fail_open or fail_closed
  failure_threshold: 5
  reset_timeout_seconds: 30.0
  half_open_requests: 3
  sample_rate: 10
  latency_threshold_ms: 10.0

# Telemetry settings
telemetry:
  enabled: false
  api_key: null
  # endpoint: auto-detected (override with RAXE_TELEMETRY_ENDPOINT or raxe telemetry endpoint set)
  batch_size: 10
  flush_interval_seconds: 30.0
  max_queue_size: 1000
  async_send: true

# L2 scoring settings
l2_scoring:
  mode: balanced  # fast, balanced, or thorough
  custom_thresholds: null
  weights: null
  family_adjustments: null
  enable_consistency_check: true
  enable_margin_analysis: true
  enable_entropy: false
```

---

## Configuration Options

### Scan Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `packs_root` | string | `~/.raxe/packs` | Directory containing detection rule packs |
| `enable_l2` | boolean | `true` | Enable ML-based L2 detection |
| `use_production_l2` | boolean | `true` | Use optimized production model (int8) vs development model (fp16) |
| `l2_confidence_threshold` | float | `0.5` | Minimum confidence for L2 detections (0.0-1.0) |
| `fail_fast_on_critical` | boolean | `false` | Stop scanning immediately on CRITICAL threat |
| `min_confidence_for_skip` | float | `0.7` | Skip additional checks if L1 confidence exceeds this |
| `enable_schema_validation` | boolean | `false` | Validate rule schemas on load |
| `schema_validation_mode` | string | `log_only` | How to handle validation errors: `log_only`, `warn`, or `strict` |
| `api_key` | string | `null` | API key for cloud features (optional) |
| `customer_id` | string | `null` | Customer ID for enterprise features |

### Policy Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `block_on_critical` | boolean | `true` | Automatically block CRITICAL threats |
| `block_on_high` | boolean | `false` | Automatically block HIGH severity threats |
| `allow_on_low_confidence` | boolean | `true` | Allow requests even with low-confidence detections |
| `confidence_threshold` | float | `0.7` | Minimum confidence to enforce policy (0.0-1.0) |

### Performance Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mode` | string | `fail_open` | Circuit breaker mode: `fail_open` (allow on failure) or `fail_closed` (block on failure) |
| `failure_threshold` | int | `5` | Number of failures before opening circuit breaker |
| `reset_timeout_seconds` | float | `30.0` | Seconds before attempting to close circuit breaker |
| `half_open_requests` | int | `3` | Number of test requests in half-open state |
| `sample_rate` | int | `10` | Percentage of requests to profile (0-100) |
| `latency_threshold_ms` | float | `10.0` | Latency threshold for performance warnings (ms) |

### Telemetry Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` (CE default) | Enable privacy-preserving telemetry |
| `api_key` | string | `null` | Telemetry API key (optional) |
| `endpoint` | string | (auto-detected) | Telemetry endpoint URL (see [Endpoint Configuration](#endpoint-configuration)) |
| `batch_size` | int | `10` | Number of events to batch before sending |
| `flush_interval_seconds` | float | `30.0` | Maximum seconds before flushing batch |
| `max_queue_size` | int | `1000` | Maximum events to queue before dropping |
| `async_send` | boolean | `true` | Send telemetry asynchronously |

**Privacy Note:** RAXE CE telemetry sends detection metadata plus API key and prompt hash for client identification and uniqueness tracking. We NEVER send raw prompts, responses, matched text, or end-user identifiers. See [Privacy](#privacy--telemetry) section below.

### Endpoint Configuration

RAXE uses a centralized endpoint configuration system with environment-aware defaults. Endpoints are automatically selected based on your environment.

**Environment Detection Priority:**
1. `RAXE_ENV` environment variable
2. API key prefix (`raxe_live_` → production, `raxe_temp_` → development)
3. Default: `development`

**Available Environments:**

| Environment | API Base | Telemetry Endpoint |
|-------------|----------|-------------------|
| `production` | `https://api.raxe.ai` | `https://api.raxe.ai/v1/telemetry` |
| `development` | `https://api.raxe.ai` | `https://api.raxe.ai/v1/telemetry` |
| `local` | `http://localhost:8080` | `http://localhost:8080/v1/telemetry` |

**CLI Endpoint Commands:**

```bash
# Show current endpoint configuration
raxe telemetry endpoint show

# Switch to a different environment
raxe telemetry endpoint use development   # Use dev Cloud Run URLs
raxe telemetry endpoint use local         # Use localhost:8080
raxe telemetry endpoint use production    # Use production URLs

# Set a custom endpoint (full URL required)
raxe telemetry endpoint set https://your-server.com/v1/telemetry

# Reset to auto-detected default
raxe telemetry endpoint reset

# Test all endpoints are reachable
raxe telemetry endpoint test
```

**Environment Variable Override:**

```bash
# Override telemetry endpoint for session
export RAXE_TELEMETRY_ENDPOINT=https://your-server.com/v1/telemetry

# Set environment explicitly
export RAXE_ENV=development
```

**Source of Truth:** Endpoint defaults are defined in `src/raxe/infrastructure/config/endpoints.py`.

### L2 Scoring Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mode` | string | `balanced` | Detection mode: `fast`, `balanced`, or `thorough` |
| `custom_thresholds` | dict | `null` | Custom confidence thresholds per threat family |
| `weights` | dict | `null` | Custom weights for L1/L2 score combination |
| `family_adjustments` | dict | `null` | Per-family confidence adjustments |
| `enable_consistency_check` | boolean | `true` | Check L1/L2 agreement and flag inconsistencies |
| `enable_margin_analysis` | boolean | `true` | Analyze confidence margins for better accuracy |
| `enable_entropy` | boolean | `false` | Enable entropy-based obfuscation detection (experimental) |

---

## Environment Variables

All configuration options can be overridden with environment variables using the `RAXE_` prefix.

### Global Settings

```bash
# API and authentication
export RAXE_API_KEY=raxe_test_xxx
export RAXE_CUSTOMER_ID=customer_123

# Logging
export RAXE_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
export RAXE_LOG_DIR=~/.raxe/logs
export RAXE_NO_COLOR=true  # Disable colored output
export RAXE_VERBOSE=true   # Enable verbose output
export RAXE_QUIET=true     # Suppress all output except errors
```

### Scan Settings

```bash
export RAXE_PACKS_ROOT=~/.raxe/packs
export RAXE_ENABLE_L2=true
export RAXE_USE_PRODUCTION_L2=true
export RAXE_L2_CONFIDENCE_THRESHOLD=0.5
export RAXE_FAIL_FAST_ON_CRITICAL=false
export RAXE_MIN_CONFIDENCE_FOR_SKIP=0.7
export RAXE_ENABLE_SCHEMA_VALIDATION=false
export RAXE_SCHEMA_VALIDATION_MODE=log_only
```

### Policy Settings

```bash
export RAXE_BLOCK_ON_CRITICAL=true
export RAXE_BLOCK_ON_HIGH=false
export RAXE_ALLOW_ON_LOW_CONFIDENCE=true
export RAXE_CONFIDENCE_THRESHOLD=0.7
```

### Performance Settings

```bash
export RAXE_PERFORMANCE_MODE=fail_open  # fail_open or fail_closed
export RAXE_FAILURE_THRESHOLD=5
export RAXE_RESET_TIMEOUT_SECONDS=30.0
```

### Telemetry Settings

```bash
export RAXE_TELEMETRY_ENABLED=true
# Endpoint is auto-detected by default. Override with:
export RAXE_TELEMETRY_ENDPOINT=https://your-server.com/v1/telemetry
# Or set environment to use predefined endpoints:
export RAXE_ENV=development  # production, staging, development, test, local
export RAXE_TELEMETRY_BATCH_SIZE=10
export RAXE_TELEMETRY_FLUSH_INTERVAL_SECONDS=30.0
export RAXE_TELEMETRY_MAX_QUEUE_SIZE=1000
export RAXE_TELEMETRY_ASYNC_SEND=true
```

---

## CLI Configuration Commands

### View Configuration

```bash
# Display current configuration
raxe config show

# Validate configuration file
raxe config validate
```

### Modify Configuration

```bash
# Set a configuration value
raxe config set telemetry.enabled false
raxe config set performance.mode fast
raxe config set scan.enable_l2 true

# Reset to defaults
raxe config reset

# Edit configuration file directly
raxe config edit
```

**Note:** Not all config options are exposed via `raxe config set`. For advanced settings, edit the config file directly with `raxe config edit` or manually edit `~/.raxe/config.yaml`.

---

## Programmatic Configuration

### Python SDK

#### Basic Configuration

```python
from raxe import Raxe

# Use defaults (reads from ~/.raxe/config.yaml and env vars)
raxe = Raxe()

# Explicit configuration (highest priority)
raxe = Raxe(
    api_key="raxe_test_xxx",
    telemetry=False,
    l2_enabled=True,
)

# From custom config file
from pathlib import Path
raxe = Raxe.from_config_file(Path("./custom-config.yaml"))
```

#### Scan-Level Configuration

```python
# Override settings per scan
result = raxe.scan(
    text="Ignore all previous instructions",
    l1_enabled=True,
    l2_enabled=True,
    mode="balanced",  # fast, balanced, or thorough
    confidence_threshold=0.5,
    explain=False,  # Include explanations in result
    dry_run=False,  # Don't send telemetry
    block_on_threat=False  # Raise exception on threat
)
```

#### Advanced Configuration

```python
from pathlib import Path
from raxe import Raxe
from raxe.infrastructure.config.scan_config import ScanConfig
from raxe.domain.policies import Policy, PolicyAction, PolicyCondition, Severity

# Build custom scan config
config = ScanConfig(
    packs_root=Path.home() / ".raxe" / "packs",
    enable_l2=True,
    use_production_l2=True,
    l2_confidence_threshold=0.5,
)

# Use custom config
raxe = Raxe(config=config)

# Define custom policies using new policy system
block_critical_policy = Policy(
    name="block_critical",
    conditions=[PolicyCondition(severity=Severity.CRITICAL, min_confidence=0.7)],
    action=PolicyAction.BLOCK
)

# Apply policy to scan results
result = raxe.scan("Your text here")
action = block_critical_policy.evaluate(result.detections)
```

---

## Common Configuration Scenarios

### 1. Maximum Security (Zero False Negatives)

```yaml
scan:
  enable_l2: true
  use_production_l2: true
  l2_confidence_threshold: 0.3  # Lower threshold = more detections
  fail_fast_on_critical: true

policy:
  block_on_critical: true
  block_on_high: true
  confidence_threshold: 0.5  # Block even moderate confidence

l2_scoring:
  mode: thorough  # Most comprehensive detection

performance:
  mode: fail_closed  # Block on any error
```

**Trade-offs:** Higher false positive rate, slower performance (~2-3x latency)

### 2. Maximum Performance (Minimal Latency)

```yaml
scan:
  enable_l2: false  # L1 only (regex-based)
  fail_fast_on_critical: true
  min_confidence_for_skip: 0.5  # Skip early if confident

l2_scoring:
  mode: fast

performance:
  mode: fail_open  # Don't block on errors
  latency_threshold_ms: 5.0
```

**Trade-offs:** May miss sophisticated attacks, no ML-based detection

### 3. Balanced Production (Recommended)

```yaml
scan:
  enable_l2: true
  use_production_l2: true
  l2_confidence_threshold: 0.5

policy:
  block_on_critical: true
  block_on_high: false
  confidence_threshold: 0.7

l2_scoring:
  mode: balanced
  enable_consistency_check: true
  enable_margin_analysis: true

performance:
  mode: fail_open
  latency_threshold_ms: 10.0

telemetry:
  enabled: true  # Help improve detection
  async_send: true
```

**Trade-offs:** Balanced security/performance, <10ms P95 latency

### 4. Privacy-First (Zero Telemetry)

```yaml
telemetry:
  enabled: false

scan:
  api_key: null
  customer_id: null

# Everything else runs 100% locally
```

### 5. Development/Testing

```yaml
scan:
  enable_l2: true
  use_production_l2: false  # Use fp16 model for better explainability
  enable_schema_validation: true
  schema_validation_mode: strict

l2_scoring:
  mode: thorough
  enable_consistency_check: true
  enable_margin_analysis: true
  enable_entropy: true  # Experimental features

performance:
  mode: fail_closed  # Catch all errors during dev
  sample_rate: 100  # Profile all requests
```

---

## Privacy & Telemetry

### What We Collect (CE Default: Enabled)

RAXE CE ships with telemetry **enabled by default** to help improve community detection quality. We have **zero tolerance for identifiable end-user data**.

**What we SEND:**
```json
{
  "api_key": "raxe_...",              // Client identification for service access
  "prompt_hash": "sha256:abc123...",  // SHA-256 for uniqueness (hard to reverse)
  "rule_id": "pi-001",                // Rule that triggered
  "severity": "HIGH",                 // Severity level
  "confidence": 0.95,                 // Confidence score
  "detection_count": 3,               // Number of detections
  "l1_hit": true,                     // L1 detection triggered
  "l2_hit": false,                    // L2 (ML) detection triggered
  "scan_duration_ms": 4.2,            // Total scan time
  "l1_duration_ms": 1.1,              // L1 processing time
  "l2_duration_ms": 3.1,              // L2 processing time
  "timestamp": "2025-01-23T10:30:00Z",// When
  "version": "0.0.1",                 // RAXE version
  "platform": "darwin"                // Platform
}
```

**What we NEVER send:**
- ❌ Raw prompts or responses (never transmitted)
- ❌ Matched text or snippets (never transmitted)
- ❌ End-user identifiers (your customers' user_id, session_id)
- ❌ IP addresses or geolocation
- ❌ Rule patterns or detection logic
- ❌ System prompts or configuration

### Disable Telemetry

> **Note:** Disabling telemetry requires **Pro tier or higher**. Community Edition (free) users help improve detection by contributing anonymized metadata. [Upgrade to Pro](https://raxe.ai/pricing) to disable telemetry.

**CLI (Pro+ only):**
```bash
raxe telemetry disable
# or
raxe config set telemetry.enabled false
```

**Environment variable (Pro+ only):**
```bash
export RAXE_TELEMETRY_ENABLED=false
```

**Python SDK (Pro+ only):**
```python
raxe = Raxe(telemetry=False)
```

**Config file (Pro+ only):**
```yaml
telemetry:
  enabled: false
```

### Verify What's Sent

You can audit exactly what telemetry is sent:

```bash
# Check telemetry status and queue depth
raxe telemetry status

# View pending events in queue
raxe telemetry dlq list

# Force immediate delivery of queued events
raxe telemetry flush

# Check system health
raxe doctor
```

All telemetry code is available at `src/raxe/infrastructure/telemetry/` and `src/raxe/domain/telemetry/` - audit it yourself!

---

## Troubleshooting

### Configuration Not Loading

```bash
# Check which config file is being used
raxe config show

# Validate config syntax
raxe config validate

# Check for environment variable overrides
env | grep RAXE_
```

### Performance Issues

```bash
# Profile scan performance
raxe profile "your text"

# Disable L2 for faster scans
export RAXE_ENABLE_L2=false

# Use fast mode
export RAXE_L2_SCORING_MODE=fast
```

### False Positives

```yaml
# Increase confidence threshold
policy:
  confidence_threshold: 0.8  # More conservative

# Disable specific threat families
# (currently not supported - file feature request)
```

### Config File Syntax Errors

```bash
# Validate YAML syntax
raxe config validate

# Reset to defaults
raxe config reset

# Manually check YAML
python -c "import yaml; yaml.safe_load(open('~/.raxe/config.yaml'))"
```

---

## Migration Guide

### From v0.0.x to v0.1.0

The configuration format changed significantly in v0.1.0. To migrate:

1. **Backup old config:**
   ```bash
   cp ~/.raxe/config.yaml ~/.raxe/config.yaml.backup
   ```

2. **Initialize new config:**
   ```bash
   raxe init
   ```

3. **Manually migrate settings:**
   - Old `detection.l2_enabled` → New `scan.enable_l2`
   - Old `detection.mode` → New `l2_scoring.mode`
   - Old `core.api_key` → New `scan.api_key`

4. **Validate:**
   ```bash
   raxe config validate
   raxe doctor
   ```

---

## Related Documentation

- [Getting Started](getting-started.md) - Quick start guide
- [Architecture](architecture.md) - System design and components
- [Custom Rules](CUSTOM_RULES.md) - Writing detection rules
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [API Reference](api_reference.md) - Python SDK documentation

---

## Questions?

- 📖 [Documentation](https://docs.raxe.ai)
- 💬 [GitHub Discussions](https://github.com/raxe-ai/raxe-ce/discussions)
- 🐛 [Report Issues](https://github.com/raxe-ai/raxe-ce/issues)
- 📧 [Email](mailto:community@raxe.ai)
