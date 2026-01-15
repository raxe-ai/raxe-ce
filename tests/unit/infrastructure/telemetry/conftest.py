"""
Pytest fixtures for infrastructure telemetry tests.

These fixtures provide mocks and test doubles for infrastructure components.
"""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def temp_db() -> Generator[Path, None, None]:
    """Create a temporary SQLite database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    try:
        db_path.unlink()
    except OSError:
        pass


@pytest.fixture
def temp_credentials_file(tmp_path: Path) -> Path:
    """Create a temporary credentials file with sample data (non-expired)."""
    from datetime import datetime, timedelta, timezone

    # Use future dates to ensure credentials are not expired
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(days=7)  # Created 7 days ago
    expires_at = now + timedelta(days=7)  # Expires in 7 days

    creds_file = tmp_path / "credentials.json"
    creds_file.write_text(
        json.dumps(
            {
                "api_key": "raxe_temp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  # 32 chars
                "key_type": "temporary",
                "installation_id": "inst_abc123def456gh",
                "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "first_seen_at": None,
            }
        )
    )
    return creds_file


@pytest.fixture
def mock_http_success_response() -> MagicMock:
    """Mock successful HTTP response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.code = 200
    mock_response.content = b'{"status": "ok", "accepted": 1, "rejected": 0}'
    mock_response.json.return_value = {
        "status": "ok",
        "accepted": 1,
        "rejected": 0,
        "duplicates": 0,
        "processing_time_ms": 45,
    }
    mock_response.read.return_value = mock_response.content
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = lambda s, *args: None
    return mock_response


@pytest.fixture
def mock_http_error_response() -> MagicMock:
    """Mock HTTP error response (5xx)."""
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.code = 503
    mock_response.text = "Service Unavailable"
    mock_response.reason = "Service Unavailable"
    return mock_response


@pytest.fixture
def mock_http_rate_limited_response() -> MagicMock:
    """Mock rate limited HTTP response (429)."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.code = 429
    mock_response.headers = {
        "Retry-After": "60",
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": "1706178660",
    }
    mock_response.json.return_value = {
        "status": "rate_limited",
        "error": "rate_limit_exceeded",
        "message": "Rate limit exceeded. Retry after 60 seconds.",
        "retry_after": 60,
    }
    return mock_response


@pytest.fixture
def mock_http_validation_error_response() -> MagicMock:
    """Mock validation error HTTP response (422)."""
    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.code = 422
    mock_response.json.return_value = {
        "status": "error",
        "error": "privacy_violation",
        "message": "Event contains prohibited field: prompt_text",
        "code": "PRI_002",
    }
    return mock_response


@pytest.fixture
def mock_async_http_client(mock_http_success_response: MagicMock) -> AsyncMock:
    """Mock async HTTP client."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_http_success_response)
    mock_client.aclose = AsyncMock()
    return mock_client


@pytest.fixture
def sample_events_batch() -> list[dict[str, Any]]:
    """Sample batch of telemetry events."""
    return [
        {
            "event_id": "evt_abc123",
            "event_type": "scan",
            "timestamp": "2025-01-25T10:30:00.000Z",
            "priority": "critical",
            "payload": {"prompt_hash": "a" * 64, "threat_detected": True, "scan_duration_ms": 15.5},
        },
        {
            "event_id": "evt_def456",
            "event_type": "scan",
            "timestamp": "2025-01-25T10:30:01.000Z",
            "priority": "standard",
            "payload": {"prompt_hash": "b" * 64, "threat_detected": False, "scan_duration_ms": 8.2},
        },
    ]


@pytest.fixture
def sample_batch_request() -> dict[str, Any]:
    """Sample batch request matching schema."""
    return {
        "batch_id": "batch_abc123def456",
        "schema_version": "1.0.0",
        "client_version": "0.2.0",
        "installation_id": "inst_abc123def456",
        "session_id": "sess_xyz789abc123",
        "sent_at": "2025-01-25T10:30:00.000Z",
        "event_count": 2,
        "compression": "gzip",
        "queue_stats": {"critical_pending": 5, "standard_pending": 120, "dlq_size": 0},
        "events": [],  # To be filled with sample_events_batch
    }


