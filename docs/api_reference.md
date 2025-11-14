# API Reference

## Python SDK

*Documentation will be added as SDK is implemented.*

### Quick Start

```python
from raxe import Raxe

# Initialize
raxe = Raxe(api_key="optional")

# Scan a prompt
result = raxe.scan(prompt="...")

# Check for threats
if result.has_threats():
    print(f"Severity: {result.highest_severity}")
```

### Classes

#### `Raxe`

Main SDK client.

#### `ScanResult`

Result of a threat scan.

### CLI Reference

*Documentation will be added as CLI is implemented.*

```bash
# Initialize RAXE
raxe init

# Scan a prompt
raxe scan "Your prompt here"

# Configure
raxe config set api_key YOUR_KEY
```

*Full API documentation coming soon.*
