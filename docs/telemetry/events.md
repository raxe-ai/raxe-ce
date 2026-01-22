# Telemetry Events Reference

**Schema Version:** 1.2.0
**Last Updated:** 2025-11-27

This document describes all telemetry events emitted by the RAXE client. All events are privacy-preserving by design - no raw prompts, matched text, or PII is ever transmitted.

## Overview

RAXE emits 12 event types across two priority queues:

| Priority | Flush Interval | Events |
|----------|---------------|--------|
| Critical | 5 seconds | installation, activation, session_end, error, key_upgrade, team_invite |
| Standard | 5 minutes | session_start, performance, feature_usage, heartbeat |
| Conditional | Varies | scan (critical if HIGH/CRITICAL), config_changed (critical if disabling telemetry) |

## Common Fields

All events share these top-level fields:

```python
@dataclass(frozen=True)
class TelemetryEvent:
    event_id: str           # Unique ID with evt_ prefix (e.g., "evt_a1b2c3d4e5f67890")
    event_type: str         # One of the 12 event types
    timestamp: str          # ISO 8601 UTC timestamp
    priority: Literal["critical", "standard"]
    payload: dict[str, Any] # Event-specific data
    org_id: str | None      # Organization ID for multi-tenant tracking (optional)
    team_id: str | None     # Team ID for team-level analytics (optional)
```

### Organization and Team Tracking

The `org_id` and `team_id` fields enable multi-tenant analytics:

- **org_id**: Links events to a specific organization (e.g., `"org_acme123"`)
- **team_id**: Links events to a specific team within an organization (e.g., `"team_backend"`)

Both fields are optional and propagate automatically when set during client initialization.

### Credential Metadata

The client stores server-side permissions locally for offline checks:

```python
@dataclass
class Credentials:
    api_key: str
    key_type: Literal["temporary", "live", "test"]
    installation_id: str
    created_at: str  # ISO 8601
    expires_at: str | None  # For temp keys (14 days)
    first_seen_at: str | None  # Server-provided

    # Server permission cache (from /v1/health)
    can_disable_telemetry: bool = False
    offline_mode: bool = False
    tier: str = "temporary"  # temporary, community, pro, enterprise
    last_health_check: str | None = None  # ISO 8601 timestamp
```

**Permission fields:**

| Field | Type | Description |
|-------|------|-------------|
| `can_disable_telemetry` | bool | Whether key tier allows disabling telemetry |
| `offline_mode` | bool | Whether offline scanning is permitted (Enterprise only) |
| `tier` | string | Key tier: temporary, community, pro, enterprise |
| `last_health_check` | string | ISO 8601 timestamp of last server health check |

Permissions are refreshed automatically on first batch send of each session, or manually via:

```python
from raxe.application.telemetry_shipper import TelemetryShipper

shipper = TelemetryShipper()
shipper.refresh_permissions(force=True)
```

---

## Event Types

### 1. installation

**Priority**: Critical
**Trigger**: Fired once on first import/install of RAXE

Tracks new installations for growth metrics and environment distribution analysis.

```python
from raxe.domain.telemetry import create_installation_event, generate_installation_id

event = create_installation_event(
    installation_id=generate_installation_id(),  # "inst_a1b2c3d4e5f67890"
    client_version="0.0.1",
    python_version="3.11.5",
    platform="darwin",  # darwin | linux | win32
    install_method="pip",  # pip | uv | pipx | poetry | conda | source | unknown
    ml_available=True,
    installed_extras=["ml", "openai"],
    platform_version="0.0.1",
    acquisition_source="pip_install",  # See values below
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| installation_id | string | Yes | Unique identifier with `inst_` prefix |
| client_version | string | Yes | RAXE version installed |
| python_version | string | Yes | Python interpreter version |
| platform | enum | Yes | `darwin`, `linux`, `win32` |
| install_method | enum | Yes | Package manager used |
| acquisition_source | enum | Yes | How user discovered RAXE |
| ml_available | boolean | No | Whether ML dependencies installed |
| installed_extras | array | No | Optional packages installed |
| platform_version | string | No | OS version string |

**Acquisition Source Values**:

| Value | Description |
|-------|-------------|
| pip_install | Installed via `pip install raxe` |
| github_release | Downloaded from GitHub releases |
| docker | Installed via Docker image |
| homebrew | Installed via `brew install raxe` |
| website_download | Downloaded from raxe.ai |
| referral | Referred by another user (via `RAXE_REFERRAL_CODE`) |
| enterprise_deploy | Enterprise deployment |
| ci_integration | Installed in CI/CD pipeline |
| unknown | Default/fallback |

---

### 2. activation

**Priority**: Critical
**Trigger**: Tracks first use of specific features (time-to-value metrics)

Measures how quickly users reach key milestones after installation.

```python
from raxe.domain.telemetry import create_activation_event

