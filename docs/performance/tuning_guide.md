# RAXE Performance Tuning Guide

## Overview

This guide helps you optimize RAXE CE performance for your specific use case. RAXE is designed to achieve **P95 scan latency < 10ms** while maintaining high detection accuracy. This document covers configuration options, optimization techniques, and best practices.

## Table of Contents

1. [Performance Targets](#performance-targets)
2. [Quick Wins](#quick-wins)
3. [Configuration Options](#configuration-options)
4. [Layer-Specific Tuning](#layer-specific-tuning)
5. [Hardware Recommendations](#hardware-recommendations)
6. [Monitoring Performance](#monitoring-performance)
7. [Advanced Optimization](#advanced-optimization)
8. [Troubleshooting](#troubleshooting)

---

## Performance Targets

### Default Performance Goals

RAXE is designed to meet these latency targets:

| Metric | Target | Acceptable | Needs Optimization |
|--------|--------|------------|-------------------|
| P50 Latency | < 5ms | 5-10ms | > 10ms |
| P95 Latency | < 10ms | 10-25ms | > 25ms |
| P99 Latency | < 25ms | 25-50ms | > 50ms |
| Throughput | > 1000 scans/sec | 500-1000 | < 500 |

### Component Breakdown

Typical latency distribution:

- **L1 (Rule-based)**: 3-7ms (60-70% of total time)
- **L2 (ML-based)**: 0.5-2ms (10-20% of total time)
- **Overhead**: 1-3ms (10-20% of total time - merging, policy, telemetry)

If your profile differs significantly, use the profiling tools to identify bottlenecks.

---

## Quick Wins

### 1. Enable Fail-Fast on Critical

Skip L2 analysis when CRITICAL threats are detected by L1:

```yaml
# config.yaml
performance:
  fail_fast_on_critical: true  # Skip L2 if CRITICAL detected
```

**Impact**: 20-30% faster on prompts with critical threats
**Trade-off**: None (CRITICAL is already highest severity)

### 2. Adjust Performance Mode

Choose the right balance for your needs:

```yaml
performance:
  mode: fast        # Fastest (fewer rules)
  # mode: balanced  # Default (good balance)
  # mode: accurate  # Most thorough (all rules)
```

**Impact**:
- `fast`: 30-40% faster, 85-90% detection rate
- `balanced`: Baseline, ~95% detection rate
- `accurate`: 20-30% slower, ~98% detection rate

### 3. Disable Unused Features

Turn off features you don't need:

```yaml
telemetry:
  enabled: false  # Disable telemetry

performance:
  l2_enabled: false  # Disable ML layer (L1 only)

schema_validation:
  enabled: false  # Disable runtime validation
```

**Impact**: 10-15% faster per disabled feature

### 4. Use Rule Pack Precedence

Only load rule packs you need:

```yaml
packs:
  precedence:
    - custom     # Your custom rules (fastest)
    # - community  # Community rules (disable if not needed)
    - core       # Core rules (essential)
```

**Impact**: 5-10% faster per disabled pack category

---

## Configuration Options

### Complete Performance Configuration

```yaml
# .raxe/config.yaml

# Performance tuning
performance:
  # Overall mode (fast|balanced|accurate)
  mode: balanced

  # L2 ML detection
  l2_enabled: true

  # Skip L2 if CRITICAL already detected
  fail_fast_on_critical: true

  # Maximum acceptable latency (ms)
  # If exceeded, enter degraded mode
  max_latency_ms: 10

  # Circuit breaker settings
  circuit_breaker:
    failure_threshold: 5
    reset_timeout_sec: 30

# Rule pack configuration
packs:
  # Pack loading precedence
  precedence:
    - custom
    - community
    - core

  # Cache compiled rules (recommended)
  cache_compiled: true

  # Cache TTL (seconds)
  cache_ttl: 3600

# Telemetry (adds overhead)
telemetry:
  enabled: true

  # Batch size (larger = less frequent sends)
  batch_size: 100

  # Send interval (seconds)
  send_interval: 60

# Schema validation (development only)
schema_validation:
  enabled: false  # Disable in production
  mode: log_only  # log_only|warn|enforce
```

---

## Layer-Specific Tuning

### L1 (Rule-Based Detection)

L1 typically accounts for 60-70% of scan time. Optimization strategies:

#### 1. Optimize Regular Expressions

Inefficient regex patterns are the #1 cause of slow L1 performance.

**Bad** (causes backtracking):
```yaml
# Slow - catastrophic backtracking
pattern: "(.*)*@(.*)*.com"
```

**Good** (explicit, bounded):
```yaml
# Fast - explicit matching
pattern: "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.com"
```

**Tips**:
- Avoid nested quantifiers (`(.*)*(.*)+`)
- Use character classes instead of `.` when possible
- Anchor patterns (`^`, `$`) when appropriate
- Use atomic groups for complex patterns
- Test patterns at [regex101.com](https://regex101.com)

#### 2. Rule Ordering

Rules are evaluated in precedence order. Put most common/critical rules first:

```yaml
# Good: Common patterns first
rules:
  - id: pi-001
    category: PI
    severity: CRITICAL
    enabled: true

  - id: prompt-injection-001
    category: prompt-injection
    severity: HIGH
    enabled: true

  # Less common patterns last
  - id: rare-pattern-123
    enabled: false  # Disable if rarely matched
```

#### 3. Disable Unused Rules

Only enable rules you need:

```python
from raxe.sdk import Raxe

raxe = Raxe(
    enabled_categories=["PI", "prompt-injection"],  # Only these categories
    disabled_rules=["rare-001", "rare-002"],        # Exclude specific rules
)
```

**Impact**: 5-10% faster per disabled category

### L2 (ML-Based Detection)

L2 typically accounts for 10-20% of scan time. Optimization strategies:

#### 1. Disable L2 When Not Needed

If L1 rules are sufficient for your use case:

```yaml
performance:
  l2_enabled: false
```

**Impact**: 10-20% faster
**Trade-off**: No ML-based detection (lower recall on novel attacks)

#### 2. Use Fail-Fast Mode

Skip L2 when CRITICAL threats already detected:

```yaml
performance:
  fail_fast_on_critical: true
```

**Impact**: 20-30% faster on malicious prompts

#### 3. L2 Model Selection

Choose the right model for your latency budget:

```python
from raxe.sdk import Raxe

raxe = Raxe(
    l2_model="fast",      # Fastest (0.5-1ms)
    # l2_model="balanced",  # Default (1-2ms)
    # l2_model="accurate",  # Slowest but best (2-5ms)
)
```

---

## Hardware Recommendations

### Minimum Requirements

- **CPU**: 2 cores, 2.0 GHz
- **RAM**: 512 MB available
- **Storage**: 100 MB for rules and cache

**Performance**: 200-500 scans/sec

### Recommended Configuration

- **CPU**: 4+ cores, 2.5+ GHz
- **RAM**: 1-2 GB available
- **Storage**: SSD preferred for cache

**Performance**: 1000-2000 scans/sec

### High-Performance Setup

- **CPU**: 8+ cores, 3.0+ GHz
- **RAM**: 4+ GB available
- **Storage**: NVMe SSD for cache
- **Network**: Low latency to RAXE cloud API (if telemetry enabled)

**Performance**: 5000+ scans/sec

### Cloud Deployment

#### AWS Recommendations

- **Compute**: c7g.xlarge or better (ARM64 Graviton)
- **Storage**: gp3 EBS volume
- **Networking**: Enhanced networking enabled

#### GCP Recommendations

- **Compute**: c2-standard-4 or n2-standard-4
- **Storage**: SSD persistent disk
- **Networking**: Premium tier

#### Azure Recommendations

- **Compute**: F4s v2 or better
- **Storage**: Premium SSD
- **Networking**: Accelerated networking

---

## Monitoring Performance

### Using Built-in Profiling

```bash
# Profile a single scan
raxe profile "test prompt" --iterations 100

# Save profile for visualization
raxe profile "test" -o scan.prof
snakeviz scan.prof

# Benchmark throughput
raxe benchmark -f prompts.txt -n 1000
```

### Prometheus Metrics

```bash
# Start metrics server
raxe metrics-server --port 9090

# View metrics
curl http://localhost:9090/metrics
```

**Key metrics to monitor**:

- `raxe_scan_duration_seconds{layer="regex"}` - L1 latency
- `raxe_scan_duration_seconds{layer="ml"}` - L2 latency
- `raxe_scans_total` - Scan count by severity/action
- `raxe_detections_total` - Detection count by rule
- `raxe_rule_execution_duration_seconds` - Per-rule latency

### Application-Level Monitoring

```python
from raxe.sdk import Raxe

raxe = Raxe()

# Scan and check performance
result = raxe.scan("test prompt")

print(f"Scan time: {result.duration_ms:.2f}ms")
print(f"L1 time: {result.scan_result.metadata['l1_duration_ms']:.2f}ms")
print(f"L2 time: {result.scan_result.metadata['l2_duration_ms']:.2f}ms")

# Check statistics
stats = raxe.stats
print(f"Average scan time: {stats['average_scan_time_ms']:.2f}ms")
```

### Grafana Dashboards

See [monitoring setup guide](../examples/monitoring_setup.md) for Grafana dashboard configuration.

---

## Advanced Optimization

### 1. Rule Compilation Caching

Pre-compile rules on startup:

```python
from raxe.sdk import Raxe

raxe = Raxe(
    preload_rules=True,     # Compile rules at init (slower startup, faster scans)
    cache_compiled=True,    # Cache compiled patterns
)
```

**Impact**:
- Startup: +50-100ms
- Scan time: -10-15%

### 2. Batch Scanning

Scan multiple prompts together:

```python
prompts = ["prompt 1", "prompt 2", "prompt 3"]

# Bad: Individual scans
for prompt in prompts:
    result = raxe.scan(prompt)

# Good: Batch scan (amortizes overhead)
results = raxe.scan_batch(prompts)
```

**Impact**: 20-30% faster for batches > 10 prompts

### 3. Async Scanning (Future)

Use async for I/O-bound operations:

```python
import asyncio
from raxe.sdk.async_client import AsyncRaxe

async def scan_many():
    async with AsyncRaxe() as raxe:
        tasks = [raxe.scan(p) for p in prompts]
        results = await asyncio.gather(*tasks)
    return results

# Coming in future release
```

### 4. Custom Rule Filters

Filter rules based on context:

```python
from raxe.sdk import Raxe

def should_apply_rule(rule, context):
    """Only apply relevant rules based on context."""
    if context.get("user_type") == "admin":
        # Skip certain rules for admins
        return rule.id not in ["rate-limit-001"]
    return True

raxe = Raxe(rule_filter=should_apply_rule)
```

### 5. Resource Limits

Set resource limits to prevent runaway scans:

```yaml
performance:
  # Maximum text length to scan (bytes)
  max_input_length: 100000

  # Maximum rule execution time (ms)
  max_rule_execution_ms: 100

  # Maximum total scan time (ms)
  max_scan_duration_ms: 50
```

---

## Troubleshooting

### Symptom: High L1 Latency

**Diagnosis**:
```bash
raxe profile "slow prompt" --iterations 100
```

Look for slow rules in the output.

**Solutions**:
1. Optimize regex patterns (avoid backtracking)
2. Disable rarely-matching rules
3. Reduce enabled rule categories
4. Use `performance.mode: fast`

### Symptom: High L2 Latency

**Solutions**:
1. Use lighter L2 model: `l2_model: fast`
2. Enable fail-fast: `fail_fast_on_critical: true`
3. Disable L2: `l2_enabled: false`

### Symptom: Variable Latency (Spikes)

**Diagnosis**:
```bash
# Check P95 and P99 latency
raxe benchmark -f prompts.txt --iterations 1000
```

**Solutions**:
1. Enable rule caching: `cache_compiled: true`
2. Warm up rules on startup: `preload_rules: true`
3. Check for GC pauses (Python GC tuning)
4. Use batch scanning to amortize overhead

### Symptom: Low Throughput

**Diagnosis**:
```bash
# Benchmark throughput
raxe benchmark -p "test" --iterations 10000
```

**Solutions**:
1. Disable telemetry: `telemetry.enabled: false`
2. Disable schema validation: `schema_validation.enabled: false`
3. Use performance mode: `performance.mode: fast`
4. Check CPU/memory availability
5. Profile for bottlenecks

### Symptom: Memory Growth

**Diagnosis**:
```bash
# Profile memory
raxe profile "test" --memory --iterations 1000
```

**Solutions**:
1. Reduce cache TTL: `packs.cache_ttl: 1800`
2. Limit telemetry queue: `telemetry.max_queue_size: 1000`
3. Disable rule caching if memory constrained
4. Check for rule compilation leaks

---

## Performance Checklist

Before deploying to production, verify:

- [ ] Profiled with representative workload
- [ ] P95 latency < 10ms
- [ ] Throughput meets requirements
- [ ] Prometheus metrics configured
- [ ] Alerts set up for performance degradation
- [ ] Rule pack optimized (disabled unused categories)
- [ ] Fail-fast enabled for CRITICAL threats
- [ ] Telemetry batch size tuned
- [ ] Schema validation disabled in production
- [ ] Resource limits configured
- [ ] Monitoring dashboards set up

---

## Best Practices Summary

1. **Start with defaults** - RAXE is optimized for most use cases
2. **Measure before optimizing** - Use profiling tools to identify real bottlenecks
3. **Optimize rules first** - L1 regex is usually the bottleneck
4. **Enable fail-fast** - Skip L2 when CRITICAL already detected
5. **Batch when possible** - Amortize overhead across multiple scans
6. **Monitor continuously** - Set up Prometheus + Grafana
7. **Test under load** - Benchmark with realistic workloads
8. **Tune incrementally** - Change one setting at a time

---

## Additional Resources

- [Benchmarking Guide](./benchmarking.md) - How to run performance benchmarks
- [Monitoring Setup](../examples/monitoring_setup.md) - Prometheus + Grafana setup
- [Architecture Docs](../architecture.md) - Understanding RAXE internals
- [API Reference](../api_reference.md) - SDK configuration options

For performance-related issues, check our [GitHub Discussions](https://github.com/raxe-ai/raxe-ce/discussions) or contact support.

---

**Last Updated**: 2025-11-15
**Version**: 1.0.0
