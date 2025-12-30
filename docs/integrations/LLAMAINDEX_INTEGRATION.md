# LlamaIndex Integration for RAXE

## Overview

This document describes the LlamaIndex integration for RAXE, providing automatic security scanning for LlamaIndex applications including query engines, RAG pipelines, and agents.

## Integration Architecture

```
                    LlamaIndex Application
                           |
                           v
           +-------------------------------+
           |      CallbackManager /        |
           |      Instrumentation          |
           +-------------------------------+
                           |
          +----------------+----------------+
          |                                 |
          v                                 v
+-------------------+           +-------------------+
| RaxeLlamaIndex    |           | RaxeSpanHandler   |
| Callback (v0.10+) |           | (v0.10.20+)       |
+-------------------+           +-------------------+
          |                                 |
          v                                 v
+-----------------------------------------------+
|              Raxe.scan()                      |
|        (Unified scanning pipeline)            |
+-----------------------------------------------+
          |
          v
+-------------------+    +-------------------+
|    L1 Detection   |--->|    L2 Detection   |
|  (460+ rules)     |    |   (ML classifier) |
+-------------------+    +-------------------+
```

## Components

### 1. RaxeLlamaIndexCallback

The primary callback handler for LlamaIndex v0.10+. Implements the `BaseCallbackHandler` interface.

**Scanned Events:**
- `QUERY` - User queries before processing
- `LLM` - Prompts and responses
- `SYNTHESIZE` - Synthesized responses
- `AGENT_STEP` - Agent task inputs
- `FUNCTION_CALL` - Tool inputs and outputs
- `RETRIEVE` - (Future) Retrieved context validation

**Default Mode:** Log-only (non-blocking)

### 2. RaxeQueryEngineCallback

Specialized callback for query engine and RAG pipeline use cases.

- Optimized for `QUERY`, `RETRIEVE`, `SYNTHESIZE` events
- Agent scanning disabled by default
- Simplified configuration

### 3. RaxeAgentCallback

Specialized callback for LlamaIndex agents (ReActAgent, FunctionCallingAgent).

- Focused on `AGENT_STEP` and `FUNCTION_CALL` events
- Scans tool inputs and outputs
- Default log-only mode

### 4. RaxeSpanHandler

Instrumentation handler for LlamaIndex v0.10.20+ using the new instrumentation API.

- Structured spans with duration tracking
- OpenTelemetry compatible
- More granular control

## Usage Examples

### Basic Query Engine Integration

```python
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.callbacks import CallbackManager
from raxe import Raxe
from raxe.sdk.integrations import RaxeLlamaIndexCallback

# Initialize RAXE
raxe = Raxe()

# Create callback handler (default: log-only mode)
raxe_callback = RaxeLlamaIndexCallback(raxe_client=raxe)

# Configure LlamaIndex
callback_manager = CallbackManager([raxe_callback])
Settings.callback_manager = callback_manager

# Create and query index
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()

# Queries are automatically scanned
response = query_engine.query("What are the key findings?")
```

### Agent Integration with Blocking

```python
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.core.callbacks import CallbackManager
from raxe.sdk.integrations import RaxeAgentCallback

# Create agent callback with blocking enabled
raxe_callback = RaxeAgentCallback(
    block_on_threats=True  # Block on any detected threats
)
callback_manager = CallbackManager([raxe_callback])

# Define tools
def calculate(expression: str) -> str:
    """Calculate a mathematical expression."""
    return str(eval(expression))

calc_tool = FunctionTool.from_defaults(fn=calculate)

# Create agent
agent = ReActAgent.from_tools(
    tools=[calc_tool],
    callback_manager=callback_manager,
    verbose=True,
)

# Agent interactions are scanned
try:
    response = agent.chat("Calculate 2 + 2")
except SecurityException as e:
    print(f"Blocked: {e.result.severity}")
```

### Instrumentation API (v0.10.20+)

```python
from llama_index.core.instrumentation import get_dispatcher
from raxe.sdk.integrations import RaxeSpanHandler

# Create span handler
span_handler = RaxeSpanHandler(
    block_on_threats=False,  # Log only
    scan_llm_inputs=True,
    scan_llm_outputs=True,
)

# Register with root dispatcher
root_dispatcher = get_dispatcher()
root_dispatcher.add_span_handler(span_handler)

# All operations now traced and scanned
```

### Custom Raxe Configuration

```python
from raxe import Raxe
from raxe.sdk.integrations import RaxeLlamaIndexCallback

# Create Raxe with custom configuration
raxe = Raxe(
    api_key="raxe_...",
    telemetry=True,
    l2_enabled=True,  # ML detection
)

# Create callback with custom settings
callback = RaxeLlamaIndexCallback(
    raxe_client=raxe,
    block_on_query_threats=True,
    block_on_response_threats=False,
    scan_agent_actions=True,
)
```

## Configuration Options

### RaxeLlamaIndexCallback

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `raxe_client` | `Raxe` | None | Raxe instance (creates default if None) |
| `block_on_query_threats` | `bool` | False | Block on input threats |
| `block_on_response_threats` | `bool` | False | Block on output threats |
| `scan_retrieved_context` | `bool` | False | Scan RAG context (future) |
| `scan_agent_actions` | `bool` | True | Scan agent/tool operations |

