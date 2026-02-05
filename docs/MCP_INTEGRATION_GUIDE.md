# MCP Integration Guide

RAXE provides comprehensive Model Context Protocol (MCP) integration for securing AI assistant workflows. This guide covers both integration modes:

1. **MCP Server** - RAXE as a tool provider
2. **MCP Security Gateway** - RAXE as a traffic inspector

## Installation

```bash
pip install raxe[mcp]
```

## Quick Start

### Option 1: MCP Server (RAXE as Tool Provider)

Add RAXE's threat detection tools to your AI assistant:

```bash
raxe mcp serve
```

The MCP server exposes these tools:
- `scan_prompt` - Scan text for security threats
- `list_threat_families` - List available threat categories
- `get_rule_info` - Get details about specific detection rules

### Option 2: MCP Security Gateway (Recommended)

Protect ANY MCP server by routing traffic through RAXE:

```bash
raxe mcp gateway -u "npx @modelcontextprotocol/server-filesystem /tmp"
```

The gateway transparently scans:
- Tool call arguments
- Tool responses
- Resources
- Prompt templates

---

## MCP Server Mode

### Claude Desktop Configuration

Add to `~/.config/claude/claude_desktop_config.json` (macOS/Linux) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "raxe-security": {
      "command": "raxe",
      "args": ["mcp", "serve"]
    }
  }
}
```

### Cursor Configuration

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "raxe-security": {
      "command": "raxe",
      "args": ["mcp", "serve"]
    }
  }
}
```

### Available Tools

#### scan_prompt

Scan text for security threats including prompt injection, jailbreak attempts, and data exfiltration.

**Input:**
```json
{
  "text": "User input to scan",
  "context": "Optional context about the text source"
}
```

**Output:**
```
✓ SAFE: No threats detected

Scan completed in 5.2ms
  L1 (rules): 2.1ms
  L2 (ML):    3.1ms
```

Or if threats detected:
```
⚠ THREATS DETECTED

━━━ L1 Rule Detections (2) ━━━
  [HIGH] pi-001 (PI)
      Category: Prompt Injection
      Message: Detected attempt to override instructions
      Confidence: 95%

━━━ Summary ━━━
  Total threats: 2 L1 + 0 L2
  Scan time: 8.5ms (L1: 3.2ms, L2: 5.3ms)
```

#### list_threat_families

List available threat detection families:

- **PI** - Prompt Injection
- **JB** - Jailbreak
- **DE** - Data Exfiltration
- **RP** - Role Play manipulation
- **CS** - Context Switching
- **SE** - Social Engineering
- **TA** - Token Abuse
- **CI** - Code Injection

#### get_rule_info

Get detailed information about a specific detection rule:

**Input:**
```json
{
  "rule_id": "pi-001"
}
```

**Output:**
```
Rule: pi-001
Family: PI
Severity: HIGH
Description: Detects attempts to override or ignore previous instructions
```

### Python API

```python
from raxe.mcp import create_server

# Create and run server
server = create_server(verbose=True)
await server.run_async()
```

---

## MCP Security Gateway Mode

The MCP Security Gateway acts as a transparent proxy between MCP clients (like Claude Desktop) and MCP servers. It intercepts ALL traffic and scans for threats.

### Architecture

```
┌─────────────────────┐
│   MCP Host          │
│  (Claude Desktop)   │
└─────────┬───────────┘
          │ JSON-RPC
          ▼
┌─────────────────────────────────┐
│   RAXE MCP Security Gateway     │
├─────────────────────────────────┤
│ • Intercept tool calls          │
│ • Scan tool arguments (L1+L2)   │
│ • Scan tool responses           │
│ • Scan resources                │
│ • Scan prompt templates         │
│ • Block/log per policy          │
│ • Rate limiting                 │
└─────────┬───────────────────────┘
          │ JSON-RPC
          ▼
┌─────────────────────┐
│   MCP Server(s)     │
│  (filesystem, git,  │
│   database, etc.)   │
└─────────────────────┘
```

### Basic Usage

