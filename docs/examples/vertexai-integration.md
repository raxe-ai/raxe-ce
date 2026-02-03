# Vertex AI Integration

RAXE wrapper for [Google Cloud Vertex AI](https://cloud.google.com/vertex-ai) that automatically scans all prompts and responses with PaLM and Gemini models.

## Installation

```bash
pip install raxe google-cloud-aiplatform
```

## Prerequisites

1. **Google Cloud Project**: Create or select a project in [Google Cloud Console](https://console.cloud.google.com)
2. **Enable Vertex AI API**: Enable the Vertex AI API for your project
3. **Authentication**: Set up authentication via one of:
   - `gcloud auth application-default login`
   - Service account key file
   - Workload identity

## Quick Start

```python
from raxe.sdk.wrappers import RaxeVertexAI

# Initialize with your Google Cloud project
client = RaxeVertexAI(
    project="my-project",
    location="us-central1"
)

# Generate with automatic scanning
response = client.generate(
    prompt="What is the capital of France?",
    model="text-bison"
)

print(response.text)
```

## Blocking Mode

```python
from raxe.sdk.wrappers import RaxeVertexAI
from raxe.sdk.exceptions import SecurityException

# Enable blocking on threats
client = RaxeVertexAI(
    project="my-project",
    location="us-central1",
    raxe_block_on_threat=True,
)

try:
    response = client.generate(
        prompt=user_input,
        model="text-bison"
    )
except SecurityException as e:
    print(f"Blocked: {e.message}")
```

## Configuration Options

```python
from raxe import Raxe
from raxe.sdk.wrappers import RaxeVertexAI
from google.oauth2 import service_account

# Custom credentials
credentials = service_account.Credentials.from_service_account_file(
    "path/to/service-account.json"
)

# Custom RAXE client
raxe = Raxe(telemetry=False)

client = RaxeVertexAI(
    project="my-project",
    location="us-central1",

    # Google Cloud options
    credentials=credentials,

    # RAXE options
    raxe=raxe,
    raxe_block_on_threat=False,     # Log-only (default)
    raxe_scan_responses=True,       # Scan responses (default)
)
```

## Supported Models

### PaLM 2 Models

| Model | Description |
|-------|-------------|
| `text-bison` | Text generation |
| `text-bison@002` | Latest text generation |
| `chat-bison` | Multi-turn chat |
| `chat-bison@002` | Latest chat |
| `code-bison` | Code generation |
| `codechat-bison` | Code chat |

### Gemini Models

| Model | Description |
|-------|-------------|
| `gemini-pro` | General text |
| `gemini-pro-vision` | Multimodal (text + images) |
| `gemini-ultra` | Most capable |

## Generation API

### Basic Generation

```python
response = client.generate(
    prompt="Explain quantum computing in simple terms",
    model="text-bison"
)

print(response.text)
```

### With Parameters

```python
response = client.generate(
    prompt="Write a creative story about AI",
    model="text-bison",
    temperature=0.8,
    max_output_tokens=1024,
    top_p=0.95,
    top_k=40,
)
```

### Code Generation

```python
response = client.generate(
    prompt="Write a Python function to calculate fibonacci",
    model="code-bison",
    temperature=0.2,
)

print(response.text)
```

## Chat API

### Start a Chat Session

```python
# Start chat session
chat = client.start_chat(model="chat-bison")

# Send messages
response = chat.send_message("Hello!")
print(response.text)

response = chat.send_message("What can you help me with?")
print(response.text)
```

### Chat with System Context

```python
chat = client.start_chat(
    model="chat-bison",
    context="You are a helpful coding assistant specializing in Python."
)

response = chat.send_message("How do I read a CSV file?")
```

### Chat with Examples

```python
chat = client.start_chat(
    model="chat-bison",
    examples=[
        {
            "input": {"content": "Hi"},
            "output": {"content": "Hello! How can I help you today?"}
        }
    ]
)
```

## Gemini API

### Basic Gemini

```python
response = client.generate(
    prompt="Explain machine learning",
    model="gemini-pro"
)
```

### Gemini with Images (Vision)

```python
import base64

# Load image
with open("image.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

response = client.generate_multimodal(
    model="gemini-pro-vision",
    contents=[
        {"type": "text", "text": "What's in this image?"},
        {"type": "image", "data": image_data, "mime_type": "image/png"}
    ]
)
```

### Gemini Chat

```python
chat = client.start_gemini_chat(model="gemini-pro")

response = chat.send_message("Hello!")
print(response.text)
```

## Streaming

### Stream Generation

```python
for chunk in client.generate_stream(
    prompt="Write a long story",
    model="text-bison"
):
    print(chunk.text, end="", flush=True)
```

### Stream Chat

```python
chat = client.start_chat(model="chat-bison")

for chunk in chat.send_message_stream("Tell me a joke"):
    print(chunk.text, end="", flush=True)
```

## Async Support

```python
import asyncio
from raxe.sdk.wrappers import RaxeVertexAI

async def main():
    client = RaxeVertexAI(
        project="my-project",
        location="us-central1"
    )

    response = await client.generate_async(
        prompt="What is AI?",
        model="text-bison"
    )

    print(response.text)

asyncio.run(main())
```

## Statistics

```python
client = RaxeVertexAI(project="my-project", location="us-central1")

# After some API calls...
stats = client.stats
print(f"Total calls: {stats['total_calls']}")
print(f"Prompts scanned: {stats['prompts_scanned']}")
print(f"Responses scanned: {stats['responses_scanned']}")
print(f"Threats detected: {stats['threats_detected']}")
print(f"Calls blocked: {stats['calls_blocked']}")
```

## API Reference

### RaxeVertexAI

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project` | `str` | Required | Google Cloud project ID |
| `location` | `str` | `"us-central1"` | Google Cloud location |
| `credentials` | `Credentials` | `None` | Google Cloud credentials |
| `raxe` | `Raxe` | `None` | RAXE client (auto-created) |
| `raxe_block_on_threat` | `bool` | `False` | Block on threat detection |
| `raxe_scan_responses` | `bool` | `True` | Scan model responses |

### Methods

| Method | Description |
|--------|-------------|
| `generate(prompt, model, **kwargs)` | Generate text |
| `generate_stream(prompt, model, **kwargs)` | Stream generation |
| `generate_async(prompt, model, **kwargs)` | Async generation |
| `start_chat(model, **kwargs)` | Start PaLM chat |
| `start_gemini_chat(model)` | Start Gemini chat |
| `generate_multimodal(model, contents)` | Gemini vision |

## Regions

| Region | Location Code |
|--------|---------------|
| US Central | `us-central1` |
| US East | `us-east4` |
| US West | `us-west1` |
| Europe | `europe-west4` |
| Asia | `asia-northeast1` |

## Troubleshooting

### Authentication Errors

```bash
# Set up application default credentials
gcloud auth application-default login

# Or use service account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

### API Not Enabled

```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com
```

### Quota Errors

Check quotas in Google Cloud Console and request increases if needed.

### Import Errors

```bash
# Install required packages
pip install google-cloud-aiplatform>=1.25.0
```

## Related Documentation

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [RAXE Detection Rules](../CUSTOM_RULES.md)
- [Policy System](../POLICIES.md)
- [Anthropic Integration](anthropic-integration.md)
