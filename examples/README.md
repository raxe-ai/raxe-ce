# RAXE CE Examples

This directory contains example code showing how to use RAXE CE in various scenarios.

## Quick Start Examples

### Basic Scan
[`basic_scan.py`](basic_scan.py) - Simplest way to scan a prompt for threats

```python
from raxe import Raxe
raxe = Raxe()
result = raxe.scan(prompt="...")
```

### OpenAI Wrapper
[`openai_wrapper.py`](openai_wrapper.py) - Wrap OpenAI client for automatic scanning

```python
from raxe import Raxe
raxe = Raxe()
client = raxe.wrap(openai.Client())
```

### Decorator Pattern
[`decorator_pattern.py`](decorator_pattern.py) - Use decorators to protect functions

```python
@raxe.protect(block_on_threat=True)
def generate_response(prompt):
    ...
```

## Running Examples

```bash
# Install RAXE CE first
pip install -e .

# Run an example
python examples/basic_scan.py
```

## More Examples Coming

- LangChain integration
- Anthropic client wrapper
- Batch processing
- Custom rule development
- Performance monitoring
