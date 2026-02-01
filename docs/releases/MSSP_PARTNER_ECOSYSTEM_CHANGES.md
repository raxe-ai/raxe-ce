# MSSP/Partner Ecosystem - Change Document

**Version:** 0.10.0
**Date:** 2024-01-30
**Status:** Ready for QA Validation

---

## Executive Summary

This release introduces the MSSP (Managed Security Service Provider) / Partner Ecosystem, enabling MSSPs to deploy RAXE agents across multiple customers with centralized monitoring, configurable alert forwarding, and per-customer data privacy controls.

---

## 1. New Features Overview

| Feature | Description | Primary Files |
|---------|-------------|---------------|
| MSSP Management | Create/manage MSSP partners | `src/raxe/cli/mssp.py` |
| Customer Management | Per-customer configuration | `src/raxe/cli/customer.py` |
| Agent Management | Track agent status/heartbeats | `src/raxe/cli/agent.py` |
| SIEM Integration | Splunk, CrowdStrike, Sentinel | `src/raxe/infrastructure/siem/` |
| Webhook Delivery | HMAC-signed alert delivery | `src/raxe/infrastructure/webhooks/` |
| Heartbeat Scheduler | Agent health monitoring | `src/raxe/application/heartbeat_scheduler.py` |
| Audit Logging | Data transmission audit trail | `src/raxe/infrastructure/audit/` |
| Partner SDK | Programmatic MSSP management | `src/raxe/sdk/partner/` |
| Telemetry MSSP Context | MSSP hierarchy in telemetry | `src/raxe/domain/telemetry/` |

---

## 2. CLI Commands Added

### 2.1 MSSP Management (`raxe mssp`)

```bash
# Create a new MSSP
raxe mssp create --id <mssp_id> --name "Partner Name" \
    --webhook-url https://soc.partner.com/alerts \
    --webhook-secret <secret>

# List all MSSPs
raxe mssp list [--output json|table]

# Show MSSP details
raxe mssp show <mssp_id> [--output json|table]

# Delete an MSSP
raxe mssp delete <mssp_id> [--force]

# Test webhook connectivity
raxe mssp test-webhook <mssp_id>
```

### 2.2 Customer Management (`raxe customer`)

```bash
# Create a customer under an MSSP
raxe customer create --mssp <mssp_id> --id <customer_id> \
    --name "Customer Name" \
    --data-mode full|privacy_safe \
    --retention-days 30

# List customers
raxe customer list --mssp <mssp_id> [--output json|table]

# Show customer details
raxe customer show --mssp <mssp_id> <customer_id>

# Configure customer settings
raxe customer configure <customer_id> --mssp <mssp_id> \
    --data-mode privacy_safe \
    --retention-days 60

# Delete a customer
raxe customer delete --mssp <mssp_id> <customer_id> [--force]
```

### 2.3 Agent Management (`raxe agent`)

```bash
# Register an agent
raxe agent register --mssp <mssp_id> --customer <customer_id> \
    --version 0.10.0 <agent_id>

# List agents
raxe agent list --mssp <mssp_id> [--customer <customer_id>]

# Show agent status
raxe agent status --mssp <mssp_id> --customer <customer_id> <agent_id>

# Send heartbeat
raxe agent heartbeat <agent_id>

# Unregister agent
raxe agent unregister <agent_id> [--force]
```

---

## 3. New Infrastructure Components

### 3.1 SIEM Adapters

Three SIEM adapters for enterprise integration:

| Adapter | Format | Authentication |
|---------|--------|----------------|
| **Splunk HEC** | JSON lines with `event` wrapper | Bearer token |
| **CrowdStrike Falcon LogScale** | JSON array with `@timestamp`, `@tags` | Bearer token |
| **Microsoft Sentinel** | PascalCase JSON with Azure fields | Base64 shared key |

**Files:**
- `src/raxe/infrastructure/siem/base.py` - Base adapter interface
- `src/raxe/infrastructure/siem/splunk.py` - Splunk HEC adapter
- `src/raxe/infrastructure/siem/crowdstrike.py` - CrowdStrike adapter
- `src/raxe/infrastructure/siem/sentinel.py` - Sentinel adapter
- `src/raxe/infrastructure/siem/dispatcher.py` - Multi-SIEM routing

