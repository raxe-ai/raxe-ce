# Layer Control API Reference

Complete API documentation for RAXE's layer control system, including performance modes, layer enablement, and confidence tuning.

## Table of Contents

1. [Overview](#overview)
2. [ScanPipeline.scan() Method](#scanpipelinescan-method)
3. [Layer Control Parameters](#layer-control-parameters)
4. [Performance Modes](#performance-modes)
5. [Confidence Threshold](#confidence-threshold)
6. [Result Metadata](#result-metadata)
7. [Code Examples](#code-examples)
8. [Best Practices](#best-practices)

## Overview

The Layer Control API provides fine-grained control over RAXE's detection pipeline:

- **Layer Control**: Enable/disable L1 (rule-based) and L2 (ML-based) detection
- **Performance Modes**: Pre-configured profiles (fast/balanced/thorough)
- **Confidence Tuning**: Filter detections by confidence score
- **Metadata Tracking**: Detailed performance and attribution metrics

## ScanPipeline.scan() Method

### Method Signature

```python
def scan(
    self,
    text: str,
    *,
    l1_enabled: bool = True,
    l2_enabled: bool = True,
    mode: Optional[str] = None,
    confidence_threshold: float = 0.0,
    explain: bool = False,
    customer_id: Optional[str] = None,
    context: Optional[dict] = None,
) -> ScanPipelineResult:
    """Scan text for security threats with layer control.

    Args:
        text: Text to scan (cannot be empty)
        l1_enabled: Enable L1 rule-based detection (default: True)
        l2_enabled: Enable L2 ML-based detection (default: True)
        mode: Performance mode override ("fast", "balanced", "thorough")
        confidence_threshold: Minimum confidence to include (0.0-1.0)
        explain: Include detailed explanations in metadata
        customer_id: Optional customer ID for policy evaluation
        context: Optional additional context metadata

    Returns:
        ScanPipelineResult with detections and metadata

    Raises:
        ValueError: If text is empty or mode is invalid
    """
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | *required* | Text to scan (prompt or response) |
| `l1_enabled` | `bool` | `True` | Enable L1 rule-based detection |
| `l2_enabled` | `bool` | `True` | Enable L2 ML-based detection |
| `mode` | `Optional[str]` | `None` | Performance mode ("fast", "balanced", "thorough") |
| `confidence_threshold` | `float` | `0.0` | Filter detections below this confidence (0.0-1.0) |
| `explain` | `bool` | `False` | Include detailed explanations |
| `customer_id` | `Optional[str]` | `None` | Customer ID for policy lookup |
| `context` | `Optional[dict]` | `None` | Additional metadata |

### Return Type: ScanPipelineResult

```python
@dataclass(frozen=True)
class ScanPipelineResult:
    """Complete scan pipeline result."""

    # Core results
    scan_result: CombinedScanResult  # L1+L2 detections
    policy_decision: BlockAction      # ALLOW/WARN/BLOCK
    should_block: bool                # Whether to block request

    # Performance metrics
    duration_ms: float                # Total scan time
    l1_duration_ms: float             # L1 processing time
    l2_duration_ms: float             # L2 processing time

    # Detection counts
    l1_detections: int                # L1 detection count
    l2_detections: int                # L2 prediction count
    plugin_detections: int            # Plugin detection count

    # Privacy-preserving hash
    text_hash: str                    # SHA256 of scanned text

    # Metadata
    metadata: dict[str, object]       # Additional pipeline metadata

    # Properties
    @property
    def has_threats(self) -> bool:
        """True if any threats detected."""

    @property
    def severity(self) -> Optional[str]:
        """Highest severity across all detections."""

    @property
    def total_detections(self) -> int:
        """Total detections across all layers."""

    def layer_breakdown(self) -> dict[str, int]:
        """Detection count by layer."""

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary."""
```

## Layer Control Parameters

### l1_enabled

Controls L1 rule-based detection.

**Type**: `bool`
**Default**: `True`

**When to disable**:
- Pure ML-based analysis required
- Measuring L2-only performance
- Overhead measurement (`l1_enabled=False, l2_enabled=False`)

**Example**:
```python
# L1 only (fastest)
result = pipeline.scan(text, l1_enabled=True, l2_enabled=False)

# L2 only (ML only)
result = pipeline.scan(text, l1_enabled=False, l2_enabled=True)

# Both (default)
result = pipeline.scan(text, l1_enabled=True, l2_enabled=True)
```

**Performance Impact**:
```
l1_enabled=True  → +3-5ms latency, +85% detection recall
l1_enabled=False → Saves 3-5ms, -15% recall
```

### l2_enabled

Controls L2 ML-based detection.

**Type**: `bool`
**Default**: `True`

**When to disable**:
- Latency-critical paths (<5ms required)
- High-throughput scenarios (>1000 req/s)
- Rule-based detection sufficient

**Example**:
```python
# Disable L2 for fast mode
result = pipeline.scan(text, l2_enabled=False)

# Check metadata
assert result.metadata["l2_enabled"] is False
assert result.l2_duration_ms == 0.0
```

**Performance Impact**:
```
l2_enabled=True  → +0.5-20ms latency, +10-15% detection recall
l2_enabled=False → Saves 0.5-20ms, -10-15% recall
```

## Performance Modes

Pre-configured profiles optimized for different use cases.

### mode Parameter

**Type**: `Optional[str]`
**Default**: `None` (uses layer settings as-is)
**Valid Values**: `"fast"`, `"balanced"`, `"thorough"`

**When mode is set, it overrides `l1_enabled` and `l2_enabled`.**

### Mode: "fast"

Optimized for minimum latency.

**Configuration**:
```python
mode="fast" → {
    l1_enabled: True,
    l2_enabled: False,
    confidence_threshold: 0.5,
    # Rule selection: high-confidence only
}
```

**Characteristics**:
- **Latency**: <3ms P95
- **Throughput**: ~1000 req/s
- **Accuracy**: 85-90%
- **False Positive Rate**: <1%
- **False Negative Rate**: ~15%

**Use Cases**:
- Synchronous API endpoints
- High-volume public APIs
- Latency-critical paths
- Real-time chat applications

**Example**:
```python
result = pipeline.scan(prompt, mode="fast")
assert result.metadata["mode"] == "fast"
assert result.metadata["l1_enabled"] is True
assert result.metadata["l2_enabled"] is False
```

### Mode: "balanced"

Default production configuration.

**Configuration**:
```python
mode="balanced" → {
    l1_enabled: True,
    l2_enabled: True,
    confidence_threshold: 0.7,
    # Rule selection: standard set
}
```

**Characteristics**:
- **Latency**: <10ms P95
- **Throughput**: ~500 req/s
- **Accuracy**: 95-98%
- **False Positive Rate**: ~2%
- **False Negative Rate**: ~5%

**Use Cases**:
- General production deployments
- Standard security requirements
- Moderate traffic volumes
- Backend API integrations

**Example**:
```python
result = pipeline.scan(prompt, mode="balanced")
assert result.metadata["mode"] == "balanced"
assert result.metadata["l1_enabled"] is True
assert result.metadata["l2_enabled"] is True
```

### Mode: "thorough"

Maximum accuracy configuration.

**Configuration**:
```python
mode="thorough" → {
    l1_enabled: True,
    l2_enabled: True,
    confidence_threshold: 0.3,
    # Rule selection: all rules
}
```

**Characteristics**:
- **Latency**: <100ms P95
- **Throughput**: ~50 req/s
- **Accuracy**: 99%+
- **False Positive Rate**: ~5%
- **False Negative Rate**: <1%

**Use Cases**:
- Security audits
- Compliance reviews
- High-risk operations
- Batch processing

**Example**:
```python
result = pipeline.scan(prompt, mode="thorough")
assert result.metadata["mode"] == "thorough"
assert result.metadata["confidence_threshold"] == 0.3
```

### Mode Comparison Table

| Metric | Fast | Balanced | Thorough |
|--------|------|----------|----------|
| P95 Latency | <3ms | <10ms | <100ms |
| Throughput | 1000/s | 500/s | 50/s |
| Accuracy | 85-90% | 95-98% | 99%+ |
| FP Rate | <1% | ~2% | ~5% |
| FN Rate | ~15% | ~5% | <1% |
| L1 Enabled | ✓ | ✓ | ✓ |
| L2 Enabled | ✗ | ✓ | ✓ |
| Confidence | 0.5 | 0.7 | 0.3 |

## Confidence Threshold

Filter detections by minimum confidence score.

### confidence_threshold Parameter

**Type**: `float`
**Default**: `0.0` (include all detections)
**Range**: `0.0` to `1.0`

**Behavior**:
- Detections with `confidence < threshold` are filtered out
- Does not affect scanning, only result filtering
- Applied after both L1 and L2 detection

**Example**:
```python
# Only include high-confidence detections
result = pipeline.scan(
    text,
    confidence_threshold=0.9
)

# Check filtered results using flat API
for detection in result.detections:
    assert detection.confidence >= 0.9
```

### Threshold Selection Guide

| Threshold | Use Case | FP Rate | FN Rate |
|-----------|----------|---------|---------|
| 0.9-1.0 | User-facing blocking | <1% | ~15% |
| 0.7-0.89 | Standard monitoring | ~5% | ~5% |
| 0.5-0.69 | Security audit | ~15% | <2% |
| 0.3-0.49 | Threat research | ~30% | <1% |

### Combining with Modes

```python
# Fast mode with custom threshold
result = pipeline.scan(
    text,
    mode="fast",
    confidence_threshold=0.8
)
# Overrides fast mode's default 0.5 threshold
```

## Result Metadata

The `metadata` dictionary contains detailed scan information.

### Standard Metadata Fields

```python
result.metadata = {
    # Layer control
    "mode": "balanced",           # Performance mode used
    "l1_enabled": True,           # L1 was enabled
    "l2_enabled": True,           # L2 was enabled
    "confidence_threshold": 0.7,  # Threshold applied

    # Timing breakdown
    "l1_duration_ms": 5.23,      # L1 processing time
    "l2_duration_ms": 1.45,      # L2 processing time
    "policy_duration_ms": 0.34,  # Policy evaluation time
    "telemetry_duration_ms": 0.12, # Telemetry queueing time

    # Detection details
    "l1_rules_checked": 47,      # Number of L1 rules evaluated
    "l1_rules_matched": 2,       # Number of L1 rules that matched
    "l2_models_used": ["v1.2.0"], # L2 model versions

    # Optional fields (if explain=True)
    "explain": True,
    "explanation": {
        "l1_reasoning": "Rule pi-001 matched pattern...",
        "l2_reasoning": "Model detected prompt injection with 0.92 confidence",
    },
}
```

### Accessing Metadata

```python
# Get specific field
mode = result.metadata.get("mode", "unknown")

# Check if explain was enabled
if result.metadata.get("explain"):
    print(result.metadata["explanation"])

# Get timing breakdown
l1_pct = (result.l1_duration_ms / result.duration_ms) * 100
l2_pct = (result.l2_duration_ms / result.duration_ms) * 100
```

## Code Examples

### Example 1: Dynamic Mode Selection

```python
from raxe.application.scan_pipeline import ScanPipeline

def scan_with_dynamic_mode(pipeline: ScanPipeline, text: str, traffic_tier: str):
    """Select mode based on traffic tier."""

    mode_map = {
        "free": "fast",      # Free tier: latency critical
        "pro": "balanced",   # Pro tier: balanced
        "enterprise": "thorough",  # Enterprise: max accuracy
    }

    mode = mode_map.get(traffic_tier, "balanced")

    result = pipeline.scan(text, mode=mode)

    return result
```

### Example 2: Adaptive Confidence Threshold

```python
def scan_with_adaptive_threshold(
    pipeline: ScanPipeline,
    text: str,
    user_risk_score: float
):
    """Adjust threshold based on user risk."""

    # High-risk users: strict threshold
    if user_risk_score > 0.8:
        threshold = 0.5
    # Normal users: standard threshold
    elif user_risk_score > 0.3:
        threshold = 0.7
    # Low-risk users: permissive threshold
    else:
        threshold = 0.9

    result = pipeline.scan(
        text,
        confidence_threshold=threshold
    )

    return result
```

### Example 3: Progressive Scanning

```python
def scan_progressive(pipeline: ScanPipeline, text: str):
    """Scan with progressive fallback."""

    # Try fast mode first
    result = pipeline.scan(text, mode="fast")

    # If high-confidence threat, return immediately
    if result.has_threats and result.severity in ["CRITICAL", "HIGH"]:
        return result

    # If no clear threat, run thorough scan
    if not result.has_threats or max(d.confidence for d in result.detections) < 0.7:
        result = pipeline.scan(text, mode="thorough")

    return result
```

### Example 4: Layer Isolation Testing

```python
def compare_layers(pipeline: ScanPipeline, text: str):
    """Compare L1 vs L2 detection."""

    # L1 only
    l1_result = pipeline.scan(
        text,
        l1_enabled=True,
        l2_enabled=False
    )

    # L2 only
    l2_result = pipeline.scan(
        text,
        l1_enabled=False,
        l2_enabled=True
    )

    # Both layers
    combined_result = pipeline.scan(
        text,
        l1_enabled=True,
        l2_enabled=True
    )

    return {
        "l1_only": l1_result.total_detections,
        "l2_only": l2_result.total_detections,
        "combined": combined_result.total_detections,
        "l1_unique": l1_result.total_detections - l2_result.total_detections,
        "l2_unique": l2_result.total_detections - l1_result.total_detections,
    }
```

### Example 5: Performance Monitoring

```python
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitor layer performance."""

    def __init__(self, pipeline: ScanPipeline):
        self.pipeline = pipeline
        self.stats: Dict[str, list] = {
            "l1_durations": [],
            "l2_durations": [],
            "total_durations": [],
        }

    def scan_with_monitoring(self, text: str, mode: str = "balanced"):
        """Scan and collect performance stats."""

        result = self.pipeline.scan(text, mode=mode)

        # Collect stats
        self.stats["l1_durations"].append(result.l1_duration_ms)
        self.stats["l2_durations"].append(result.l2_duration_ms)
        self.stats["total_durations"].append(result.duration_ms)

        # Log if slow
        if result.duration_ms > 50:
            logger.warning(
                f"Slow scan detected: {result.duration_ms:.2f}ms "
                f"(L1: {result.l1_duration_ms:.2f}ms, "
                f"L2: {result.l2_duration_ms:.2f}ms)"
            )

        return result

    def get_stats(self) -> dict:
        """Get performance statistics."""
        import statistics

        return {
            "l1_mean": statistics.mean(self.stats["l1_durations"]),
            "l1_p95": statistics.quantiles(self.stats["l1_durations"], n=20)[18],
            "l2_mean": statistics.mean(self.stats["l2_durations"]),
            "l2_p95": statistics.quantiles(self.stats["l2_durations"], n=20)[18],
            "total_mean": statistics.mean(self.stats["total_durations"]),
            "total_p95": statistics.quantiles(self.stats["total_durations"], n=20)[18],
        }
```

## Best Practices

### 1. Choose the Right Mode

```python
# ✅ GOOD: Use mode based on use case
if endpoint.is_public_api():
    mode = "fast"
elif endpoint.requires_accuracy():
    mode = "thorough"
else:
    mode = "balanced"

# ❌ BAD: Always using thorough mode
mode = "thorough"  # Wastes latency budget
```

### 2. Don't Combine Mode with Layer Control

```python
# ✅ GOOD: Use mode OR layer control
result = pipeline.scan(text, mode="fast")

# ✅ GOOD: Use explicit layer control
result = pipeline.scan(text, l1_enabled=True, l2_enabled=False)

# ❌ BAD: Mixing mode and layer control
result = pipeline.scan(text, mode="fast", l2_enabled=True)  # Confusing!
```

### 3. Use Confidence Threshold Wisely

```python
# ✅ GOOD: Threshold based on action
if action == "block_request":
    threshold = 0.9  # High threshold for blocking
elif action == "log_event":
    threshold = 0.5  # Lower threshold for logging

# ❌ BAD: Overly aggressive threshold
threshold = 0.3  # Too many false positives
```

### 4. Monitor Performance

```python
# ✅ GOOD: Track and alert on performance
if result.duration_ms > SLA_LATENCY:
    logger.warning(f"Latency SLA violated: {result.duration_ms:.2f}ms")
    metrics.increment("sla_violations")

# ❌ BAD: Ignoring performance metrics
result = pipeline.scan(text)  # No monitoring
```

### 5. Use explain Sparingly

```python
# ✅ GOOD: Only in debugging/audit scenarios
if user.is_admin or request.is_audit:
    result = pipeline.scan(text, explain=True)

# ❌ BAD: Always enabling explain
result = pipeline.scan(text, explain=True)  # Performance overhead
```

## Error Handling

```python
from raxe.application.scan_pipeline import ScanPipeline

try:
    result = pipeline.scan(
        text="",  # Empty text
        mode="invalid",  # Invalid mode
    )
except ValueError as e:
    # Handle validation errors
    logger.error(f"Scan validation error: {e}")
    # Error messages:
    # - "Text cannot be empty"
    # - "mode must be one of: fast, balanced, thorough"
```

## Migration Guide

### From Simple scan() to Layer Control

**Before**:
```python
result = pipeline.scan(text)
```

**After (with mode)**:
```python
result = pipeline.scan(text, mode="balanced")
```

**After (with explicit control)**:
```python
result = pipeline.scan(
    text,
    l1_enabled=True,
    l2_enabled=True,
    confidence_threshold=0.7
)
```

## Additional Resources

- [Performance Tuning Guide](../PERFORMANCE_TUNING.md)
- [ScanPipeline Source Code](../../src/raxe/application/scan_pipeline.py)
- [Profiler API](./profiler.md)
- [Custom Rules Guide](../CUSTOM_RULES.md)