event = create_activation_event(
    feature="first_scan",  # See values below
    seconds_since_install=120.5,
    activation_context={"entry_point": "cli"},
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| feature | enum | Yes | Feature being activated |
| seconds_since_install | float | Yes | Time elapsed since installation |
| activation_context | object | No | Additional context |

**Feature Values**:

| Value | Description |
|-------|-------------|
| first_scan | First prompt scan performed |
| first_threat | First threat detected |
| first_block | First threat blocked by policy |
| first_cli | First CLI command executed |
| first_sdk | First SDK API call |
| first_decorator | First use of `@protect` decorator |
| first_wrapper | First use of OpenAI/Anthropic wrapper |
| first_langchain | First LangChain integration use |
| first_l2_detection | First ML-based (L2) detection |
| first_custom_rule | First custom rule loaded |

---

### 3. session_start

**Priority**: Standard
**Trigger**: Fired when a new Python interpreter session begins

Enables DAU/WAU/MAU tracking and session analytics.

```python
from raxe.domain.telemetry import create_session_start_event, generate_session_id

event = create_session_start_event(
    session_id=generate_session_id(),  # "sess_a1b2c3d4e5f67890"
    session_number=5,
    entry_point="cli",  # cli | sdk | wrapper | integration | repl
    previous_session_gap_hours=24.5,
    environment={"is_ci": False, "is_interactive": True, "is_notebook": False},
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | string | Yes | Unique identifier with `sess_` prefix |
| session_number | integer | Yes | Sequential count for this installation |
| entry_point | enum | No | How RAXE was invoked |
| previous_session_gap_hours | float | No | Hours since last session |
| environment | object | No | Session environment details |

---

### 4. session_end

**Priority**: Critical
**Trigger**: Fired when Python interpreter session ends

Captures session duration and engagement metrics.

```python
from raxe.domain.telemetry import create_session_end_event

event = create_session_end_event(
    session_id="sess_abc123def456789",
    duration_seconds=3600.0,
    scans_in_session=50,
    threats_in_session=3,
    end_reason="normal",  # normal | error | timeout | interrupt | unknown
    peak_memory_mb=150.5,
    features_used=["cli", "explain"],
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | string | Yes | Session being ended |
| duration_seconds | float | Yes | Total session duration |
| scans_in_session | integer | Yes | Number of scans performed |
| threats_in_session | integer | Yes | Number of threats detected |
| end_reason | enum | No | How session ended |
| peak_memory_mb | float | No | Peak memory usage |
| features_used | array | No | Features used during session |

---

### 5. scan

**Priority**: Conditional (Critical if severity HIGH/CRITICAL, otherwise Standard)
**Trigger**: Fired for each threat detection scan

Core telemetry event - tracks detection performance without exposing prompt content.

```python
from raxe.domain.telemetry import create_scan_event, create_prompt_hash

event = create_scan_event(
    prompt_hash=create_prompt_hash("user prompt text"),  # SHA-256 hash
    threat_detected=True,
    scan_duration_ms=4.5,
    detection_count=2,
    highest_severity="HIGH",  # NONE | LOW | MEDIUM | HIGH | CRITICAL
    rule_ids=["pi-001", "pi-002"],
    families=["PI", "JB"],
    l1_duration_ms=2.0,
    l2_duration_ms=2.5,
    l1_hit=True,
    l2_hit=False,
    l2_enabled=True,
    prompt_length=150,
    action_taken="block",  # allow | block | warn | redact
    entry_point="sdk",  # cli | sdk | wrapper | integration
    wrapper_type="openai",  # openai | anthropic | langchain | none
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| prompt_hash | string | Yes | SHA-256 hash of prompt (privacy) |
| threat_detected | boolean | Yes | Whether any threat detected |
| scan_duration_ms | float | Yes | Total scan duration |
| detection_count | integer | No | Number of detections found |
| highest_severity | enum | No | Highest severity level |
| rule_ids | array | No | Triggered rule IDs (max 10) |
| families | array | No | Threat families (PI, JB, PII, etc.) |
| l1_duration_ms | float | No | L1 (rule-based) scan time |
| l2_duration_ms | float | No | L2 (ML-based) scan time |
| l1_hit | boolean | No | L1 detection triggered |
| l2_hit | boolean | No | L2 detection triggered |
| l2_enabled | boolean | No | Whether L2 was enabled |
| prompt_length | integer | No | Character length of prompt |
| action_taken | enum | No | Action taken by policy |
| entry_point | enum | No | How scan was triggered |
| wrapper_type | enum | No | Wrapper used if applicable |

> **Note:** For the complete scan telemetry schema including L2 fields (`token_count`, `tokens_truncated`, voting details, model metadata), see [SCAN_TELEMETRY_SCHEMA.md](../SCAN_TELEMETRY_SCHEMA.md).

---

### 6. error

**Priority**: Critical
**Trigger**: Fired when an error occurs

Enables debugging and quality improvement without exposing sensitive data.

```python
from raxe.domain.telemetry import create_error_event, hash_text

event = create_error_event(
    error_type="validation_error",
    error_code="RAXE_001",
    component="engine",  # cli | sdk | engine | ml | rules | config | telemetry | wrapper
    error_message_hash=hash_text("Invalid prompt format"),
    operation="scan",
    is_recoverable=True,
    stack_trace_hash=hash_text("traceback..."),
    context={"python_version": "3.11.5", "raxe_version": "1.0.0", "platform": "darwin"},
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| error_type | enum | Yes | Category of error |
| error_code | string | Yes | Specific error code (e.g., RAXE_001) |
| component | enum | Yes | Component where error occurred |
| error_message_hash | string | No | SHA-256 hash of error message |
| operation | string | No | Operation being performed |
| is_recoverable | boolean | No | Whether error was recovered |
| stack_trace_hash | string | No | SHA-256 hash of stack trace |
| context | object | No | Non-sensitive context |

**Error Type Values**:

- `validation_error`
- `configuration_error`
- `rule_loading_error`
- `ml_model_error`
- `network_error`
- `permission_error`
- `timeout_error`
- `internal_error`

---

### 7. performance

**Priority**: Standard
**Trigger**: Sent periodically with aggregated metrics

Provides performance insights without per-scan data.

```python
from raxe.domain.telemetry import create_performance_event

event = create_performance_event(
    period_start="2025-01-22T10:00:00Z",
    period_end="2025-01-22T11:00:00Z",
    scan_count=1000,
    latency_percentiles={"p50_ms": 2.5, "p95_ms": 8.0, "p99_ms": 12.0, "max_ms": 25.0},
    l1_latency_percentiles={"p50_ms": 1.0, "p95_ms": 3.0, "p99_ms": 5.0},
    l2_latency_percentiles={"p50_ms": 5.0, "p95_ms": 15.0, "p99_ms": 25.0},
    memory_usage={"current_mb": 100.0, "peak_mb": 150.0},
    threat_detection_rate=0.05,
    rules_loaded=150,
    l2_enabled=True,
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| period_start | string | Yes | Start of measurement period (ISO 8601) |
| period_end | string | Yes | End of measurement period (ISO 8601) |
| scan_count | integer | Yes | Number of scans in period |
| latency_percentiles | object | No | Overall scan latency distribution |
| l1_latency_percentiles | object | No | L1 scan latency distribution |
| l2_latency_percentiles | object | No | L2 scan latency distribution |
| memory_usage | object | No | Memory statistics |
| threat_detection_rate | float | No | Percentage of scans with threats (0.0-1.0) |
| rules_loaded | integer | No | Number of rules loaded |
| l2_enabled | boolean | No | Whether L2 ML detection enabled |

---

### 8. feature_usage

**Priority**: Standard
**Trigger**: Tracks usage of specific features

Enables product analytics and feature adoption tracking.

```python
from raxe.domain.telemetry import create_feature_usage_event

event = create_feature_usage_event(
    feature="cli_scan",  # See values below
    action="completed",  # invoked | completed | failed | cancelled
    duration_ms=150.5,
    success=True,
    metadata={"output_format": "json"},
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| feature | enum | Yes | Feature being used |
| action | enum | Yes | Action taken |
| duration_ms | float | No | Time spent using feature |
| success | boolean | No | Whether usage was successful |
| metadata | object | No | Feature-specific metadata |

**Feature Values**:

| Category | Values |
|----------|--------|
| CLI | cli_scan, cli_rules_list, cli_rules_show, cli_config, cli_stats, cli_repl, cli_explain, cli_validate_rule, cli_doctor, cli_telemetry_dlq |
| SDK | sdk_scan, sdk_batch_scan, sdk_layer_control |
| Wrappers | wrapper_openai, wrapper_anthropic |
| Integrations | integration_langchain |
| Other | custom_rule_loaded, policy_applied |

---

### 9. heartbeat

**Priority**: Standard
**Trigger**: Periodic health signal (every 5 minutes)

Monitors long-running processes and telemetry system health.

```python
from raxe.domain.telemetry import create_heartbeat_event

event = create_heartbeat_event(
    uptime_seconds=3600.0,
    scans_since_last_heartbeat=100,
    threats_since_last_heartbeat=5,
    memory_mb=120.5,
    queue_depths={"critical": 0, "standard": 10, "dlq": 2},
    circuit_breaker_state="closed",  # closed | open | half_open
    last_successful_ship="2025-01-22T10:55:00Z",
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| uptime_seconds | float | Yes | Time since process started |
| scans_since_last_heartbeat | integer | Yes | Scans since last heartbeat |
| threats_since_last_heartbeat | integer | No | Threats since last heartbeat |
| memory_mb | float | No | Current memory usage |
| queue_depths | object | No | Telemetry queue sizes |
| circuit_breaker_state | enum | No | Circuit breaker state |
| last_successful_ship | string | No | Last successful telemetry ship |

---

### 10. key_upgrade

**Priority**: Critical
**Trigger**: Fired when API key is upgraded

Tracks conversion funnel from trial to paid tiers.

```python
from raxe.domain.telemetry import create_key_upgrade_event

event = create_key_upgrade_event(
    previous_key_type="temp",  # temp | community | pro | enterprise
    new_key_type="community",  # community | pro | enterprise
    days_on_previous=7,
    scans_on_previous=500,
    threats_on_previous=25,
    conversion_trigger="trial_expiry",
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| previous_key_type | enum | Yes | Previous key tier |
| new_key_type | enum | Yes | New key tier |
| days_on_previous | integer | No | Days on previous tier |
| scans_on_previous | integer | No | Total scans on previous tier |
| threats_on_previous | integer | No | Threats detected on previous tier |
| conversion_trigger | enum | No | What triggered the upgrade |

**Conversion Trigger Values**:

- `trial_expiry`
- `rate_limit_hit`
- `feature_needed`
- `manual_upgrade`
- `promo_code`

---

### 11. config_changed

**Priority**: Conditional (Critical if disabling telemetry, otherwise Standard)
**Trigger**: Fired when configuration is changed

Tracks configuration changes, especially telemetry opt-outs.

```python
from raxe.domain.telemetry import create_config_changed_event

event = create_config_changed_event(
    changed_via="cli",  # cli | sdk | config_file | env_var
    changes=[
        {"key": "telemetry.enabled", "old_value": True, "new_value": False}
    ],
    is_final_event=True,  # True if disabling telemetry
    org_id="org_123",
    team_id="team_456",
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| changed_via | enum | Yes | How configuration was changed |
| changes | array | Yes | List of configuration changes |
| is_final_event | boolean | No | True if last event before telemetry disable |

**Change Object Structure**:

```python
{
    "key": "telemetry.enabled",  # Configuration key
    "old_value": True,           # Previous value (optional)
    "new_value": False           # New value
}
```

---

### 12. team_invite

**Priority**: Critical
**Trigger**: Tracks team invitations for viral growth metrics

Enables tracking of team growth and referral patterns.

```python
from raxe.domain.telemetry import create_team_invite_event, hash_text

event = create_team_invite_event(
    inviter_installation_id="inst_abc123def456789",
    invitee_email_hash=hash_text("user@example.com"),  # SHA-256 hash, never raw email
    org_id="org_123",
    team_id="team_456",
    role="member",  # admin | member | viewer
    invite_method="email",  # email | link | api
)
```

**Payload Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| inviter_installation_id | string | Yes | Installation ID of inviter |
| invitee_email_hash | string | Yes | SHA-256 hash of invitee's email |
| org_id | string | Yes | Organization identifier |
| team_id | string | Yes | Team identifier |
| role | enum | Yes | Role assigned to invitee |
| invite_method | enum | Yes | How invitation was sent |

---

## Tier-Based Telemetry Behavior

Your API key tier affects how telemetry works. The client checks feature flags returned by the `/v1/health` endpoint.

### Telemetry Requirements by Tier

| Tier | Telemetry Required | Can Disable | Offline Mode |
|------|-------------------|-------------|--------------|
| Temporary | Yes | No | No |
| Community | Yes | No | No |
| Pro | No | Yes | No |
| Enterprise | No | Yes | Yes |

### Why Telemetry is Required for Free Tiers

For Temporary and Community tiers, telemetry is the "payment" for using RAXE:

- Improves detection accuracy for everyone through aggregated threat intelligence
- Identifies false positives and negatives to refine rules
- No PII or prompt content is ever transmitted (only hashes and metadata)

### Attempting to Disable Telemetry on Community Tier

If you try to disable telemetry on a tier that requires it:

```bash
$ raxe config set telemetry.enabled false

Error: Telemetry cannot be disabled on the free tier.

Telemetry helps improve RAXE for everyone and contains no personal data.
Only detection metadata (rule IDs, severity levels, timing) is shared.

To disable telemetry, upgrade to Pro at: https://console.raxe.ai/upgrade
```

The server also enforces this - if events arrive with telemetry marked as disabled from a temp/community key, the server returns 403:

```json
{
  "error": "telemetry_required",
  "message": "Telemetry is required for Community tier.",
  "code": "AUTH_006",
  "upgrade_url": "https://console.raxe.ai/upgrade"
}
```

### Pro/Enterprise: Disabling Telemetry

Paid tiers can disable telemetry. When you do, a final `config_changed` event is sent before stopping:

```python
from raxe import Raxe

# This works on Pro/Enterprise tiers
raxe = Raxe(telemetry_enabled=False)

# Or via CLI
# $ raxe config set telemetry.enabled false
# Telemetry disabled. No data will be sent to RAXE servers.
```

### Offline Mode (Enterprise Only)

Enterprise tier supports offline scanning without any network connectivity:

```python
from raxe import Raxe

# Enterprise key allows offline mode
raxe = Raxe(offline_mode=True)

# Scans work without network
result = raxe.scan("test prompt")  # Works offline

# Events queue locally and sync when online
```

Attempting offline mode on other tiers raises an error:

```python
from raxe import Raxe
from raxe.exceptions import RaxeOfflineNotAllowedError

try:
    raxe = Raxe(offline_mode=True)  # Community key
except RaxeOfflineNotAllowedError as e:
    print(e)
    # "Offline mode requires Enterprise tier. Contact sales at: https://console.raxe.ai/enterprise"
```

### Checking Your Tier Features

Use `raxe stats` to see your current tier and feature availability:

```bash
$ raxe stats

API Key Status
  Key Type: live (Pro)
  Tier: pro
  Expires: Never

Features
  Can Disable Telemetry: Yes
  Offline Mode: No (Enterprise only)
  Extended Retention: Yes (180 days)
  Priority Support: Yes

Rate Limits
  Requests/min: 500
  Events/day: 1,000,000
  Used today: 50,432 (5%)
```

---

## Privacy Guarantees

All events are designed with privacy as a core principle:

**Allowed Data**:
- SHA-256 hashes (prompt hashes, email hashes, error message hashes)
- Detection metadata (rule IDs, severity levels, threat families)
- Aggregated counts and statistics
- SDK/client versions and platform info

**Prohibited Data** (server rejects with 422):
- Raw prompt or response text
- Matched text from detections
- Rule patterns or detection logic
- PII (names, emails, addresses)
- IP addresses or API keys
- File paths containing usernames
- Environment variables with secrets

## ID Generators

The telemetry module provides generators for consistent ID formats:

```python
from raxe.domain.telemetry import (
    generate_event_id,        # "evt_a1b2c3d4e5f67890"
    generate_installation_id, # "inst_a1b2c3d4e5f67890"
    generate_session_id,      # "sess_a1b2c3d4e5f67890"
    generate_batch_id,        # "batch_a1b2c3d4e5f67890"
)
```

## Utility Functions

```python
from raxe.domain.telemetry import (
    create_prompt_hash,  # Create SHA-256 hash for scan events
    event_to_dict,       # Convert TelemetryEvent to dict for serialization
    hash_text,           # General-purpose text hashing
)

# Example: Convert event to JSON-serializable dict
event_dict = event_to_dict(event)
```

## Error Handling

### Key Expiry and Authentication

When an API key expires, the client raises `CredentialExpiredError` with helpful guidance:

```python
from raxe.infrastructure.telemetry.credential_store import (
    CredentialStore,
    CredentialExpiredError,
)

store = CredentialStore()

try:
    creds = store.get_or_create(raise_on_expired=True)
except CredentialExpiredError as e:
    print(f"Error: {e}")
    print(f"Get a new key at: {e.console_url}")
    print(f"Days expired: {e.days_expired}")
```

**CLI Check:**

```bash
# Check local key status with days remaining
$ raxe auth status

# Check with server (remote validation)
$ raxe auth status --remote

# Doctor command also checks key expiry
$ raxe doctor
```

### Key Expiry Warnings

RAXE displays warnings when temporary API keys are nearing expiration (days 11-14 of 14-day validity):

| Days Remaining | Behavior |
|----------------|----------|
| 10+ days | Normal operation, no warnings |
| 4-10 days | Warning displayed in `raxe doctor` output |
| 1-3 days | Warning displayed on every scan command |
| 0 days | "Expires TODAY" warning on every command |
| Expired | `CredentialExpiredError` raised, scanning blocked |

**Example warnings:**

```bash
# Days 11-13 (scans work normally, warning displayed)
$ raxe scan "test"
Warning: Your API key expires in 3 days. Get a permanent key at https://console.raxe.ai
# ... scan results ...

# Day 14 (last day)
$ raxe scan "test"
Warning: Your API key expires TODAY. Get a permanent key at https://console.raxe.ai
# ... scan results ...

# After expiry
$ raxe scan "test"
Error: Your API key has expired (2 days ago).
Get a new key at: https://console.raxe.ai
```

### Daily Limit Handling

Daily event limits return HTTP 403 (not 429) to prevent infinite retry loops:

```json
{
  "error": "daily_limit_exceeded",
  "code": "DAILY_LIMIT_001",
  "message": "Daily event limit exceeded. Resets at 2025-01-26T00:00:00Z.",
  "details": {
    "daily_limit": 50000,
    "events_today": 50001,
    "reset_at": 1737849600
  }
}
```

**Client behavior:**
- Events are moved to DLQ with reason "Daily limit exceeded"
- No retries until `reset_at` timestamp (midnight UTC)
- Use `raxe telemetry dlq list` to view queued events

### Telemetry Disable Validation

Attempting to disable telemetry on tiers that require it:

```bash
$ raxe config set telemetry.enabled false

# On Community tier:
Error: Telemetry cannot be disabled on the free tier.

Telemetry helps improve RAXE for everyone and contains no personal data.
Only detection metadata (rule IDs, severity levels, timing) is shared.

To disable telemetry, upgrade to Pro at: https://console.raxe.ai/upgrade
```

The server also enforces this - if a request arrives with telemetry marked as disabled from a tier that requires it:

```json
{
  "error": "telemetry_required",
  "code": "AUTH_006",
  "message": "Telemetry is required for Community tier.",
  "upgrade_url": "https://console.raxe.ai/upgrade"
}
```

---

## Changelog

### v1.2.0 (2025-11-27)

**Breaking Changes:**
- Daily limit errors now return HTTP 403 (not 429) with code `DAILY_LIMIT_001`

**New Features:**
- `CredentialExpiredError` exception with `console_url` and `days_expired` attributes
- Remote auth status check: `raxe auth status --remote`
- Credential fields for server permissions: `can_disable_telemetry`, `offline_mode`, `tier`, `last_health_check`
- Telemetry disable validation based on key tier

**Client Improvements:**
- Health check permission refresh on first batch send
- Stale credential detection with 24-hour cache
- Better error messages for expired keys

### v1.1.0 (2025-01-25)

- Added `org_id` and `team_id` fields to all events
- Added `acquisition_source` field for installation events
- Added `team_invite` event type for viral growth tracking
- Added tier-based telemetry requirements

### v1.0.0 (2025-01-25)

- Initial specification

---

## See Also

- [Telemetry API Reference](/docs/telemetry/api.md) - Client-side API documentation
- [Configuration Guide](/docs/configuration.md) - Telemetry configuration options
- [Privacy Policy](/docs/POLICIES.md) - Data handling policies
