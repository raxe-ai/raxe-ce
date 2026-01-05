# AI Agent Security Model

## Think-Time Security for Autonomous Agents

RAXE provides **think-time security** — real-time threat detection during AI agent inference, before action execution. This document explains the agent security model and how RAXE protects autonomous AI systems.

## Why AI Agents Need Runtime Security

AI agents aren't just LLMs — they're **autonomous systems** that:

| Capability | Risk |
|------------|------|
| **Execute tools** | Shell commands, APIs, databases at machine speed |
| **Maintain memory** | Persistent state vulnerable to poisoning |
| **Coordinate** | Multi-agent workflows propagate attacks |
| **Act autonomously** | Seconds from compromise to action |

### Training-Time Safety Isn't Enough

- **Static guardrails don't adapt** — Novel attacks bypass trained defenses
- **Indirect injection bypasses input filters** — Malicious content in retrieved documents
- **Multi-step workflows evade single-turn detection** — Attacks spread across agent interactions

## RAXE Agent Protection

### Scan Points

RAXE scans at multiple points where threats can enter or propagate:

| Scan Type | Description | Threats Detected | Status |
|-----------|-------------|------------------|--------|
| `PROMPT` | User input to agents | Direct prompt injection | Available |
| `RESPONSE` | LLM outputs | Jailbreak outputs, PII leakage | Available |
| `TOOL_CALL` | Tool invocation requests | Dangerous tool abuse | Available |
| `TOOL_RESULT` | Tool execution results | Injection via tool output | Available |
| `AGENT_ACTION` | Agent reasoning steps | Compromised reasoning | Available |
| `RAG_CONTEXT` | Retrieved documents | Indirect injection via RAG | Available |
| `SYSTEM_PROMPT` | System instructions | System prompt leakage | Coming soon |
| `MEMORY_CONTENT` | Persisted memory | Memory poisoning attacks | Coming soon |

### AgentScanner Architecture

```python
from raxe.sdk.agent_scanner import AgentScanner, AgentScannerConfig

config = AgentScannerConfig(
    scan_prompts=True,
    scan_responses=True,
    scan_tool_calls=True,
    scan_tool_results=True,
    scan_agent_actions=True,
    scan_rag_context=True,
    scan_memory_content=True,
    on_threat="log",  # "log" | "block"
)

scanner = AgentScanner(raxe, config)
```

### Tool Validation

RAXE validates tool usage before execution:

```python
from raxe.sdk.agent_scanner import ToolPolicy

# Block dangerous tools
policy = ToolPolicy.block_tools(
    "shell",
    "execute_command",
    "file_write",
    "code_interpreter",
)

# Or allowlist safe tools
policy = ToolPolicy.allow_only(
    "search",
    "calculator",
    "weather",
)
```

### Built-in Dangerous Tool Detection

RAXE includes detection for commonly abused tools:

- `shell` / `bash` / `terminal`
- `execute_command` / `run_code`
- `file_write` / `file_delete`
- `code_interpreter`
- `sql_query` / `database_write`
- `http_request` (to internal networks)

## OWASP Alignment

RAXE's capabilities align with the [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications/) (December 2025):

| OWASP Risk | Description | RAXE Capability |
|------------|-------------|-----------------|
| **ASI01: Excessive Tool Permissions** | Agents given dangerous tool access | ToolPolicy allowlist/blocklist |
| **ASI02: Tool Output Exploitation** | Malicious content in tool results | Tool result scanning |
| **ASI03: Identity & Privilege Abuse** | Agents impersonating users | Tool validation modes |
| **ASI04: Memory Manipulation** | Poisoning agent memory | Memory content scanning |
| **ASI05: Model Interaction Manipulation** | Direct/indirect prompt injection | Dual-layer L1+L2 detection |
| **ASI06: Prompt Injection (Multi-Agent)** | Attacks across agent boundaries | Agent-to-agent scanning, trace correlation |
| **ASI07: Human-Agent Trust Exploitation** | Agents manipulating users | Threat severity + confidence scoring |
| **ASI08: Cascading Failures** | Failures propagating through agents | Trace-aware detection, early blocking |
| **ASI09: Insufficient Logging** | Missing audit trails | Full telemetry with privacy preservation |
| **ASI10: Rogue Agents** | Agents acting outside parameters | Behavioral anomaly detection (L2 ML) |

