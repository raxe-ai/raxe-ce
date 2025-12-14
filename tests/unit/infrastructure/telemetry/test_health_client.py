"""
Unit tests for the health_client module.

Tests the HTTP client for the /v1/health endpoint including:
- Successful health check responses
- Authentication errors (401, 403)
- Network errors
- Timeout handling
- Response parsing
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from raxe.infrastructure.telemetry.health_client import (
    AuthenticationError,
    HealthCheckError,
    HealthResponse,
    NetworkError,
    ServerError,
    TimeoutError,
    TrialStatus,
    check_health,
)


class TestHealthResponse:
    """Tests for HealthResponse parsing."""

    def test_from_api_response_full(self):
        """Test parsing a complete API response."""
        data = {
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
                "rate_limit": {
                    "requests_per_minute": 100,
                    "events_per_day": 100000,
                },
                "features": {
                    "can_disable_telemetry": False,
                    "offline_mode": False,
                    "extended_retention": False,
                },
                "usage_today": {
                    "events_sent": 5432,
                    "events_remaining": 94568,
                },
                "trial_status": {
                    "is_trial": True,
                    "days_remaining": 14,
                    "scans_during_trial": 1000,
                    "threats_detected_during_trial": 50,
                },
            },
        }

        response = HealthResponse.from_api_response(data)

        assert response.key_type == "temp"
        assert response.tier == "community"
        assert response.days_remaining == 14
        assert response.events_today == 5432
        assert response.events_remaining == 94568
        assert response.rate_limit_rpm == 100
        assert response.rate_limit_daily == 100000
        assert response.can_disable_telemetry is False
        assert response.offline_mode is False
        assert response.server_time == "2025-01-25T10:30:00.000Z"
        assert response.trial_status is not None
        assert response.trial_status.is_trial is True
        assert response.trial_status.days_remaining == 14
        assert response.trial_status.scans_during_trial == 1000
        assert response.trial_status.threats_detected_during_trial == 50

    def test_from_api_response_live_key(self):
        """Test parsing a live (permanent) key response."""
        data = {
            "status": "healthy",
            "server_time": "2025-01-25T10:30:00.000Z",
            "key": {
                "type": "live",
                "tier": "pro",
                "rate_limit": {
                    "requests_per_minute": 500,
                    "events_per_day": 1000000,
                },
                "features": {
                    "can_disable_telemetry": True,
                    "offline_mode": True,
                    "extended_retention": True,
                },
                "usage_today": {
                    "events_sent": 10000,
                    "events_remaining": 990000,
                },
            },
        }

        response = HealthResponse.from_api_response(data)

        assert response.key_type == "live"
        assert response.tier == "pro"
        assert response.days_remaining is None  # Permanent key
        assert response.events_today == 10000
        assert response.rate_limit_rpm == 500
        assert response.can_disable_telemetry is True
        assert response.offline_mode is True
        assert response.trial_status is None

    def test_from_api_response_minimal(self):
        """Test parsing a minimal response with missing fields."""
        data = {
            "server_time": "2025-01-25T10:30:00.000Z",
            "key": {},
        }

        response = HealthResponse.from_api_response(data)

        assert response.key_type == "unknown"
        assert response.tier == "unknown"
        assert response.days_remaining is None
        assert response.events_today == 0
        assert response.events_remaining == 0
        assert response.rate_limit_rpm == 0
        assert response.rate_limit_daily == 0
        assert response.can_disable_telemetry is False
        assert response.offline_mode is False
        assert response.trial_status is None


class TestTrialStatus:
    """Tests for TrialStatus dataclass."""

    def test_trial_status_creation(self):
        """Test creating a TrialStatus instance."""
        status = TrialStatus(
            is_trial=True,
            days_remaining=7,
            scans_during_trial=500,
            threats_detected_during_trial=25,
        )

        assert status.is_trial is True
        assert status.days_remaining == 7
        assert status.scans_during_trial == 500
        assert status.threats_detected_during_trial == 25

    def test_trial_status_immutable(self):
        """Test that TrialStatus is immutable (frozen)."""
        status = TrialStatus(
            is_trial=True,
            days_remaining=7,
            scans_during_trial=500,
            threats_detected_during_trial=25,
        )

        with pytest.raises(AttributeError):
            status.days_remaining = 10


class TestCheckHealth:
    """Tests for the check_health function."""

    @patch("raxe.infrastructure.telemetry.health_client.httpx.Client")
    def test_check_health_success(self, mock_client_class):
        """Test successful health check."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "server_time": "2025-01-25T10:30:00.000Z",
            "key": {
                "type": "live",
                "tier": "pro",
                "rate_limit": {
                    "requests_per_minute": 500,
                    "events_per_day": 1000000,
                },
                "features": {
                    "can_disable_telemetry": True,
                    "offline_mode": True,
                },
                "usage_today": {
                    "events_sent": 100,
                    "events_remaining": 999900,
                },
            },
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Call function
        result = check_health("raxe_live_abc123def456ghi789jkl012mno345")

        # Verify
        assert isinstance(result, HealthResponse)
        assert result.key_type == "live"
        assert result.tier == "pro"
        assert result.events_today == 100

        # Verify request was made correctly
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "/v1/health" in call_args[0][0]
        assert "Bearer raxe_live_abc123def456ghi789jkl012mno345" in call_args[1]["headers"]["Authorization"]

    @patch("raxe.infrastructure.telemetry.health_client.httpx.Client")
    def test_check_health_401_unauthorized(self, mock_client_class):
        """Test authentication error (401)."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": "invalid_api_key",
            "message": "API key is invalid or revoked",
            "code": "AUTH_001",
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            check_health("raxe_live_invalid_key_here_12345678")

        assert "invalid" in str(exc_info.value).lower()

    @patch("raxe.infrastructure.telemetry.health_client.httpx.Client")
    def test_check_health_403_expired(self, mock_client_class):
        """Test expired key error (403)."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": "key_expired",
            "message": "Temporary API key expired",
            "code": "AUTH_002",
            "console_url": "https://console.raxe.ai/keys",
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            check_health("raxe_temp_expired_key_here12345678")

        assert "expired" in str(exc_info.value).lower()
        assert "console.raxe.ai" in str(exc_info.value)

    @patch("raxe.infrastructure.telemetry.health_client.httpx.Client")
    def test_check_health_500_server_error(self, mock_client_class):
        """Test server error (500)."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(ServerError) as exc_info:
            check_health("raxe_live_abc123def456ghi789jkl012mno345")

        assert "500" in str(exc_info.value)

    @patch("raxe.infrastructure.telemetry.health_client.httpx.Client")
    def test_check_health_connection_error(self, mock_client_class):
        """Test network connection error."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        mock_client_class.return_value = mock_client

        with pytest.raises(NetworkError) as exc_info:
            check_health("raxe_live_abc123def456ghi789jkl012mno345")

        assert "reach server" in str(exc_info.value).lower()

    @patch("raxe.infrastructure.telemetry.health_client.httpx.Client")
    def test_check_health_timeout(self, mock_client_class):
        """Test request timeout."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
        mock_client_class.return_value = mock_client

        with pytest.raises(TimeoutError) as exc_info:
            check_health("raxe_live_abc123def456ghi789jkl012mno345")

        assert "timed out" in str(exc_info.value).lower()

    @patch("raxe.infrastructure.telemetry.health_client.httpx.Client")
    def test_check_health_custom_endpoint(self, mock_client_class):
        """Test using a custom endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "server_time": "2025-01-25T10:30:00.000Z",
            "key": {"type": "live", "tier": "pro"},
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        check_health(
            "raxe_live_abc123def456ghi789jkl012mno345",
            endpoint="https://custom-api.example.com",
        )

        call_args = mock_client.get.call_args
        assert "https://custom-api.example.com/v1/health" in call_args[0][0]

    @patch("raxe.infrastructure.telemetry.health_client.httpx.Client")
    def test_check_health_endpoint_trailing_slash(self, mock_client_class):
        """Test endpoint with trailing slash is handled correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "server_time": "2025-01-25T10:30:00.000Z",
            "key": {"type": "live", "tier": "pro"},
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        check_health(
            "raxe_live_abc123def456ghi789jkl012mno345",
            endpoint="https://test.example.com/",
        )

        call_args = mock_client.get.call_args
        # Should not have double slashes
        assert "https://test.example.com/v1/health" in call_args[0][0]
        assert "//v1" not in call_args[0][0]


class TestHealthResponseImmutability:
    """Tests for HealthResponse immutability."""

    def test_health_response_is_frozen(self):
        """Test that HealthResponse is immutable."""
        response = HealthResponse(
            key_type="live",
            tier="pro",
            days_remaining=None,
            events_today=100,
            events_remaining=999900,
            rate_limit_rpm=500,
            rate_limit_daily=1000000,
            can_disable_telemetry=True,
            offline_mode=True,
            server_time="2025-01-25T10:30:00.000Z",
        )

        with pytest.raises(AttributeError):
            response.key_type = "temp"


class TestHealthResponseEquality:
    """Tests for HealthResponse equality."""

    def test_health_response_equality(self):
        """Test that identical HealthResponse objects are equal."""
        response1 = HealthResponse(
            key_type="live",
            tier="pro",
            days_remaining=None,
            events_today=100,
            events_remaining=999900,
            rate_limit_rpm=500,
            rate_limit_daily=1000000,
            can_disable_telemetry=True,
            offline_mode=True,
            server_time="2025-01-25T10:30:00.000Z",
        )

        response2 = HealthResponse(
            key_type="live",
            tier="pro",
            days_remaining=None,
            events_today=100,
            events_remaining=999900,
            rate_limit_rpm=500,
            rate_limit_daily=1000000,
            can_disable_telemetry=True,
            offline_mode=True,
            server_time="2025-01-25T10:30:00.000Z",
        )

        assert response1 == response2
