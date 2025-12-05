# API Reference

Complete API documentation for RAXE Python SDK.

---

## Installation

```bash
# Core SDK
pip install raxe

# With ML detection (L2)
pip install raxe[ml]

# With specific LLM wrappers
pip install raxe openai     # For RaxeOpenAI
pip install raxe anthropic  # For RaxeAnthropic
```

---

## Quick Start

```python
from raxe import Raxe

raxe = Raxe()
result = raxe.scan("Ignore all previous instructions")

# Boolean evaluation - True when safe
if result:
    print("Safe to proceed")
else:
    print(f"Threat: {result.severity}")
```

---

## Module Exports

All primary classes are available from the top-level `raxe` module:

```python
from raxe import (
    # Core client
    Raxe,
    AsyncRaxe,

    # LLM Wrappers (require respective packages installed)
    RaxeOpenAI,     # Requires: openai
    RaxeAnthropic,  # Requires: anthropic

    # Types
    ScanResult,
    Detection,
    Severity,

    # Exceptions
    RaxeException,
    RaxeBlockedError,
    SecurityException,

    # Metadata
    __version__,
)
```

---

## Raxe Class

The main SDK client for all scanning operations.

### Constructor

```python
Raxe(
    api_key: str | None = None,
    config_path: Path | None = None,
    telemetry: bool = True,
    l2_enabled: bool = True,
    **kwargs
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str \| None` | `None` | Optional API key for cloud features |
| `config_path` | `Path \| None` | `None` | Path to config file (overrides default search) |
| `telemetry` | `bool` | `True` | Enable privacy-preserving telemetry |
| `l2_enabled` | `bool` | `True` | Enable L2 ML detection |

**Configuration Cascade:**
1. Explicit parameters (highest priority)
2. Environment variables (`RAXE_*`)
3. Config file
4. Defaults (lowest priority)

**Example:**

```python
# Default configuration
raxe = Raxe()

# Disable telemetry (Pro+ tier only)
raxe = Raxe(telemetry=False)  # Requires Pro+ license

# From config file
raxe = Raxe.from_config_file(Path("~/.raxe/config.yaml"))
```

---

### scan()

Scan text for security threats.

```python
def scan(
    self,
    text: str,
    *,
    customer_id: str | None = None,
    context: dict[str, object] | None = None,
    block_on_threat: bool = False,
    mode: str = "balanced",
    l1_enabled: bool = True,
    l2_enabled: bool = True,
    confidence_threshold: float = 0.5,
    explain: bool = False,
    dry_run: bool = False,
    use_async: bool = True,
) -> ScanPipelineResult
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | (required) | Text to scan (prompt or response) |
| `customer_id` | `str \| None` | `None` | Customer ID for policy evaluation |
| `context` | `dict \| None` | `None` | Additional metadata for scan |
| `block_on_threat` | `bool` | `False` | Raise `SecurityException` if threat detected |
| `mode` | `str` | `"balanced"` | Performance mode: "fast", "balanced", "thorough" |
| `l1_enabled` | `bool` | `True` | Enable L1 regex detection |
| `l2_enabled` | `bool` | `True` | Enable L2 ML detection |
| `confidence_threshold` | `float` | `0.5` | Minimum confidence for reporting (0.0-1.0) |
| `explain` | `bool` | `False` | Include explanations in results |
| `dry_run` | `bool` | `False` | Test scan without saving to database |
| `use_async` | `bool` | `True` | Use async pipeline for parallel L1+L2 |

**Returns:** `ScanPipelineResult`

**Raises:**
- `SecurityException`: If `block_on_threat=True` and threat detected
- `ValidationError`: If text is empty or invalid

**Performance Modes:**

| Mode | Target Latency | Layers | Use Case |
|------|----------------|--------|----------|
| `"fast"` | <3ms | L1 only | Real-time, latency-critical |
| `"balanced"` | <10ms | L1 + L2 | Default, recommended |
| `"thorough"` | <100ms | All layers | Maximum detection |

**Examples:**

```python
# Basic scan
result = raxe.scan("Hello world")
print(f"Safe: {bool(result)}")

# Fast mode (L1 only)
result = raxe.scan("test", mode="fast")

# With blocking
try:
    result = raxe.scan("Ignore instructions", block_on_threat=True)
except SecurityException as e:
    print(f"Blocked: {e.result.severity}")

