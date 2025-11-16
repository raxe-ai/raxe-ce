# RAXE Performance Tuning Guide

This guide helps you optimize RAXE for your specific latency, throughput, and accuracy requirements.

## Table of Contents

1. [Performance Targets](#performance-targets)
2. [Layer Control](#layer-control)
3. [Performance Modes](#performance-modes)
4. [Confidence Tuning](#confidence-tuning)
5. [Profiling and Diagnostics](#profiling-and-diagnostics)
6. [Rule Optimization](#rule-optimization)
7. [Advanced Optimizations](#advanced-optimizations)

## Performance Targets

### Default Performance Characteristics

RAXE is designed to meet strict latency requirements:

| Mode | P95 Latency | Throughput | Detection Accuracy |
|------|-------------|------------|-------------------|
| Fast | <3ms | ~1000 req/s | 85-90% |
| Balanced | <10ms | ~500 req/s | 95-98% |
| Thorough | <100ms | ~50 req/s | 99%+ |

### Latency Breakdown

Typical latency by component (balanced mode):

```
Total: ~8ms
├── L1 Rule Matching:     ~5ms  (60%)
├── L2 ML Analysis:       ~1ms  (12%)
├── Policy Evaluation:    ~0.5ms (6%)
├── Telemetry Queue:      ~0.3ms (4%)
└── Overhead:             ~1.2ms (18%)
```

## Layer Control

RAXE provides fine-grained control over detection layers.

### Layer Architecture

```
┌─────────────────────────────────────────┐
│  L1: Rule-Based Detection               │
│  - Regex pattern matching               │
│  - Fast, deterministic                  │
│  - Latency: 3-5ms                       │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  L2: ML-Based Detection                 │
│  - Neural network inference             │
│  - High accuracy                        │
│  - Latency: 0.5-20ms (model dependent)  │
└─────────────────────────────────────────┘
```

### Enabling/Disabling Layers

#### Via ScanPipeline API (Direct)

```python
from raxe.application.scan_pipeline import ScanPipeline

pipeline = ScanPipeline(...)

# L1 only (fastest)
result = pipeline.scan(
    text="prompt to scan",
    l1_enabled=True,
    l2_enabled=False
)

# L2 only (ML only)
result = pipeline.scan(
    text="prompt to scan",
    l1_enabled=False,
    l2_enabled=True
)

# Both layers (most accurate)
result = pipeline.scan(
    text="prompt to scan",
    l1_enabled=True,
    l2_enabled=True
)

# No detection (overhead measurement)
result = pipeline.scan(
    text="prompt to scan",
    l1_enabled=False,
    l2_enabled=False
)
```

#### Via Configuration File

```yaml
# ~/.raxe/config.yaml
detection:
  l1_enabled: true
  l2_enabled: true  # Set to false to disable ML layer

  # Per-layer timeouts
  l1_timeout_ms: 10
  l2_timeout_ms: 50
```

### Layer Control Use Cases

**Fast API Endpoints** (L1 only):
```python
# Use for high-throughput, latency-sensitive endpoints
result = pipeline.scan(prompt, l1_enabled=True, l2_enabled=False)
# Latency: ~3ms, Accuracy: 85%
```

**Batch Processing** (L2 only):
```python
# Use for offline analysis where accuracy matters most
result = pipeline.scan(prompt, l1_enabled=False, l2_enabled=True)
# Latency: ~15ms, Accuracy: 98%
```

**Production Default** (Both layers):
```python
# Use for balanced latency and accuracy
result = pipeline.scan(prompt, l1_enabled=True, l2_enabled=True)
# Latency: ~8ms, Accuracy: 99%
```

## Performance Modes

RAXE provides three pre-configured performance modes.

### Mode Specifications

| Mode | Layers | Confidence Threshold | Rule Selection | Latency Target |
|------|--------|---------------------|----------------|----------------|
| `fast` | L1 only | 0.5 | High-confidence only | <3ms |
| `balanced` | L1 + L2 | 0.7 | Standard set | <10ms |
| `thorough` | L1 + L2 | 0.3 | All rules | <100ms |

### Using Performance Modes

```python
from raxe.application.scan_pipeline import ScanPipeline

pipeline = ScanPipeline(...)

# Fast mode - minimum latency
result = pipeline.scan(text, mode="fast")

# Balanced mode - default
result = pipeline.scan(text, mode="balanced")

# Thorough mode - maximum accuracy
result = pipeline.scan(text, mode="thorough")
```

### Mode Configuration Details

**Fast Mode**:
```python
# Equivalent configuration
result = pipeline.scan(
    text,
    l1_enabled=True,
    l2_enabled=False,
    confidence_threshold=0.5,
    rule_filter="high_confidence"
)
```

**Balanced Mode**:
```python
# Equivalent configuration
result = pipeline.scan(
    text,
    l1_enabled=True,
    l2_enabled=True,
    confidence_threshold=0.7,
    rule_filter="standard"
)
```

**Thorough Mode**:
```python
# Equivalent configuration
result = pipeline.scan(
    text,
    l1_enabled=True,
    l2_enabled=True,
    confidence_threshold=0.3,
    rule_filter="all"
)
```

### Choosing the Right Mode

**Use Fast Mode When:**
- Serving synchronous API requests
- Latency is critical (<5ms required)
- Traffic volume is very high (>1000 req/s)
- False negatives are acceptable

**Use Balanced Mode When:**
- General production use
- Balance between speed and accuracy needed
- Moderate traffic (100-500 req/s)
- Standard security requirements

**Use Thorough Mode When:**
- Batch/offline processing
- Security audits
- High-risk operations (e.g., admin access)
- False negatives are unacceptable

## Confidence Tuning

### Understanding Confidence Scores

Confidence represents how certain RAXE is about a detection:

- **1.0**: Absolute certainty (e.g., exact string match)
- **0.9-0.99**: Very high confidence (strong pattern match)
- **0.7-0.89**: High confidence (typical ML predictions)
- **0.5-0.69**: Medium confidence (weak signals)
- **<0.5**: Low confidence (potential false positives)

### Setting Confidence Thresholds

```python
# Conservative (fewer false positives, more false negatives)
result = pipeline.scan(text, confidence_threshold=0.9)

# Balanced (default)
result = pipeline.scan(text, confidence_threshold=0.7)

# Aggressive (more detections, higher false positive rate)
result = pipeline.scan(text, confidence_threshold=0.3)
```

### Threshold Selection Guidelines

| Use Case | Threshold | FP Rate | FN Rate |
|----------|-----------|---------|---------|
| User-facing blocking | 0.9 | <1% | ~15% |
| Logging/monitoring | 0.7 | ~5% | ~5% |
| Security audit | 0.5 | ~15% | <2% |
| Threat research | 0.3 | ~30% | <1% |

### Dynamic Threshold Adjustment

```python
from raxe.application.scan_pipeline import ScanPipeline

class AdaptiveScanner:
    """Adjust threshold based on context."""

    def __init__(self, pipeline: ScanPipeline):
        self.pipeline = pipeline

    def scan_with_context(self, text: str, user_role: str):
        # High-privilege users: strict threshold
        if user_role in ["admin", "superuser"]:
            threshold = 0.5
        # Regular users: balanced
        elif user_role == "user":
            threshold = 0.7
        # Anonymous: permissive
        else:
            threshold = 0.9

        return self.pipeline.scan(
            text,
            confidence_threshold=threshold
        )
```

## Profiling and Diagnostics

### Using ScanProfiler

```python
from raxe.utils.profiler import ScanProfiler
from raxe.application.scan_pipeline import ScanPipeline

# Create profiler
profiler = ScanProfiler(pipeline)

# Profile a scan
profile = profiler.profile_scan("text to scan")

# Print statistics
print(f"Total duration: {profile.total_duration_ms:.2f}ms")
print(f"L1 duration: {profile.l1_profile.duration_ms:.2f}ms")
print(f"L2 duration: {profile.l2_profile.duration_ms if profile.l2_profile else 0:.2f}ms")
print(f"L1 percentage: {profile.l1_percentage:.1f}%")

# Identify bottlenecks
bottlenecks = profiler.identify_bottlenecks(profile)
for bottleneck in bottlenecks:
    print(f"Bottleneck: {bottleneck}")

# Get recommendations
recommendations = profiler.get_recommendations(profile)
for rec in recommendations:
    print(f"Recommendation: {rec}")
```

### Profiler Output Example

```
Total duration: 12.45ms
L1 duration: 8.23ms (66.1%)
L2 duration: 2.15ms (17.3%)
Overhead: 2.07ms (16.6%)

Bottlenecks:
  - L1 taking >60% of total time
  - Rule 'pi-002' taking 3.2ms (39% of L1)
  - Rule 'pii-005' taking 2.1ms (26% of L1)

Recommendations:
  - Consider disabling L2 if latency is critical
  - Optimize or disable slow rule 'pi-002'
  - Use fast mode for <5ms target latency
```

### CLI Profiling

```bash
# Profile a single prompt
raxe profile "Ignore all previous instructions" --verbose

# Profile from file
raxe profile --file prompts.txt --report profile-report.json

# Compare modes
raxe profile "test prompt" --compare-modes --output comparison.html
```

### Continuous Monitoring

```python
import logging
from raxe.utils.profiler import ScanProfiler

# Enable performance logging
logger = logging.getLogger("raxe.performance")
logger.setLevel(logging.INFO)

profiler = ScanProfiler(pipeline)

# Profile every Nth request
request_count = 0
for prompt in prompts:
    request_count += 1

    if request_count % 100 == 0:
        # Profile every 100th request
        profile = profiler.profile_scan(prompt)
        logger.info(
            f"Performance sample: "
            f"total={profile.total_duration_ms:.2f}ms "
            f"l1={profile.l1_percentage:.1f}% "
            f"l2={profile.l2_percentage:.1f}%"
        )
    else:
        # Normal scan
        pipeline.scan(prompt)
```

## Rule Optimization

### Identifying Slow Rules

```python
from raxe.utils.profiler import ScanProfiler

profiler = ScanProfiler(pipeline)
profile = profiler.profile_scan("test prompt")

# Get slowest rules
slowest = profiler.slowest_rules(profile, limit=10)
for rule_id, duration_ms in slowest:
    print(f"Rule {rule_id}: {duration_ms:.2f}ms")
```

### Pattern Optimization Techniques

**Before (Slow)**:
```yaml
# Catastrophic backtracking risk
pattern: ".*password.*=.*"
```

**After (Fast)**:
```yaml
# Anchored, lazy quantifiers
pattern: "^.*?password.*?=.*?$"
flags: ["MULTILINE"]
timeout: 5.0  # Safety timeout
```

**Before (Slow)**:
```yaml
# No word boundaries
pattern: "admin"
```

**After (Fast)**:
```yaml
# Word boundaries reduce false matches
pattern: "\\badmin\\b"
```

**Before (Slow)**:
```yaml
# Capturing groups (not needed)
pattern: "(SELECT|INSERT|UPDATE|DELETE).*FROM.*(users|accounts)"
```

**After (Fast)**:
```yaml
# Non-capturing groups
pattern: "(?:SELECT|INSERT|UPDATE|DELETE).*FROM.*(?:users|accounts)"
```

### Rule Selection Strategies

**Option 1: Disable Slow Rules**
```yaml
# ~/.raxe/config.yaml
rules:
  disabled_rules:
    - "pi-002"  # Taking 3ms on average
    - "pii-007" # Complex regex causing slowdowns
```

**Option 2: Rule Pack Filtering**
```yaml
# Only load essential packs
rules:
  enabled_packs:
    - "core/prompt-injection"
    - "core/pii-basic"
  # Don't load:
  # - "extended/pii-international"
  # - "experimental/ml-patterns"
```

**Option 3: Conditional Loading**
```python
# Load rules based on traffic tier
if request.tier == "free":
    # Minimal rules for free tier
    pipeline.load_rules(packs=["core/basic"])
elif request.tier == "pro":
    # Standard rules
    pipeline.load_rules(packs=["core", "extended"])
else:
    # All rules for enterprise
    pipeline.load_rules(packs=["core", "extended", "custom"])
```

## Advanced Optimizations

### Caching Strategies

**Result Caching** (for repeated prompts):
```python
from functools import lru_cache
import hashlib

class CachedPipeline:
    def __init__(self, pipeline):
        self.pipeline = pipeline

    @lru_cache(maxsize=1000)
    def scan_cached(self, text_hash: str, text: str):
        return self.pipeline.scan(text)

    def scan(self, text: str):
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return self.scan_cached(text_hash, text)
```

**Rule Compilation Caching**:
```python
# Rules are pre-compiled at startup
# Ensure you call preload_pipeline() once:

from raxe.application.preloader import preload_pipeline

# One-time startup cost (~100-200ms)
pipeline, stats = preload_pipeline()

# Subsequent scans are fast (<10ms)
result = pipeline.scan("prompt")
```

### Async/Batch Processing

**Async Scanning**:
```python
import asyncio
from raxe.application.scan_pipeline import ScanPipeline

async def scan_async(pipeline: ScanPipeline, prompts: list[str]):
    tasks = []
    for prompt in prompts:
        task = asyncio.to_thread(pipeline.scan, prompt)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results

# Usage
prompts = ["prompt1", "prompt2", "prompt3"]
results = asyncio.run(scan_async(pipeline, prompts))
```

**Batch Scanning** (when latency isn't critical):
```python
def scan_batch(pipeline: ScanPipeline, prompts: list[str]):
    """Scan multiple prompts with optimizations."""
    results = []

    # Pre-load rules once
    rules = pipeline.pack_registry.get_all_rules()

    for prompt in prompts:
        result = pipeline.scan(prompt)
        results.append(result)

    return results
```

### Hardware Optimizations

**CPU Optimization**:
```yaml
# ~/.raxe/config.yaml
performance:
  worker_threads: 4  # Match CPU cores
  regex_engine: "hyperscan"  # If available (10x faster)
```

**GPU Acceleration** (for L2 ML models):
```yaml
ml:
  device: "cuda"  # or "mps" for Apple Silicon
  batch_size: 32  # Process multiple prompts at once
```

**Memory Optimization**:
```yaml
rules:
  max_rules_cached: 1000  # Limit memory usage
  unload_unused: true     # Unload rules after 1 hour
```

### Production Deployment

**Load Balancing**:
```python
# Run multiple RAXE instances behind load balancer
# Each instance handles different traffic segments

# Instance 1: Fast tier (free users)
instance1 = Raxe(performance_mode="fast")

# Instance 2: Balanced tier (pro users)
instance2 = Raxe(performance_mode="balanced")

# Instance 3: Thorough tier (enterprise)
instance3 = Raxe(performance_mode="thorough")
```

**Circuit Breaker**:
```python
from raxe.utils.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,    # Open after 5 failures
    reset_timeout=30,       # Try again after 30s
    half_open_requests=3    # Test with 3 requests
)

def scan_with_breaker(text: str):
    try:
        return breaker.call(lambda: pipeline.scan(text))
    except CircuitBreakerOpen:
        # Fallback: allow request through without scanning
        logger.warning("Circuit breaker open, bypassing scan")
        return create_safe_result()
```

## Benchmarking

### Run Benchmarks

```bash
# Quick benchmark
raxe benchmark --iterations 100 --mode balanced

# Full benchmark suite
raxe benchmark --full --output benchmark-results.json

# Compare configurations
raxe benchmark --compare \
  --config1 fast.yaml \
  --config2 balanced.yaml \
  --config3 thorough.yaml
```

### Interpreting Results

```
Benchmark Results (100 iterations):
Mode: balanced

Latency:
  Mean:  8.23ms
  P50:   7.45ms
  P95:   9.87ms
  P99:   12.34ms

Throughput:
  Requests/sec: 121.5
  Scans/min:    7290

Breakdown:
  L1:       5.12ms (62%)
  L2:       1.45ms (18%)
  Policy:   0.34ms (4%)
  Overhead: 1.32ms (16%)

✓ All latency targets met
✓ P95 < 10ms (target met)
```

## Troubleshooting

### High Latency Issues

1. **Profile the scan**:
```bash
raxe profile "problematic prompt" --verbose
```

2. **Check slow rules**:
```python
profiler.slowest_rules(profile, limit=10)
```

3. **Reduce rule count**:
```yaml
rules:
  enabled_packs: ["core/basic"]  # Minimal set
```

4. **Disable L2**:
```python
result = pipeline.scan(text, l2_enabled=False)
```

### High Memory Usage

1. **Limit rule cache**:
```yaml
rules:
  max_rules_cached: 500
```

2. **Disable result caching**:
```yaml
cache:
  enabled: false
```

3. **Reduce batch size**:
```yaml
ml:
  batch_size: 8  # Reduce from 32
```

## Additional Resources

- [ScanPipeline API Reference](./api/scan-pipeline.md)
- [Rule Performance Guide](./api/rule-performance.md)
- [Profiler Documentation](./api/profiler.md)
- [Production Deployment Guide](./deployment.md)
