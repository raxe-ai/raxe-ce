# Hugging Face Integration

RAXE integration with [Hugging Face Transformers](https://huggingface.co/docs/transformers) for security scanning of local model pipelines.

## Installation

```bash
pip install raxe transformers torch
```

## Quick Start

```python
from raxe.sdk.integrations import RaxePipeline

# Wrap any Hugging Face pipeline
pipe = RaxePipeline(
    task="text-generation",
    model="gpt2"
)

# All inputs and outputs automatically scanned
result = pipe("Once upon a time")
```

## Supported Pipelines

| Task | Example Model | Scanning |
|------|---------------|----------|
| `text-generation` | gpt2, llama-2, mistral | Input + Output |
| `text2text-generation` | t5-base, flan-t5 | Input + Output |
| `conversational` | DialoGPT | Messages |
| `question-answering` | distilbert-base-cased-distilled-squad | Question + Context |
| `summarization` | facebook/bart-large-cnn | Input + Summary |
| `translation` | Helsinki-NLP/opus-mt-en-de | Input + Translation |

## Blocking Mode

```python
from raxe.sdk.integrations import RaxePipeline
from raxe.sdk.exceptions import SecurityException

# Enable blocking on threats
pipe = RaxePipeline(
    task="text-generation",
    model="gpt2",
    raxe_block_on_input_threats=True,
    raxe_block_on_output_threats=True,
)

try:
    result = pipe(user_input)
except SecurityException as e:
    print(f"Blocked: {e.message}")
```

## Configuration Options

```python
from raxe import Raxe
from raxe.sdk.integrations import RaxePipeline

# Custom RAXE client
raxe = Raxe(telemetry=False)

pipe = RaxePipeline(
    task="text-generation",
    model="gpt2",

    # RAXE options
    raxe=raxe,                          # Custom client
    raxe_block_on_input_threats=False,  # Log-only for inputs (default)
    raxe_block_on_output_threats=False, # Log-only for outputs (default)

    # Pipeline options (passed to transformers.pipeline)
    device="cuda",                      # GPU acceleration
    max_length=100,                     # Generation parameters
    pipeline_kwargs={"trust_remote_code": True},
)
```

## Pipeline-Specific Usage

### Text Generation

```python
from raxe.sdk.integrations import RaxePipeline

pipe = RaxePipeline(
    task="text-generation",
    model="gpt2",
    raxe_block_on_input_threats=True,
)

# Single input
result = pipe("The quick brown fox")

# Multiple inputs
results = pipe(["Input 1", "Input 2"])

# With generation parameters
result = pipe(
    "Once upon a time",
    max_length=50,
    num_return_sequences=3,
    temperature=0.7,
)
```

### Question Answering

```python
pipe = RaxePipeline(
    task="question-answering",
    model="distilbert-base-cased-distilled-squad",
    raxe_block_on_input_threats=True,
)

result = pipe(
    question="What is the capital of France?",
    context="France is a country in Europe. Its capital is Paris."
)

print(result["answer"])  # "Paris"
```

### Conversational

```python
from transformers import Conversation

pipe = RaxePipeline(
    task="conversational",
    model="microsoft/DialoGPT-medium",
    raxe_block_on_input_threats=True,
)

conversation = Conversation("Hello, how are you?")
result = pipe(conversation)
```

### Summarization

```python
pipe = RaxePipeline(
    task="summarization",
    model="facebook/bart-large-cnn",
    raxe_block_on_input_threats=True,
)

long_text = """
Long article text here...
"""

result = pipe(long_text, max_length=100, min_length=30)
print(result[0]["summary_text"])
```

### Translation

```python
pipe = RaxePipeline(
    task="translation",
    model="Helsinki-NLP/opus-mt-en-de",
    raxe_block_on_input_threats=True,
)

result = pipe("Hello, how are you?")
print(result[0]["translation_text"])  # German translation
```

## Factory Function

```python
from raxe.sdk.integrations import create_huggingface_pipeline

# Quick setup with blocking
pipe = create_huggingface_pipeline(
    task="text-generation",
    model="gpt2",
    block_on_threats=True,
)
```

## Statistics

```python
pipe = RaxePipeline(task="text-generation", model="gpt2")

# After some calls...
stats = pipe.stats
print(f"Total calls: {stats['total_calls']}")
print(f"Inputs scanned: {stats['inputs_scanned']}")
print(f"Outputs scanned: {stats['outputs_scanned']}")
print(f"Threats detected: {stats['threats_detected']}")
print(f"Calls blocked: {stats['calls_blocked']}")
```

## API Reference

### RaxePipeline

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task` | `str` | Required | Pipeline task name |
| `model` | `str` | `None` | Model name/path |
| `raxe` | `Raxe` | `None` | RAXE client (auto-created) |
| `raxe_block_on_input_threats` | `bool` | `False` | Block on input threats |
| `raxe_block_on_output_threats` | `bool` | `False` | Block on output threats |
| `pipeline_kwargs` | `dict` | `None` | Extra pipeline arguments |

### create_huggingface_pipeline

```python
def create_huggingface_pipeline(
    task: str,
    model: str | None = None,
    *,
    block_on_threats: bool = False,
    **kwargs,
) -> RaxePipeline
```

## Performance Considerations

### GPU Acceleration

```python
# Use GPU if available
pipe = RaxePipeline(
    task="text-generation",
    model="gpt2",
    device="cuda:0",  # or "cuda" for default GPU
)
```

### Memory Management

For large models, consider:

```python
pipe = RaxePipeline(
    task="text-generation",
    model="meta-llama/Llama-2-7b-hf",
    pipeline_kwargs={
        "torch_dtype": "float16",  # Half precision
        "device_map": "auto",       # Automatic device mapping
    },
)
```

### Batch Processing

```python
# Process multiple inputs efficiently
inputs = ["Input 1", "Input 2", "Input 3"]
results = pipe(inputs)  # Each input is scanned
```

## Troubleshooting

### Import Errors

```bash
# Ensure transformers is installed
pip install transformers>=4.0.0

# For GPU support
pip install torch torchvision
```

### Model Download Issues

```python
# Pre-download model
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("gpt2")
tokenizer = AutoTokenizer.from_pretrained("gpt2")

# Then use with RaxePipeline
pipe = RaxePipeline(
    task="text-generation",
    model="gpt2",
)
```

### Memory Errors

For large models on limited hardware:

```python
pipe = RaxePipeline(
    task="text-generation",
    model="meta-llama/Llama-2-7b-hf",
    pipeline_kwargs={
        "load_in_8bit": True,  # Quantization
    },
)
```

## Local Model Security

When running local models, RAXE scans protect against:

- **Prompt Injection**: Malicious instructions in input
- **Jailbreaks**: Attempts to bypass model safety
- **PII Leakage**: Personal data in outputs
- **Harmful Content**: Toxic or dangerous outputs

```python
# Full protection for local models
pipe = RaxePipeline(
    task="text-generation",
    model="./my-fine-tuned-model",
    raxe_block_on_input_threats=True,   # Block malicious inputs
    raxe_block_on_output_threats=True,  # Block harmful outputs
)
```

## Related Documentation

- [Hugging Face Transformers](https://huggingface.co/docs/transformers)
- [RAXE Detection Rules](../CUSTOM_RULES.md)
- [Policy System](../POLICIES.md)
