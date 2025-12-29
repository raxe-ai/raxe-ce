# AutoGen Integration Guide

This guide explains how to integrate RAXE security scanning with Microsoft AutoGen (pyautogen) for multi-agent conversations.

## Overview

RAXE provides `RaxeConversationGuard` for automatic security scanning of AutoGen multi-agent conversations. The integration uses AutoGen's hook system to intercept messages without modifying your agent code.

**Key Features:**
- Hook-based message interception (no code changes to agents)
- Configurable blocking modes (log-only, block-on-threat, etc.)
- Multi-agent conversation awareness
- Function/tool call scanning
- Privacy-preserving logging

**Requirements:**
- pyautogen >= 0.2.0 or autogen-agentchat ~= 0.2
- RAXE SDK

## Quick Start

```python
from autogen import AssistantAgent, UserProxyAgent
from raxe import Raxe
from raxe.sdk.integrations import RaxeConversationGuard

# Create RAXE client
raxe = Raxe()

# Create conversation guard (default: log-only mode)
guard = RaxeConversationGuard(raxe)

# Create AutoGen agents
llm_config = {"model": "gpt-4", "api_key": "..."}
assistant = AssistantAgent("assistant", llm_config=llm_config)
user = UserProxyAgent("user", code_execution_config={"use_docker": False})

# Register agents with guard
guard.register(assistant)
guard.register(user)

# Start conversation - all messages are automatically scanned
user.initiate_chat(assistant, message="Hello! How are you?")
```

## Configuration Options

### Scan Modes

The `ScanMode` enum controls how detected threats are handled:

| Mode | Description | Use Case |
|------|-------------|----------|
| `LOG_ONLY` | Log threats, allow all messages (default) | Development, monitoring |
| `BLOCK_ON_THREAT` | Block any detected threat | High-security environments |
| `BLOCK_ON_HIGH` | Block HIGH and CRITICAL severity | Balanced security |
| `BLOCK_ON_CRITICAL` | Block only CRITICAL severity | Minimal intervention |

```python
from raxe.sdk.integrations import AgentScannerConfig, ScanMode

# Block on HIGH or CRITICAL threats
config = AgentScannerConfig(mode=ScanMode.BLOCK_ON_HIGH)
guard = RaxeConversationGuard(raxe, config=config)
```

### Message Type Scanning

Control which message types are scanned:

```python
config = AgentScannerConfig(
    scan_human_input=True,      # Messages from humans
    scan_agent_messages=True,   # Agent-to-agent messages
    scan_agent_responses=True,  # Final responses to humans
    scan_function_calls=True,   # Function/tool calls
    scan_function_results=True, # Function/tool results
    scan_system_messages=False, # System prompts (disabled by default)
)
```

### Callbacks

Define custom handlers for threats and blocks:

```python
def on_threat_detected(message: str, result):
    # Custom threat handling
    print(f"Threat detected: {result.severity}")
    # Send to monitoring system, etc.

def on_message_blocked(message: str, result):
    # Custom blocking handler
    print(f"Message blocked: {result.severity}")
    # Alert admin, etc.

config = AgentScannerConfig(
    mode=ScanMode.BLOCK_ON_HIGH,
    on_threat=on_threat_detected,
    on_block=on_message_blocked,
)
```

### Confidence Threshold

Set minimum confidence for threat reporting:

```python
config = AgentScannerConfig(
    confidence_threshold=0.8,  # Only report high-confidence threats
)
```

## Multi-Agent Scenarios

### Register Multiple Agents

```python
# Create all agents
researcher = AssistantAgent("researcher", llm_config=llm_config)
writer = AssistantAgent("writer", llm_config=llm_config)
critic = AssistantAgent("critic", llm_config=llm_config)
user = UserProxyAgent("user")

# Register all at once
guard.register_all(researcher, writer, critic, user)

# Or register individually
guard.register(researcher)
guard.register(writer)
guard.register(critic)
guard.register(user)
```

