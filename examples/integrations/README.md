# RAXE Integration Examples

This directory contains comprehensive examples for integrating RAXE with popular LLM frameworks and providers.

## Available Integrations

### 1. LangChain Integration (`langchain_example.py`)

Automatically scan all LLM interactions in LangChain applications using a callback handler.

**Installation:**
```bash
pip install raxe langchain openai
```

**Quick Start:**
```python
from langchain.llms import OpenAI
from raxe.sdk.integrations import RaxeCallbackHandler

# Add RAXE callback to automatically scan all interactions
llm = OpenAI(callbacks=[RaxeCallbackHandler()])

# All prompts and responses automatically scanned
response = llm("What is AI?")
```

**Features:**
- ✅ Scans LLM prompts and responses
- ✅ Scans tool inputs and outputs
- ✅ Scans agent actions
- ✅ Works with chains, agents, and memory
- ✅ Blocking and monitoring modes

**Examples:**
- Basic LLM scanning
- Monitoring mode (no blocking)
- Chain integration
- Selective scanning (skip tools)
- Custom RAXE configuration
- Threat blocking demonstration

---

### 2. Anthropic Integration (`anthropic_example.py`)

Drop-in replacement for Anthropic's Claude client with automatic scanning.

**Installation:**
```bash
pip install raxe anthropic
```

**Quick Start:**
```python
from raxe.sdk.wrappers import RaxeAnthropic

# Replace Anthropic with RaxeAnthropic
client = RaxeAnthropic(api_key="sk-ant-...")

# All messages.create calls automatically scanned
response = client.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**Features:**
- ✅ Drop-in replacement for `anthropic.Anthropic`
- ✅ Scans all user messages
- ✅ Optional response scanning
- ✅ Streaming support
- ✅ Multi-turn conversations
- ✅ Blocking and monitoring modes

**Examples:**
- Basic usage
- Monitoring mode
- Multi-turn conversations
- Response scanning control
- Custom RAXE configuration
- Threat blocking
- Streaming responses
- Using `raxe.wrap()` helper

---

### 3. Google Vertex AI Integration (`vertexai_example.py`)

Wrapper for Google Cloud Vertex AI with automatic scanning for PaLM and Gemini models.

**Installation:**
```bash
pip install raxe google-cloud-aiplatform
```

**Setup:**
```bash
# Authenticate with Google Cloud
gcloud auth application-default login
```

**Quick Start:**
```python
from raxe.sdk.wrappers import RaxeVertexAI

# Initialize with your project
client = RaxeVertexAI(
    project="your-project-id",
    location="us-central1"
)

# Generate with automatic scanning
response = client.generate(
    prompt="Explain AI",
    model="text-bison"
)
```

**Features:**
- ✅ Supports PaLM 2 models (text-bison, chat-bison)
- ✅ Supports Gemini models (gemini-pro)
- ✅ Text generation interface
- ✅ Chat session interface
- ✅ Automatic prompt and response scanning
- ✅ Blocking and monitoring modes

**Examples:**
- Basic text generation
- Gemini models
- Chat sessions
- Monitoring mode
- Custom RAXE configuration
- Threat blocking
- Response scanning control
- Parameter tuning
- Multi-model usage

---

### 4. Hugging Face Integration (`huggingface_example.py`)

Wrapper for Hugging Face transformers pipelines with automatic scanning.

**Installation:**
```bash
pip install raxe transformers torch
```

**Quick Start:**
```python
from raxe.sdk.integrations import RaxePipeline

# Create protected pipeline
pipe = RaxePipeline(
    task="text-generation",
    model="gpt2"
)

