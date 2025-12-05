# Telemetry API Reference

**Version:** 1.2.0
**Last Updated:** 2025-11-27

This document describes the client-side API for RAXE telemetry, including credential management, health checks, and permission handling.

## Quick Start

```python
from raxe.infrastructure.telemetry.credential_store import CredentialStore
from raxe.infrastructure.telemetry.health_client import check_health
from raxe.application.telemetry_shipper import TelemetryShipper

# 1. Get or create credentials (auto-generates temp key if needed)
store = CredentialStore()
creds = store.get_or_create()

# 2. Check server status
response = check_health(creds.api_key)
print(f"Tier: {response.tier}")
print(f"Can disable telemetry: {response.can_disable_telemetry}")

# 3. Ship events
shipper = TelemetryShipper(credentials=creds)
result = shipper.ship_batch([{"event_type": "scan", ...}])
```

---

## Credential Store

The `CredentialStore` manages API key storage with chmod 600 protection.

### Location

```
~/.raxe/credentials.json
```

### API

```python
from raxe.infrastructure.telemetry.credential_store import (
    CredentialStore,
    Credentials,
    CredentialError,
    CredentialExpiredError,
    InvalidKeyFormatError,
    validate_key_format,
)
```

### CredentialStore Class

```python
class CredentialStore:
    """Secure credential storage with chmod 600 protection."""

    def __init__(self, credential_path: Path | None = None) -> None:
        """Initialize credential store.

        Args:
            credential_path: Custom path (default: ~/.raxe/credentials.json)
        """

    def load(self) -> Credentials | None:
        """Load credentials from file.

        Returns:
            Credentials if file exists, None otherwise.

        Raises:
            CredentialError: If file exists but cannot be parsed.
        """

    def save(self, credentials: Credentials) -> None:
        """Save credentials with chmod 600.

        Raises:
            CredentialError: If file cannot be written.
        """

    def get_or_create(self, *, raise_on_expired: bool = True) -> Credentials:
        """Load existing or generate new temp credentials.

        Args:
            raise_on_expired: If True, raises CredentialExpiredError
                when credentials are expired.

        Returns:
            Existing or newly generated credentials.

        Raises:
            CredentialExpiredError: If expired and raise_on_expired=True.
        """

    def upgrade_key(
        self,
        new_api_key: str,
        key_type: Literal["live", "test"],
    ) -> Credentials:
        """Upgrade from temporary to permanent key.

        Preserves installation_id from existing credentials.

        Raises:
            InvalidKeyFormatError: If key format is invalid.
            CredentialError: If key_type doesn't match prefix.
        """

    def update_from_health(self, health_response: dict) -> Credentials | None:
        """Update cached permissions from /v1/health response.

        Args:
            health_response: Dict with can_disable_telemetry, tier, etc.

        Returns:
            Updated credentials, or None if no credentials loaded.
        """

    def delete(self) -> bool:
        """Delete credentials file.

        Returns:
            True if deleted, False if didn't exist.
        """
```

### Credentials Dataclass

```python
@dataclass
class Credentials:
    api_key: str
    key_type: Literal["temporary", "live", "test"]
    installation_id: str
    created_at: str
    expires_at: str | None
    first_seen_at: str | None

    # Server permission cache
    can_disable_telemetry: bool = False
    offline_mode: bool = False
    tier: str = "temporary"
    last_health_check: str | None = None

    def is_expired(self) -> bool:
        """Check if credential has expired."""

    def is_temporary(self) -> bool:
        """Check if this is a temporary key."""

    def days_until_expiry(self) -> int | None:
        """Days remaining until expiry (None if no expiry)."""

    def days_since_expiry(self) -> int | None:
        """Days past expiry (for expired keys)."""

    def is_health_check_stale(self, max_age_hours: int = 24) -> bool:
        """Check if cached health check is stale."""
```

### Exceptions

```python
class CredentialError(Exception):
    """Base error for credential operations."""

class CredentialExpiredError(CredentialError):
    """API key has expired.

    Attributes:
        console_url: URL to get a new key.
        days_expired: Number of days past expiry.
    """

class InvalidKeyFormatError(CredentialError):
    """API key format is invalid."""
```

### Usage Examples

**Auto-generate temporary credentials:**

```python
store = CredentialStore()
creds = store.get_or_create()
print(f"Key type: {creds.key_type}")  # "temporary"
print(f"Expires: {creds.expires_at}")  # 14 days from now
```

**Handle expired keys:**

```python
try:
    creds = store.get_or_create(raise_on_expired=True)
except CredentialExpiredError as e:
    print(f"Key expired {e.days_expired} days ago")
    print(f"Get a new key at: {e.console_url}")
```

**Upgrade to permanent key:**

```python
creds = store.upgrade_key("raxe_live_abc123...", "live")
print(f"Upgraded to: {creds.key_type}")  # "live"
print(f"Expires: {creds.expires_at}")  # None (permanent)
```