@pytest.fixture
def queue_with_events(temp_db: Path):
    """Create queue pre-populated with events."""
    from raxe.infrastructure.telemetry.queue import EventPriority, EventQueue

    queue = EventQueue(db_path=temp_db)

    # Add events of different priorities
    for i in range(5):
        queue.enqueue(
            event_type="scan",
            payload={"n": i, "priority": "critical"},
            priority=EventPriority.CRITICAL,
        )

    for i in range(10):
        queue.enqueue(
            event_type="scan", payload={"n": i, "priority": "high"}, priority=EventPriority.HIGH
        )

    for i in range(20):
        queue.enqueue(
            event_type="scan", payload={"n": i, "priority": "medium"}, priority=EventPriority.MEDIUM
        )

    for i in range(15):
        queue.enqueue(
            event_type="heartbeat", payload={"n": i, "priority": "low"}, priority=EventPriority.LOW
        )

    return queue


@pytest.fixture
def circuit_breaker_config() -> dict[str, Any]:
    """Circuit breaker test configuration."""
    return {
        "failure_threshold": 3,
        "reset_timeout_seconds": 1,  # Short for testing
        "half_open_requests": 2,
        "success_threshold": 2,
    }


@pytest.fixture
def retry_policy_config() -> dict[str, Any]:
    """Retry policy test configuration."""
    return {
        "max_retries": 3,
        "initial_delay_ms": 10,  # Short for testing
        "max_delay_ms": 100,
        "backoff_multiplier": 2.0,
        "jitter_factor": 0.1,
        "retry_on_status": [429, 500, 502, 503, 504],
    }


@pytest.fixture
def telemetry_config_data() -> dict[str, Any]:
    """Telemetry configuration test data.

    Uses a test URL to avoid coupling tests to production endpoints.
    For testing actual endpoint resolution, see tests/unit/infrastructure/config/test_endpoints.py.
    """
    return {
        "enabled": True,
        "endpoint": "http://test.local/v1/telemetry",  # Test-specific endpoint
        "api_key": "raxe_test_abc123def456xyz789",
        "batch_size": 50,
        "max_batch_bytes": 100000,
        "critical_flush_interval_seconds": 5,
        "standard_flush_interval_seconds": 300,
        "max_queue_size": 10000,
        "max_retry_count": 10,
        "compression": "gzip",
        "dry_run": False,
        "debug": False,
    }


@pytest.fixture
def mock_telemetry_endpoint():
    """Mock the telemetry HTTP endpoint using urllib."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "ok", "accepted": 1}'
        mock_response.code = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_response
        yield mock_urlopen


@pytest.fixture
def mock_telemetry_endpoint_failure():
    """Mock telemetry endpoint that fails."""
    import urllib.error

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url=None, code=503, msg="Service Unavailable", hdrs={}, fp=None
        )
        yield mock_urlopen


@pytest.fixture
def health_check_response() -> dict[str, Any]:
    """Sample health check response."""
    return {
        "status": "healthy",
        "server_time": "2025-01-25T10:30:00.000Z",
        "api_version": "1.1.0",
        "region": "europe-west4",
        "key": {
            "key_id": "key_abc123",
            "type": "temp",
            "created_at": "2025-01-25T10:00:00Z",
            "expires_at": "2025-02-08T10:00:00Z",
            "first_seen_at": "2025-01-25T10:00:00Z",
            "customer_id": "cust_trial_xyz789",
            "tier": "community",
            "rate_limit": {"requests_per_minute": 100, "events_per_day": 100000},
            "features": {
                "can_disable_telemetry": False,
                "offline_mode": False,
                "extended_retention": False,
            },
            "usage_today": {"events_sent": 5432, "events_remaining": 94568},
            "trial_status": {
                "is_trial": True,
                "days_remaining": 14,
                "scans_during_trial": 0,
                "threats_detected_during_trial": 0,
            },
        },
    }


@pytest.fixture
def dry_run_response() -> dict[str, Any]:
    """Sample dry-run response."""
    return {
        "status": "dry_run",
        "batch_id": "batch_abc123def456",
        "would_accept": 2,
        "would_reject": 0,
        "validation_errors": [],
        "note": "No events were stored. This is a validation-only request.",
    }


@pytest.fixture
def partial_success_response() -> dict[str, Any]:
    """Sample partial success response (202)."""
    return {
        "status": "partial",
        "batch_id": "batch_abc123def456",
        "accepted": 48,
        "rejected": 2,
        "duplicates": 0,
        "processing_time_ms": 52,
        "errors": [
            {
                "event_id": "evt_bad001",
                "error": "invalid_schema",
                "message": "Missing required field: event_type",
                "code": "EVT_001",
            },
            {
                "event_id": "evt_bad002",
                "error": "privacy_violation",
                "message": "Event contains prohibited field: prompt_text",
                "code": "PRI_002",
            },
        ],
    }