### 3.2 Webhook Delivery System

HMAC-SHA256 signed webhook delivery with retry logic.

**Signature Format:**
```
X-RAXE-Signature: sha256=<hmac_hex>
X-RAXE-Timestamp: <unix_timestamp>
```

**Signature Payload:** `{timestamp}.{json_body}`

**Files:**
- `src/raxe/infrastructure/webhooks/delivery.py` - HTTP delivery
- `src/raxe/infrastructure/webhooks/signing.py` - HMAC signing

### 3.3 Heartbeat Scheduler

Background scheduler that sends periodic heartbeat events.

**Configuration:**
- `interval_seconds` - Heartbeat frequency (default: 60)
- `heartbeat_threshold_seconds` - Offline detection threshold

**Tracked Metrics:**
- `uptime_seconds` - Agent uptime
- `scans_since_last_heartbeat` - Scan count
- `threats_since_last_heartbeat` - Threat count

**Files:**
- `src/raxe/application/heartbeat_scheduler.py`

### 3.4 Audit Logging

Immutable audit trail for all MSSP data transmissions.

**Logged Fields:**
- `audit_id` - Unique audit record ID
- `mssp_id`, `customer_id` - Context
- `event_id` - Source event
- `data_mode` - Privacy mode used
- `data_fields_sent` - Fields transmitted
- `destination_url` - Webhook endpoint (redacted)
- `delivery_status` - success/failed
- `http_status_code` - Response code

**Files:**
- `src/raxe/infrastructure/audit/mssp_audit_logger.py`

---

## 4. Partner SDK

Programmatic API for MSSP automation.

```python
from raxe.sdk.partner import PartnerClient, create_partner_client

# Initialize client
client = create_partner_client("mssp_acme")

# Customer management
customer = client.create_customer(
    customer_id="cust_alpha",
    name="Alpha Corp",
    data_mode="full",
    data_fields=["prompt", "matched_text"],
)

customers = client.list_customers()
client.configure_customer("cust_alpha", retention_days=60)
client.delete_customer("cust_alpha")

# Agent management
agents = client.list_agents(customer_id="cust_alpha")
agent = client.get_agent("agent_001")

# Statistics
mssp_stats = client.get_mssp_stats()
customer_stats = client.get_customer_stats("cust_alpha")

# Webhook testing
result = client.test_webhook()
```

**Files:**
- `src/raxe/sdk/partner/__init__.py`
- `src/raxe/sdk/partner/client.py`

---

## 5. Telemetry Schema v3.0

### 5.1 New Top-Level Fields

```json
{
  "mssp_id": "mssp_acme",
  "customer_id": "cust_alpha",
  "agent_id": "agent_001"
}
```

### 5.2 New `_mssp_context` Block

Added when MSSP context is present:

```json
{
  "_mssp_context": {
    "mssp_id": "mssp_acme",
    "customer_id": "cust_alpha",
    "customer_name": "Alpha Corp",
    "app_id": "production_api",
    "agent_id": "agent_001",
    "data_mode": "full",
    "data_fields": ["prompt", "matched_text", "response"]
  }
}
```

### 5.3 New `_mssp_data` Block (Full Mode Only)

Contains sensitive data for MSSP webhook only (never sent to RAXE):

```json
{
  "_mssp_data": {
    "prompt_text": "Ignore all instructions...",
    "matched_text": "Ignore all instructions",
    "response_text": "...",
    "system_prompt": "..."
  }
}
```

### 5.4 Privacy Modes

| Mode | `_mssp_context` | `_mssp_data` | Raw Text |
|------|-----------------|--------------|----------|
| `privacy_safe` | Yes | No | Never |
| `full` | Yes | Yes | MSSP webhook only |

---

## 6. Configuration Files

### 6.1 MSSP Configuration

Location: `~/.raxe/mssp/{mssp_id}/config.yaml`

```yaml
mssp:
  id: mssp_acme
  name: Acme Security Services
  tier: partner
  webhook:
    url: https://soc.acme.com/raxe/alerts
    secret: <hmac_secret>
    timeout_seconds: 30
    retry_count: 3
  defaults:
    data_mode: privacy_safe
    retention_days: 30
```

### 6.2 Customer Configuration

