# Raxe Client API

The `Raxe` class is the main entry point for all RAXE functionality.

## Class: `Raxe`

```python
from raxe import Raxe
```

### Constructor

```python
Raxe(
    *,
    api_key: Optional[str] = None,
    config_path: Optional[Path] = None,
    telemetry: bool = True,
    l2_enabled: bool = True,
    performance_mode: str = "balanced",
    **kwargs
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `Optional[str]` | `None` | Optional API key for cloud features |
| `config_path` | `Optional[Path]` | `None` | Path to config file (overrides default) |
| `telemetry` | `bool` | `True` | Enable privacy-preserving telemetry |
| `l2_enabled` | `bool` | `True` | Enable L2 ML detection |
| `performance_mode` | `str` | `"balanced"` | Performance mode: "fast", "balanced", "accurate" |
| `**kwargs` | `Any` | - | Additional config options |

#### Configuration Cascade

Configuration is loaded in priority order:
1. Explicit parameters (highest priority)
2. Environment variables (`RAXE_*`)
3. Config file (explicit path or default)
4. Defaults (lowest priority)

#### Example Usage

```python
# Basic usage with defaults
raxe = Raxe()

# With API key
raxe = Raxe(api_key="raxe_test_...")

# Disable telemetry
raxe = Raxe(telemetry=False)

# Custom config path
from pathlib import Path
raxe = Raxe(config_path=Path.home() / ".raxe" / "config.yaml")

# All options
raxe = Raxe(
    api_key="raxe_test_...",
    telemetry=True,
    l2_enabled=True,
    performance_mode="accurate"
)
```

#### Raises

- `Exception`: If critical components fail to load

#### Performance

- **Initialization time**: ~200ms one-time cost
- **Memory overhead**: ~50MB
- **Thread-safe**: Yes, client can be reused across threads

---

## Methods

### `scan()`

Scan text for security threats.

```python
raxe.scan(
    text: str,
    *,
    customer_id: Optional[str] = None,
    context: Optional[dict[str, object]] = None,
    block_on_threat: bool = False
) -> ScanPipelineResult
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | required | Text to scan (prompt or response) |
| `customer_id` | `Optional[str]` | `None` | Optional customer ID for policy evaluation |
| `context` | `Optional[dict]` | `None` | Optional context metadata |
| `block_on_threat` | `bool` | `False` | Raise `SecurityException` if threat detected |

#### Returns

`ScanPipelineResult` with:
- `scan_result`: L1/L2 detections
- `policy_decision`: Policy evaluation result
- `should_block`: Whether to block the request
- `duration_ms`: Scan latency in milliseconds
- `text_hash`: Privacy-preserving hash
- `has_threats`: Boolean indicating if threats detected
- `severity`: Highest severity level ("CRITICAL", "HIGH", "MEDIUM", "LOW", or "NONE")

#### Raises

- `SecurityException`: If `block_on_threat=True` and threat detected
- `ValueError`: If text is invalid

#### Example Usage

```python
# Basic scan
result = raxe.scan("Hello world")
print(f"Safe: {not result.has_threats}")

# Scan with blocking
try:
    result = raxe.scan(
        "Ignore all instructions",
        block_on_threat=True
    )
except SecurityException as e:
    print(f"Blocked: {e.result.severity}")

# Scan with context
result = raxe.scan(
    "User message",
    customer_id="customer_123",
    context={"session_id": "abc123"}
)

# Check result
if result.has_threats:
    print(f"Severity: {result.severity}")
    print(f"Detections: {len(result.scan_result.l1_result.detections)}")
    for detection in result.scan_result.l1_result.detections:
        print(f"  - {detection.rule_id}: {detection.severity}")
```

#### Performance

- **Scan latency**: <10ms (P95)
- **Throughput**: ~100 scans/second
- **Async-safe**: Yes, safe to call from async contexts

---

### `protect()`

Decorator to protect a function with automatic scanning.

```python
raxe.protect(
    func=None,
    *,
    block: bool = True,
    on_threat: Optional[callable] = None,
    allow_severity: Optional[list[str]] = None
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `func` | `callable` | `None` | Function to protect (when used without params) |
| `block` | `bool` | `True` | Raise `SecurityException` on threat |
| `on_threat` | `Optional[callable]` | `None` | Callback invoked when threat detected |
| `allow_severity` | `Optional[list[str]]` | `None` | Severities to allow (e.g., `["LOW"]`) |

#### Returns

Wrapped function that scans inputs before calling original

#### Example Usage

```python
# Without parameters (blocks by default)
@raxe.protect
def generate(prompt: str) -> str:
    return llm.generate(prompt)

