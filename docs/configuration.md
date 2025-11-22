# RAXE Configuration Guide

This guide covers all configuration options for RAXE Community Edition.

## Quick Start

### Initialize Configuration

```bash
raxe init
```

This creates `~/.raxe/config.yaml` with sensible defaults.

### Configuration Locations

RAXE looks for configuration in this order:

1. `./raxe/config.yaml` (project-specific)
2. `~/.raxe/config.yaml` (user-level)
3. Environment variables (overrides)
4. Built-in defaults

## Basic Configuration

### Minimal Configuration

```yaml
# ~/.raxe/config.yaml
scan:
  enable_l2: true      # Enable ML detection

policy:
  block_on_critical: true  # Block critical threats

telemetry:
  enabled: false       # Privacy-first: disabled by default
```

### Recommended Configuration

```yaml
scan:
  packs_root: ~/.raxe/packs
  enable_l2: true
  use_production_l2: true
  l2_confidence_threshold: 0.5

l2_scoring:
  mode: balanced       # Balanced security/FP trade-off

policy:
  block_on_critical: true
  block_on_high: false
  confidence_threshold: 0.7

performance:
  mode: fail_open      # Continue on errors
  latency_threshold_ms: 10.0

telemetry:
  enabled: false       # Disable for privacy
```

## Configuration Sections

### 1. Scan Configuration

Controls detection behavior:

```yaml
scan:
  # Rule packs location
  packs_root: ~/.raxe/packs

  # L2 ML Detection
  enable_l2: true                    # Enable/disable ML detection
  use_production_l2: true            # Use production ML model
  l2_confidence_threshold: 0.5       # Min confidence to flag (0.0-1.0)

  # Performance
  fail_fast_on_critical: false       # Stop scanning on first critical
  min_confidence_for_skip: 0.7       # Skip low-confidence detections
```

**Options Explained:**

- `packs_root`: Directory containing detection rule packs
- `enable_l2`: Toggle ML-based (L2) detection
- `use_production_l2`: Use production model vs. development model
- `l2_confidence_threshold`: Minimum ML confidence to flag as threat (0.0-1.0)
- `fail_fast_on_critical`: Stop scanning after first CRITICAL detection (faster)
- `min_confidence_for_skip`: Ignore detections below this confidence

### 2. L2 Scoring Configuration

Advanced ML detection scoring with hierarchical threat analysis:

#### Simple Mode (Recommended)

```yaml
l2_scoring:
  mode: balanced  # Options: high_security, balanced, low_fp
```

**Modes Explained:**

| Mode | Use Case | FP Rate | FN Rate | Recommended For |
|------|----------|---------|---------|-----------------|
| `high_security` | Financial, Healthcare | Higher | Lower | Maximum protection |
| `balanced` | General purpose | Medium | Medium | Most applications |
| `low_fp` | Customer support | Lower | Higher | Minimize false alarms |

#### Advanced Mode

```yaml
l2_scoring:
  mode: balanced

  # Signal quality checks
  enable_consistency_check: true   # Check confidence variance
  enable_margin_analysis: true     # Analyze probability margins
  enable_entropy: false             # Uncertainty estimation (future)
```

**Signal Quality Checks:**

- `consistency_check`: Ensures L2 confidence levels are consistent (reduces FPs)
- `margin_analysis`: Analyzes probability distribution margins (improves accuracy)
- `entropy`: Future feature for uncertainty estimation

#### Expert Mode (Custom Thresholds)

```yaml
l2_scoring:
  mode: balanced

  custom_thresholds:
    safe: 0.5                     # Below this = SAFE
    fp_likely: 0.55               # Low score = likely false positive
    review: 0.70                  # Inconsistent signals = needs review
    threat: 0.85                  # Confident threat = block
    high_threat: 0.95             # Very confident = block + alert
    inconsistency_threshold: 0.05 # Max variance for consistent signals
    weak_family: 0.4              # Weak family confidence threshold
    weak_subfamily: 0.3           # Weak subfamily confidence threshold
```

