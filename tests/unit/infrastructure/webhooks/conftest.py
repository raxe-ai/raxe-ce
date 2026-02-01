"""
Pytest fixtures for webhook infrastructure tests.

These fixtures provide mocks and test doubles for webhook components.
"""

import json
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class WebhookConfig:
    """Test configuration for webhook delivery."""

    endpoint: str = "https://mssp.example.com/webhooks/raxe"
    secret: str = "whsec_test_secret_key_for_hmac_signing"
    timeout_seconds: int = 10
    retry_count: int = 3
    retry_delay_ms: int = 100
    max_retry_delay_ms: int = 5000


@pytest.fixture
def webhook_config() -> WebhookConfig:
    """Provide standard webhook configuration for tests."""
    return WebhookConfig()


@pytest.fixture
def webhook_config_no_retry() -> WebhookConfig:
    """Provide webhook configuration with no retries."""
    return WebhookConfig(retry_count=0)


@pytest.fixture
def webhook_config_short_timeout() -> WebhookConfig:
    """Provide webhook configuration with short timeout for testing."""
    return WebhookConfig(timeout_seconds=1)


@pytest.fixture
def sample_webhook_payload() -> dict[str, Any]:
    """Sample webhook payload for testing."""
    return {
        "event_type": "threat_detected",
        "mssp_id": "mssp_test123",
        "customer_id": "cust_abc456",
        "timestamp": "2025-01-29T10:30:00.000Z",
        "payload": {
            "scan_id": "scan_xyz789",
            "prompt_hash": "sha256:" + "a" * 64,
            "threat_detected": True,
            "highest_severity": "HIGH",
            "detection_count": 2,
            "rule_ids": ["pi-001", "pi-002"],
            "action_taken": "block",
        },
    }


@pytest.fixture
def sample_webhook_payload_json(sample_webhook_payload: dict[str, Any]) -> bytes:
    """Sample webhook payload as JSON bytes."""
    return json.dumps(sample_webhook_payload, separators=(",", ":")).encode("utf-8")


@pytest.fixture
def mock_urlopen_success() -> Generator[MagicMock, None, None]:
    """Mock urllib.request.urlopen for successful responses."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.code = 200
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_response
        yield mock_urlopen


@pytest.fixture
def mock_urlopen_server_error() -> Generator[MagicMock, None, None]:
    """Mock urllib.request.urlopen for 500 server errors."""
    import urllib.error

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://mssp.example.com/webhooks/raxe",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )
        yield mock_urlopen


@pytest.fixture
def mock_urlopen_bad_request() -> Generator[MagicMock, None, None]:
    """Mock urllib.request.urlopen for 400 client errors."""
    import urllib.error

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://mssp.example.com/webhooks/raxe",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=None,
        )
        yield mock_urlopen


@pytest.fixture
def mock_urlopen_timeout() -> Generator[MagicMock, None, None]:
    """Mock urllib.request.urlopen for timeout errors."""

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = TimeoutError("Connection timed out")
        yield mock_urlopen


@pytest.fixture
def mock_urlopen_connection_error() -> Generator[MagicMock, None, None]:
    """Mock urllib.request.urlopen for connection errors."""
    import urllib.error

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        yield mock_urlopen


@pytest.fixture
def fixed_timestamp() -> int:
    """Provide a fixed Unix timestamp for deterministic testing."""
    return 1706526600  # 2024-01-29T10:30:00Z


@pytest.fixture
def circuit_breaker_test_config() -> dict[str, Any]:
    """Circuit breaker configuration for webhook tests."""
    return {
        "failure_threshold": 3,
        "reset_timeout_seconds": 1,  # Short for testing
        "half_open_requests": 2,
        "success_threshold": 2,
    }