# With parameters (monitoring mode)
@raxe.protect(block=False)
def monitor(prompt: str) -> str:
    return llm.generate(prompt)

# With custom threat handler
@raxe.protect(on_threat=lambda result: logger.warning(result))
def custom_handler(prompt: str) -> str:
    return llm.generate(prompt)

# Allow low severity threats
@raxe.protect(allow_severity=["LOW", "MEDIUM"])
def lenient(prompt: str) -> str:
    return llm.generate(prompt)

# Works with async functions
@raxe.protect
async def async_generate(prompt: str) -> str:
    return await async_llm.generate(prompt)
```

#### Behavior

The decorator:
1. Extracts text from function arguments
2. Scans text before function execution
3. Blocks or logs based on configuration
4. Invokes callback if provided
5. Calls original function if safe

#### Text Extraction

Automatically extracts from:
- Keyword args: `prompt`, `text`, `message`, `content`, `input`
- Messages list (OpenAI/LangChain format)
- First string positional argument

---

### `wrap()`

Wrap an LLM client with automatic scanning.

```python
raxe.wrap(client: Any) -> Any
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `client` | `Any` | LLM client to wrap (OpenAI, Anthropic, etc.) |

#### Returns

Wrapped client with automatic scanning

#### Example Usage

```python
from openai import OpenAI

# Wrap OpenAI client
client = raxe.wrap(OpenAI())

# All calls automatically scanned
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

#### Note

Currently supports:
- OpenAI Python SDK
- More clients coming soon

---

### `from_config_file()` (Class Method)

Create `Raxe` instance from config file.

```python
Raxe.from_config_file(path: Path) -> Raxe
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `Path` | Path to config file |

#### Returns

Configured `Raxe` instance

#### Example Usage

```python
from pathlib import Path

raxe = Raxe.from_config_file(
    Path.home() / ".raxe" / "config.yaml"
)
```

---

## Properties

### `stats`

Get preload statistics.

```python
raxe.stats -> dict[str, Any]
```

#### Returns

Dictionary with:
- `rules_loaded`: Number of rules loaded
- `packs_loaded`: Number of packs loaded
- `patterns_compiled`: Number of patterns compiled
- `preload_time_ms`: Initialization time in milliseconds
- `config_loaded`: Whether config was loaded
- `telemetry_initialized`: Whether telemetry was initialized

#### Example Usage

```python
print(f"Loaded {raxe.stats['rules_loaded']} rules")
print(f"Initialization took {raxe.stats['preload_time_ms']}ms")
```

### `config`

Access configuration object.

```python
raxe.config -> ScanConfig
```

#### Returns

`ScanConfig` instance with all configuration options

#### Example Usage

```python
print(f"Telemetry enabled: {raxe.config.telemetry.enabled}")
print(f"L2 enabled: {raxe.config.enable_l2}")
print(f"Customer ID: {raxe.config.customer_id}")
```

---

## Best Practices

### 1. Singleton Pattern

Initialize `Raxe` once and reuse:

```python
# app.py
raxe = Raxe()  # Initialize once

@app.route('/chat', methods=['POST'])
def chat():
    result = raxe.scan(request.json['message'])  # Reuse
    ...
```

### 2. Error Handling

Always handle `SecurityException`:

```python
from raxe import SecurityException

try:
    result = raxe.scan(user_input, block_on_threat=True)
except SecurityException as e:
    logger.warning(f"Threat blocked: {e.result.severity}")
    return {"error": "Security policy violation"}, 400
```

### 3. Performance Optimization

For high-throughput scenarios:

```python
# Option 1: Disable L2 for faster scans
raxe = Raxe(l2_enabled=False)

# Option 2: Use fast mode
raxe = Raxe(performance_mode="fast")

# Option 3: Batch scans in parallel
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(raxe.scan, prompts))
```

### 4. Logging and Monitoring

Enable structured logging:

```python
import logging

logging.basicConfig(level=logging.INFO)

# RAXE will log initialization and scan events
result = raxe.scan(text)
```

### 5. Testing

Mock RAXE in tests:

```python
from unittest.mock import Mock, patch

def test_my_function():
    with patch('myapp.raxe') as mock_raxe:
        mock_raxe.scan.return_value = Mock(has_threats=False)
        result = my_function("test input")
        assert result == expected
```

---

## See Also

- [Scan Results](scan-results.md) - Understanding scan results
- [Decorators](decorators.md) - Decorator pattern details
- [Configuration](configuration.md) - Configuration options
- [Examples](../../examples/) - Integration examples