### GroupChat

```python
from autogen import GroupChat, GroupChatManager

# Create agents
agents = [researcher, writer, critic]

# Register each agent
for agent in agents:
    guard.register(agent)

# Create group chat
groupchat = GroupChat(agents=agents, messages=[], max_round=10)
manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

# Register manager too
guard.register(manager)

# Start chat
user.initiate_chat(manager, message="Research and write about AI safety")
```

## Advanced Usage

### Manual Scanning

Scan text outside the hook flow:

```python
# Validate user input before starting chat
user_input = get_user_input()
result = guard.scan_manual(
    user_input,
    message_type=MessageType.HUMAN_INPUT,
    sender_name="user"
)

if result.should_block:
    print("Cannot proceed - security threat detected")
else:
    user.initiate_chat(assistant, message=user_input)
```

### Handling SecurityException

When blocking is enabled, `SecurityException` is raised:

```python
from raxe.sdk.exceptions import SecurityException

try:
    user.initiate_chat(assistant, message="Malicious prompt here")
except SecurityException as e:
    print(f"Blocked: {e.result.severity}")
    print(f"Detections: {e.result.total_detections}")
    # Handle blocked message appropriately
```

### Checking Registration Status

```python
# Check which agents are registered
print(f"Registered agents: {guard.registered_agents}")

# Check if specific agent is registered
if "assistant" in guard.registered_agents:
    print("Assistant is protected")
```

### Unregistering Agents

```python
# Unregister an agent (removes from tracking, hooks remain)
guard.unregister(assistant)
```

## Architecture

### Hook System

`RaxeConversationGuard` registers two hooks with each agent:

1. **`process_message_before_send`**: Scans outgoing messages before sending
2. **`process_last_received_message`**: Scans incoming messages before reply

### Message Flow

```
User Input
    |
    v
+-------------------+
| UserProxyAgent    |
| (hooks: before_   |
|  send, received)  |
+-------------------+
    |
    v (scanned)
+-------------------+
| AssistantAgent    |
| (hooks: before_   |
|  send, received)  |
+-------------------+
    |
    v (scanned)
Response to User
```

### AgentScanner Composition

`RaxeConversationGuard` uses the `AgentScanner` base class via composition:

```python
class RaxeConversationGuard:
    def __init__(self, raxe: Raxe, config: AgentScannerConfig | None = None):
        self._scanner = AgentScanner(raxe, config or AgentScannerConfig())

    def scan_manual(self, text: str, **kwargs) -> AgentScanResult:
        return self._scanner.scan_message(text, **kwargs)
```

This pattern allows:
- Reuse of core scanning logic across frameworks
- Consistent configuration options
- Framework-specific hook implementations

## Best Practices

### 1. Start with LOG_ONLY Mode

Begin with monitoring to understand threat patterns before enabling blocking:

```python
# Development/initial deployment
config = AgentScannerConfig(mode=ScanMode.LOG_ONLY)
guard = RaxeConversationGuard(raxe, config=config)
```

### 2. Use Callbacks for Alerting

Set up callbacks to integrate with your monitoring:

```python
import logging
logger = logging.getLogger(__name__)

def on_threat(message, result):
    logger.warning(
        "agent_threat_detected",
        extra={
            "severity": result.severity,
            "detection_count": result.total_detections,
        }
    )

config = AgentScannerConfig(on_threat=on_threat)
```

### 3. Register All Conversation Participants

Ensure all agents in a conversation are registered:

```python
# Bad: Only registering some agents
guard.register(assistant)  # user not registered!

# Good: Register all agents
guard.register(assistant)
guard.register(user)
guard.register(manager)  # If using GroupChat
```

### 4. Handle Blocking Gracefully

When using blocking modes, catch and handle exceptions:

