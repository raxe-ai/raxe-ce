# MSSP Integration Guide

> Guide for Managed Security Service Providers (MSSPs) to deploy and manage RAXE across multiple customers.

## Overview

RAXE's MSSP/Partner ecosystem enables:
- **Multi-tenant management**: Manage multiple customers under one MSSP account
- **Centralized alerting**: Receive scan alerts via webhook to your SOC
- **Privacy controls**: Per-customer data mode configuration (full vs privacy_safe)
- **Configurable fields**: Control exactly what data is sent per customer

## Architecture

```
RAXE Platform
    └── MSSP/Partner (mssp_id)
            ├── Webhook URL (your SOC endpoint)
            ├── Webhook Secret (HMAC signing)
            │
            └── Customer (customer_id)
                    ├── data_mode (full | privacy_safe)
                    ├── data_fields (prompt, matched_text, etc.)
                    ├── retention_days (0-90)
                    │
                    └── Agent (deployed at customer)
                            └── Sends scans → MSSP webhook
```

### MSSP Tiers

MSSPs have subscription tiers that determine customer limits:

| Tier | Max Customers | Description |
|------|---------------|-------------|
| **Starter** | 10 | Default tier for new MSSPs |
| **Professional** | 50 | Growing security practices |
| **Enterprise** | Unlimited | Large-scale deployments |

Set the tier when creating an MSSP:

```bash
raxe mssp create --id mssp_yourcompany \
    --name "Your Security Services" \
    --webhook-url https://soc.yourcompany.com/alerts \
    --webhook-secret secret \
    --tier professional \
    --max-customers 50
```

---

## Quick Start

### 1. Create Your MSSP

```bash
# Set MSSP data directory
export RAXE_MSSP_DIR=~/.raxe/mssp_data

# Create MSSP with webhook
raxe mssp create \
  --id mssp_yourcompany \
  --name "Your Security Services" \
  --webhook-url https://soc.yourcompany.com/raxe/alerts \
  --webhook-secret your_secret_key_here
```

### 2. Create Customers

```bash
# Customer with full data access
raxe customer create \
  --mssp mssp_yourcompany \
  --id cust_acme \
  --name "Acme Corporation" \
  --data-mode full

# Customer with privacy-safe mode (no prompt text)
raxe customer create \
  --mssp mssp_yourcompany \
  --id cust_privacyfirst \
  --name "Privacy First Inc" \
  --data-mode privacy_safe
```

### 3. Configure Data Fields (Optional)

```bash
# Only send specific fields to webhook
raxe customer configure cust_acme \
  --mssp mssp_yourcompany \
  --data-fields "prompt,matched_text"
```

### 4. Test Webhook Connection

```bash
raxe mssp test-webhook mssp_yourcompany
```

### 5. Run Scans with MSSP Context

```bash
raxe scan "Test prompt" --mssp mssp_yourcompany --customer cust_acme
```

---

## Data Privacy Modes

### Full Mode (`data_mode: full`)

Webhook receives complete scan data including:
- `prompt_text`: Raw prompt that was scanned
- `matched_text`: Text snippets that triggered rules
- All detection metadata

**Use when:** Customer has consented to full data sharing for SOC investigation.

### Privacy Safe Mode (`data_mode: privacy_safe`)

Webhook receives metadata only:
- `prompt_hash`: SHA-256 hash (irreversible)
- `prompt_length`: Character count
- Detection metadata (rule_id, severity, confidence)

**No raw text is ever transmitted.**

**Use when:** Customer requires data privacy, compliance restrictions.

---

## Webhook Payload Format

### Scan Event (Threat Detected)