**Threshold Ranges:**

- **0.0 - 0.5**: Safe (no threat)
- **0.5 - 0.7**: Uncertain (review recommended)
- **0.7 - 0.85**: Likely threat
- **0.85 - 0.95**: Confident threat (block)
- **0.95 - 1.0**: Very confident (block + alert)

#### Custom Weights

```yaml
l2_scoring:
  weights:
    binary: 0.60      # Binary is_attack classifier (most reliable)
    family: 0.25      # Attack family classifier
    subfamily: 0.15   # Attack subfamily classifier
```

**Note**: Weights must sum to 1.0

#### Per-Family Adjustments

```yaml
l2_scoring:
  family_adjustments:
    PI:   # Prompt Injection
      threat: 0.80  # Lower threshold (more sensitive)
    JB:   # Jailbreak
      threat: 0.85
    HC:   # Harmful Content (often has FPs)
      fp_likely: 0.60  # Higher FP threshold (more lenient)
```

### 3. Policy Configuration

Controls blocking behavior:

```yaml
policy:
  # Blocking behavior
  block_on_critical: true      # Block CRITICAL severity threats
  block_on_high: false         # Don't block HIGH severity (log only)

  # Confidence thresholds
  allow_on_low_confidence: true  # Allow if confidence < threshold
  confidence_threshold: 0.7      # Min confidence to block (0.0-1.0)
```

**Blocking Matrix:**

| Severity | Confidence | `block_on_critical: true` | `block_on_high: true` |
|----------|------------|---------------------------|-----------------------|
| CRITICAL | > 0.7 | ✅ BLOCK | ✅ BLOCK |
| HIGH | > 0.7 | ❌ Allow | ✅ BLOCK |
| MEDIUM | > 0.7 | ❌ Allow | ❌ Allow |
| LOW | > 0.7 | ❌ Allow | ❌ Allow |
| Any | < 0.7 | ❌ Allow (if `allow_on_low_confidence: true`) | ❌ Allow |

### 4. Performance Configuration

Controls circuit breaker and fail-safe behavior:

```yaml
performance:
  mode: fail_open                   # Options: fail_open, fail_closed
  failure_threshold: 5              # Failures before circuit opens
  reset_timeout_seconds: 30.0       # Timeout before retry
  half_open_requests: 3             # Test requests in half-open state
  sample_rate: 10                   # Performance sampling rate (%)
  latency_threshold_ms: 10.0        # Max acceptable latency (ms)
```

**Circuit Breaker States:**

1. **CLOSED** (Normal): All requests scanned
2. **OPEN** (Failing): Skip scanning after `failure_threshold` failures
3. **HALF_OPEN** (Testing): Try `half_open_requests` to test recovery

**Modes:**

- `fail_open`: Allow traffic through if RAXE fails (prioritize availability)
- `fail_closed`: Block traffic if RAXE fails (prioritize security)

**Performance Monitoring:**

- `sample_rate`: Percentage of requests to measure latency (1-100)
- `latency_threshold_ms`: Trigger warning if latency exceeds this

### 5. Telemetry Configuration

Optional privacy-preserving telemetry:

```yaml
telemetry:
  enabled: false                          # Disabled by default
  api_key: your-api-key-here              # Optional API key
  endpoint: https://telemetry.raxe.ai/v1/events
  batch_size: 10                          # Events per batch
  flush_interval_seconds: 30.0            # Max seconds between flushes
  max_queue_size: 1000                    # Max events in queue
  async_send: true                        # Send asynchronously
```

**Privacy Guarantees:**

When telemetry is enabled, RAXE sends:
- ✅ SHA-256 hash of prompt (irreversible)
- ✅ Rule IDs that matched
- ✅ Severity and confidence scores
- ✅ Anonymous usage metrics

RAXE NEVER sends:
- ❌ Raw prompt text
- ❌ LLM responses
- ❌ User PII
- ❌ API keys

**Verify Telemetry Behavior:**

```bash
raxe doctor --telemetry
```

