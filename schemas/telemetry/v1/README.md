# RAXE Telemetry Schema v1

This directory contains JSON Schema definitions for the RAXE telemetry protocol.

## Schema Version

**Current Version**: 1.2.0

See `_version.json` for version metadata and changelog.

## Directory Structure

```
schemas/telemetry/v1/
├── _version.json           # Schema version metadata
├── batch.schema.json       # Batch envelope for event submission
├── README.md               # This file
├── events/                 # Individual event type schemas
│   ├── installation.schema.json
│   ├── activation.schema.json
│   ├── session_start.schema.json
│   ├── session_end.schema.json
│   ├── scan.schema.json
│   ├── error.schema.json
│   ├── performance.schema.json
│   ├── feature_usage.schema.json
│   ├── heartbeat.schema.json
│   ├── key_upgrade.schema.json
│   ├── config_changed.schema.json
│   └── team_invite.schema.json
└── responses/              # API response schemas
    ├── success.schema.json
    ├── error.schema.json
    └── health.schema.json
```

## Event Types

| Event Type | Priority | Description |
|------------|----------|-------------|
| `installation` | Critical | First run detection, fired once per installation |
| `activation` | Critical | Time-to-value metrics for feature adoption |
| `session_start` | Standard | DAU/WAU/MAU tracking when Python session begins |
| `session_end` | Critical | Session duration and engagement metrics |
| `scan` | Critical/Standard | Core detection event (critical if HIGH/CRITICAL severity) |
| `error` | Critical | Client-side error tracking |
| `performance` | Standard | Aggregated 5-minute performance metrics |
| `feature_usage` | Standard | Feature adoption and usage tracking |
| `heartbeat` | Standard | Health signal every 5 minutes for long-running processes |
| `key_upgrade` | Critical | Trial to paid conversion tracking |
| `config_changed` | Critical/Standard | Configuration change tracking (critical if telemetry disabled) |
| `team_invite` | Critical | Team invitation for viral growth metrics |

## Common Field Patterns

### ID Patterns

| Field | Pattern | Example |
|-------|---------|---------|
| `installation_id` | `^inst_[a-zA-Z0-9]+$` | `inst_abc123XYZ` |
| `session_id` | `^sess_[a-zA-Z0-9]+$` | `sess_abc123XYZ` |
| `scan_id` | `^scan_[a-zA-Z0-9]+$` | `scan_abc123XYZ` |
| `batch_id` | `^batch_[a-zA-Z0-9]+$` | `batch_abc123XYZ` |
| `event_id` | `^evt_[a-zA-Z0-9]+$` | `evt_abc123XYZ` |
| `key_id` | `^key_[a-zA-Z0-9]+$` | `key_abc123XYZ` |

### Hash Format

All SHA-256 hashes use a consistent format with the `sha256:` prefix:

```
Pattern: ^sha256:[a-f0-9]{64}$
Length: 71 characters (7 prefix + 64 hex)
Example: sha256:a1b2c3d4e5f6...
```

Fields using this format:
- `prompt_hash` (scan events)
- `error_message_hash` (error events)
- `stack_trace_hash` (error events)
- `invitee_email_hash` (team_invite events)

### Multi-tenant Fields

All event schemas include optional multi-tenant fields:

```json
{
  "org_id": {
    "type": "string",
    "maxLength": 100,
    "description": "Organization ID for multi-tenant tracking"
  },
  "team_id": {
    "type": "string",
    "maxLength": 100,
    "description": "Team ID for team-level analytics"
  }
}
```

**Exception**: `team_invite` events require both `org_id` and `team_id` as mandatory fields.

## Validation

### Using ajv (Node.js)

```bash
npm install ajv ajv-formats

# Validate a batch
ajv validate -s batch.schema.json -d batch.json
```

### Using jsonschema (Python)

```python
import json
from jsonschema import validate, Draft7Validator

# Load schema
with open("schemas/telemetry/v1/batch.schema.json") as f:
    schema = json.load(f)

# Validate
batch = {"batch_id": "batch_abc123", ...}
validate(instance=batch, schema=schema)
```

### Using check-jsonschema CLI

```bash
pip install check-jsonschema

check-jsonschema --schemafile batch.schema.json batch.json
```

## Schema Versioning Policy

RAXE uses semantic versioning for schemas:

- **Major** (X.0.0): Breaking changes requiring client updates
- **Minor** (0.X.0): New event types or optional fields (backward compatible)
- **Patch** (0.0.X): Documentation fixes, pattern corrections

### Compatibility Rules

1. **Clients** must send `schema_version` in batch requests
2. **Server** rejects requests with unsupported schema versions
3. **New optional fields** can be added in minor versions
4. **Required fields** cannot be added without major version bump
5. **Enum values** can be extended in minor versions

### Version Check

Before sending telemetry:
1. Call `GET /v1/health` to retrieve server's supported schema range
2. Compare with client's schema version
3. Warn user if upgrade is recommended

## Privacy Requirements

All schemas enforce privacy-first design:

### Allowed
- SHA-256 hashes (with `sha256:` prefix)
- Detection metadata (rule IDs, severity levels)
- Aggregated counts and statistics
- SDK/client version information
- Timestamps

### Prohibited (Server rejects with 422)
- Raw prompt/response text
- Matched text from detection
- Rule patterns or detection logic
- PII (names, emails in plain text)
- IP addresses
- API keys or secrets
- File paths containing usernames
- Environment variables with secrets

## API Endpoints

| Endpoint | Method | Schema | Description |
|----------|--------|--------|-------------|
| `/v1/telemetry` | POST | `batch.schema.json` | Submit telemetry batch |
| `/v1/telemetry/dry-run` | POST | `batch.schema.json` | Validate without storing |
| `/v1/health` | GET | `responses/health.schema.json` | Health check with key info |

## Response Schemas

### Success Response (200/207)

```json
{
  "status": "ok",
  "batch_id": "batch_abc123",
  "accepted": 10,
  "rejected": 0,
  "duplicates": 2,
  "server_time": "2025-01-26T12:00:00Z"
}
```

### Error Response (4xx/5xx)

```json
{
  "error": "validation_error",
  "message": "Invalid prompt_hash format",
  "code": "VAL_001",
  "details": {
    "field": "events[0].payload.prompt_hash"
  }
}
```

## Changelog

### 1.2.0 (2025-11-27)
- Standardized `installation_id` patterns across all schemas
- Updated hash format to use `sha256:` prefix consistently
- Added comprehensive documentation

### 1.1.0
- Added `team_invite` event type for viral growth tracking

### 1.0.0
- Initial schema release
- 11 event types for comprehensive CX/Growth metrics
- Batch envelope with queue statistics
- Response schemas for success, error, and health endpoints
