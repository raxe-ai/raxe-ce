# LiteLLM Integration

RAXE integration with [LiteLLM](https://github.com/BerriAI/litellm) for security scanning across 200+ LLM providers through a unified interface.

## Installation

```bash
pip install raxe litellm
```

## Quick Start

```python
import litellm
from raxe.sdk.integrations import RaxeLiteLLMCallback

# Create callback handler (default: log-only mode)
callback = RaxeLiteLLMCallback()

# Register with LiteLLM
litellm.callbacks = [callback]

# All LLM calls are now automatically scanned
response = litellm.completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello, how are you?"}]
)
```

## Blocking Mode

```python
from raxe.sdk.integrations import RaxeLiteLLMCallback, LiteLLMConfig
from raxe.sdk.exceptions import ThreatDetectedError

# Enable blocking on threats
config = LiteLLMConfig(
    block_on_threats=True,
    scan_inputs=True,
    scan_outputs=True,
)
callback = RaxeLiteLLMCallback(config=config)
litellm.callbacks = [callback]

try:
    response = litellm.completion(
        model="gpt-4",
        messages=[{"role": "user", "content": user_input}]
    )
except ThreatDetectedError as e:
    print(f"Blocked: {e.rule_id} - {e.severity}")
```

## Factory Function

```python
from raxe.sdk.integrations import create_litellm_handler

# Simple blocking mode
handler = create_litellm_handler(block_on_threats=True)
litellm.callbacks = [handler]
```

## Configuration Options

```python
from raxe.sdk.integrations import LiteLLMConfig

config = LiteLLMConfig(
    # Blocking behavior
    block_on_threats=False,      # Default: log-only (safe for production)

    # What to scan
    scan_inputs=True,            # Scan input messages
    scan_outputs=True,           # Scan LLM responses
    include_metadata=True,       # Include call metadata in context
)
```

## Supported Providers

LiteLLM supports 200+ providers. All calls through LiteLLM are automatically scanned:

| Provider | Model Examples |
|----------|----------------|
| OpenAI | gpt-4, gpt-3.5-turbo |
| Anthropic | claude-3-opus, claude-3-sonnet |
| Azure OpenAI | azure/gpt-4 |
| AWS Bedrock | bedrock/anthropic.claude-3 |
| Google VertexAI | vertex_ai/gemini-pro |
| Cohere | command, command-light |
| Replicate | replicate/llama-2-70b |
| Hugging Face | huggingface/... |
| Ollama | ollama/llama2 |

## LiteLLM Proxy Configuration

For LiteLLM proxy deployments, add RAXE as a custom callback:

```yaml
# config.yaml
litellm_settings:
  callbacks: ["raxe.sdk.integrations.litellm.RaxeLiteLLMCallback"]
```

Or programmatically:

```python
from litellm import Router
from raxe.sdk.integrations import RaxeLiteLLMCallback

router = Router(
    model_list=[...],
    callbacks=[RaxeLiteLLMCallback()]
)
```

## Async Support

```python
import asyncio
import litellm
from raxe.sdk.integrations import RaxeLiteLLMCallback

callback = RaxeLiteLLMCallback()
litellm.callbacks = [callback]

async def main():
    response = await litellm.acompletion(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )
    return response

asyncio.run(main())
```

## Statistics

```python
callback = RaxeLiteLLMCallback()

# After some API calls...
stats = callback.stats
print(f"Total calls: {stats['total_calls']}")
print(f"Prompts scanned: {stats['prompts_scanned']}")
print(f"Responses scanned: {stats['responses_scanned']}")
print(f"Threats detected: {stats['threats_detected']}")
print(f"Calls blocked: {stats['calls_blocked']}")
```

## API Reference

### RaxeLiteLLMCallback

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `raxe` | `Raxe` | `None` | RAXE client (auto-created if not provided) |
| `config` | `LiteLLMConfig` | `None` | Configuration options |

### LiteLLMConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `block_on_threats` | `bool` | `False` | Raise exception on threat |
| `scan_inputs` | `bool` | `True` | Scan input messages |
| `scan_outputs` | `bool` | `True` | Scan LLM responses |
| `include_metadata` | `bool` | `True` | Include call metadata |

### create_litellm_handler

```python
def create_litellm_handler(
    raxe: Raxe | None = None,
    *,
    block_on_threats: bool = False,
    scan_inputs: bool = True,
    scan_outputs: bool = True,
) -> RaxeLiteLLMCallback
```

## Troubleshooting

### Callback Not Firing

Ensure the callback is registered before making calls:

```python
# WRONG - callback added after call
response = litellm.completion(...)
litellm.callbacks = [callback]

# CORRECT - callback added first
litellm.callbacks = [callback]
response = litellm.completion(...)
```

### Import Errors

If you get import errors, ensure litellm is installed:

```bash
pip install litellm>=1.0.0
```

### Blocking Mode Not Working

Verify `block_on_threats=True` is set:

```python
# Log-only (threats logged but not blocked)
callback = RaxeLiteLLMCallback()

# Blocking mode (threats raise exception)
callback = RaxeLiteLLMCallback(
    config=LiteLLMConfig(block_on_threats=True)
)
```

## Related Documentation

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [RAXE Detection Rules](../CUSTOM_RULES.md)
- [Policy System](../POLICIES.md)
