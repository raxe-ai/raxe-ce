# Scan Results API

Understanding RAXE scan results and how to work with them.

## ScanPipelineResult

The main result object returned by `raxe.scan()`.

```python
from raxe.application.scan_pipeline import ScanPipelineResult
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `scan_result` | `CombinedScanResult` | L1/L2 detection results |
| `policy_decision` | `BlockAction` | Policy evaluation result |
| `should_block` | `bool` | Whether to block the request |
| `duration_ms` | `float` | Total scan latency in milliseconds |
| `text_hash` | `str` | Privacy-preserving hash of scanned text |
| `metadata` | `dict` | Additional scan metadata |
| `has_threats` | `bool` | Quick check if any threats detected |
| `severity` | `str` | Highest severity: "CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE" |

### Example Usage

```python
result = raxe.scan("User input")

# Quick checks
if result.has_threats:
    print(f"Severity: {result.severity}")

# Detailed inspection
if result.should_block:
    print("Request blocked by policy")

# Performance monitoring
print(f"Scan took {result.duration_ms:.2f}ms")

# L1 detections
for detection in result.scan_result.l1_result.detections:
    print(f"Rule: {detection.rule_id}")
    print(f"Severity: {detection.severity}")
    print(f"Confidence: {detection.confidence}")
```

---

## Detection

Individual threat detection from a rule or ML model.

```python
from raxe.domain.engine.executor import Detection
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `rule_id` | `str` | Rule ID that triggered |
| `severity` | `str` | Detection severity |
| `confidence` | `float` | Confidence score (0.0 to 1.0) |
| `message` | `str` | Detection message |
| `metadata` | `dict` | Additional detection metadata |

### Example

```python
for detection in result.scan_result.l1_result.detections:
    print(f"{detection.rule_id}: {detection.severity} ({detection.confidence:.2f})")
```

---

## Severity Levels

RAXE uses four severity levels:

| Severity | Use Case | Typical Response |
|----------|----------|------------------|
| `CRITICAL` | Severe threats (data exfiltration, jailbreaks) | Always block |
| `HIGH` | Significant threats (prompt injection, PII) | Block in production |
| `MEDIUM` | Moderate concerns (suspicious patterns) | Log and monitor |
| `LOW` | Minor issues (low-confidence detections) | Log only |
| `NONE` | No threats detected | Allow |

### Example Usage

```python
result = raxe.scan(text)

if result.severity in ["CRITICAL", "HIGH"]:
    # Block high-severity threats
    raise SecurityException(result)
elif result.severity == "MEDIUM":
    # Log but allow
    logger.warning(f"Medium threat: {result.severity}")
else:
    # Process normally
    pass
```

---

## Working with Results

### Pattern 1: Simple Threat Check

```python
result = raxe.scan(user_input)

if result.has_threats:
    return {"error": "Security threat detected"}, 400
else:
    return process_input(user_input)
```

### Pattern 2: Severity-Based Handling

```python
result = raxe.scan(user_input)

match result.severity:
    case "CRITICAL" | "HIGH":
        # Block
        raise SecurityException(result)
    case "MEDIUM":
        # Log and allow
        logger.warning(f"Medium threat in {user_input[:50]}")
    case "LOW":
        # Log only
        logger.info("Low severity detection")
    case _:
        # Safe
        pass
```

### Pattern 3: Detailed Analysis

```python
result = raxe.scan(user_input)

if result.has_threats:
    # Analyze each detection
    for detection in result.scan_result.l1_result.detections:
        logger.warning(
            f"Detection: {detection.rule_id}",
            extra={
                "severity": detection.severity,
                "confidence": detection.confidence,
                "user_id": user_id
            }
        )

    # Check if blocking needed
    if result.should_block:
        return block_response(result)
```

### Pattern 4: Performance Monitoring

```python
result = raxe.scan(user_input)

# Track scan performance
metrics.histogram("raxe.scan_duration_ms", result.duration_ms)

# Track threat rate
metrics.increment(
    "raxe.scans",
    tags=[f"has_threats:{result.has_threats}"]
)
```

### Pattern 5: Logging for Analysis

```python
import structlog

logger = structlog.get_logger()

result = raxe.scan(user_input)

logger.info(
    "raxe_scan_completed",
    text_hash=result.text_hash,
    has_threats=result.has_threats,
    severity=result.severity,
    duration_ms=result.duration_ms,
    detections=len(result.scan_result.l1_result.detections)
)
```

---

## Performance Characteristics

### Scan Latency

- **P50**: ~3ms
- **P95**: <10ms
- **P99**: <20ms

### Throughput

- **Sequential**: ~100 scans/second
- **Parallel** (10 workers): ~500 scans/second

### Memory

- **Per scan**: <1KB allocation
- **Client overhead**: ~50MB resident

---

## See Also

- [Raxe Client](raxe-client.md) - Main SDK documentation
- [Exceptions](exceptions.md) - Error handling
- [Examples](../../examples/) - Integration patterns
