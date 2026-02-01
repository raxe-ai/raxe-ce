"""CEF Syslog adapter.

Sends CEF-formatted events over Syslog (UDP/TCP/TLS).
RFC 5424 compliant message formatting.

Syslog Message Format (RFC 5424):
    <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID SD MSG

CEF Message is embedded as MSG content.
"""

from __future__ import annotations

import os
import socket
import ssl
import threading
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from raxe.domain.siem.config import SIEMConfig
from raxe.infrastructure.siem.base import BaseSIEMAdapter, SIEMDeliveryResult
from raxe.infrastructure.siem.cef.formatter import CEFFormatter


class CEFSyslogAdapter(BaseSIEMAdapter):
    """CEF over Syslog adapter.

    Supports UDP, TCP, and TLS transports.

    RFC 5424 PRI Calculation:
        PRI = (facility * 8) + severity

    Common facilities:
        0 = kern, 1 = user, 16-23 = local0-local7

    Example:
        >>> from raxe.domain.siem.config import SIEMConfig, SIEMType
        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.CEF,
        ...     endpoint_url="syslog://siem.example.com",
        ...     auth_token="not-used",
        ...     extra={"transport": "udp", "port": 514, "facility": 16}
        ... )
        >>> adapter = CEFSyslogAdapter(config)
        >>> event = adapter.transform_event(raxe_event)
        >>> result = adapter.send_event(event)
    """

    # RFC 5424 version
    SYSLOG_VERSION = "1"

    # RAXE app name for syslog
    APP_NAME = "RAXE"

    def __init__(self, config: SIEMConfig) -> None:
        """Initialize CEF Syslog adapter.

        Args:
            config: SIEM configuration
        """
        super().__init__(config)
        self._formatter = CEFFormatter(
            device_vendor=config.arcsight_device_vendor,
            device_product=config.arcsight_device_product,
            device_version=config.arcsight_device_version,
        )

        # Parse syslog URL
        parsed = urlparse(config.endpoint_url)
        self._host = parsed.hostname or "localhost"
        self._port = config.cef_port
        self._transport = config.cef_transport
        self._facility = config.cef_facility
        self._use_tls = config.cef_use_tls

        # TCP connection state (lazy-initialized)
        self._tcp_socket: socket.socket | None = None
        self._tcp_lock = threading.Lock()

    @property
    def name(self) -> str:
        return f"cef-syslog-{self._transport}"

    @property
    def display_name(self) -> str:
        transport_upper = self._transport.upper()
        if self._use_tls:
            return f"CEF (Syslog/{transport_upper}/TLS)"
        return f"CEF (Syslog/{transport_upper})"

    @property
    def host(self) -> str:
        """Syslog server hostname."""
        return self._host

    @property
    def port(self) -> int:
        """Syslog server port."""
        return self._port

    @property
    def transport(self) -> str:
        """Transport protocol (udp, tcp)."""
        return self._transport

    @property
    def facility(self) -> int:
        """Syslog facility code."""
        return self._facility

    def _calculate_pri(self, cef_severity: int) -> int:
        """Calculate syslog PRI value.

        PRI = (facility * 8) + severity

        Args:
            cef_severity: CEF severity 0-10

        Returns:
            Syslog PRI value
        """
        syslog_severity = self._formatter.map_cef_to_syslog_severity(cef_severity)
        return (self._facility * 8) + syslog_severity

    def _format_timestamp(self) -> str:
        """Format current time as RFC 5424 timestamp.

        Format: YYYY-MM-DDTHH:MM:SS.sssZ

        Returns:
            ISO 8601 timestamp string
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _get_hostname(self) -> str:
        """Get local hostname for syslog header.

        Returns:
            Local hostname
        """
        return socket.gethostname()

    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Transform RAXE event to syslog message.

        Creates RFC 5424 compliant syslog message with CEF content.

        Args:
            event: RAXE telemetry event

        Returns:
            Dict with syslog_message, cef_message, and original_event
        """
        # Get CEF formatted message
        cef_message = self._formatter.format_event(event)

        # Extract severity for PRI calculation
        cef_severity = self._formatter._extract_severity(event)
        pri = self._calculate_pri(cef_severity)

        # Build RFC 5424 header
        # Format: <PRI>VERSION TIMESTAMP HOSTNAME APP PROCID MSGID SD MSG
        timestamp = self._format_timestamp()
        hostname = self._get_hostname()
        procid = str(os.getpid())
        msgid = event.get("event_id", "-")

        # SD (Structured Data) - we use NILVALUE for now
        sd = "-"

        # Build complete syslog message
        syslog_message = (
            f"<{pri}>{self.SYSLOG_VERSION} "
            f"{timestamp} {hostname} {self.APP_NAME} {procid} {msgid} {sd} "
            f"{cef_message}"
        )

        return {
            "syslog_message": syslog_message,
            "cef_message": cef_message,
            "original_event": event,
        }

    def send_event(self, event: dict[str, Any]) -> SIEMDeliveryResult:
        """Send a single syslog message.

        Args:
            event: Transformed event (from transform_event)

        Returns:
            Delivery result
        """
        return self.send_batch([event])

    def send_batch(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        """Send batch of syslog messages.

        For UDP: Each message sent independently
        For TCP: Messages sent with octet counting framing

        Args:
            events: List of transformed events

        Returns:
            Aggregate delivery result
        """
        if not events:
            return SIEMDeliveryResult(success=True, events_accepted=0)

        if self._transport == "udp":
            return self._send_udp(events)
        else:  # tcp or tls
            return self._send_tcp(events)

    def _send_udp(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        """Send messages via UDP.

        Args:
            events: List of transformed events

        Returns:
            Delivery result
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(self._config.timeout_seconds)

                for event in events:
                    message = event["syslog_message"].encode("utf-8")
                    sock.sendto(message, (self._host, self._port))

            result = SIEMDeliveryResult(
                success=True,
                events_accepted=len(events),
            )
            self._update_stats(result, batch_size=len(events))
            return result

        except TimeoutError:
            result = SIEMDeliveryResult(
                success=False,
                error_message="UDP send timeout",
            )
            self._update_stats(result, batch_size=len(events))
            return result

        except OSError as e:
            result = SIEMDeliveryResult(
                success=False,
                error_message=f"UDP error: {e}",
            )
            self._update_stats(result, batch_size=len(events))
            return result

    def _send_tcp(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        """Send messages via TCP with optional TLS.

        Uses octet counting framing: LENGTH<space>MESSAGE

        Args:
            events: List of transformed events

        Returns:
            Delivery result
        """
        try:
            with self._tcp_lock:
                sock = self._get_tcp_socket()

                for event in events:
                    message = event["syslog_message"].encode("utf-8")
                    # Octet counting frame: LENGTH<space>MESSAGE
                    framed = f"{len(message)} ".encode() + message
                    sock.sendall(framed)

            result = SIEMDeliveryResult(
                success=True,
                events_accepted=len(events),
            )
            self._update_stats(result, batch_size=len(events))
            return result

        except TimeoutError:
            self._close_tcp_socket()
            result = SIEMDeliveryResult(
                success=False,
                error_message="TCP send timeout",
            )
            self._update_stats(result, batch_size=len(events))
            return result

        except (OSError, ssl.SSLError) as e:
            self._close_tcp_socket()
            result = SIEMDeliveryResult(
                success=False,
                error_message=f"TCP error: {e}",
            )
            self._update_stats(result, batch_size=len(events))
            return result

    def _get_tcp_socket(self) -> socket.socket:
        """Get or create TCP socket (with optional TLS).

        Returns:
            Connected socket
        """
        if self._tcp_socket is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._config.timeout_seconds)

            if self._use_tls:
                context = ssl.create_default_context()
                sock = context.wrap_socket(sock, server_hostname=self._host)

            sock.connect((self._host, self._port))
            self._tcp_socket = sock

        return self._tcp_socket

    def _close_tcp_socket(self) -> None:
        """Close TCP socket if open."""
        if self._tcp_socket is not None:
            try:
                self._tcp_socket.close()
            except OSError:
                pass
            self._tcp_socket = None

    def health_check(self) -> bool:
        """Check if syslog endpoint is reachable.

        UDP: DNS resolution check (connectionless)
        TCP: Connection attempt

        Returns:
            True if endpoint appears healthy
        """
        if self._transport == "udp":
            return self._health_check_udp()
        else:
            return self._health_check_tcp()

    def _health_check_udp(self) -> bool:
        """Check UDP endpoint via DNS resolution.

        UDP is connectionless, so we can only verify DNS.

        Returns:
            True if DNS resolves
        """
        try:
            socket.getaddrinfo(self._host, self._port)
            return True
        except socket.gaierror:
            return False

    def _health_check_tcp(self) -> bool:
        """Check TCP endpoint via connection attempt.

        Returns:
            True if connection succeeds
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)

            if self._use_tls:
                context = ssl.create_default_context()
                sock = context.wrap_socket(sock, server_hostname=self._host)

            sock.connect((self._host, self._port))
            sock.close()
            return True

        except (OSError, ssl.SSLError):
            return False

    def close(self) -> None:
        """Close resources."""
        self._close_tcp_socket()
        super().close()
