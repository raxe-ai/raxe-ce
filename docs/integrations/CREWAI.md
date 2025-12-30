# CrewAI Integration

RAXE integration with [CrewAI](https://crewai.com) for protecting multi-agent workflows.

## Installation

```bash
pip install raxe crewai
```

## Quick Start

```python
from crewai import Crew, Agent, Task
from raxe import Raxe
from raxe.sdk.integrations import RaxeCrewGuard

# Create guard (default: log-only mode)
guard = RaxeCrewGuard(Raxe())

# Use callbacks with your crew
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    step_callback=guard.step_callback,
    task_callback=guard.task_callback,
)

result = crew.kickoff()
```

## Blocking Mode

```python
from raxe.sdk.integrations import RaxeCrewGuard, CrewGuardConfig
from raxe.sdk.agent_scanner import ScanMode

# Enable blocking on high-severity threats
config = CrewGuardConfig(mode=ScanMode.BLOCK_ON_HIGH)
guard = RaxeCrewGuard(Raxe(), config=config)
```

## Configuration

```python
from raxe.sdk.integrations.crewai import CrewGuardConfig
from raxe.sdk.agent_scanner import ScanMode

config = CrewGuardConfig(
    # Blocking mode
    mode=ScanMode.BLOCK_ON_HIGH,  # BLOCK_ON_THREAT, BLOCK_ON_HIGH, BLOCK_ON_CRITICAL

    # What to scan
    scan_step_outputs=True,
    scan_task_outputs=True,
    scan_tool_inputs=True,
    scan_tool_outputs=True,
    scan_agent_thoughts=True,

    # Tool wrapping
    wrap_tools=True,  # Auto-wrap tools for scanning
)

guard = RaxeCrewGuard(Raxe(), config=config)
```

## Tool Wrapping

```python
# Wrap tools for automatic scanning
guard = RaxeCrewGuard(Raxe())

# Wrap individual tools
wrapped_tool = guard.wrap_tool(my_tool)

# Or wrap all tools
wrapped_tools = guard.wrap_tools([tool1, tool2, tool3])
```

## Callbacks with Crew

```python
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    step_callback=guard.step_callback,   # Scans each agent step
    task_callback=guard.task_callback,   # Scans task outputs
)
```

## Available Modes

| Mode | Description |
|------|-------------|
| `ScanMode.LOG_ONLY` | Log threats, allow execution (default) |
| `ScanMode.BLOCK_ON_THREAT` | Block any detected threat |
| `ScanMode.BLOCK_ON_HIGH` | Block HIGH and CRITICAL severity |
| `ScanMode.BLOCK_ON_CRITICAL` | Block only CRITICAL severity |

## Error Handling

```python
from raxe.sdk.exceptions import SecurityException

try:
    result = crew.kickoff()
except SecurityException as e:
    print("Crew execution blocked for security reasons")
```

## Statistics

```python
# Check scan stats
print(guard.stats.to_dict())
# {'total_scans': 50, 'threats_detected': 2, 'blocked': 1}

# Reset stats for new run
guard.reset_stats()
```

## Files

- `src/raxe/sdk/integrations/crewai.py` - Implementation
- `tests/unit/sdk/integrations/test_crewai.py` - Unit tests

## More Information

- [Full Documentation](https://docs.raxe.ai/integrations/crewai)
- [CrewAI Docs](https://docs.crewai.com)