# High confidence only
result = raxe.scan("test", confidence_threshold=0.8)
```

---

### scan_fast()

Fast scan using L1 only (target <3ms).

```python
def scan_fast(self, text: str, **kwargs) -> ScanPipelineResult
```

Equivalent to `scan(text, mode="fast", l2_enabled=False)`.

---

### scan_thorough()

Thorough scan using all detection layers (target <100ms).

```python
def scan_thorough(self, text: str, **kwargs) -> ScanPipelineResult
```

Equivalent to `scan(text, mode="thorough")`.

---

### scan_high_confidence()

Scan with high confidence threshold.

```python
def scan_high_confidence(
    self,
    text: str,
    threshold: float = 0.8,
    **kwargs
) -> ScanPipelineResult
```

---

### protect()

Decorator to protect a function.

```python
def protect(
    self,
    func=None,
    *,
    block: bool = True,
    on_threat: Callable | None = None,
    allow_severity: list[str] | None = None
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `func` | `Callable` | `None` | Function to protect |
| `block` | `bool` | `True` | Raise exception on threat |
| `on_threat` | `Callable \| None` | `None` | Custom threat handler |
| `allow_severity` | `list[str] \| None` | `None` | Severities to allow (e.g., `["LOW"]`) |

**Examples:**

```python
# Basic protection (blocks by default)
@raxe.protect
def generate(prompt: str) -> str:
    return llm.generate(prompt)

# Monitor mode (logs only)
@raxe.protect(block=False)
def monitor(prompt: str) -> str:
    return llm.generate(prompt)

# Custom handler
@raxe.protect(on_threat=lambda r: log.warning(f"Threat: {r.severity}"))
def custom(prompt: str) -> str:
    return llm.generate(prompt)
```

---

### wrap()

Wrap an LLM client with RAXE scanning.

```python
def wrap(self, client) -> WrappedClient
```

Creates a proxy that automatically scans all prompts and responses.

```python
from openai import OpenAI

raxe = Raxe()
client = raxe.wrap(OpenAI())

# All calls automatically scanned
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

---

### Utility Methods

```python
# Get all loaded rules
rules = raxe.get_all_rules()

# List rule packs
packs = raxe.list_rule_packs()

# Check API key status
has_key = raxe.has_api_key()

# Check telemetry status
enabled = raxe.get_telemetry_enabled()

# Get pipeline stats
stats = raxe.get_pipeline_stats()

# Validate configuration
validation = raxe.validate_configuration()

# Get initialization stats
init_stats = raxe.initialization_stats
```

---

## ScanPipelineResult

Result from scanning operations.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `has_threats` | `bool` | True if any threats detected |
| `severity` | `str \| None` | Highest severity ("LOW", "MEDIUM", "HIGH", "CRITICAL") |
| `total_detections` | `int` | Total detection count |
| `detections` | `list[Detection]` | Flat list of L1 detections |
| `should_block` | `bool` | True if request should be blocked |
| `policy_decision` | `BlockAction` | Policy evaluation result |
| `duration_ms` | `float` | Total scan duration |
| `text_hash` | `str` | Privacy-preserving hash |

### Boolean Evaluation

`ScanPipelineResult` supports boolean evaluation for clean conditionals:

```python
result = raxe.scan("Hello world")

# True when safe (no threats)
if result:
    print("Safe to proceed")

# False when threats detected
if not result:
    print(f"Threat: {result.severity}")
```

**Truth Table:**

| Threats | `bool(result)` | `if result:` | `if not result:` |
|---------|----------------|--------------|------------------|
| None | `True` | Executes | Skips |
| Detected | `False` | Skips | Executes |

### Convenience Properties

The flat API provides direct access without deep nesting:

```python
# Old way (still works)
result.scan_result.l1_result.detections
result.scan_result.combined_severity

# New way (recommended)
result.detections        # Flat list of detections
result.severity          # Direct access to severity
result.total_detections  # Total count
```

### Methods

```python
# Convert to dictionary
data = result.to_dict()

# Get layer breakdown
breakdown = result.layer_breakdown()
# {"L1": 2, "L2": 1, "PLUGIN": 0}
```

---

## Detection

Individual threat detection from L1 rules.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `rule_id` | `str` | Rule identifier (e.g., "pi-001") |
| `severity` | `Severity` | Detection severity |
| `confidence` | `float` | Confidence score (0.0-1.0) |
| `category` | `str` | Threat category (e.g., "pi", "jb", "pii") |
| `matches` | `list[Match]` | Pattern matches that triggered detection |
| `message` | `str` | Human-readable message describing the detection |

---

## Severity

Enum representing threat severity levels.

```python
from raxe import Severity

class Severity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
```

**Comparison:**

```python
# Severities are comparable
Severity.CRITICAL > Severity.HIGH  # True
Severity.LOW < Severity.MEDIUM     # True
```

---

## AsyncRaxe

Async version of the Raxe client for high-throughput applications.

```python
from raxe import AsyncRaxe

async_raxe = AsyncRaxe()
result = await async_raxe.scan("prompt")
```

All methods mirror the synchronous `Raxe` class but are async.

---

## RaxeOpenAI

Drop-in replacement for OpenAI client with automatic scanning.

```python
from raxe import RaxeOpenAI

client = RaxeOpenAI(api_key="sk-...")

# Automatic threat detection on all requests
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**Note:** Requires `openai` package installed.

---

## RaxeAnthropic

Drop-in replacement for Anthropic client with automatic scanning.

```python
from raxe import RaxeAnthropic

client = RaxeAnthropic(api_key="...")

# Automatic threat detection
response = client.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**Note:** Requires `anthropic` package installed.

---

## Exceptions

### Exception Hierarchy

```
RaxeException (base)
    ConfigurationError
    ValidationError
    RuleError
    DatabaseError
    InfrastructureError
    SecurityException
        RaxeBlockedError
```

### RaxeException

Base exception for all RAXE errors.

```python
from raxe import RaxeException

try:
    result = raxe.scan(prompt)
except RaxeException as e:
    print(f"Error: {e.message}")
    if e.error:
        print(f"Code: {e.error.code}")
        print(f"Fix: {e.error.remediation}")
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `message` | `str` | Error message |
| `error` | `RaxeError \| None` | Structured error info |
| `code` | `ErrorCode \| None` | Error code enum |
| `remediation` | `str \| None` | Suggested fix |
| `doc_url` | `str \| None` | Documentation link |

### SecurityException

Raised when threat detected and blocking enabled.

```python
from raxe import SecurityException

try:
    result = raxe.scan(prompt, block_on_threat=True)
except SecurityException as e:
    print(f"Threat: {e.result.severity}")
    print(f"Detections: {e.result.total_detections}")
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `result` | `ScanPipelineResult` | Full scan result |

### RaxeBlockedError

Raised when request blocked by policy.

```python
from raxe import RaxeBlockedError

try:
    result = raxe.scan(prompt, block_on_threat=True)
except RaxeBlockedError as e:
    print(f"Blocked: {e.result.policy_decision}")
```

---

## Error Codes

All error codes follow format `{CATEGORY}-{NUMBER}`.

### Categories

| Category | Range | Description |
|----------|-------|-------------|
| `CFG` | 001-099 | Configuration errors |
| `RULE` | 100-199 | Rule-related errors |
| `SEC` | 200-299 | Security errors |
| `DB` | 300-399 | Database errors |
| `VAL` | 400-499 | Validation errors |
| `INFRA` | 500-599 | Infrastructure errors |

### Common Error Codes

```python
from raxe.sdk.exceptions import ErrorCode

# Check error code
if exc.code == ErrorCode.VAL_EMPTY_INPUT:
    print("Provide non-empty input")

# Get category
category = exc.code.category  # ErrorCategory.VAL
```

See [Error Codes Reference](ERROR_CODES.md) for complete list.

---

## CLI Reference

### Commands

```bash
# Scan text
raxe scan "your text"
raxe scan "text" --explain  # With explanations
raxe scan "text" --quiet    # Exit code only (for CI/CD)
raxe scan "text" --format json  # JSON output

# Rules
raxe rules list            # List all rules
raxe rules show pi-001     # Show rule details

# Configuration
raxe init                  # Create default config
raxe config show           # Show current config
raxe config validate       # Validate config

# Diagnostics
raxe doctor                # Health check
raxe stats                 # Usage statistics

# Interactive
raxe repl                  # Interactive mode
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (no threats) |
| `1` | Threat detected |
| `2` | Invalid input |
| `3` | Configuration error |
| `4` | Scan error |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RAXE_API_KEY` | API key for cloud features | None |
| `RAXE_TELEMETRY` | Enable telemetry ("true"/"false") | "true" |
| `RAXE_CONFIG_PATH` | Config file path | ~/.raxe/config.yaml |
| `RAXE_LOG_LEVEL` | Log level (DEBUG, INFO, etc.) | INFO |
| `RAXE_DB_PATH` | Database path | ~/.raxe/scan_history.db |

---

## Type Hints

Full type hints are available for IDE support:

```python
from raxe import Raxe, ScanPipelineResult, Detection, Severity
from raxe.sdk.exceptions import RaxeException, ErrorCode, RaxeError
```

---

## Performance

### Benchmarks

| Operation | Target | Typical |
|-----------|--------|---------|
| Initialization | <500ms | ~200ms |
| L1 scan | <5ms | ~2ms |
| L2 scan | <50ms | ~15ms |
| Combined (async) | <10ms | ~5ms |

### Optimization Tips

```python
# Reuse client instance
raxe = Raxe()  # Initialize once

# Use fast mode for real-time
result = raxe.scan_fast(text)

# Disable L2 if not needed
result = raxe.scan(text, l2_enabled=False)

# Use async for batch processing
async_raxe = AsyncRaxe()
results = await asyncio.gather(*[
    async_raxe.scan(t) for t in texts
])
```

---

## Version Compatibility

| RAXE Version | Python | Dependencies |
|--------------|--------|--------------|
| 0.2.x | 3.10+ | pydantic>=2.0 |
| 0.1.x | 3.9+ | pydantic>=1.8 |

---

## See Also

- [Quick Start Guide](../QUICKSTART.md)
- [Error Codes Reference](ERROR_CODES.md)
- [Policy Configuration](POLICIES.md)
- [Custom Rules Guide](CUSTOM_RULES.md)