**Check permissions:**

```python
creds = store.load()
if creds and creds.can_disable_telemetry:
    print("Telemetry can be disabled")
else:
    print("Telemetry is required for this tier")
```

---

## Health Client

The `health_client` module provides HTTP calls to the `/v1/health` endpoint.

### API

```python
from raxe.infrastructure.telemetry.health_client import (
    check_health,
    check_health_async,
    HealthResponse,
    HealthCheckError,
    AuthenticationError,
    NetworkError,
    ServerError,
    TimeoutError,
)
```

### check_health Function

```python
def check_health(
    api_key: str,
    *,
    endpoint: str = "https://api.raxe.ai",
    timeout: float = 10.0,
) -> HealthResponse:
    """Call /v1/health endpoint.

    Args:
        api_key: RAXE API key for authentication.
        endpoint: API endpoint URL.
        timeout: Request timeout in seconds.

    Returns:
        HealthResponse with key metadata and usage info.

    Raises:
        NetworkError: Cannot reach server.
        AuthenticationError: Invalid or expired key.
        ServerError: Server returns 5xx.
        TimeoutError: Request times out.
    """
```

### HealthResponse Dataclass

```python
@dataclass(frozen=True)
class HealthResponse:
    key_type: str           # live, test, temp
    tier: str               # temporary, community, pro, enterprise
    days_remaining: int | None
    events_today: int
    events_remaining: int
    rate_limit_rpm: int     # Requests per minute
    rate_limit_daily: int   # Events per day
    can_disable_telemetry: bool
    offline_mode: bool
    server_time: str        # ISO 8601
    trial_status: TrialStatus | None

    @classmethod
    def from_api_response(cls, data: dict) -> HealthResponse:
        """Parse raw API response."""
```

### TrialStatus Dataclass

```python
@dataclass(frozen=True)
class TrialStatus:
    is_trial: bool
    days_remaining: int | None
    scans_during_trial: int
    threats_detected_during_trial: int
```

### Usage Examples

**Basic health check:**

```python
response = check_health("raxe_live_abc123...")
print(f"Tier: {response.tier}")
print(f"Events today: {response.events_today}")
print(f"Events remaining: {response.events_remaining}")
```

**Check feature availability:**

```python
response = check_health(api_key)
if response.can_disable_telemetry:
    print("You can disable telemetry")
if response.offline_mode:
    print("Offline mode is available")
```

**Handle errors:**

```python
try:
    response = check_health(api_key)
except AuthenticationError as e:
    print(f"Invalid key: {e}")
except NetworkError as e:
    print(f"Network error: {e}")
except TimeoutError as e:
    print(f"Timeout: {e}")
```

**Async version:**

```python
import asyncio

async def main():
    response = await check_health_async("raxe_live_abc123...")
    print(f"Tier: {response.tier}")

asyncio.run(main())
```

---

## Telemetry Shipper

The `TelemetryShipper` handles batch sending with circuit breaker and retry logic.

### API

```python
from raxe.application.telemetry_shipper import (
    TelemetryShipper,
    TelemetryShipperConfig,
    ShipResult,
    HealthCheckResult,
    ShipperError,
    CircuitOpenError,
    RateLimitError,
    AuthenticationError,
    PrivacyViolationError,
    DailyLimitExceededError,
)
```

### TelemetryShipperConfig

```python
@dataclass
class TelemetryShipperConfig:
    endpoint: str = "https://api.raxe.ai/v1/telemetry"
    health_endpoint: str = "https://api.raxe.ai/v1/health"
    timeout_seconds: float = 30.0
    max_retries: int = 10
    retry_base_delay: float = 1.0
    max_batch_size: int = 100
    compression: bool = True
    dry_run: bool = False

    # Circuit breaker
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 30.0
    circuit_half_open_max_calls: int = 2
```

### TelemetryShipper Class

```python
class TelemetryShipper:
    def __init__(
        self,
        config: TelemetryShipperConfig | None = None,
        credentials: Credentials | None = None,
        queue: DualQueue | None = None,
    ) -> None:
        """Initialize shipper."""

    def ship_batch(self, events: list[dict]) -> ShipResult:
        """Ship a batch of events.

        On first batch send, performs health check to refresh permissions.

        Returns:
            ShipResult with accepted/rejected counts.
        """

    def check_health(self, force: bool = False) -> HealthCheckResult:
        """Check API health and get key metadata.

        Args:
            force: Bypass cache and fetch fresh data.

        Returns:
            HealthCheckResult with tier, features, clock drift.
        """

    def can_disable_telemetry(self) -> bool:
        """Check if current key allows disabling telemetry."""

    def get_circuit_state(self) -> str:
        """Get circuit breaker state: closed, open, half_open."""

    def get_stats(self) -> dict:
        """Get shipping statistics."""

    def reset_circuit(self) -> None:
        """Reset circuit breaker to closed state."""

    def refresh_permissions(self, force: bool = False) -> bool:
        """Refresh server permissions from health check."""
```

