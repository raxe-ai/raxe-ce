"""Application Layer Test Fixtures.

This module provides shared fixtures for testing telemetry components:
- BatchSender (HTTP client with circuit breaker)
- SessionTracker (session and activation tracking)
- TelemetryOrchestrator (coordinating component)
- CLI commands (telemetry management)
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from unittest.mock import MagicMock, Mock, patch

import pytest

from raxe.domain.telemetry.events import (
    EventType,
    TelemetryEvent,
    create_error_event,
    create_scan_event,
    create_session_end_event,
    create_session_start_event,
    generate_event_id,
    generate_session_id,
)
from raxe.infrastructure.telemetry.config import RetryPolicyConfig, TelemetryConfig
from raxe.infrastructure.telemetry.credential_store import Credentials, CredentialStore
from raxe.infrastructure.telemetry.dual_queue import DualQueue, StateKey
from raxe.infrastructure.telemetry.sender import (
    BatchSender,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryPolicy,
)

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Credential Fixtures
# =============================================================================


@pytest.fixture
def mock_credentials() -> Credentials:
    """Provide test credentials for telemetry."""
    return Credentials(
        api_key="raxe_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        key_type="test",
        installation_id="inst_test1234567890ab",
        created_at="2025-01-22T10:00:00Z",
        expires_at=None,
        first_seen_at=None,
    )


@pytest.fixture
def mock_temp_credentials() -> Credentials:
    """Provide temporary test credentials that expire."""
    expiry = datetime.now(timezone.utc) + timedelta(days=14)
    return Credentials(
        api_key="raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        key_type="temporary",
        installation_id="inst_temp1234567890ab",
        created_at="2025-01-22T10:00:00Z",
        expires_at=expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
        first_seen_at=None,
    )


@pytest.fixture
def mock_credential_store(mock_credentials: Credentials, tmp_path: Path) -> CredentialStore:
    """Provide a mock credential store with test credentials."""
    store = CredentialStore(tmp_path / "credentials.json")
    store.save(mock_credentials)
    return store


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def telemetry_config() -> TelemetryConfig:
    """Provide a test telemetry configuration.

    Uses localhost URL which is allowed for HTTP (security exception for testing).
    """
    return TelemetryConfig(
        enabled=True,
        endpoint="http://localhost:9999/v1/telemetry",  # localhost allowed for HTTP
        privacy_mode="strict",
        batch_size=100,
        flush_interval_ms=5000,
        max_queue_size=10000,
        sample_rate=1.0,
        compression="gzip",
        send_performance_metrics=True,
        send_error_reports=True,
        retry_policy=RetryPolicyConfig(
            max_retries=3,
            initial_delay_ms=1000,
            max_delay_ms=30000,
            backoff_multiplier=2.0,
            retry_on_status=[429, 500, 502, 503, 504],
        ),
    )


@pytest.fixture
def disabled_telemetry_config() -> TelemetryConfig:
    """Provide a disabled telemetry configuration."""
    return TelemetryConfig(
        enabled=False,
        endpoint="http://localhost:9999/v1/telemetry",  # localhost allowed for HTTP
        privacy_mode="strict",
    )


# =============================================================================
# Queue Fixtures
# =============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path for testing."""
    return tmp_path / "telemetry.db"


@pytest.fixture
def mock_queue(temp_db_path: Path) -> Generator[DualQueue, None, None]:
    """Provide a DualQueue instance with temporary database."""
    queue = DualQueue(
        db_path=temp_db_path,
        critical_max_size=1000,
        standard_max_size=5000,
        max_retry_count=3,
    )
    yield queue
    queue.close()


@pytest.fixture
def populated_queue(mock_queue: DualQueue) -> DualQueue:
    """Provide a DualQueue pre-populated with test events."""
    # Add some standard priority events
    for i in range(5):
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=False,
            scan_duration_ms=5.0,
        )
        mock_queue.enqueue(event)

    # Add some critical priority events
    for i in range(3):
        event = create_scan_event(
            prompt_hash="b" * 64,
            threat_detected=True,
            scan_duration_ms=8.0,
            highest_severity="HIGH",
        )
        mock_queue.enqueue(event)

    return mock_queue


# =============================================================================
# Circuit Breaker Fixtures
# =============================================================================