```bash
# Protect a filesystem server
raxe mcp gateway -u "npx @modelcontextprotocol/server-filesystem /tmp"

# Protect a git server with blocking enabled
raxe mcp gateway -u "npx @modelcontextprotocol/server-git" --on-threat block

# Use a config file for multiple servers
raxe mcp gateway --config mcp-security.yaml
```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "protected-filesystem": {
      "command": "raxe",
      "args": [
        "mcp", "gateway",
        "-u", "npx @modelcontextprotocol/server-filesystem /tmp"
      ]
    }
  }
}
```

### Configuration File

Generate a sample config:
```bash
raxe mcp generate-config
```

This creates `mcp-security.yaml`:

```yaml
# RAXE MCP Security Gateway Configuration

gateway:
  listen: stdio
  default_policy:
    on_threat: log        # log, block, or warn
    severity_threshold: HIGH  # LOW, MEDIUM, HIGH, CRITICAL
    rate_limit_rpm: 60

  telemetry_enabled: true
  l2_enabled: true

upstreams:
  - name: filesystem
    command: npx
    args:
      - "@modelcontextprotocol/server-filesystem"
      - "/path/to/safe/directory"
    scan_tool_calls: true
    scan_tool_responses: true
    scan_resources: true

  - name: git
    command: npx
    args:
      - "@modelcontextprotocol/server-git"
    scan_tool_calls: true
    scan_tool_responses: true
    # Override policy for this upstream
    policy:
      on_threat: block
      severity_threshold: MEDIUM
```

### Policy Options

| Option | Values | Description |
|--------|--------|-------------|
| `on_threat` | `log`, `block`, `warn` | Action when threat detected |
| `severity_threshold` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | Minimum severity to trigger action |
| `rate_limit_rpm` | `0-9999` | Requests per minute (0 = unlimited) |

### Security Features

The gateway includes several security hardening features:

| Feature | Description |
|---------|-------------|
| **Rate Limiting** | Per-client rate limiting with LRU eviction (max 10,000 tracked clients) |
| **Message Size Limits** | 10MB max message size with chunked discard for DoS protection |
| **Error Recovery** | Automatic recovery from parsing/handler errors without gateway crash |
| **Sanitized Errors** | Internal error details logged but not exposed to clients |
| **Request Timeouts** | 30-second timeout for upstream requests |

### Scanning Points

| Point | What's Scanned | Threats Detected |
|-------|---------------|------------------|
| Tool calls | Arguments, parameters | Command injection, prompt injection |
| Tool responses | Output content | Data exfiltration, indirect injection |
| Resources | File/resource content | Hidden instructions, sensitive data |
| Prompts | Template content | Injection payloads, jailbreak attempts |
| Sampling | System prompts | Context manipulation |

### Python API

```python
from raxe.mcp import create_gateway, GatewayConfig, UpstreamConfig

# Load from config file
config = GatewayConfig.load("mcp-security.yaml")

# Or create programmatically
config = GatewayConfig(
    l2_enabled=True,
    upstreams=[
        UpstreamConfig(
            name="filesystem",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", "/tmp"],
        )
    ]
)

# Create and run gateway
gateway = create_gateway(config)
await gateway.run()

# Get statistics
stats = gateway.get_stats()
print(f"Requests blocked: {stats['requests_blocked']}")
print(f"Threats detected: {stats['threats_detected']}")
```

---

## Security Auditing

Audit your existing MCP configuration for security issues:

```bash
raxe mcp audit ~/.config/claude/claude_desktop_config.json
```

Output:
```
MCP Configuration Audit: ~/.config/claude/claude_desktop_config.json

┌──────────┬────────────┬──────────────────────────────────────┬─────────────────────────────────┐
│ Severity │ Server     │ Issue                                │ Recommendation                  │
├──────────┼────────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ CRITICAL │ shell      │ Server has shell execution capabili… │ Use RAXE gateway to monitor to… │
│ HIGH     │ filesystem │ Filesystem server has access to se…  │ Restrict to specific directori… │
│ INFO     │ git        │ Server is not protected by RAXE ga…  │ Consider using: raxe mcp gatew… │
└──────────┴────────────┴──────────────────────────────────────┴─────────────────────────────────┘

Found 1 CRITICAL issues that require immediate attention!
```

JSON output for CI/CD:
```bash
raxe mcp audit ~/.config/claude/claude_desktop_config.json --json
```

---

## CLI Reference

### raxe mcp serve

Start the MCP server (RAXE as tool provider).

```
Options:
  --transport [stdio]     Transport protocol (default: stdio)
  --log-level [debug|info|warn|error]
                         Log level (default: info)
  -q, --quiet            Suppress startup banner