```python
from raxe.sdk.exceptions import SecurityException

try:
    user.initiate_chat(assistant, message=user_input)
except SecurityException as e:
    # Log the incident
    log_security_event(e)
    # Provide user feedback
    print("Your message was blocked for security reasons.")
    # Optionally allow retry with modified input
```

### 5. Consider Performance

For latency-sensitive applications:

```python
config = AgentScannerConfig(
    # Disable scanning of less critical message types
    scan_function_results=False,
    scan_system_messages=False,
    # Higher threshold = fewer scans flagged
    confidence_threshold=0.7,
)
```

## Troubleshooting

### Agent Not Being Scanned

**Problem**: Messages from an agent are not being scanned.

**Solution**: Ensure the agent is registered:
```python
print(guard.registered_agents)  # Check registration
guard.register(agent)           # Register if missing
```

### TypeError on Registration

**Problem**: `TypeError: Expected ConversableAgent`

**Solution**: Ensure you're passing an AutoGen ConversableAgent or subclass:
```python
# Wrong
guard.register("my_agent")

# Correct
guard.register(AssistantAgent("my_agent", llm_config=config))
```

### Blocking Not Working

**Problem**: Threats detected but not blocked.

**Solution**: Check the scan mode:
```python
print(guard.config.mode)  # Should be BLOCK_ON_* not LOG_ONLY

# Update mode if needed
config = AgentScannerConfig(mode=ScanMode.BLOCK_ON_THREAT)
guard = RaxeConversationGuard(raxe, config=config)
```

## API Reference

### RaxeConversationGuard

```python
class RaxeConversationGuard:
    def __init__(
        self,
        raxe: Raxe,
        config: AgentScannerConfig | None = None,
    ) -> None: ...

    @property
    def config(self) -> AgentScannerConfig: ...

    @property
    def registered_agents(self) -> set[str]: ...

    def register(self, agent: ConversableAgent) -> None: ...

    def register_all(self, *agents: ConversableAgent) -> None: ...

    def unregister(self, agent: ConversableAgent) -> None: ...

    def scan_manual(
        self,
        text: str,
        *,
        message_type: MessageType = MessageType.AGENT_TO_AGENT,
        sender_name: str | None = None,
        receiver_name: str | None = None,
    ) -> AgentScanResult: ...
```

### AgentScannerConfig

```python
@dataclass
class AgentScannerConfig:
    mode: ScanMode = ScanMode.LOG_ONLY
    scan_human_input: bool = True
    scan_agent_messages: bool = True
    scan_agent_responses: bool = True
    scan_function_calls: bool = True
    scan_function_results: bool = True
    scan_system_messages: bool = False
    on_threat: Callable[[str, ScanPipelineResult], None] | None = None
    on_block: Callable[[str, ScanPipelineResult], None] | None = None
    severity_threshold: str = "LOW"
    confidence_threshold: float = 0.5
```

### ScanMode

```python
class ScanMode(str, Enum):
    LOG_ONLY = "log_only"
    BLOCK_ON_THREAT = "block_on_threat"
    BLOCK_ON_HIGH = "block_on_high"
    BLOCK_ON_CRITICAL = "block_on_critical"
```

### MessageType

```python
class MessageType(str, Enum):
    HUMAN_INPUT = "human_input"
    AGENT_TO_AGENT = "agent_to_agent"
    AGENT_RESPONSE = "agent_response"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"
    SYSTEM = "system"
```

## Version Compatibility

| AutoGen Version | RAXE Integration |
|-----------------|------------------|
| pyautogen 0.2.x | Fully supported |
| autogen-agentchat ~= 0.2 | Fully supported |
| AG2 (fork) | Compatible via 0.2 API |
| AutoGen 0.4.x | Migration may be needed |

**Note**: Microsoft no longer maintains pyautogen on PyPI after 0.2.34. For continued updates, use `autogen-agentchat~=0.2` from Microsoft or the AG2 fork.
