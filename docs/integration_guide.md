# Integration Guide

## Quick Integration

### Option 1: Auto-Configuration

```python
import raxe
raxe.init()  # Auto-detect and wrap

# Your LLM code works as normal
```

### Option 2: Wrap Existing Client

```python
from raxe import Raxe
import openai

raxe = Raxe()
client = raxe.wrap(openai.Client())

# Use OpenAI normally - RAXE scans automatically
```

### Option 3: Decorator Pattern

```python
from raxe import Raxe

raxe = Raxe()

@raxe.protect(block_on_threat=True)
def generate_response(prompt: str) -> str:
    return llm.generate(prompt)
```

## Supported Frameworks

- ✅ OpenAI (coming soon)
- ✅ Anthropic (coming soon)
- ✅ LangChain (coming soon)
- 🔜 More coming

## Configuration

### Environment Variables

```bash
RAXE_API_KEY=your_key
RAXE_TELEMETRY_ENABLED=true
RAXE_DETECTION_MODE=hybrid
```

### Config File

`~/.raxe/config.yaml`:

```yaml
api_key: your_key
telemetry_enabled: true
detection_mode: hybrid
fail_open: true
```

*Full integration guide coming soon.*
