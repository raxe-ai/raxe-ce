# LangChain Integration with RAXE

Protect LangChain applications with RAXE security using callbacks and decorators.

## Features

- Custom callback handler for automatic scanning
- Agent and tool protection
- Input and output scanning
- Decorator-based protection

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
python langchain_raxe.py
```

## Patterns

### 1. Callback Handler

```python
from langchain.callbacks.base import BaseCallbackHandler

class RaxeCallbackHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        # Scan before LLM call
        for prompt in prompts:
            raxe.scan(prompt, block_on_threat=True)
```

### 2. Tool Protection

```python
@tool
def my_tool(query: str) -> str:
    result = raxe.scan(query)
    if result.has_threats:
        return "Blocked"
    return process(query)
```

### 3. Decorator Pattern

```python
@raxe.protect
def run_chain(user_input: str):
    return chain.run(input=user_input)
```

## Learn More

- [LangChain Docs](https://python.langchain.com)
- [RAXE Documentation](https://docs.raxe.ai)