```

### raxe mcp gateway

Start the MCP Security Gateway (RAXE as traffic inspector).

```
Options:
  -u, --upstream TEXT    Upstream MCP server command (can specify multiple)
  -c, --config PATH      Path to gateway config file
  --on-threat [log|block|warn]
                         Action on threat detection (default: log)
  --severity-threshold [LOW|MEDIUM|HIGH|CRITICAL]
                         Minimum severity to trigger action (default: HIGH)
  --no-l2                Disable L2 ML detection for faster scanning
  -v, --verbose          Enable verbose logging
```

### raxe mcp audit

Audit an MCP configuration file for security issues.

```
Arguments:
  CONFIG_FILE            Path to MCP config file

Options:
  --json                 Output results as JSON
```

### raxe mcp generate-config

Generate a sample gateway configuration file.

```
Options:
  -o, --output PATH      Output file path (default: mcp-security.yaml)
```

---

## Privacy

RAXE's MCP integration follows strict privacy principles:

### What We NEVER Return
- `matched_text` - The actual text that triggered detection
- `pattern` - Detection patterns (could be used to bypass)
- `context_before/after` - Surrounding text
- Raw prompts or responses

### What We CAN Return
- `rule_id` - Detection rule identifier
- `severity` - Threat severity level
- `confidence` - Detection confidence score
- `category` - Threat family/category
- `message` - General description

---

## Error Codes

The gateway uses standard JSON-RPC 2.0 error codes plus application-specific codes:

### Standard JSON-RPC Errors

| Code | Name | Description |
|------|------|-------------|
| -32700 | Parse Error | Invalid JSON received |
| -32603 | Internal Error | Internal server error |

### Application Errors (-32000 to -32099)

| Code | Name | Description |
|------|------|-------------|
| -32000 | Rate Limit | Client exceeded rate limit |
| -32001 | Blocked | Request blocked due to security threat |
| -32002 | No Upstream | No upstream server configured |
| -32003 | Upstream Failed | Upstream server request failed |
| -32004 | Message Too Large | Message exceeds 10MB limit |

---

## Troubleshooting

### MCP SDK not installed

```
Error: MCP SDK is not installed
Install with: pip install raxe[mcp]
```

Solution: Install MCP dependencies:
```bash
pip install raxe[mcp]
```

### Gateway not connecting to upstream

Check that the upstream command works independently:
```bash
npx @modelcontextprotocol/server-filesystem /tmp
```

### High latency

Disable L2 ML detection for faster scanning:
```bash
raxe mcp gateway --no-l2 -u "..."
```

### Too many false positives

Increase the severity threshold:
```bash
raxe mcp gateway --severity-threshold CRITICAL -u "..."
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RAXE_MCP_GATEWAY_PORT` | HTTP port for gateway | `8080` |
| `RAXE_MCP_GATEWAY_HOST` | HTTP host for gateway | `127.0.0.1` |
| `RAXE_MCP_GATEWAY_TELEMETRY` | Enable telemetry | `true` |
| `RAXE_MCP_GATEWAY_L2` | Enable L2 detection | `true` |
| `RAXE_MCP_GATEWAY_ON_THREAT` | Default threat action | `log` |
| `RAXE_MCP_GATEWAY_SEVERITY_THRESHOLD` | Default severity threshold | `HIGH` |

---

## Integration Examples

### Protecting Multiple Servers

```yaml
# mcp-security.yaml
upstreams:
  - name: filesystem
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/projects"]
    policy:
      on_threat: warn

  - name: database
    command: npx
    args: ["@modelcontextprotocol/server-postgres"]
    policy:
      on_threat: block
      severity_threshold: MEDIUM

  - name: shell
    command: npx
    args: ["@modelcontextprotocol/server-shell"]
    policy:
      on_threat: block
      severity_threshold: LOW
```

### MSSP Integration

For MSSP deployments, configure customer-specific policies:

```yaml
gateway:
  default_policy:
    on_threat: log

upstreams:
  - name: customer-fs
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/data"]
    env:
      MSSP_ID: "mssp_partner"
      CUSTOMER_ID: "cust_acme"
```

The gateway automatically includes MSSP context in telemetry.

---

## See Also

- [RAXE SDK Documentation](./api_reference.md)
- [Agent Security Guide](./AGENT_SECURITY.md)
- [MSSP Integration Guide](./MSSP_INTEGRATION_GUIDE.md)
