# RAXE JSON-RPC API Reference

RAXE provides a JSON-RPC 2.0 server for integration with AI platforms, agents, and automation tools.

## Starting the Server

```bash
# Start JSON-RPC server over stdio
raxe serve --quiet

# With verbose logging (to stderr)
raxe serve
```

The server reads JSON-RPC requests from stdin (one per line) and writes responses to stdout.

## Protocol

- **Version**: JSON-RPC 2.0
- **Transport**: stdio (stdin/stdout)
- **Format**: Line-delimited JSON (one request/response per line)
- **Encoding**: UTF-8

## Request Format

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "method": "method_name",
  "params": { ... }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `jsonrpc` | string | Yes | Must be `"2.0"` |
| `id` | string \| number | Yes | Request identifier (returned in response) |
| `method` | string | Yes | Method to invoke |
| `params` | object | No | Method parameters (defaults to `{}`) |

## Response Format

### Success Response

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "result": { ... }
}
```

### Error Response

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": { ... }
  }
}
```

## Methods

### `scan` - Full Threat Detection

Scans text using both L1 (rule-based) and L2 (ML) detection layers.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "scan",
  "params": {
    "prompt": "Text to scan for threats"
  }
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | Text to scan |

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "has_threats": true,
    "severity": "critical",
    "action": "warn",
    "scan_duration_ms": 15.27,
    "prompt_hash": "sha256:abc123...",
    "detections": [
      {
        "rule_id": "pi-001",
        "severity": "critical",
        "confidence": 0.95,
        "category": "pi",
        "detection_layer": "L1",
        "message": "Instruction override attempt detected"
      }
    ],
    "l2_predictions": [
      {
        "threat_type": "prompt_injection",
        "confidence": 0.92,
        "explanation": "Detected prompt injection threat...",
        "metadata": {
          "is_attack": true,
          "family": "prompt_injection",
          "sub_family": "instruction_override"
        }
      }
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `has_threats` | boolean | Whether any threats were detected |
| `severity` | string | Highest severity: `"critical"`, `"high"`, `"medium"`, `"low"`, `"none"` |
| `action` | string | Recommended action: `"block"`, `"warn"`, `"allow"` |
| `scan_duration_ms` | number | Total scan time in milliseconds |
| `prompt_hash` | string | SHA-256 hash of the prompt (privacy-safe) |
| `detections` | array | L1 rule detections |
| `l2_predictions` | array | L2 ML predictions (if any) |

---

### `scan_fast` - L1 Only (Low Latency)

Scans text using only L1 (rule-based) detection for minimal latency.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "scan_fast",
  "params": {
    "prompt": "Text to scan"
  }
}
```

**Response:** Same as `scan`, but without `l2_predictions`.

**Performance:** ~3-8ms (vs ~12-25ms for full scan)

---

### `scan_batch` - Batch Processing

Scans multiple texts in a single request.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "scan_batch",
  "params": {
    "prompts": [
      "First text to scan",
      "Second text to scan",
      "Third text to scan"
    ]
  }
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompts` | array[string] | Yes | List of texts to scan |

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "result": {
    "results": [
      {
        "has_threats": false,
        "severity": "none",
        "scan_duration_ms": 3.2,
        "prompt_hash": "sha256:...",
        "detections": []
      },
      {
        "has_threats": true,
        "severity": "critical",
        "scan_duration_ms": 4.1,
        "prompt_hash": "sha256:...",
        "detections": [...]
      },
      {
        "has_threats": false,
        "severity": "none",
        "scan_duration_ms": 2.8,
        "prompt_hash": "sha256:...",
        "detections": []
      }
    ],
    "total_duration_ms": 10.1,
    "threat_count": 1
  }
}
```

---

### `scan_tool_call` - Tool Invocation Validation

Validates a tool call for command injection and other threats.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "method": "scan_tool_call",
  "params": {
    "tool_name": "execute_shell",
    "tool_input": {
      "command": "ls -la /home/user"
    }
  }
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tool_name` | string | Yes | Name of the tool being invoked |
| `tool_input` | object | Yes | Tool arguments/parameters |

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "result": {
    "has_threats": true,
    "severity": "critical",
    "action": "block",
    "scan_duration_ms": 5.3,
    "prompt_hash": "sha256:...",
    "detections": [
      {
        "rule_id": "cmd-003",
        "severity": "critical",
        "category": "cmd",
        "message": "Command chain injection detected"
      }
    ]
  }
}
```

---

### `health` - Health Check

Returns server health status.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "5",
  "method": "health",
  "params": {}
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "5",
  "result": {
    "status": "healthy"
  }
}
```