```json
{
  "event_type": "scan",
  "timestamp": "2026-01-29T10:30:00Z",
  "payload": {
    "prompt_hash": "sha256:abc123...",
    "prompt_length": 156,
    "threat_detected": true,
    "scan_duration_ms": 12.5,
    "action_taken": "allow",
    "entry_point": "sdk",

    "mssp_id": "mssp_yourcompany",
    "customer_id": "cust_acme",

    "_mssp_context": {
      "mssp_id": "mssp_yourcompany",
      "customer_id": "cust_acme",
      "customer_name": "Acme Corporation",
      "data_mode": "full",
      "data_fields": ["prompt", "matched_text"]
    },

    "_mssp_data": {
      "prompt_text": "Ignore all previous instructions...",
      "matched_text": ["Ignore all previous instructions"]
    },

    "agent": {
      "version": "0.9.0",
      "platform": "darwin",
      "integration": "langchain"
    },

    "l1": {
      "hit": true,
      "detection_count": 3,
      "highest_severity": "critical",
      "families": ["PI", "AGENT"],
      "detections": [
        {"rule_id": "pi-001", "severity": "critical", "confidence": 0.85}
      ]
    },

    "l2": {
      "hit": true,
      "binary": {"is_threat": true, "threat_probability": 0.95},
      "family": {"prediction": "prompt_injection", "confidence": 0.98}
    }
  }
}
```

### Privacy Safe Mode (No _mssp_data)

```json
{
  "event_type": "scan",
  "payload": {
    "prompt_hash": "sha256:abc123...",
    "prompt_length": 156,
    "threat_detected": true,

    "_mssp_context": {
      "mssp_id": "mssp_yourcompany",
      "customer_id": "cust_privacyfirst",
      "customer_name": "Privacy First Inc",
      "data_mode": "privacy_safe"
    },

    "l1": { ... },
    "l2": { ... }
  }
}
```

Note: `_mssp_data` block is **not present** in privacy_safe mode.

---

## Webhook Signature Verification

All webhooks are signed with HMAC-SHA256. Verify using:

```python
import hmac
import hashlib

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    """Verify X-Raxe-Signature header."""
    timestamp = request.headers.get('X-Raxe-Timestamp')
    expected = "sha256=" + hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**Headers sent:**
- `X-Raxe-Signature`: HMAC-SHA256 signature
- `X-Raxe-Timestamp`: Unix timestamp
- `Content-Type`: application/json

---

## CLI Reference

### MSSP Commands

```bash
raxe mssp create --id <id> --name <name> --webhook-url <url> --webhook-secret <secret>
raxe mssp list
raxe mssp show <mssp_id>
raxe mssp test-webhook <mssp_id>
raxe mssp delete <mssp_id> [--force]
```

### Customer Commands

```bash
raxe customer create --mssp <mssp_id> --id <id> --name <name> [--data-mode full|privacy_safe]
raxe customer list --mssp <mssp_id>
raxe customer show --mssp <mssp_id> <customer_id>
raxe customer configure <customer_id> --mssp <mssp_id> [options]
raxe customer delete --mssp <mssp_id> <customer_id> [--force]
```

### Agent Commands

```bash
raxe agent register --mssp <mssp_id> --customer <customer_id> [--version <ver>] <agent_id>
raxe agent list --mssp <mssp_id> [--customer <customer_id>]
raxe agent status --mssp <mssp_id> --customer <customer_id> <agent_id>
raxe agent heartbeat <agent_id>
raxe agent unregister <agent_id> [--force]
```

### Configuration Options

```bash
raxe customer configure <customer_id> --mssp <mssp_id> \
  --data-mode full \                    # full or privacy_safe
  --data-fields "prompt,matched_text" \ # Comma-separated list
  --retention-days 90 \                 # 0-90 days
  --heartbeat-threshold 300             # Seconds before offline
```

### SIEM Commands

```bash
# Configure SIEM for a customer
raxe customer siem configure <customer_id> --mssp <mssp_id> --type <type> --url <url> --token <token> [options]

# Show SIEM configuration
raxe customer siem show <customer_id> --mssp <mssp_id>

# Test SIEM connection
raxe customer siem test <customer_id> --mssp <mssp_id>

# Disable SIEM integration
raxe customer siem disable <customer_id> --mssp <mssp_id>
```

### SIEM Configuration Examples

```bash
# Splunk HEC
raxe customer siem configure cust_acme --mssp mssp_yourcompany \
    --type splunk \
    --url https://splunk.company.com:8088/services/collector/event \
    --token "hec-token-here" \
    --splunk-index security \
    --splunk-source raxe