### ShipResult Dataclass

```python
@dataclass
class ShipResult:
    success: bool
    accepted: int
    rejected: int
    duplicates: int
    errors: list[dict]
    server_time: str | None
    duration_ms: float
```

### Error Classes

```python
class ShipperError(Exception):
    """Base exception for shipper errors."""

class CircuitOpenError(ShipperError):
    """Circuit breaker is open."""

class RateLimitError(ShipperError):
    """Rate limit exceeded (429)."""
    retry_after: float | None  # Seconds to wait

class AuthenticationError(ShipperError):
    """Authentication failed (401/403)."""

class PrivacyViolationError(ShipperError):
    """Privacy violation detected (422)."""

class DailyLimitExceededError(ShipperError):
    """Daily event limit exceeded (403 with DAILY_LIMIT_001).

    IMPORTANT: Do NOT retry until reset_at timestamp.
    """
    reset_at: int | None  # Unix timestamp (midnight UTC)
```

### Usage Examples

**Basic batch shipping:**

```python
config = TelemetryShipperConfig()
shipper = TelemetryShipper(config=config, credentials=creds)

events = [
    {"event_type": "scan", "event_id": "evt_123", ...},
    {"event_type": "heartbeat", "event_id": "evt_456", ...},
]

result = shipper.ship_batch(events)
if result.success:
    print(f"Shipped {result.accepted} events")
else:
    print(f"Failed: {result.errors}")
```

**Dry-run mode (for testing):**

```python
config = TelemetryShipperConfig(dry_run=True)
shipper = TelemetryShipper(config=config)

result = shipper.ship_batch(events)
# Events are logged but not sent
```

**Handle daily limit:**

```python
try:
    result = shipper.ship_batch(events)
except DailyLimitExceededError as e:
    from datetime import datetime, timezone
    reset_time = datetime.fromtimestamp(e.reset_at, tz=timezone.utc)
    print(f"Daily limit exceeded. Resets at: {reset_time}")
    # Do NOT retry - wait until reset_at
```

**Monitor circuit breaker:**

```python
state = shipper.get_circuit_state()
if state == "open":
    print("Circuit is open - requests will fail fast")
    shipper.reset_circuit()  # Manual reset if needed
```

**Get shipping statistics:**

```python
stats = shipper.get_stats()
print(f"Batches sent: {stats['batches_sent']}")
print(f"Events sent: {stats['events_sent']}")
print(f"Compression ratio: {stats['compression_ratio']:.2f}")
print(f"Circuit state: {stats['circuit_state']}")
```

---

## CLI Commands

### Authentication

```bash
# Open console to manage keys
raxe auth login

# Check local key status
raxe auth status

# Check with server (real-time info)
raxe auth status --remote
```

### Telemetry Management

```bash
# Show telemetry status
raxe stats --telemetry

# Force flush all queues
raxe telemetry flush

# List dead letter queue
raxe telemetry dlq list

# Show DLQ event details
raxe telemetry dlq show evt_abc123

# Retry failed events
raxe telemetry dlq retry

# Clear old DLQ events
raxe telemetry dlq clear --older-than 7d
```

### Configuration

```bash
# Show telemetry config
raxe config show telemetry

# Disable telemetry (Pro/Enterprise only)
raxe config set telemetry.enabled false

# Enable dry-run mode
export RAXE_TELEMETRY_DRY_RUN=true
```

---

## Error Codes

### Authentication Errors

| Code | HTTP | Description |
|------|------|-------------|
| AUTH_001 | 401 | Invalid API key |
| AUTH_002 | 403 | Key expired |
| AUTH_006 | 403 | Telemetry required for tier |

### Rate Limit Errors

| Code | HTTP | Description | Action |
|------|------|-------------|--------|
| RATE_001 | 429 | Per-minute limit | Retry after `Retry-After` header |
| DAILY_LIMIT_001 | 403 | Daily limit | Do NOT retry until `reset_at` |

### Privacy Errors

| Code | HTTP | Description |
|------|------|-------------|
| PRI_001 | 422 | Contains prohibited PII |
| PRI_002 | 422 | Raw text detected |

---

## Rate Limits by Tier

| Tier | Requests/min | Events/day | Can Disable Telemetry | Offline Mode |
|------|-------------|------------|----------------------|--------------|
| Temporary | 50 | 50,000 | No | No |
| Community | 100 | 100,000 | No | No |
| Pro | 500 | 1,000,000 | Yes | No |
| Enterprise | 2,000 | Unlimited | Yes | Yes |

---

## See Also

- [Telemetry Events Reference](/docs/telemetry/events.md) - Event types and payloads
- [Configuration Guide](/docs/configuration.md) - All configuration options
- [Troubleshooting](/docs/troubleshooting.md) - Common issues and solutions
