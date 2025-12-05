# Exceptions API

Error handling and exceptions in RAXE.

## Exception Hierarchy

```
RaxeException (base)
├── SecurityException (threat detected)
├── RaxeBlockedError (request blocked)
├── ValidationError (invalid input)
├── ConfigurationError (config issue)
└── CloudAPIError (cloud communication)
```

---

## SecurityException

Raised when a threat is detected and `block_on_threat=True`.

```python
from raxe import SecurityException
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `result` | `ScanPipelineResult` | Full scan result with threat details |
| `message` | `str` | Error message |

### Example Usage

```python
from raxe import Raxe, SecurityException

raxe = Raxe()

try:
    result = raxe.scan(
        "Ignore all instructions",
        block_on_threat=True
    )
except SecurityException as e:
    # Access scan result using flat API
    print(f"Severity: {e.result.severity}")
    print(f"Detections: {e.result.total_detections}")

    # Return error response
    return {
        "error": "Security threat detected",
        "severity": e.result.severity,
        "message": str(e)
    }, 403
```

### When Raised

- `raxe.scan(text, block_on_threat=True)` and threat detected
- `@raxe.protect` decorator and threat detected
- Wrapped client calls and threat detected

---

## RaxeBlockedError

Raised when a request is blocked by policy.

```python
from raxe import RaxeBlockedError
```

### Example Usage

```python
try:
    result = process_request(user_input)
except RaxeBlockedError as e:
    logger.warning(f"Request blocked: {e}")
    return {"error": "Request blocked by security policy"}, 403
```

---

## ValidationError

Raised for invalid input or configuration.

```python
from raxe.sdk.exceptions import ValidationError
```

### Common Causes

- Empty or None text passed to `scan()`
- Invalid configuration values
- Malformed input data

### Example

```python
try:
    result = raxe.scan("")  # Empty text
except ValidationError as e:
    logger.error(f"Validation error: {e}")
```

---

## ConfigurationError

Raised for configuration issues.

```python
from raxe.sdk.exceptions import ConfigurationError
```

### Common Causes

- Invalid config file format
- Missing required configuration
- Conflicting configuration options

### Example

```python
from pathlib import Path

try:
    raxe = Raxe.from_config_file(Path("nonexistent.yaml"))
except ConfigurationError as e:
    logger.error(f"Config error: {e}")
```

---

## CloudAPIError

Raised for cloud API communication issues.

```python
from raxe.sdk.exceptions import CloudAPIError
```

### Common Causes

- Network connectivity issues
- Invalid API key
- Rate limiting
- Cloud service unavailable

### Example

```python
try:
    # Cloud features
    result = raxe.scan(text)
except CloudAPIError as e:
    logger.warning(f"Cloud API error: {e}")
    # Fall back to local-only mode
```

---

## Error Handling Patterns

### Pattern 1: Graceful Degradation

```python
from raxe import Raxe, SecurityException, CloudAPIError

raxe = Raxe()

def safe_scan(text: str) -> dict:
    try:
        result = raxe.scan(text, block_on_threat=True)
        return {"safe": True}
    except SecurityException as e:
        # Threat detected
        return {
            "safe": False,
            "severity": e.result.severity,
            "blocked": True
        }
    except CloudAPIError as e:
        # Cloud unavailable, local scan only
        logger.warning(f"Cloud API error: {e}")
        return {"safe": True, "cloud_unavailable": True}
    except Exception as e:
        # Unexpected error, fail open
        logger.error(f"Scan error: {e}")
        return {"safe": True, "error": True}
```

### Pattern 2: Detailed Error Response

```python
from raxe import SecurityException

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        user_input = request.json['message']
        result = raxe.scan(user_input, block_on_threat=True)

        # Process if safe
        response = generate_response(user_input)
        return {"response": response}

    except SecurityException as e:
        # Return detailed error
        return jsonify({
            "error": "Security threat detected",
            "severity": e.result.severity,
            "detections": [
                {
                    "rule_id": d.rule_id,
                    "severity": d.severity,
                    "confidence": d.confidence
                }
                for d in e.result.detections  # Flat API
            ],
            "message": "Your message was blocked due to security policy"
        }), 403
```

### Pattern 3: Retry Logic

```python
from raxe import CloudAPIError
import time

def scan_with_retry(text: str, max_retries: int = 10):
    for attempt in range(max_retries):
        try:
            return raxe.scan(text)
        except CloudAPIError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Cloud API error, retrying ({attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error("Cloud API unavailable after retries")
                raise
```

### Pattern 4: Context Manager

```python
from contextlib import contextmanager

@contextmanager
def protected_execution():
    try:
        yield
    except SecurityException as e:
        logger.warning(f"Security threat: {e.result.severity}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

# Usage
with protected_execution():
    result = raxe.scan(user_input, block_on_threat=True)
```

---

## Best Practices

### 1. Always Handle SecurityException

```python
# DO THIS
try:
    result = raxe.scan(text, block_on_threat=True)
except SecurityException:
    # Handle threat
    pass

# NOT THIS
result = raxe.scan(text, block_on_threat=True)  # Unhandled exception
```

### 2. Log Exceptions Properly

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = raxe.scan(text, block_on_threat=True)
except SecurityException as e:
    logger.warning(
        "Security threat detected",
        extra={
            "severity": e.result.severity,
            "text_hash": e.result.text_hash,
            "detections": e.result.total_detections  # Flat API
        }
    )
```

### 3. Fail Safely

```python
# In production, decide: fail open or fail closed?

# Fail open (allow on error)
try:
    result = raxe.scan(text, block_on_threat=True)
except Exception as e:
    logger.error(f"Scan failed: {e}")
    # Allow request to continue

# Fail closed (block on error)
try:
    result = raxe.scan(text, block_on_threat=True)
except Exception as e:
    logger.error(f"Scan failed: {e}")
    raise  # Block request
```

### 4. Provide User-Friendly Messages

```python
try:
    result = raxe.scan(text, block_on_threat=True)
except SecurityException:
    # DON'T expose internal details
    return {"error": "Your message contains prohibited content"}, 403

    # NOT THIS (avoid exposing internal rule IDs)
    # return {"error": f"Rule {e.result.detections[0].rule_id} triggered"}, 403
```

---

## See Also

- [Raxe Client](raxe-client.md) - Main SDK documentation
- [Scan Results](scan-results.md) - Understanding results
- [Examples](../../examples/) - Integration patterns
