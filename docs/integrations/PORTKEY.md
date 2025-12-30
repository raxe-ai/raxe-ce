# Portkey AI Gateway Integration

RAXE integration with [Portkey AI Gateway](https://portkey.ai) for LLM security scanning.

## Overview

Portkey is an AI gateway that routes requests to 200+ LLMs with built-in observability,
caching, and guardrails. RAXE integrates as a custom webhook guardrail.

## Integration Patterns

### 1. Webhook Guardrail (Portkey → RAXE)

Portkey calls RAXE webhook for input/output validation.

```python
from fastapi import FastAPI, Request
from raxe import Raxe
from raxe.sdk.integrations.portkey import RaxePortkeyWebhook

app = FastAPI()
webhook = RaxePortkeyWebhook(Raxe())

@app.post("/raxe/guardrail")
async def guardrail(request: Request):
    return webhook.handle_request(await request.json())
```

Portkey config:
```json
{
  "beforeRequestHooks": [{
    "id": "raxe-security",
    "type": "guardrail",
    "checks": [{
      "id": "default.webhook",
      "parameters": {
        "webhookURL": "https://your-endpoint/raxe/guardrail"
      }
    }],
    "deny": true
  }]
}
```

### 2. Client Wrapper (RAXE → Portkey)

Scan locally before Portkey sends to LLM.

```python
from portkey_ai import Portkey
from raxe.sdk.integrations.portkey import RaxePortkeyGuard

guard = RaxePortkeyGuard(block_on_threats=True)
client = guard.wrap_client(Portkey(api_key="..."))

response = client.chat.completions.create(
    messages=[{"role": "user", "content": "Hello"}],
    model="gpt-4"
)
```

## API Reference

### RaxePortkeyWebhook

Webhook handler for Portkey guardrail requests.

**Methods:**
- `handle_request(data: dict) -> dict` - Handle sync request
- `handle_request_async(data: dict) -> dict` - Handle async request

**Response Format:**
```json
{
  "verdict": true,  // true = pass, false = block
  "data": {
    "reason": "...",
    "severity": "HIGH",
    "detections": 1,
    "rule_ids": ["pi-001"],
    "scan_duration_ms": 5.2
  }
}
```

### RaxePortkeyGuard

Client-side guard for Portkey SDK.

**Methods:**
- `wrap_client(client) -> client` - Wrap Portkey client
- `scan_and_call(fn, messages=...) -> result` - Scan and call function
- `reset_stats()` - Reset statistics

### PortkeyGuardConfig

Configuration for both webhook and guard.

**Fields:**
- `block_on_threats: bool = False` - Return false verdict on threats
- `block_severity_threshold: str = "HIGH"` - Minimum severity to block
- `scan_inputs: bool = True` - Scan input messages
- `scan_outputs: bool = True` - Scan responses
- `fail_open: bool = True` - Pass on errors (Portkey default)

## Testing

```bash
pytest tests/unit/sdk/integrations/test_portkey.py -v
```

## Files

- `src/raxe/sdk/integrations/portkey.py` - Implementation
- `tests/unit/sdk/integrations/test_portkey.py` - Tests (37 tests)
- `docs/integrations/PORTKEY.md` - This file

## Sources

- [Portkey Docs](https://portkey.ai/docs)
- [Portkey Gateway GitHub](https://github.com/Portkey-AI/gateway)
- [Bring Your Own Guardrails](https://portkey.ai/docs/integrations/guardrails/bring-your-own-guardrails)
