"""Privacy-first telemetry infrastructure.

Telemetry that respects user privacy by design:
- Only sends hashes, never actual text
- No PII is ever transmitted
- User controls opt-in/opt-out
- Batch sending for efficiency
- Graceful degradation on errors
"""

from raxe.infrastructure.telemetry.credential_store import (
    CredentialError,
    CredentialExpiredError,
    Credentials,
    CredentialStore,
    InvalidKeyFormatError,
    validate_key_format,
)
from raxe.infrastructure.telemetry.hook import TelemetryConfig, TelemetryHook, hash_text
from raxe.infrastructure.telemetry.queue import (
    EventPriority,
    EventQueue,
    QueuedEvent,
)
from raxe.infrastructure.telemetry.dual_queue import (
    DualQueue,
    StateKey,
)
from raxe.infrastructure.telemetry.flush_scheduler import (
    FlushConfig,
    FlushScheduler,
    HttpShipper,
    SQLiteDualQueueAdapter,
)
from raxe.infrastructure.telemetry.health_client import (
    AuthenticationError,
    HealthCheckError,
    HealthResponse,
    NetworkError,
    ServerError,
    TimeoutError,
    check_health,
    check_health_async,
)

__all__ = [
    # Hook (existing)
    "TelemetryConfig",
    "TelemetryHook",
    "hash_text",
    # Credential store
    "CredentialStore",
    "Credentials",
    "CredentialError",
    "CredentialExpiredError",
    "InvalidKeyFormatError",
    "validate_key_format",
    # Event queue
    "EventQueue",
    "QueuedEvent",
    "EventPriority",
    # Dual queue
    "DualQueue",
    "StateKey",
    # Flush scheduler
    "FlushConfig",
    "FlushScheduler",
    "HttpShipper",
    "SQLiteDualQueueAdapter",
    # Health client
    "HealthCheckError",
    "AuthenticationError",
    "NetworkError",
    "ServerError",
    "TimeoutError",
    "HealthResponse",
    "check_health",
    "check_health_async",
]
