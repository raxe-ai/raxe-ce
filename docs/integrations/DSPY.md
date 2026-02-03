# DSPy Integration

RAXE integration with [DSPy](https://github.com/stanfordnlp/dspy) for security scanning of declarative language model pipelines and optimized modules.

## Installation

```bash
pip install raxe dspy-ai
```

## Quick Start

### Callback Mode

```python
import dspy
from raxe.sdk.integrations import RaxeDSPyCallback

# Create and register callback
callback = RaxeDSPyCallback()
dspy.configure(callbacks=[callback])

# Define a DSPy module
class QA(dspy.Module):
    def __init__(self):
        self.generate = dspy.ChainOfThought("question -> answer")

    def forward(self, question):
        return self.generate(question=question)

# All DSPy calls are now automatically scanned
qa = QA()
result = qa(question="What is machine learning?")
```

### Module Wrapper Mode

```python
from raxe.sdk.integrations import RaxeModuleGuard

# Create guard
guard = RaxeModuleGuard()

# Wrap any DSPy module
protected_qa = guard.wrap_module(qa)

# Calls are automatically scanned
result = protected_qa(question="Explain neural networks")
```

## Blocking Mode

```python
from raxe.sdk.integrations import RaxeDSPyCallback, DSPyConfig
from raxe.sdk.exceptions import ThreatDetectedError

# Enable blocking on threats
config = DSPyConfig(
    block_on_threats=True,
    scan_lm_prompts=True,
    scan_lm_responses=True,
)
callback = RaxeDSPyCallback(config=config)
dspy.configure(callbacks=[callback])

try:
    result = qa(question=user_input)
except ThreatDetectedError as e:
    print(f"Blocked: {e.rule_id} - {e.severity}")
```

## Factory Function

```python
from raxe.sdk.integrations import create_dspy_handler

# Simple blocking mode
handler = create_dspy_handler(block_on_threats=True)
dspy.configure(callbacks=[handler])
```

## Configuration Options

```python
from raxe.sdk.integrations import DSPyConfig

config = DSPyConfig(
    # Blocking behavior
    block_on_threats=False,        # Default: log-only

    # Module-level scanning
    scan_module_inputs=True,       # Scan inputs to modules
    scan_module_outputs=True,      # Scan outputs from modules

    # LM-level scanning
    scan_lm_prompts=True,          # Scan prompts to LMs
    scan_lm_responses=True,        # Scan LM responses

    # Tool scanning
    scan_tool_calls=True,          # Scan tool arguments
    scan_tool_results=True,        # Scan tool results
)
```

## Scanning Levels

DSPy integration scans at multiple levels:

```
┌─────────────────────────────────────────────┐
│              DSPy Module                     │
│  ┌─────────────────────────────────────────┐│
│  │  Input ──► RAXE Scan                    ││
│  └─────────────────────────────────────────┘│
│                    │                         │
│                    ▼                         │
│  ┌─────────────────────────────────────────┐│
│  │  LM Prompt ──► RAXE Scan                ││
│  │        │                                 ││
│  │        ▼                                 ││
│  │  LM Response ──► RAXE Scan              ││
│  └─────────────────────────────────────────┘│
│                    │                         │
│                    ▼                         │
│  ┌─────────────────────────────────────────┐│
│  │  Output ──► RAXE Scan                   ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

## Signatures and Modules

### ChainOfThought

```python
import dspy
from raxe.sdk.integrations import RaxeDSPyCallback

callback = RaxeDSPyCallback()
dspy.configure(callbacks=[callback])

# Define signature
class Summarize(dspy.Signature):
    """Summarize the given document."""
    document: str = dspy.InputField()
    summary: str = dspy.OutputField()

# Create module
summarizer = dspy.ChainOfThought(Summarize)

# Automatically scanned
result = summarizer(document="Long document here...")
```

### ReAct Agent

```python
class ToolModule(dspy.Module):
    def __init__(self, tools):
        self.react = dspy.ReAct("question -> answer", tools=tools)

    def forward(self, question):
        return self.react(question=question)

# With RAXE callback, tool calls are scanned
tool_agent = ToolModule(tools=[search_tool, calculator_tool])
result = tool_agent(question="What is 2+2?")
```

## Combining with DSPy Tracing

```python
import dspy
from raxe.sdk.integrations import RaxeDSPyCallback

callback = RaxeDSPyCallback()
dspy.configure(callbacks=[callback])

# Use DSPy's built-in tracing
with dspy.settings.trace():
    result = qa(question="Explain AI safety")

    # Access trace history for debugging
    history = dspy.settings.trace_history
    print(history)
```

## Statistics

```python
callback = RaxeDSPyCallback()

# After some module calls...
stats = callback.stats
print(f"Modules scanned: {stats['modules_scanned']}")
print(f"LM prompts scanned: {stats['lm_prompts_scanned']}")
print(f"LM responses scanned: {stats['lm_responses_scanned']}")
print(f"Tool calls scanned: {stats['tool_calls_scanned']}")
print(f"Threats detected: {stats['threats_detected']}")
```

## API Reference

### RaxeDSPyCallback

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `raxe` | `Raxe` | `None` | RAXE client (auto-created) |
| `config` | `DSPyConfig` | `None` | Configuration options |

### DSPyConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `block_on_threats` | `bool` | `False` | Raise exception on threat |
| `scan_module_inputs` | `bool` | `True` | Scan module inputs |
| `scan_module_outputs` | `bool` | `True` | Scan module outputs |
| `scan_lm_prompts` | `bool` | `True` | Scan LM prompts |
| `scan_lm_responses` | `bool` | `True` | Scan LM responses |
| `scan_tool_calls` | `bool` | `True` | Scan tool arguments |
| `scan_tool_results` | `bool` | `True` | Scan tool results |

### RaxeModuleGuard

| Method | Description |
|--------|-------------|
| `wrap_module(module)` | Wrap a DSPy module with RAXE scanning |

### create_dspy_handler

```python
def create_dspy_handler(
    raxe: Raxe | None = None,
    *,
    block_on_threats: bool = False,
    **kwargs,
) -> RaxeDSPyCallback
```

## Troubleshooting

### Callback Not Firing

Ensure DSPy is configured with the callback:

```python
# WRONG - callback not registered
callback = RaxeDSPyCallback()
result = qa(question="...")

# CORRECT - configure DSPy first
callback = RaxeDSPyCallback()
dspy.configure(callbacks=[callback])
result = qa(question="...")
```

### Multiple Callbacks

DSPy supports multiple callbacks:

```python
dspy.configure(callbacks=[
    RaxeDSPyCallback(),
    other_callback,
])
```

### Optimizer Compatibility

RAXE scanning works with DSPy optimizers:

```python
from dspy.teleprompt import BootstrapFewShot

optimizer = BootstrapFewShot(metric=my_metric)
optimized_qa = optimizer.compile(qa, trainset=trainset)

# Optimized module still scanned
result = optimized_qa(question="...")
```

## Related Documentation

- [DSPy Documentation](https://dspy-docs.vercel.app/)
- [RAXE Agent Security](../AGENT_SECURITY.md)
- [Policy System](../POLICIES.md)
