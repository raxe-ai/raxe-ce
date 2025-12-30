# RAXE v0.4.0 - Agentic Framework Integrations

We're excited to announce RAXE v0.4.0 with first-class support for the most popular agentic AI frameworks!

## What's New

### Agentic Framework Integrations

RAXE now seamlessly integrates with your existing multi-agent systems:

**LangChain** - Just add the callback handler:
```python
from langchain.llms import OpenAI
from raxe.sdk.integrations import RaxeCallbackHandler

llm = OpenAI(callbacks=[RaxeCallbackHandler()])
```

**CrewAI** - Protect your crews with step callbacks:
```python
from raxe.sdk.integrations import RaxeCrewGuard

guard = RaxeCrewGuard(Raxe())
crew = Crew(agents=[...], step_callback=guard.step_callback)
```

**AutoGen** - Works with both v0.2.x and v0.4+:
```python
from raxe.sdk.integrations import RaxeConversationGuard

guard = RaxeConversationGuard(Raxe())
guard.register(my_agent)  # v0.2.x
# or
protected = guard.wrap_agent(agent)  # v0.4+
```

**LlamaIndex** - Callback and instrumentation support:
```python
from raxe.sdk.integrations import RaxeLlamaIndexCallback

Settings.callback_manager = CallbackManager([RaxeLlamaIndexCallback()])
```

**Portkey AI Gateway** - Custom guardrail webhook:
```python
from raxe.sdk.integrations import RaxePortkeyWebhook

webhook = RaxePortkeyWebhook()  # Use as Portkey guardrail
```

### Core AgentScanner

All integrations are powered by the new unified `AgentScanner`:
- `ScanMode` - LOG_ONLY, BLOCK_ON_THREAT, BLOCK_ON_HIGH, BLOCK_ON_CRITICAL
- `ToolPolicy` - Block dangerous tools like shell, file_write
- `MessageType` - Track HUMAN_INPUT, AGENT_TO_AGENT, FUNCTION_CALL, FUNCTION_RESULT

### Key Features

- **Log-only by default** - Safe to add to production without breaking flows
- **Blocking when you need it** - Enable `block_on_prompt_threats=True` for strict mode
- **Tool validation** - Prevent agents from using dangerous tools
- **Trace-aware scanning** - Correlation IDs for debugging multi-agent flows

## Upgrade

```bash
pip install --upgrade raxe
```

## Documentation

- [Integration Guide](https://docs.raxe.ai/integrations)
- [LangChain](https://docs.raxe.ai/integrations/langchain)
- [CrewAI](https://docs.raxe.ai/integrations/crewai)
- [AutoGen](https://docs.raxe.ai/integrations/autogen)
- [LlamaIndex](https://docs.raxe.ai/integrations/llamaindex)
- [Portkey](https://docs.raxe.ai/integrations/portkey)

---

Questions? Join our [Slack](https://join.slack.com/t/raxeai/shared_invite/zt-3kch8c9zp-A8CMJYWQjBBpzV4KNnAQcQ) or email community@raxe.ai
