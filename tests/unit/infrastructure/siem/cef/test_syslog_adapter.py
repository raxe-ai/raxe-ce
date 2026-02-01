"""Tests for CEF Syslog adapter.

CEF over Syslog uses RFC 5424 format with CEF as the message content.
"""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem.cef.syslog_adapter import CEFSyslogAdapter


@pytest.fixture
def cef_syslog_udp_config() -> SIEMConfig:
    """CEF Syslog UDP configuration for testing."""
    return SIEMConfig(
        siem_type=SIEMType.CEF,
        endpoint_url="syslog://siem.example.com",
        auth_token="not-used-for-syslog",
        extra={
            "transport": "udp",
            "port": 514,
            "facility": 16,  # local0
        },
    )


@pytest.fixture
def cef_syslog_tcp_config() -> SIEMConfig:
    """CEF Syslog TCP configuration for testing."""
    return SIEMConfig(
        siem_type=SIEMType.CEF,
        endpoint_url="syslog://siem.example.com",
        auth_token="not-used-for-syslog",
        extra={
            "transport": "tcp",
            "port": 6514,
            "facility": 16,
            "use_tls": False,
        },
    )


@pytest.fixture
def sample_raxe_event() -> dict:
    """Sample RAXE scan event for testing."""
    return {
        "event_type": "scan",
        "event_id": "evt_test123",
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
            "l1": {
                "hit": True,
                "highest_severity": "CRITICAL",
                "families": ["PI"],
                "detections": [{"rule_id": "pi-001", "severity": "CRITICAL"}],
            },
        },
    }


class TestCEFSyslogAdapterProperties:
    """Test adapter properties."""

    def test_name_is_cef_syslog(self, cef_syslog_udp_config: SIEMConfig) -> None:
        """Adapter name identifies syslog transport."""
        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        assert "cef" in adapter.name.lower()

    def test_display_name_includes_transport(self, cef_syslog_udp_config: SIEMConfig) -> None:
        """Display name indicates transport type."""
        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        assert "UDP" in adapter.display_name or "Syslog" in adapter.display_name