## Agent Framework Integration

### LangChain

```python
from raxe import Raxe
from raxe.sdk.integrations import create_langchain_handler
from langchain.agents import create_react_agent

handler = create_langchain_handler(
    Raxe(),
    block_on_threats=False,  # Log-only by default
    scan_tools=True,
)

agent = create_react_agent(llm, tools, callbacks=[handler])
```

### CrewAI (Multi-Agent)

```python
from raxe import Raxe
from raxe.sdk.integrations import create_crewai_guard

guard = create_crewai_guard(
    Raxe(),
    scan_agent_thoughts=True,
    scan_task_outputs=True,
)

protected_crew = guard.protect(crew)
result = protected_crew.kickoff()
```

### AutoGen (Conversational)

```python
from raxe import Raxe
from raxe.sdk.integrations import create_autogen_guard

guard = create_autogen_guard(
    Raxe(),
    scan_messages=True,
    scan_function_calls=True,
)

guard.register(agent)
```

### LlamaIndex (RAG + Agents)

```python
from raxe import Raxe
from raxe.sdk.integrations import create_llamaindex_callback

callback = create_llamaindex_callback(
    Raxe(),
    scan_retrieval=True,
    scan_agent_actions=True,
)

agent = create_react_agent(llm, tools, callbacks=[callback])
```

## Detection Architecture

### Dual-Layer Detection

```
Input → L1 (Rules) → L2 (ML) → Decision
         ~1ms        ~9ms      ~10ms total
```

**L1: 460+ Pattern Rules**
- Regex-based detection for known attack patterns
- ~1ms latency
- Covers: prompt injection, jailbreaks, PII, encoding tricks

**L2: 5-Head ML Ensemble**
- On-device classification
- Multiple heads vote on threat categories
- Catches novel and obfuscated attacks
- No cloud inference required

### Trace Correlation

RAXE correlates threats across agent workflow steps:

```python
# Trace-aware scanning
scanner.scan_prompt(
    prompt,
    trace_id="agent-session-123",
    step_id="step-5",
)
```

This enables:
- Detection of multi-step attacks
- Attribution of threats to specific workflow points
- Correlation of related detections

## Best Practices

### 1. Start with Log-Only Mode

```python
# Safe default: observe before blocking
config = AgentScannerConfig(on_threat="log")
```

### 2. Use Tool Policies

```python
# Restrict dangerous tool access
policy = ToolPolicy.block_tools("shell", "execute_command")
```

### 3. Scan All Agent Communication

Enable comprehensive scanning:

```python
config = AgentScannerConfig(
    scan_prompts=True,
    scan_responses=True,
    scan_tool_calls=True,
    scan_tool_results=True,
    scan_agent_actions=True,
    scan_rag_context=True,
    scan_memory_content=True,
)
```

### 4. Handle Blocks Gracefully

```python
from raxe.sdk.exceptions import SecurityException

try:
    result = agent.invoke(input)
except SecurityException as e:
    # Return safe fallback response
    return "I cannot process that request."
```

### 5. Monitor Detection Metrics

```python
stats = scanner.stats
print(f"Total scans: {stats['total_scans']}")
print(f"Threats detected: {stats['threats_detected']}")
print(f"Blocks: {stats['blocks']}")
```

## Privacy Guarantees

RAXE's agent protection maintains privacy:

- **100% local processing** — All scanning happens on-device
- **No prompt transmission** — Raw prompts never leave your infrastructure
- **Anonymized telemetry** — Only detection metadata (rule IDs, severity) if opted in
- **Explainable detections** — Every threat attributable to specific rules or ML heads