Location: `~/.raxe/mssp/{mssp_id}/customers/{customer_id}/config.yaml`

```yaml
customer:
  id: cust_alpha
  name: Alpha Corporation
  mssp_id: mssp_acme
  data_mode: full
  data_fields:
    - prompt
    - matched_text
    - response
  retention_days: 60
  heartbeat_threshold_seconds: 300
```

### 6.3 Customer SIEM Configuration

Location: `~/.raxe/mssp/{mssp_id}/customers/{customer_id}/siem.yaml`

```yaml
siem:
  type: splunk
  endpoint_url: https://splunk.customer.com:8088/services/collector/event
  auth_token: <hec_token>
  extra:
    index: security
    source: raxe
```

---

## 7. Data Flow Architecture

```
Agent (SDK/CLI)
    │
    ├── Scan with threat detected
    │
    ▼
RAXE Telemetry Pipeline
    │
    ├─► RAXE Platform (metadata-only)
    │   - prompt_hash, prompt_length
    │   - rule_id, severity, confidence
    │   - mssp_id, customer_id, agent_id
    │   - NO prompt_text, response_text
    │
    └─► MSSP Webhook (configurable)
        │
        ├─► If data_mode=full:
        │   - All metadata PLUS
        │   - prompt_text, matched_text
        │   - (based on data_fields config)
        │
        └─► If data_mode=privacy_safe:
            - Metadata only (same as RAXE)
```

---

## 8. Files Changed/Added

### New Files (30+)

```
src/raxe/cli/mssp.py
src/raxe/cli/customer.py
src/raxe/cli/agent.py
src/raxe/application/mssp_service.py
src/raxe/application/heartbeat_scheduler.py
src/raxe/application/mssp_webhook_sender.py
src/raxe/domain/mssp/__init__.py
src/raxe/domain/mssp/models.py
src/raxe/domain/mssp/config.py
src/raxe/domain/siem/__init__.py
src/raxe/domain/siem/config.py
src/raxe/infrastructure/siem/__init__.py
src/raxe/infrastructure/siem/base.py
src/raxe/infrastructure/siem/splunk.py
src/raxe/infrastructure/siem/crowdstrike.py
src/raxe/infrastructure/siem/sentinel.py
src/raxe/infrastructure/siem/dispatcher.py
src/raxe/infrastructure/webhooks/__init__.py
src/raxe/infrastructure/webhooks/delivery.py
src/raxe/infrastructure/webhooks/signing.py
src/raxe/infrastructure/agent/__init__.py
src/raxe/infrastructure/agent/registry.py
src/raxe/infrastructure/audit/__init__.py
src/raxe/infrastructure/audit/mssp_audit_logger.py
src/raxe/sdk/partner/__init__.py
src/raxe/sdk/partner/client.py
```

### Modified Files

```
src/raxe/domain/telemetry/scan_telemetry_builder.py  # Added MSSP context
src/raxe/infrastructure/config/yaml_config.py        # Added get_config_path()
src/raxe/cli/__init__.py                             # Registered new CLI groups
```

---

## 9. Test Coverage

### Unit Tests Added

```
tests/unit/cli/test_mssp.py                          # 17 tests
tests/unit/application/test_mssp_webhook_sender.py   # 11 tests
tests/unit/infrastructure/audit/test_mssp_audit_logger.py  # 9 tests
tests/unit/domain/telemetry/test_mssp_telemetry.py   # 21 tests
```

**Total: 58 new unit tests**

---

## 10. Breaking Changes

None. All changes are additive and backward compatible.

---

## 11. Dependencies

No new external dependencies required.

---

## 12. Security Considerations

1. **HMAC Signing**: All webhooks are signed with SHA-256 HMAC
2. **Privacy Modes**: `privacy_safe` mode never transmits raw text
3. **Audit Trail**: All data transmissions are logged immutably
4. **URL Redaction**: Webhook URLs are redacted in audit logs
5. **Secret Storage**: Webhook secrets stored in local config files only

---

## 13. Known Limitations

1. **Scale**: Designed for 1-10 MSSPs with ~500 total agents
2. **Storage**: Local file-based storage (no database)
3. **Dashboard**: API-first (no web UI included)
4. **Retention**: Configurable 0-90 days per customer
