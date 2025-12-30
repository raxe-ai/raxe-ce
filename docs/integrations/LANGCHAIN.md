# LangChain Integration

RAXE integration with [LangChain](https://langchain.com) for protecting chains, agents, and RAG pipelines.

## Installation

```bash
pip install raxe langchain langchain-core
```

## Quick Start

```python
from langchain_openai import ChatOpenAI
from raxe.sdk.integrations import RaxeCallbackHandler

# Create callback handler (default: log-only mode)
handler = RaxeCallbackHandler()

# Use with LangChain
llm = ChatOpenAI(model="gpt-4", callbacks=[handler])

# All prompts are automatically scanned
response = llm.invoke("Hello, how are you?")
```

## Blocking Mode

```python
from raxe.sdk.integrations import RaxeCallbackHandler
from raxe.sdk.exceptions import SecurityException

# Enable blocking on threats
handler = RaxeCallbackHandler(block_on_prompt_threats=True)

try:
    response = llm.invoke(user_input)
except SecurityException as e:
    print("Blocked due to security threat")
```

## Configuration Options

```python
handler = RaxeCallbackHandler(
    # Blocking behavior
    block_on_prompt_threats=True,    # Block if prompt threat detected
    block_on_response_threats=True,  # Block if response threat detected

    # What to scan
    scan_tools=True,           # Scan tool inputs/outputs
    scan_agent_actions=True,   # Scan agent actions
)
```

## Chain Integration

```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

handler = RaxeCallbackHandler(block_on_prompt_threats=True)

chain = LLMChain(
    llm=ChatOpenAI(model="gpt-4"),
    prompt=PromptTemplate(template="Answer: {question}"),
    callbacks=[handler]
)

result = chain.run(question="What is AI?")
```

## Agent Integration

```python
from langchain.agents import create_react_agent, AgentExecutor
from raxe.sdk.agent_scanner import ToolPolicy

# Block dangerous tools
handler = RaxeCallbackHandler(
    block_on_prompt_threats=True,
    tool_policy=ToolPolicy.block_tools("shell", "execute_code")
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    callbacks=[handler]
)
```

## API Reference

### RaxeCallbackHandler

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `raxe` | `Raxe` | `None` | RAXE client (auto-created if not provided) |
| `block_on_prompt_threats` | `bool` | `False` | Block on prompt threats |
| `block_on_response_threats` | `bool` | `False` | Block on response threats |
| `scan_tools` | `bool` | `True` | Scan tool inputs/outputs |
| `scan_agent_actions` | `bool` | `True` | Scan agent actions |
| `tool_policy` | `ToolPolicy` | `None` | Tool restrictions |

## Files

- `src/raxe/sdk/integrations/langchain.py` - Implementation
- `tests/unit/sdk/integrations/test_langchain.py` - Unit tests

## More Information

- [Full Documentation](https://docs.raxe.ai/integrations/langchain)
- [LangChain Docs](https://python.langchain.com/docs)