# CrowdStrike Falcon LogScale
raxe customer siem configure cust_acme --mssp mssp_yourcompany \
    --type crowdstrike \
    --url https://cloud.humio.com/api/v1/ingest/hec \
    --token "ingest-token"

# Microsoft Sentinel
raxe customer siem configure cust_acme --mssp mssp_yourcompany \
    --type sentinel \
    --url https://workspace.ods.opinsights.azure.com/api/logs \
    --token "base64-shared-key" \
    --sentinel-workspace-id "ws-123"

# CEF over HTTP
raxe customer siem configure cust_acme --mssp mssp_yourcompany \
    --type cef \
    --url https://collector.company.com/cef \
    --token "bearer-token"

# CEF over Syslog UDP
raxe customer siem configure cust_acme --mssp mssp_yourcompany \
    --type cef \
    --url syslog://siem.company.com \
    --transport udp --port 514

# CEF over Syslog TCP with TLS
raxe customer siem configure cust_acme --mssp mssp_yourcompany \
    --type cef \
    --url syslog://siem.company.com \
    --transport tcp --port 6514 --tls

# ArcSight SmartConnector
raxe customer siem configure cust_acme --mssp mssp_yourcompany \
    --type arcsight \
    --url https://arcsight.company.com/receiver/v1/events \
    --token "connector-token" \
    --smart-connector-id sc-001 \
    --device-vendor "RAXE" \
    --device-product "ThreatDetection"
```

---

## SDK Integration

### Python SDK

```python
from raxe import Raxe

raxe = Raxe()

# Scan with MSSP context
result = raxe.scan(
    "user input here",
    mssp_id="mssp_yourcompany",
    customer_id="cust_acme"
)
```

### Integration Frameworks (LangChain, etc.)

```python
from raxe.sdk.integrations.langchain import create_langchain_handler

# Create handler with MSSP context
handler = create_langchain_handler(
    mssp_id="mssp_yourcompany",
    customer_id="cust_acme"
)
```

---

## Agent Management

### Registering Agents

Register agents to track deployments across customers:

```bash
# Register agent with version info
raxe agent register --mssp mssp_yourcompany --customer cust_acme \
    --version 0.10.0 agent_prod_001
```

**Output:**
```
✓ Registered agent 'agent_prod_001'

  MSSP: mssp_yourcompany
  Customer: cust_acme
  Version: 0.10.0
  Platform: darwin
  Status: online
```

### Agent Heartbeats

Agents send periodic heartbeats to confirm they're running:

```bash
raxe agent heartbeat agent_prod_001
```

**Output:**
```
✓ Heartbeat sent for 'agent_prod_001'

  Status: online
  Uptime: 3600s
```

### Monitoring Agent Status

```bash
# List all agents for an MSSP
raxe agent list --mssp mssp_yourcompany

# Get detailed status
raxe agent status --mssp mssp_yourcompany --customer cust_acme agent_prod_001
```

**Status Output:**
```
       Agent Status: agent_prod_001
┌────────────────┬─────────────────────┐
│ Agent ID       │ agent_prod_001      │
│ Status         │ online              │
│ MSSP           │ mssp_yourcompany    │
│ Customer       │ cust_acme           │
│ Version        │ 0.10.0              │
│ Platform       │ darwin              │
│ Integration    │ langchain           │
│ First Seen     │ 2026-01-30T10:00:00 │
│ Last Heartbeat │ 2026-01-30T11:30:00 │
│ Uptime         │ 5400s               │
│ Total Scans    │ 1250                │
│ Total Threats  │ 23                  │
└────────────────┴─────────────────────┘
```

---

## Partner SDK

For programmatic MSSP management, use the Partner SDK:

```python
from raxe.sdk.partner import create_partner_client

# Initialize client
client = create_partner_client("mssp_yourcompany")

# Create customers programmatically
customer = client.create_customer(
    customer_id="cust_new",
    name="New Customer Corp",
    data_mode="full",
    data_fields=["prompt", "matched_text"],
)