# All inputs and outputs automatically scanned
result = pipe("Once upon a time", max_length=50)
```

**Features:**
- ✅ Works with any transformers pipeline
- ✅ Scans inputs and outputs
- ✅ Supports text generation, QA, summarization, etc.
- ✅ Batch processing support
- ✅ Local model deployment
- ✅ Blocking and monitoring modes

**Supported Tasks:**
- text-generation
- text2text-generation
- question-answering
- summarization
- translation
- sentiment-analysis
- And more...

**Examples:**
- Text generation
- Question answering
- Summarization
- Monitoring mode
- Custom RAXE configuration
- Threat blocking
- Input vs output scanning
- Batch processing
- Translation
- Sentiment analysis

---

## Common Usage Patterns

### Monitoring Mode (Log Only)

Don't block requests, just log threats for monitoring:

```python
# LangChain
handler = RaxeCallbackHandler(
    block_on_prompt_threats=False,
    block_on_response_threats=False
)

# Anthropic
client = RaxeAnthropic(
    raxe_block_on_threat=False,
    raxe_scan_responses=True
)

# Vertex AI
client = RaxeVertexAI(
    project="...",
    raxe_block_on_threat=False
)

# Hugging Face
pipe = RaxePipeline(
    task="...",
    model="...",
    raxe_block_on_input_threats=False,
    raxe_block_on_output_threats=False
)
```

### Custom RAXE Configuration

Use custom RAXE settings across integrations:

```python
from raxe import Raxe

# Create custom RAXE client
raxe = Raxe(
    telemetry=False,  # Disable telemetry
    l2_enabled=True,   # Enable ML detection
)

# Use with any integration
handler = RaxeCallbackHandler(raxe_client=raxe)
client = RaxeAnthropic(raxe=raxe)
vertex_client = RaxeVertexAI(project="...", raxe=raxe)
pipe = RaxePipeline(task="...", model="...", raxe=raxe)
```

### Blocking vs Monitoring

Control when to block vs monitor:

```python
# Block on prompts, monitor responses
client = RaxeAnthropic(
    raxe_block_on_threat=True,      # Block malicious inputs
    raxe_scan_responses=True         # Monitor outputs
)

# Monitor everything (development)
handler = RaxeCallbackHandler(
    block_on_prompt_threats=False,
    block_on_response_threats=False
)

# Block everything (production)
pipe = RaxePipeline(
    task="...",
    model="...",
    raxe_block_on_input_threats=True,
    raxe_block_on_output_threats=True
)
```

---

## Performance Considerations

All integrations are designed for minimal performance impact:

- **Initialization**: One-time overhead (~100-200ms)
- **Scanning**: <10ms per request (P95)
- **Memory**: Negligible overhead

### Performance Tips

1. **Reuse clients**: Initialize once, use many times
2. **Disable response scanning**: If only concerned about inputs
3. **Use monitoring mode**: In development to reduce blocking overhead
4. **Batch processing**: More efficient than individual requests

---

## Error Handling

All integrations raise `SecurityException` when threats are detected:

```python
from raxe.sdk.exceptions import SecurityException

try:
    response = client.generate(prompt)
except SecurityException as e:
    print(f"Blocked: {e.result.severity}")
    print(f"Detections: {e.result.total_detections}")
    # Handle blocked request
```

---

## Environment Variables

All integrations respect these environment variables:

- `RAXE_API_KEY`: RAXE Cloud API key (optional)
- `RAXE_TELEMETRY_ENABLED`: Enable/disable telemetry (default: true)
- `RAXE_L2_ENABLED`: Enable/disable ML detection (default: true)

Provider-specific variables:
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `GOOGLE_APPLICATION_CREDENTIALS`: Google Cloud credentials

---

## Running Examples

Each example file is self-contained and can be run directly:

```bash
# Set API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...

# Run examples
python langchain_example.py
python anthropic_example.py
python vertexai_example.py
python huggingface_example.py
```

---

## Next Steps

1. **Choose an integration** that matches your stack
2. **Run the example** to see it in action
3. **Customize configuration** for your needs
4. **Deploy to production** with confidence

## Support

- Documentation: https://docs.raxe.ai
- Issues: https://github.com/raxe-ai/raxe-ce/issues
- Community: https://discord.gg/raxe-ai

---

**Last Updated:** 2025-11-15