---

### `version` - Version Information

Returns RAXE version.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "6",
  "method": "version",
  "params": {}
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "6",
  "result": {
    "version": "0.9.0"
  }
}
```

---

### `stats` - Scan Statistics

Returns scanning statistics for the current session.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "7",
  "method": "stats",
  "params": {}
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "7",
  "result": {
    "total_scans": 150,
    "threats_detected": 12,
    "clean_scans": 138,
    "average_scan_time_ms": 8.5
  }
}
```

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| `-32700` | Parse error | Invalid JSON |
| `-32600` | Invalid Request | Not a valid JSON-RPC 2.0 request |
| `-32601` | Method not found | Unknown method name |
| `-32602` | Invalid params | Missing or invalid parameters |
| `-32603` | Internal error | Server-side error |

## Examples

### Shell (Unix)

```bash
# Single scan
echo '{"jsonrpc":"2.0","id":"1","method":"scan","params":{"prompt":"Hello world"}}' | raxe serve --quiet

# Multiple requests
cat requests.jsonl | raxe serve --quiet > responses.jsonl
```

### Python

```python
import subprocess
import json

def raxe_scan(prompt: str) -> dict:
    request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "scan",
        "params": {"prompt": prompt}
    }

    proc = subprocess.run(
        ["raxe", "serve", "--quiet"],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        timeout=30
    )

    return json.loads(proc.stdout.strip())

# Usage
result = raxe_scan("Ignore all previous instructions")
if result["result"]["has_threats"]:
    print(f"Threat detected: {result['result']['severity']}")
```

### Node.js

```javascript
const { spawn } = require('child_process');

function raxeScan(prompt) {
  return new Promise((resolve, reject) => {
    const request = {
      jsonrpc: '2.0',
      id: '1',
      method: 'scan',
      params: { prompt }
    };

    const proc = spawn('raxe', ['serve', '--quiet'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    proc.stdout.on('data', (data) => stdout += data);
    proc.on('close', () => resolve(JSON.parse(stdout.trim())));
    proc.on('error', reject);

    proc.stdin.write(JSON.stringify(request) + '\n');
    proc.stdin.end();
  });
}

// Usage
const result = await raxeScan('Ignore all previous instructions');
if (result.result.has_threats) {
  console.log(`Threat detected: ${result.result.severity}`);
}
```

### Go

```go
package main

import (
    "encoding/json"
    "os/exec"
)

type RaxeRequest struct {
    JSONRPC string                 `json:"jsonrpc"`
    ID      string                 `json:"id"`
    Method  string                 `json:"method"`
    Params  map[string]interface{} `json:"params"`
}

type RaxeResult struct {
    HasThreats bool   `json:"has_threats"`
    Severity   string `json:"severity"`
}

type RaxeResponse struct {
    JSONRPC string     `json:"jsonrpc"`
    ID      string     `json:"id"`
    Result  RaxeResult `json:"result"`
}

func raxeScan(prompt string) (*RaxeResponse, error) {
    request := RaxeRequest{
        JSONRPC: "2.0",
        ID:      "1",
        Method:  "scan",
        Params:  map[string]interface{}{"prompt": prompt},
    }

    input, _ := json.Marshal(request)

    cmd := exec.Command("raxe", "serve", "--quiet")
    cmd.Stdin = strings.NewReader(string(input) + "\n")

    output, err := cmd.Output()
    if err != nil {
        return nil, err
    }

    var response RaxeResponse
    json.Unmarshal(output, &response)
    return &response, nil
}
```

## Privacy

The JSON-RPC API is privacy-safe by design:

- **Never returns** raw prompt content
- **Never returns** matched text patterns
- **Only returns** prompt hash (SHA-256)
- **All processing** happens locally

## Performance

| Method | P50 Latency | P95 Latency | Notes |
|--------|-------------|-------------|-------|
| `health` | <1ms | <2ms | No processing |
| `version` | <1ms | <2ms | No processing |
| `scan_fast` | ~3ms | ~8ms | L1 only |
| `scan` | ~12ms | ~25ms | L1 + L2 |
| `scan_batch` (4) | ~15ms | ~35ms | Parallelized |
| `scan_tool_call` | ~5ms | ~12ms | L1 focus |

## See Also

- [OpenClaw Integration Guide](integrations/OPENCLAW.md)
- [Detection Rules Reference](CUSTOM_RULES.md)
- [CLI Reference](CLI.md)