## Environment Variables

Override any configuration value with environment variables:

```bash
# General settings
export RAXE_CONFIG_PATH=~/.raxe/config.yaml
export RAXE_LOG_LEVEL=DEBUG

# Scan settings
export RAXE_SCAN_ENABLE_L2=true
export RAXE_SCAN_L2_CONFIDENCE_THRESHOLD=0.5

# Policy settings
export RAXE_POLICY_BLOCK_ON_CRITICAL=true
export RAXE_POLICY_BLOCK_ON_HIGH=false

# Telemetry settings
export RAXE_TELEMETRY_ENABLED=false
export RAXE_TELEMETRY_API_KEY=your-key-here

# Performance settings
export RAXE_PERFORMANCE_MODE=fail_open
export RAXE_PERFORMANCE_LATENCY_THRESHOLD_MS=10.0
```

**Environment Variable Format:**

`RAXE_<SECTION>_<KEY>=<VALUE>`

Example: `telemetry.enabled` → `RAXE_TELEMETRY_ENABLED`

## Programmatic Configuration

Configure RAXE in code:

```python
from raxe import Raxe

# Basic configuration
raxe = Raxe(
    telemetry=False,
    l2_enabled=True,
    block_on_threat=True,
    log_level="INFO"
)

# Advanced configuration
from raxe.infrastructure.config import ScanConfig, PolicyConfig

scan_config = ScanConfig(
    enable_l2=True,
    l2_confidence_threshold=0.5,
    fail_fast_on_critical=False
)

policy_config = PolicyConfig(
    block_on_critical=True,
    block_on_high=False,
    confidence_threshold=0.7
)

raxe = Raxe(
    scan_config=scan_config,
    policy_config=policy_config
)
```

## Use Case Configurations

### 1. High Security (Financial, Healthcare)

```yaml
scan:
  enable_l2: true
  l2_confidence_threshold: 0.4  # More sensitive

l2_scoring:
  mode: high_security
  enable_consistency_check: true
  enable_margin_analysis: true

policy:
  block_on_critical: true
  block_on_high: true          # Block HIGH severity too
  confidence_threshold: 0.6    # Lower threshold = more blocking

performance:
  mode: fail_closed            # Block on errors (security first)

telemetry:
  enabled: false               # Privacy-first
```

### 2. Balanced (Recommended for Most)

```yaml
scan:
  enable_l2: true
  l2_confidence_threshold: 0.5

l2_scoring:
  mode: balanced

policy:
  block_on_critical: true
  block_on_high: false
  confidence_threshold: 0.7

performance:
  mode: fail_open

telemetry:
  enabled: false
```

### 3. Low False Positive (Customer Support)

```yaml
scan:
  enable_l2: true
  l2_confidence_threshold: 0.6  # Less sensitive

l2_scoring:
  mode: low_fp
  custom_thresholds:
    fp_likely: 0.60
    threat: 0.90              # Higher threshold = less blocking

policy:
  block_on_critical: true
  block_on_high: false
  confidence_threshold: 0.8   # Higher = fewer blocks

performance:
  mode: fail_open

telemetry:
  enabled: false
```

### 4. Development/Testing

```yaml
scan:
  enable_l2: true
  use_production_l2: false    # Use dev model

l2_scoring:
  mode: balanced

policy:
  block_on_critical: false    # Log only, don't block
  block_on_high: false

performance:
  mode: fail_open
  sample_rate: 100            # Monitor all requests

telemetry:
  enabled: true               # Optional: send to dev endpoint
  endpoint: http://localhost:8080/telemetry
```

## Configuration Validation

### Validate Configuration

```bash
raxe validate-config ~/.raxe/config.yaml
```

Output:

```
✓ Configuration is valid
✓ All required fields present
✓ All values within valid ranges
✓ Weights sum to 1.0
```

### Common Validation Errors

**Error**: `Weights do not sum to 1.0`