### RaxeQueryEngineCallback

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `raxe_client` | `Raxe` | None | Raxe instance |
| `block_on_threats` | `bool` | False | Block on any threats |

### RaxeAgentCallback

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `raxe_client` | `Raxe` | None | Raxe instance |
| `block_on_threats` | `bool` | False | Block on any threats |
| `scan_tool_outputs` | `bool` | True | Scan tool output values |

### RaxeSpanHandler

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `raxe_client` | `Raxe` | None | Raxe instance |
| `block_on_threats` | `bool` | False | Block on any threats |
| `scan_llm_inputs` | `bool` | True | Scan LLM inputs |
| `scan_llm_outputs` | `bool` | True | Scan LLM outputs |

## Event Types Scanned

| Event Type | on_event_start | on_event_end | Description |
|------------|----------------|--------------|-------------|
| `QUERY` | Query string | Response | User queries |
| `LLM` | Messages/prompts | Response | LLM calls |
| `SYNTHESIZE` | - | Response | Response synthesis |
| `RETRIEVE` | Query | Nodes (future) | RAG retrieval |
| `AGENT_STEP` | Task string | - | Agent operations |
| `FUNCTION_CALL` | Tool input | Tool output | Tool execution |
| `EMBEDDING` | - | - | Not scanned |

## RAG-Specific Considerations

### Current Capabilities

1. **Query Scanning**: All user queries are scanned before retrieval
2. **Response Scanning**: Synthesized responses are scanned for threats
3. **Tool Validation**: Agent tool inputs and outputs are scanned

### Future Enhancements (v0.5.0+)

1. **Retrieved Context Validation**: Scan retrieved chunks for threats
   - Detect poisoned documents in the index
   - Alert on suspicious retrieved content

2. **Prompt Template Validation**: Scan filled prompt templates
   - Detect template injection attempts
   - Validate variable substitutions

3. **Index-Time Scanning**: Scan documents during indexing
   - Prevent malicious content from entering the index
   - Quarantine suspicious documents

## Performance Impact

### Latency Overhead

| Operation | Without RAXE | With RAXE (L1) | With RAXE (L1+L2) |
|-----------|--------------|----------------|-------------------|
| Query scan | - | +5-10ms | +30-50ms |
| Response scan | - | +5-10ms | +30-50ms |
| Tool input | - | +5-10ms | +30-50ms |

### Recommendations

1. **Production**: Use default log-only mode for minimal overhead
2. **High Security**: Enable blocking with L2 for comprehensive protection
3. **Performance Critical**: Use `l2_enabled=False` for fastest scanning

## Dependencies

### Required

- `llama-index-core>=0.10.0` - Core LlamaIndex functionality
- `raxe>=0.3.0` - RAXE scanning SDK

### Optional

- `llama-index>=0.10.0` - Full LlamaIndex installation
- `llama-index-llms-*` - LLM integrations
- `llama-index-embeddings-*` - Embedding integrations

## Version Compatibility

| LlamaIndex Version | Callback API | Instrumentation API |
|--------------------|--------------|---------------------|
| 0.9.x | Not supported | Not supported |
| 0.10.0 - 0.10.19 | Supported | Not available |
| 0.10.20+ | Supported | Supported |
| 0.11.x | Supported | Recommended |

## Troubleshooting

### Common Issues

1. **Import Error**: Ensure `llama-index-core` is installed
   ```bash
   pip install llama-index-core
   ```

2. **Callback Not Triggered**: Verify callback manager is set
   ```python
   Settings.callback_manager = CallbackManager([raxe_callback])
   ```

3. **Blocking Not Working**: Ensure `block_on_*_threats=True`
   ```python
   callback = RaxeLlamaIndexCallback(block_on_query_threats=True)
   ```

### Debugging

Enable RAXE debug logging:
```python
import logging
logging.getLogger("raxe").setLevel(logging.DEBUG)
```

## Security Considerations

### Privacy

- RAXE never logs or transmits actual prompt content
- Only hashes and metadata are sent for telemetry
- Retrieved context is not stored or transmitted

### Best Practices

1. **Default to Log-Only**: Start with monitoring, enable blocking after tuning
2. **Test Thoroughly**: Validate detection before enabling blocking
3. **Handle Exceptions**: Always catch `SecurityException` gracefully
4. **Monitor Metrics**: Use RAXE telemetry to track threats

## Current Status

### Available Now (v0.3.x)

1. `RaxeLlamaIndexCallback` - Basic callback handler
2. `RaxeQueryEngineCallback` - Query engine convenience class
3. `RaxeAgentCallback` - Agent convenience class
4. `RaxeSpanHandler` - Instrumentation API handler (v0.10.20+)
5. Unit tests with mocked Raxe client

### Future Enhancements

1. Retrieved context validation (scan RAG context for threats)
2. Index-time scanning (prevent malicious content in index)
3. Integration tests with real LlamaIndex
4. Performance benchmarks

## Related Documentation

- [LlamaIndex Callbacks](https://docs.llamaindex.ai/en/stable/module_guides/observability/callbacks/)
- [LlamaIndex Instrumentation](https://docs.llamaindex.ai/en/stable/module_guides/observability/instrumentation/)
- [RAXE SDK Documentation](../SDK.md)
- [RAXE Architecture](../architecture.md)
