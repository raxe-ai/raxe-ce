"""Tests for CEF HTTP adapter.

CEF over HTTP sends CEF-formatted messages as plain text POST requests.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem.cef.http_adapter import CEFHTTPAdapter


@pytest.fixture
def cef_http_config() -> SIEMConfig:
    """CEF HTTP configuration for testing."""
    return SIEMConfig(
        siem_type=SIEMType.CEF,
        endpoint_url="https://collector.example.com/cef",
        auth_token="test-token",
        extra={"transport": "http"},
    )


@pytest.fixture
def sample_raxe_event() -> dict:
    """Sample RAXE scan event for testing."""
    return {
        "event_type": "scan",
        "event_id": "evt_test123",
        "priority": "critical",
        "timestamp": "2024-01-15T10:30:00.000Z",
        "_metadata": {
            "installation_id": "inst_abc123",
            "version": "0.9.0",
        },
        "payload": {
            "threat_detected": True,
            "prompt_hash": "sha256:abc123def456",
            "prompt_length": 156,
            "action_taken": "block",
            "scan_duration_ms": 12.5,
            "mssp_id": "mssp_test",
            "customer_id": "cust_test",
            "agent_id": "inst_abc123",
            "l1": {
                "hit": True,
                "highest_severity": "CRITICAL",
                "detection_count": 1,
                "families": ["PI"],
                "detections": [
                    {
                        "rule_id": "pi-001",
                        "severity": "CRITICAL",
                        "confidence": 0.95,
                    }
                ],
            },
            "l2": {
                "hit": False,
                "enabled": True,
            },
        },
    }


class TestCEFHTTPAdapterProperties:
    """Test adapter properties."""

    def test_name_is_cef(self, cef_http_config: SIEMConfig) -> None:
        """Adapter name is 'cef'."""
        adapter = CEFHTTPAdapter(cef_http_config)
        assert adapter.name == "cef"

    def test_display_name_is_human_readable(self, cef_http_config: SIEMConfig) -> None:
        """Adapter display name is human-readable."""
        adapter = CEFHTTPAdapter(cef_http_config)
        assert "CEF" in adapter.display_name


class TestCEFHTTPAdapterTransform:
    """Test event transformation."""

    def test_transform_returns_cef_message(
        self,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """transform_event returns dict with cef_message key."""
        adapter = CEFHTTPAdapter(cef_http_config)
        result = adapter.transform_event(sample_raxe_event)

        assert "cef_message" in result
        assert result["cef_message"].startswith("CEF:0|")

    def test_transform_includes_severity(
        self,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """Transformed event includes correct CEF severity."""
        adapter = CEFHTTPAdapter(cef_http_config)
        result = adapter.transform_event(sample_raxe_event)

        # CRITICAL = 10
        assert "|10|" in result["cef_message"]

    def test_transform_preserves_original_event(
        self,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """Original event data is preserved for reference."""
        adapter = CEFHTTPAdapter(cef_http_config)
        result = adapter.transform_event(sample_raxe_event)

        assert "original_event" in result
        assert result["original_event"]["event_id"] == "evt_test123"


class TestCEFHTTPAdapterSend:
    """Test HTTP sending."""

    @patch("requests.Session")
    def test_send_event_posts_cef_as_text(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """send_event POSTs CEF message as text/plain."""
        # Setup mock
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        transformed = adapter.transform_event(sample_raxe_event)
        result = adapter.send_event(transformed)

        assert result.success is True
        mock_session.post.assert_called_once()

        # Verify CEF message is sent as text
        call_args = mock_session.post.call_args
        assert "CEF:0|" in call_args.kwargs.get("data", "")

    @patch("requests.Session")
    def test_send_batch_uses_newline_delimiter(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """send_batch uses newline-delimited CEF messages."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        events = [
            adapter.transform_event(sample_raxe_event),
            adapter.transform_event(sample_raxe_event),
        ]
        result = adapter.send_batch(events)

        assert result.success is True
        assert result.events_accepted == 2

        # Verify newline-delimited format
        call_args = mock_session.post.call_args
        data = call_args.kwargs.get("data", "")
        assert data.count("\n") == 1  # 2 events, 1 newline between them

    @patch("requests.Session")
    def test_send_includes_bearer_auth(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """send_event includes Bearer token authentication."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        transformed = adapter.transform_event(sample_raxe_event)
        adapter.send_event(transformed)

        # Check that session was configured with Bearer auth
        assert mock_session.headers.update.called

    @patch("requests.Session")
    def test_send_handles_timeout(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """send_event handles timeout gracefully."""
        import requests

        mock_session = MagicMock()
        mock_session.post.side_effect = requests.Timeout("Connection timed out")
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        transformed = adapter.transform_event(sample_raxe_event)
        result = adapter.send_event(transformed)

        assert result.success is False
        assert "timeout" in result.error_message.lower()

    @patch("requests.Session")
    def test_send_handles_connection_error(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """send_event handles connection errors gracefully."""
        import requests

        mock_session = MagicMock()
        mock_session.post.side_effect = requests.ConnectionError("Connection refused")
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        transformed = adapter.transform_event(sample_raxe_event)
        result = adapter.send_event(transformed)

        assert result.success is False
        assert result.error_message is not None


class TestCEFHTTPAdapterHealthCheck:
    """Test health check functionality."""

    @patch("requests.Session")
    def test_health_check_success(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
    ) -> None:
        """health_check returns True when endpoint is reachable."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.head.return_value = mock_response
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        assert adapter.health_check() is True

    @patch("requests.Session")
    def test_health_check_failure(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
    ) -> None:
        """health_check returns False when endpoint is unreachable."""
        import requests

        mock_session = MagicMock()
        mock_session.head.side_effect = requests.ConnectionError()
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        assert adapter.health_check() is False


class TestCEFHTTPAdapterConfiguration:
    """Test adapter configuration options."""

    def test_uses_config_endpoint(self, cef_http_config: SIEMConfig) -> None:
        """Adapter uses endpoint from config."""
        adapter = CEFHTTPAdapter(cef_http_config)
        assert adapter.config.endpoint_url == "https://collector.example.com/cef"

    def test_uses_config_timeout(self, cef_http_config: SIEMConfig) -> None:
        """Adapter respects timeout from config."""
        adapter = CEFHTTPAdapter(cef_http_config)
        assert adapter.config.timeout_seconds == 30


class TestCEFHTTPAdapterStats:
    """Test statistics tracking."""

    @patch("requests.Session")
    def test_stats_track_sent_events(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """Statistics track successfully sent events."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        transformed = adapter.transform_event(sample_raxe_event)
        adapter.send_event(transformed)

        assert adapter.stats["events_sent"] == 1

    @patch("requests.Session")
    def test_stats_track_failed_events(
        self,
        mock_session_class: MagicMock,
        cef_http_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """Statistics track failed events."""
        import requests

        mock_session = MagicMock()
        mock_session.post.side_effect = requests.Timeout()
        mock_session_class.return_value = mock_session

        adapter = CEFHTTPAdapter(cef_http_config)
        transformed = adapter.transform_event(sample_raxe_event)
        adapter.send_event(transformed)

        assert adapter.stats["events_failed"] == 1