```yaml
# ❌ Bad
l2_scoring:
  weights:
    binary: 0.50
    family: 0.30
    subfamily: 0.15  # Sum = 0.95

# ✅ Good
l2_scoring:
  weights:
    binary: 0.60
    family: 0.25
    subfamily: 0.15  # Sum = 1.0
```

**Error**: `Invalid threshold range`

```yaml
# ❌ Bad
l2_scoring:
  custom_thresholds:
    safe: 1.5  # > 1.0

# ✅ Good
l2_scoring:
  custom_thresholds:
    safe: 0.5  # 0.0 - 1.0
```

## Performance Tuning

### Optimize for Speed

```yaml
scan:
  enable_l2: false             # Skip ML (faster)
  fail_fast_on_critical: true  # Stop on first critical
  min_confidence_for_skip: 0.8 # Skip low confidence

performance:
  latency_threshold_ms: 5.0    # Strict latency requirement
```

**Expected Latency**:
- L1 only: < 1ms (P95)
- L1 + L2: < 10ms (P95)

### Optimize for Accuracy

```yaml
scan:
  enable_l2: true
  l2_confidence_threshold: 0.4  # More sensitive
  fail_fast_on_critical: false  # Scan everything

l2_scoring:
  mode: high_security
  enable_consistency_check: true
  enable_margin_analysis: true
```

### Optimize for Low False Positives

```yaml
scan:
  l2_confidence_threshold: 0.6

l2_scoring:
  mode: low_fp
  custom_thresholds:
    fp_likely: 0.60
    threat: 0.90
```

## Troubleshooting

### Issue: Configuration Not Loading

**Check configuration file exists:**

```bash
ls -la ~/.raxe/config.yaml
```

**Check configuration is valid YAML:**

```bash
raxe validate-config ~/.raxe/config.yaml
```

**Check environment variables:**

```bash
env | grep RAXE_
```

### Issue: Performance Degradation

**Check current settings:**

```bash
raxe doctor
```

**Reduce latency:**

```yaml
scan:
  enable_l2: false  # Disable ML temporarily
```

**Check circuit breaker state:**

```bash
raxe stats --performance
```

### Issue: Too Many False Positives

**Adjust scoring mode:**

```yaml
l2_scoring:
  mode: low_fp  # More lenient
```

**Raise thresholds:**

```yaml
l2_scoring:
  custom_thresholds:
    threat: 0.90  # Higher = fewer blocks
```

### Issue: Missing Threats

**Adjust scoring mode:**

```yaml
l2_scoring:
  mode: high_security  # More aggressive
```

**Lower thresholds:**

```yaml
scan:
  l2_confidence_threshold: 0.4  # More sensitive
```

## Advanced Topics

### Custom Rule Packs

```yaml
scan:
  packs_root: ~/.raxe/packs
  additional_packs:
    - ~/my-custom-rules/
    - /opt/corporate-rules/
```

### Multiple Environments

**Development:**
```bash
export RAXE_CONFIG_PATH=./config/dev.yaml
```

**Staging:**
```bash
export RAXE_CONFIG_PATH=./config/staging.yaml
```

**Production:**
```bash
export RAXE_CONFIG_PATH=./config/prod.yaml
```

### Configuration Inheritance

```yaml
# config/base.yaml
scan:
  enable_l2: true

---
# config/prod.yaml (inherits from base)
_extends: ./base.yaml

policy:
  block_on_critical: true
```

## Next Steps

- [API Reference](api-reference.md) - Programmatic configuration
- [Performance Tuning](PERFORMANCE_TUNING.md) - Optimization guide
- [Troubleshooting](troubleshooting.md) - Common issues

## Reference

### Complete Configuration Example

See [examples/config-with-scoring.yaml](../examples/config-with-scoring.yaml) for a fully documented example.

### Configuration Schema

See [schemas/config.schema.json](../schemas/config.schema.json) for the JSON schema definition.

---

**Questions?** See [Troubleshooting](troubleshooting.md) or ask in [GitHub Discussions](https://github.com/raxe-ai/raxe-ce/discussions).
