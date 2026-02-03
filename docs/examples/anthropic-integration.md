# Anthropic Integration

RAXE drop-in replacement for the [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) that automatically scans all prompts and responses.

## Installation

```bash
pip install raxe anthropic
```

## Quick Start

```python
# Replace this:
from anthropic import Anthropic
client = Anthropic(api_key="sk-ant-...")

# With this:
from raxe.sdk.wrappers import RaxeAnthropic
client = RaxeAnthropic(api_key="sk-ant-...")

# All messages are automatically scanned
response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello, Claude!"}]
)
```

## Blocking Mode

```python
from raxe.sdk.wrappers import RaxeAnthropic
from raxe.sdk.exceptions import SecurityException

# Enable blocking on threats
client = RaxeAnthropic(
    api_key="sk-ant-...",
    raxe_block_on_threat=True,
    raxe_scan_responses=True,
)

try:
    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=1024,
        messages=[{"role": "user", "content": user_input}]
    )
except SecurityException as e:
    print(f"Blocked: {e.message}")
```

## Configuration Options

```python
from raxe import Raxe
from raxe.sdk.wrappers import RaxeAnthropic

# Custom RAXE client
raxe = Raxe(telemetry=False)

client = RaxeAnthropic(
    api_key="sk-ant-...",

    # RAXE options
    raxe=raxe,                      # Custom client
    raxe_block_on_threat=False,     # Log-only (default)
    raxe_scan_responses=True,       # Scan Claude responses (default)
)
```

## Messages API

### Basic Message

```python
from raxe.sdk.wrappers import RaxeAnthropic

client = RaxeAnthropic(api_key="sk-ant-...")

response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "What is machine learning?"}
    ]
)

print(response.content[0].text)
```

### Multi-turn Conversation

```python
response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello, I need help with Python."},
        {"role": "assistant", "content": "I'd be happy to help! What do you need?"},
        {"role": "user", "content": "How do I read a file?"}
    ]
)
```

### System Prompt

```python
response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    system="You are a helpful coding assistant.",
    messages=[
        {"role": "user", "content": "Explain decorators in Python"}
    ]
)
```

### Streaming

```python
with client.messages.stream(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a short story"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

### With Images (Vision)

```python
import base64

# Load image
with open("image.png", "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode("utf-8")

response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": "What's in this image?"
                }
            ],
        }
    ],
)
```

### Tool Use

```python
response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    tools=[
        {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            }
        }
    ],
    messages=[
        {"role": "user", "content": "What's the weather in Paris?"}
    ]
)

# Check for tool use
if response.stop_reason == "tool_use":
    tool_use = response.content[0]
    print(f"Tool: {tool_use.name}, Input: {tool_use.input}")
```

## Async Support

```python
import asyncio
from raxe.sdk.wrappers import RaxeAsyncAnthropic

async def main():
    client = RaxeAsyncAnthropic(api_key="sk-ant-...")

    response = await client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello!"}]
    )

    print(response.content[0].text)

asyncio.run(main())
```

## Statistics

```python
client = RaxeAnthropic(api_key="sk-ant-...")

# After some API calls...
stats = client.stats
print(f"Total calls: {stats['total_calls']}")
print(f"Prompts scanned: {stats['prompts_scanned']}")
print(f"Responses scanned: {stats['responses_scanned']}")
print(f"Threats detected: {stats['threats_detected']}")
print(f"Calls blocked: {stats['calls_blocked']}")
```

## API Reference

### RaxeAnthropic

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | Required | Anthropic API key |
| `raxe` | `Raxe` | `None` | RAXE client (auto-created) |
| `raxe_block_on_threat` | `bool` | `False` | Block on threat detection |
| `raxe_scan_responses` | `bool` | `True` | Scan Claude responses |

### RaxeAsyncAnthropic

Same parameters as RaxeAnthropic, but for async operations.

## Troubleshooting

### Import Errors

```bash
# Ensure anthropic is installed
pip install anthropic>=0.20.0
```

### API Key Issues

```python
# Via environment variable
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."

client = RaxeAnthropic()  # Picks up from environment

# Or explicitly
client = RaxeAnthropic(api_key="sk-ant-...")
```

### Rate Limits

```python
from anthropic import RateLimitError

try:
    response = client.messages.create(...)
except RateLimitError:
    # Handle rate limiting
    time.sleep(60)
```

## Comparison with Direct Anthropic SDK

| Feature | anthropic.Anthropic | RaxeAnthropic |
|---------|---------------------|---------------|
| API compatibility | Native | Drop-in |
| Prompt scanning | No | Automatic |
| Response scanning | No | Configurable |
| Threat blocking | No | Optional |
| Statistics | No | Built-in |

## Related Documentation

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [RAXE Detection Rules](../CUSTOM_RULES.md)
- [Policy System](../POLICIES.md)
- [OpenAI Integration](openai-integration.md)