# List all customers
customers = client.list_customers()
for c in customers:
    print(f"{c.customer_id}: {c.name} ({c.data_mode.value})")

# Configure customer settings
updated = client.configure_customer(
    "cust_new",
    data_mode="privacy_safe",
    retention_days=90,
)

# Get MSSP statistics
stats = client.get_mssp_stats()
print(f"Total customers: {stats['total_customers']}")
print(f"Total agents: {stats['total_agents']}")

# Delete customer
client.delete_customer("cust_old")
```

---

## SIEM Integration

RAXE supports forwarding events to enterprise SIEMs in native formats.

### Supported SIEMs

| SIEM | Format | Endpoint Type |
|------|--------|---------------|
| **Splunk** | HEC JSON | HTTP Event Collector |
| **CrowdStrike Falcon LogScale** | NDJSON | Humio API |
| **Microsoft Sentinel** | Azure Log Analytics | Data Collector API |
| **CEF (HTTP)** | CEF over HTTP | Generic CEF Collectors |
| **CEF (Syslog)** | CEF over Syslog | UDP/TCP/TLS Syslog |
| **ArcSight** | CEF with ArcSight Extensions | SmartConnector |

### Configuration

```python
from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem import create_siem_adapter

# Splunk HEC
splunk = create_siem_adapter(SIEMConfig(
    siem_type=SIEMType.SPLUNK,
    endpoint_url="https://splunk.company.com:8088/services/collector",
    auth_token="your-hec-token",
    extra={"index": "raxe_security", "source": "raxe"},
))

# CrowdStrike Falcon LogScale
crowdstrike = create_siem_adapter(SIEMConfig(
    siem_type=SIEMType.CROWDSTRIKE,
    endpoint_url="https://cloud.community.humio.com/api/v1/ingest/json",
    auth_token="your-ingest-token",
))

# Microsoft Sentinel
sentinel = create_siem_adapter(SIEMConfig(
    siem_type=SIEMType.SENTINEL,
    endpoint_url="https://your-workspace.ods.opinsights.azure.com",
    auth_token="base64-encoded-shared-key",
    extra={"workspace_id": "your-workspace-id"},
))

# CEF over HTTP (generic CEF collectors)
cef_http = create_siem_adapter(SIEMConfig(
    siem_type=SIEMType.CEF,
    endpoint_url="https://collector.company.com/cef",
    auth_token="your-bearer-token",
))

# CEF over Syslog UDP
cef_udp = create_siem_adapter(SIEMConfig(
    siem_type=SIEMType.CEF,
    endpoint_url="syslog://siem.company.com",
    auth_token="not-used",
    extra={"transport": "udp", "port": 514, "facility": 16},
))

# CEF over Syslog TCP with TLS
cef_tls = create_siem_adapter(SIEMConfig(
    siem_type=SIEMType.CEF,
    endpoint_url="syslog://siem.company.com",
    auth_token="not-used",
    extra={"transport": "tcp", "port": 6514, "use_tls": True},
))

# ArcSight SmartConnector
arcsight = create_siem_adapter(SIEMConfig(
    siem_type=SIEMType.ARCSIGHT,
    endpoint_url="https://arcsight.company.com/receiver/v1/events",
    auth_token="your-connector-token",
    extra={
        "smart_connector_id": "sc-001",
        "device_vendor": "RAXE",
        "device_product": "ThreatDetection",
    },
))

