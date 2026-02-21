# RAXE Examples

Complete, runnable examples showing how to integrate RAXE with popular LLM
frameworks.  Each example is self-contained and includes dependency
instructions, expected output, and graceful handling of missing API keys.

## Quick Start

```bash
pip install raxe
python examples/basic_scan.py   # No API key needed
```

## Examples

| Example | Framework | API Key Required | Install |
|---------|-----------|-----------------|---------|
| [basic_scan.py](basic_scan.py) | Direct SDK | No | `pip install raxe` |
| [langchain_guard.py](langchain_guard.py) | LangChain | Yes (OpenAI) | `pip install raxe langchain langchain-openai openai` |
| [openai_wrapper.py](openai_wrapper.py) | OpenAI | Yes | `pip install raxe[wrappers]` |
| [litellm_callback.py](litellm_callback.py) | LiteLLM | Yes (OpenAI) | `pip install raxe litellm openai` |

### basic_scan.py

Direct SDK usage with no external dependencies beyond RAXE itself.
Demonstrates clean scans, threat detection, blocking mode, and fast mode.

```bash
pip install raxe
python examples/basic_scan.py
```

### langchain_guard.py

Adds RAXE as a LangChain callback handler.  Every prompt and response
flowing through a ChatModel is automatically scanned.

```bash
pip install raxe langchain langchain-openai openai
export OPENAI_API_KEY=sk-...
python examples/langchain_guard.py
```

### openai_wrapper.py

Drop-in replacement for `openai.OpenAI`.  Swap one import and all
`chat.completions.create` calls are scanned automatically.

```bash
pip install raxe[wrappers]
export OPENAI_API_KEY=sk-...
python examples/openai_wrapper.py
```

### litellm_callback.py

Register RAXE as a LiteLLM custom callback to scan calls across 200+
LLM providers through a single integration point.

```bash
pip install raxe litellm openai
export OPENAI_API_KEY=sk-...
python examples/litellm_callback.py
```

## Policies

The [policies/](policies/) directory contains example policy YAML files
for multi-tenant deployments (balanced, strict, learning modes).

## Behaviour Notes

- **Log-only by default** -- all examples default to `block_on_threats=False`
  so adding RAXE never breaks an existing application.
- **No API key?** -- each example prints a helpful message and exits cleanly
  when `OPENAI_API_KEY` is not set, while still demonstrating local scanning.
- **Privacy** -- RAXE scans run locally.  Only metadata (hashes, rule IDs,
  severity) is transmitted for telemetry; prompt text never leaves your
  machine.