@pytest.fixture
def circuit_breaker_config() -> CircuitBreakerConfig:
    """Provide a test circuit breaker configuration."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        reset_timeout_seconds=10,
        half_open_requests=2,
        success_threshold=2,
    )


@pytest.fixture
def circuit_breaker(circuit_breaker_config: CircuitBreakerConfig) -> CircuitBreaker:
    """Provide a circuit breaker instance for testing."""
    return CircuitBreaker(config=circuit_breaker_config)


@pytest.fixture
def open_circuit_breaker(circuit_breaker: CircuitBreaker) -> CircuitBreaker:
    """Provide a circuit breaker in OPEN state."""
    # Trigger failures to open the circuit
    for _ in range(5):
        try:
            circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("Simulated failure")))
        except Exception:
            pass
    return circuit_breaker


# =============================================================================
# Retry Policy Fixtures
# =============================================================================


@pytest.fixture
def retry_policy() -> RetryPolicy:
    """Provide a test retry policy."""
    return RetryPolicy(
        max_retries=3,
        initial_delay_ms=100,  # Faster for tests
        max_delay_ms=1000,
        backoff_multiplier=2.0,
        jitter_factor=0.0,  # Disable jitter for deterministic tests
        retry_on_status=[429, 500, 502, 503, 504],
    )


# =============================================================================
# Batch Sender Fixtures
# =============================================================================


@pytest.fixture
def mock_shipper(
    circuit_breaker: CircuitBreaker,
    retry_policy: RetryPolicy,
) -> BatchSender:
    """Provide a BatchSender with dry_run-like behavior (localhost endpoint)."""
    return BatchSender(
        endpoint="http://localhost:9999/v1/telemetry",  # No actual server
        api_key="raxe_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        circuit_breaker=circuit_breaker,
        retry_policy=retry_policy,
        compression="gzip",
        timeout_seconds=5,
    )


@pytest.fixture
def production_shipper(
    circuit_breaker: CircuitBreaker,
    retry_policy: RetryPolicy,
) -> BatchSender:
    """Provide a BatchSender configured with production-like settings.

    Note: Uses localhost endpoint to avoid real API calls during testing.
    For testing actual production endpoint resolution, use the endpoints module tests.
    """
    return BatchSender(
        endpoint="http://localhost:9999/v1/telemetry",  # localhost allowed for HTTP
        api_key="raxe_test_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        circuit_breaker=circuit_breaker,
        retry_policy=retry_policy,
        compression="gzip",
        timeout_seconds=10,
    )


# =============================================================================
# Event Fixtures
# =============================================================================


@pytest.fixture
def sample_scan_event() -> TelemetryEvent:
    """Provide a sample scan event for testing."""
    return create_scan_event(
        prompt_hash="a" * 64,
        threat_detected=True,
        scan_duration_ms=4.5,
        detection_count=2,
        highest_severity="HIGH",
        rule_ids=["pi-001", "pi-002"],
        families=["PI"],
        l1_duration_ms=1.5,
        l2_duration_ms=3.0,
        l1_hit=True,
        l2_hit=False,
        l2_enabled=True,
        prompt_length=150,
        action_taken="block",
        entry_point="cli",
    )


@pytest.fixture
def sample_clean_scan_event() -> TelemetryEvent:
    """Provide a clean scan event (no threats) for testing."""
    return create_scan_event(
        prompt_hash="c" * 64,
        threat_detected=False,
        scan_duration_ms=2.0,
        detection_count=0,
        highest_severity="NONE",
        l1_duration_ms=1.0,
        l2_duration_ms=1.0,
        l1_hit=False,
        l2_hit=False,
        l2_enabled=True,
        prompt_length=50,
        action_taken="allow",
        entry_point="sdk",
    )


@pytest.fixture
def sample_error_event() -> TelemetryEvent:
    """Provide a sample error event for testing."""
    return create_error_event(
        error_type="validation_error",
        error_code="RAXE_001",
        component="engine",
        error_message_hash="d" * 64,
        operation="scan",
        is_recoverable=True,
    )


@pytest.fixture
def sample_session_start_event() -> TelemetryEvent:
    """Provide a sample session start event for testing."""
    return create_session_start_event(
        session_id=generate_session_id(),
        session_number=5,
        entry_point="cli",
        environment={"is_ci": False, "is_interactive": True},
    )


@pytest.fixture
def sample_session_end_event() -> TelemetryEvent:
    """Provide a sample session end event for testing."""
    return create_session_end_event(
        session_id=generate_session_id(),
        duration_seconds=3600.0,
        scans_in_session=50,
        threats_in_session=3,
        end_reason="normal",
        peak_memory_mb=150.5,
        features_used=["cli", "explain"],
    )


# =============================================================================
# DLQ Event Fixtures
# =============================================================================


@pytest.fixture
def dlq_events() -> list[dict[str, Any]]:
    """Provide sample DLQ events for testing CLI commands."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "event_id": "evt_dlq_001",
            "event_type": "scan",
            "priority": "standard",
            "payload": {
                "prompt_hash": "a" * 64,
                "threat_detected": False,
                "scan_duration_ms": 5.0,
            },
            "created_at": (base_time - timedelta(hours=2)).isoformat(),
            "failed_at": (base_time - timedelta(hours=1)).isoformat(),
            "failure_reason": "Connection timeout",
            "retry_count": 3,
            "server_error_code": "504",
            "server_error_message": "Gateway Timeout",
        },
        {
            "event_id": "evt_dlq_002",
            "event_type": "error",
            "priority": "critical",
            "payload": {
                "error_type": "network_error",
                "error_code": "NET_001",
                "component": "telemetry",
            },
            "created_at": (base_time - timedelta(hours=3)).isoformat(),
            "failed_at": (base_time - timedelta(minutes=30)).isoformat(),
            "failure_reason": "Server unavailable",
            "retry_count": 3,
            "server_error_code": "503",
            "server_error_message": "Service Unavailable",
        },
        {
            "event_id": "evt_dlq_003",
            "event_type": "scan",
            "priority": "critical",
            "payload": {
                "prompt_hash": "b" * 64,
                "threat_detected": True,
                "scan_duration_ms": 8.0,
                "highest_severity": "HIGH",
            },
            "created_at": (base_time - timedelta(days=10)).isoformat(),
            "failed_at": (base_time - timedelta(days=9)).isoformat(),
            "failure_reason": "Privacy violation detected",
            "retry_count": 1,
            "server_error_code": "422",
            "server_error_message": "Unprocessable Entity",
        },
    ]