class TestCEFSyslogTransform:
    """Test syslog message formatting."""

    def test_transform_includes_rfc5424_header(
        self,
        cef_syslog_udp_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """Transformed message includes RFC 5424 header."""
        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        result = adapter.transform_event(sample_raxe_event)

        syslog_message = result["syslog_message"]
        # RFC 5424 format: <PRI>1 TIMESTAMP HOSTNAME APP PROCID MSGID SD MSG
        assert syslog_message.startswith("<")
        assert ">" in syslog_message
        assert "CEF:0|" in syslog_message

    def test_transform_calculates_correct_pri(
        self,
        cef_syslog_udp_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """PRI value is correctly calculated from facility and severity."""
        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        result = adapter.transform_event(sample_raxe_event)

        syslog_message = result["syslog_message"]
        # CRITICAL = CEF 10 = syslog 2 (critical)
        # facility 16 * 8 + severity 2 = 130
        pri_end = syslog_message.index(">")
        pri = int(syslog_message[1:pri_end])
        assert pri == 130  # (16 * 8) + 2

    def test_transform_includes_cef_message(
        self,
        cef_syslog_udp_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """CEF message is embedded in syslog message."""
        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        result = adapter.transform_event(sample_raxe_event)

        assert "CEF:0|RAXE|" in result["syslog_message"]


class TestCEFSyslogUDPSend:
    """Test UDP transport."""

    @patch("socket.socket")
    def test_send_udp_success(
        self,
        mock_socket_class: MagicMock,
        cef_syslog_udp_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """UDP send succeeds when socket is working."""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__ = MagicMock(return_value=mock_socket)
        mock_socket_class.return_value.__exit__ = MagicMock(return_value=False)

        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        transformed = adapter.transform_event(sample_raxe_event)
        result = adapter.send_event(transformed)

        assert result.success is True
        assert mock_socket.sendto.called or mock_socket.send.called

    @patch("socket.socket")
    def test_send_udp_batch(
        self,
        mock_socket_class: MagicMock,
        cef_syslog_udp_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """UDP batch sends multiple messages."""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__ = MagicMock(return_value=mock_socket)
        mock_socket_class.return_value.__exit__ = MagicMock(return_value=False)

        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        events = [
            adapter.transform_event(sample_raxe_event),
            adapter.transform_event(sample_raxe_event),
        ]
        result = adapter.send_batch(events)

        assert result.success is True
        assert result.events_accepted == 2


class TestCEFSyslogTCPSend:
    """Test TCP transport."""

    @patch("socket.socket")
    def test_send_tcp_success(
        self,
        mock_socket_class: MagicMock,
        cef_syslog_tcp_config: SIEMConfig,
        sample_raxe_event: dict,
    ) -> None:
        """TCP send succeeds when connection is established."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        adapter = CEFSyslogAdapter(cef_syslog_tcp_config)
        transformed = adapter.transform_event(sample_raxe_event)
        result = adapter.send_event(transformed)

        assert result.success is True
        assert mock_socket.connect.called
        assert mock_socket.sendall.called


class TestCEFSyslogHealthCheck:
    """Test health check functionality."""

    @patch("socket.socket")
    @patch("socket.getaddrinfo")
    def test_health_check_udp_dns_success(
        self,
        mock_getaddrinfo: MagicMock,
        mock_socket_class: MagicMock,
        cef_syslog_udp_config: SIEMConfig,
    ) -> None:
        """UDP health check succeeds if DNS resolves."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_DGRAM, 0, "", ("192.168.1.1", 514))
        ]

        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        assert adapter.health_check() is True

    @patch("socket.getaddrinfo")
    def test_health_check_udp_dns_failure(
        self,
        mock_getaddrinfo: MagicMock,
        cef_syslog_udp_config: SIEMConfig,
    ) -> None:
        """UDP health check fails if DNS fails."""
        mock_getaddrinfo.side_effect = socket.gaierror("DNS resolution failed")

        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        assert adapter.health_check() is False

    @patch("socket.socket")
    def test_health_check_tcp_connection_success(
        self,
        mock_socket_class: MagicMock,
        cef_syslog_tcp_config: SIEMConfig,
    ) -> None:
        """TCP health check succeeds if connection is established."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        adapter = CEFSyslogAdapter(cef_syslog_tcp_config)
        assert adapter.health_check() is True

    @patch("socket.socket")
    def test_health_check_tcp_connection_failure(
        self,
        mock_socket_class: MagicMock,
        cef_syslog_tcp_config: SIEMConfig,
    ) -> None:
        """TCP health check fails if connection is refused."""
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError()
        mock_socket_class.return_value = mock_socket

        adapter = CEFSyslogAdapter(cef_syslog_tcp_config)
        assert adapter.health_check() is False


class TestCEFSyslogConfiguration:
    """Test syslog-specific configuration."""

    def test_parse_syslog_url(self, cef_syslog_udp_config: SIEMConfig) -> None:
        """Syslog URL is correctly parsed."""
        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        assert adapter.host == "siem.example.com"
        assert adapter.port == 514

    def test_uses_config_facility(self, cef_syslog_udp_config: SIEMConfig) -> None:
        """Adapter uses facility from config."""
        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        assert adapter.facility == 16  # local0

    def test_uses_config_transport(self, cef_syslog_udp_config: SIEMConfig) -> None:
        """Adapter uses transport from config."""
        adapter = CEFSyslogAdapter(cef_syslog_udp_config)
        assert adapter.transport == "udp"

    def test_tcp_uses_correct_port(self, cef_syslog_tcp_config: SIEMConfig) -> None:
        """TCP adapter uses configured port."""
        adapter = CEFSyslogAdapter(cef_syslog_tcp_config)
        assert adapter.port == 6514