# Send event
result = splunk.send_event(splunk.transform_event(scan_event))
print(f"Sent: {result.success}")
```

### Event Formats

**Splunk HEC:**
```json
{
  "index": "raxe_security",
  "source": "raxe",
  "event": {
    "event_type": "scan",
    "threat_detected": true,
    ...
  }
}
```

**CrowdStrike:**
```json
{
  "@timestamp": "2026-01-30T10:30:00Z",
  "event_type": "scan",
  "threat_detected": true,
  ...
}
```

**Sentinel (PascalCase):**
```json
{
  "TimeGenerated": "2026-01-30T10:30:00Z",
  "EventType": "scan",
  "ThreatDetected": true,
  ...
}
```

**CEF (Common Event Format):**
```
CEF:0|RAXE|ThreatDetection|0.10.0|pi-001|Prompt Injection Detected|10|rt=1706612400000 src=inst_abc123 suser=agent_001 act=block cs1=sha256:abc... cs1Label=PromptHash cn1=156 cn1Label=PromptLength cs2=pi-001,pi-003 cs2Label=RuleIDs
```

**ArcSight (CEF with ArcSight Extensions):**
```
CEF:0|RAXE|ThreatDetection|0.10.0|pi-001|Prompt Injection Detected|10|rt=1706612400000 src=inst_abc123 suser=agent_001 act=block cs1=sha256:abc... cs1Label=PromptHash deviceDirection=0 cat=/Security/Attack/Injection dvchost=prod-server-01 deviceExternalId=sc-001
```

### CEF Severity Mapping

| RAXE Severity | CEF Severity (0-10) | Syslog Severity |
|---------------|---------------------|-----------------|
| none | 0 | 6 (informational) |
| LOW | 3 | 5 (notice) |
| MEDIUM | 5 | 4 (warning) |
| HIGH | 7 | 3 (error) |
| CRITICAL | 10 | 2 (critical) |

### CEF Extension Fields

| CEF Key | RAXE Field | Description |
|---------|------------|-------------|
| `rt` | timestamp | Receipt time (ms epoch) |
| `src` | installation_id | Source identifier |
| `suser` | agent_id | Agent identifier |
| `msg` | (computed) | Event description |
| `act` | action_taken | Action (allow/block) |
| `cs1`/`cs1Label` | prompt_hash | PromptHash |
| `cs2`/`cs2Label` | rule_ids | RuleIDs (comma-separated) |
| `cs3`/`cs3Label` | families | ThreatFamilies |
| `cs5`/`cs5Label` | mssp_id | MSSPId |
| `cs6`/`cs6Label` | customer_id | CustomerId |
| `cn1`/`cn1Label` | prompt_length | PromptLength |
| `cn2`/`cn2Label` | scan_duration_ms | ScanDurationMs |

### ArcSight-Specific Extensions

| CEF Key | Description |
|---------|-------------|
| `deviceDirection` | Traffic direction (0=inbound prompt) |
| `cat` | ArcSight category (e.g., /Security/Attack/Injection) |
| `dvchost` | Device hostname |
| `deviceExternalId` | SmartConnector ID |

### ArcSight Category Mapping

| Threat Family | ArcSight Category |
|---------------|-------------------|
| PI (Prompt Injection) | /Security/Attack/Injection |
| JB (Jailbreak) | /Security/Attack/Evasion |
| DE (Data Exfil) | /Security/Exfiltration |
| PII (PII Exposure) | /Security/Privacy/PII |
| AGENT (Agent Manipulation) | /Security/Attack/Application |
| (default) | /Security/Suspicious |

---

## Audit Logging

Track all data transmissions for compliance:

```python
from raxe.infrastructure.audit.mssp_audit_logger import MSSPAuditLogger, MSSPAuditLoggerConfig

# Create audit logger
config = MSSPAuditLoggerConfig(
    log_directory="/var/log/raxe/audit",
    max_file_size_mb=10,
)
logger = MSSPAuditLogger(config)

# Log delivery
audit_id = logger.log_delivery(
    mssp_id="mssp_yourcompany",
    customer_id="cust_acme",
    event_id="evt_123",
    data_mode="full",
    data_fields_sent=["prompt", "matched_text"],
    delivery_status="success",
    http_status_code=200,
    destination_url="https://soc.company.com/webhook",
)

# Get statistics
stats = logger.get_stats()
print(f"Total deliveries: {stats['total_deliveries']}")
print(f"Successful: {stats['successful']}")
print(f"Failed: {stats['failed']}")

# Get recent records
recent = logger.get_recent_records(limit=10)

