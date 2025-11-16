# RAXE API Reference

Complete API documentation for RAXE Community Edition.

## Quick Navigation

- [Raxe Client](raxe-client.md) - Main SDK client
- [Scan Results](scan-results.md) - Understanding scan results
- [Decorators](decorators.md) - Function protection with decorators
- [Exceptions](exceptions.md) - Error handling
- [Configuration](configuration.md) - Configuration options
- [CLI Commands](cli.md) - Command-line interface
- [Type Reference](types.md) - Data types and enums

## Quick Reference

### Core Classes

| Class | Description | Documentation |
|-------|-------------|---------------|
| `Raxe` | Main SDK client | [docs](raxe-client.md) |
| `ScanPipelineResult` | Scan result object | [docs](scan-results.md) |
| `Detection` | Individual threat detection | [docs](types.md#detection) |
| `Severity` | Threat severity enum | [docs](types.md#severity) |

### Main Methods

```python
# Initialize client
raxe = Raxe(api_key="optional", telemetry=True)

# Scan text
result = raxe.scan("text to scan")

# Protect function
@raxe.protect
def my_function(prompt: str):
    ...

# Wrap LLM client
client = raxe.wrap(OpenAI())
```

## Installation

```bash
pip install raxe
```

## Basic Usage

```python
from raxe import Raxe

# Initialize
raxe = Raxe()

# Scan for threats
result = raxe.scan("User input here")

# Check for threats
if result.has_threats:
    print(f"Severity: {result.severity}")
    print(f"Detections: {len(result.scan_result.l1_result.detections)}")
```

## Type Hints

RAXE is fully typed. Import types for better IDE support:

```python
from raxe import Raxe, ScanResult, Detection, Severity
from raxe.application.scan_pipeline import ScanPipelineResult

def process_scan(result: ScanPipelineResult) -> None:
    # Full IDE autocomplete support
    if result.has_threats:
        ...
```

## Next Steps

- Read the [Quickstart Guide](../quickstart.md)
- Explore [Examples](../../examples/)
- View [Integration Patterns](../integration_guide.md)