@pytest.fixture
def queue_with_dlq(mock_queue: DualQueue, dlq_events: list[dict[str, Any]]) -> DualQueue:
    """Provide a queue with pre-populated DLQ events."""
    # Insert DLQ events directly into the database
    with mock_queue._get_connection() as conn:
        for event in dlq_events:
            conn.execute(
                """
                INSERT INTO telemetry_dlq (
                    event_id, event_type, priority, payload, created_at,
                    failed_at, failure_reason, retry_count,
                    server_error_code, server_error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event["event_id"],
                    event["event_type"],
                    event["priority"],
                    json.dumps(event["payload"]),
                    event["created_at"],
                    event["failed_at"],
                    event["failure_reason"],
                    event["retry_count"],
                    event.get("server_error_code"),
                    event.get("server_error_message"),
                ),
            )
        conn.commit()

    return mock_queue


# =============================================================================
# HTTP Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_http_success() -> Mock:
    """Mock successful HTTP response."""
    mock_response = Mock()
    mock_response.code = 200
    mock_response.read.return_value = json.dumps({"status": "ok", "accepted": 10}).encode()
    return mock_response


@pytest.fixture
def mock_http_rate_limited() -> Mock:
    """Mock 429 rate limited HTTP response."""
    mock_response = Mock()
    mock_response.code = 429
    mock_response.headers = {"Retry-After": "60"}
    mock_response.read.return_value = json.dumps({"error": "Rate limited"}).encode()
    return mock_response


@pytest.fixture
def mock_http_server_error() -> Mock:
    """Mock 5xx server error HTTP response."""
    mock_response = Mock()
    mock_response.code = 503
    mock_response.read.return_value = json.dumps({"error": "Service unavailable"}).encode()
    return mock_response


@pytest.fixture
def mock_http_auth_error() -> Mock:
    """Mock 401/403 authentication error HTTP response."""
    mock_response = Mock()
    mock_response.code = 401
    mock_response.read.return_value = json.dumps({"error": "Unauthorized"}).encode()
    return mock_response


@pytest.fixture
def mock_http_privacy_violation() -> Mock:
    """Mock 422 privacy violation HTTP response."""
    mock_response = Mock()
    mock_response.code = 422
    mock_response.read.return_value = json.dumps(
        {"error": "Privacy violation", "field": "payload.prompt"}
    ).encode()
    return mock_response


# =============================================================================
# Scan Result Fixtures
# =============================================================================


@pytest.fixture
def sample_scan_result() -> dict[str, Any]:
    """Provide a sample scan result for testing track_scan."""
    return {
        "threat_detected": True,
        "detections": [
            {
                "rule_id": "pi-001",
                "family": "PI",
                "severity": "HIGH",
                "confidence": 0.95,
                "matched_text_hash": "e" * 64,  # Hash, never raw text
            },
            {
                "rule_id": "pi-002",
                "family": "PI",
                "severity": "MEDIUM",
                "confidence": 0.85,
                "matched_text_hash": "f" * 64,
            },
        ],
        "highest_severity": "HIGH",
        "detection_count": 2,
        "policy_decision": {"action": "BLOCK", "reason": "High severity threat"},
        "performance": {
            "total_ms": 4.5,
            "l1_ms": 1.5,
            "l2_ms": 3.0,
            "policy_ms": 0.1,
        },
    }


@pytest.fixture
def sample_clean_scan_result() -> dict[str, Any]:
    """Provide a clean scan result (no threats) for testing."""
    return {
        "threat_detected": False,
        "detections": [],
        "highest_severity": "NONE",
        "detection_count": 0,
        "policy_decision": {"action": "ALLOW"},
        "performance": {
            "total_ms": 2.0,
            "l1_ms": 1.0,
            "l2_ms": 1.0,
            "policy_ms": 0.05,
        },
    }


# =============================================================================
# State Fixtures
# =============================================================================


@pytest.fixture
def queue_with_state(mock_queue: DualQueue) -> DualQueue:
    """Provide a queue with pre-populated state for session tracking tests."""
    # Set installation state
    mock_queue.set_state(StateKey.INSTALLATION_FIRED, "true")
    mock_queue.set_state(StateKey.INSTALLATION_ID, "inst_test1234567890ab")
    mock_queue.set_state(StateKey.INSTALL_TIMESTAMP, "2025-01-22T10:00:00Z")
    mock_queue.set_state(StateKey.SESSION_COUNT, "5")

    # Set some activation states
    mock_queue.set_state(StateKey.ACTIVATED_FIRST_SCAN, "true")
    mock_queue.set_state(StateKey.ACTIVATED_FIRST_CLI, "true")

    return mock_queue


# =============================================================================
# Utility Functions
# =============================================================================


def create_mock_urlopen_response(
    status_code: int,
    body: dict[str, Any] | str,
    headers: dict[str, str] | None = None,
) -> Mock:
    """Create a mock urlopen response for testing HTTP calls.

    Args:
        status_code: HTTP status code.
        body: Response body (dict will be JSON encoded).
        headers: Optional response headers.

    Returns:
        Mock object simulating urllib response.
    """
    response = Mock()
    response.code = status_code
    response.status = status_code

    if isinstance(body, dict):
        body = json.dumps(body)
    response.read.return_value = body.encode("utf-8")

    response.headers = headers or {}
    response.getheader = lambda key, default=None: response.headers.get(key, default)

    # Make it work as context manager
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    return response


def create_http_error(
    status_code: int,
    body: dict[str, Any] | str,
    url: str = "http://localhost:9999/v1/telemetry",
) -> Exception:
    """Create an HTTPError for testing error handling.

    Args:
        status_code: HTTP status code.
        body: Error response body.
        url: Request URL.

    Returns:
        urllib.error.HTTPError instance.
    """
    import io
    import urllib.error

    if isinstance(body, dict):
        body = json.dumps(body)

    error = urllib.error.HTTPError(
        url=url,
        code=status_code,
        msg=f"HTTP {status_code}",
        hdrs={},  # type: ignore
        fp=io.BytesIO(body.encode("utf-8")),
    )
    return error