# Cleanup old logs
deleted = logger.cleanup_old_logs(retention_days=90)
```

### Audit Record Format

```json
{
  "audit_id": "aud_abc123",
  "timestamp": "2026-01-30T10:30:00Z",
  "mssp_id": "mssp_yourcompany",
  "customer_id": "cust_acme",
  "event_id": "evt_123",
  "data_mode": "full",
  "data_fields_sent": ["prompt", "matched_text"],
  "destination_url": "https://soc.company.com/webhook",
  "delivery_status": "success",
  "http_status_code": 200
}
```

---

## Data Fields Reference

Available fields for `data_fields` configuration:

| Field | Description | Requires |
|-------|-------------|----------|
| `prompt` | Raw prompt text | data_mode: full |
| `matched_text` | L1 matched text snippets | data_mode: full |
| `response` | LLM response text | data_mode: full, scan_responses enabled |
| `system_prompt` | System prompt text | data_mode: full |
| `tool_calls` | Tool/function call details | data_mode: full |
| `rag_context` | RAG context text | data_mode: full |

If `data_fields` is empty/not set, all available fields are included in full mode.

### Example _mssp_data with All Fields

```json
{
  "_mssp_data": {
    "prompt_text": "User prompt here...",
    "matched_text": ["matched pattern 1", "matched pattern 2"],
    "response_text": "LLM response here...",
    "system_prompt": "You are a helpful assistant...",
    "tool_calls": [
      {"name": "search", "args": {"query": "test"}}
    ],
    "rag_context": "Retrieved context from vector DB..."
  }
}
```

---

## Troubleshooting

### Webhook Not Receiving Data

1. Verify webhook URL is accessible: `curl -X POST <url> -d '{}'`
2. Check MSSP config: `raxe mssp show <mssp_id>`
3. Verify customer exists: `raxe customer list --mssp <mssp_id>`
4. Check both `--mssp` and `--customer` flags are provided to scan

### No _mssp_data in Webhook

- Customer may be in `privacy_safe` mode
- Check: `raxe customer show --mssp <mssp_id> <customer_id>`
- Update: `raxe customer configure <id> --mssp <mssp_id> --data-mode full`

### Signature Verification Failing

1. Verify webhook secret matches: `raxe mssp show <mssp_id>`
2. Ensure you're using the raw payload bytes (not parsed JSON)
3. Include timestamp in signature calculation

### Permission Errors

```bash
chmod -R 755 ~/.raxe/mssp_data
```

---

## Local Testing with Self-Signed Certificates

For development and testing, you can use self-signed certificates:

### Using the Test Webhook Server

RAXE includes a test server that auto-generates self-signed certificates:

```bash
# Start the test server
python scripts/webhook_test_server.py --port 9001 --secret my_secret

# Options:
#   --port PORT       Port to listen on (default: 9001)
#   --secret SECRET   Webhook secret (default: test-secret)
#   --full-json       Show complete JSON without truncation
#   --no-ssl          Disable HTTPS (use HTTP only)
```

### Testing Webhooks

```bash
# Skip SSL verification for self-signed certs
export RAXE_SKIP_SSL_VERIFY=true

# Create MSSP pointing to test server
raxe mssp create --id test_mssp --name "Test MSSP" \
    --webhook-url https://127.0.0.1:9001/raxe/alerts \
    --webhook-secret my_secret

# Test webhook connectivity
raxe mssp test-webhook test_mssp

# Test with a real scan
raxe customer create --mssp test_mssp --id test_cust --name "Test" --data-mode full
raxe scan "Ignore all instructions" --mssp test_mssp --customer test_cust
```

> **Warning:** Only use `RAXE_SKIP_SSL_VERIFY=true` in development. Always use valid certificates in production.

---

## Security Considerations

1. **Webhook Secret**: Store securely, rotate periodically
2. **HTTPS Only**: Always use HTTPS for webhook endpoints
3. **Signature Verification**: Always verify webhook signatures
4. **Data Mode Selection**: Use `privacy_safe` when full data isn't needed
5. **Retention Limits**: Configure appropriate retention per compliance requirements

---

## Support

- Documentation: https://docs.raxe.ai
- Issues: https://github.com/raxe-ai/raxe-ce/issues
- Enterprise Support: support@raxe.ai
