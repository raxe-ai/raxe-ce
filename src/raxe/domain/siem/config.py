"""SIEM integration configuration models.

Supports per-customer SIEM routing, allowing different customers
under the same MSSP to send events to different SIEM platforms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SIEMType(str, Enum):
    """Supported SIEM platforms."""

    SPLUNK = "splunk"
    CROWDSTRIKE = "crowdstrike"
    SENTINEL = "sentinel"
    CEF = "cef"  # Generic CEF output (HTTP or Syslog)
    ARCSIGHT = "arcsight"  # ArcSight SmartConnector specific CEF
    CUSTOM = "custom"  # For webhook-based custom integrations

    @classmethod
    def from_string(cls, value: str) -> SIEMType:
        """Create SIEMType from string, case-insensitive."""
        try:
            return cls(value.lower())
        except ValueError as err:
            valid = ", ".join(t.value for t in cls)
            raise ValueError(f"Invalid SIEM type '{value}'. Valid types: {valid}") from err


@dataclass
class SIEMConfig:
    """Configuration for a SIEM integration.

    This configuration can be attached to either an MSSP (as default)
    or to a specific customer (for per-customer routing).

    Attributes:
        siem_type: Type of SIEM platform
        endpoint_url: SIEM ingestion endpoint
        auth_token: Authentication token/key
        enabled: Whether integration is active
        batch_size: Max events per batch request
        flush_interval_seconds: Max time between flushes
        retry_count: Number of retry attempts
        timeout_seconds: HTTP request timeout
        extra: Platform-specific configuration

    Example:
        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.SPLUNK,
        ...     endpoint_url="https://splunk:8088/services/collector/event",
        ...     auth_token="your-hec-token",
        ...     extra={"index": "security", "source": "raxe"}
        ... )
    """

    siem_type: SIEMType
    endpoint_url: str
    auth_token: str
    enabled: bool = True
    batch_size: int = 100
    flush_interval_seconds: int = 10
    retry_count: int = 3
    timeout_seconds: int = 30
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values."""
        if not self.endpoint_url:
            raise ValueError("endpoint_url is required")
        if not self.auth_token:
            raise ValueError("auth_token is required")

        # Enforce HTTPS for production (allow localhost for testing, syslog:// for CEF)
        is_syslog = self.endpoint_url.startswith("syslog://")
        is_https = self.endpoint_url.startswith("https://")
        is_localhost = any(
            self.endpoint_url.startswith(prefix)
            for prefix in ("http://localhost", "http://127.0.0.1", "http://[::1]")
        )

        if not (is_https or is_localhost or is_syslog):
            raise ValueError(f"SIEM endpoint must use HTTPS or syslog://: {self.endpoint_url}")

        if self.batch_size < 1 or self.batch_size > 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        if self.flush_interval_seconds < 1 or self.flush_interval_seconds > 300:
            raise ValueError("flush_interval_seconds must be between 1 and 300")
        if self.retry_count < 0 or self.retry_count > 10:
            raise ValueError("retry_count must be between 0 and 10")
        if self.timeout_seconds < 5 or self.timeout_seconds > 120:
            raise ValueError("timeout_seconds must be between 5 and 120")

    # Splunk-specific properties
    @property
    def splunk_index(self) -> str | None:
        """Splunk index name."""
        return self.extra.get("index")

    @property
    def splunk_source(self) -> str:
        """Splunk source identifier."""
        return str(self.extra.get("source", "raxe:security"))

    @property
    def splunk_sourcetype(self) -> str:
        """Splunk sourcetype."""
        return str(self.extra.get("sourcetype", "raxe:scan"))

    # CrowdStrike-specific properties
    @property
    def crowdstrike_repository(self) -> str | None:
        """CrowdStrike LogScale repository."""
        return self.extra.get("repository")

    @property
    def crowdstrike_parser(self) -> str:
        """CrowdStrike parser name."""
        return str(self.extra.get("parser", "raxe"))

    # Sentinel-specific properties
    @property
    def sentinel_workspace_id(self) -> str | None:
        """Azure Log Analytics workspace ID."""
        return self.extra.get("workspace_id")

    @property
    def sentinel_log_type(self) -> str:
        """Custom log type name (creates table: {LogType}_CL)."""
        return str(self.extra.get("log_type", "RaxeThreatDetection"))

    # CEF-specific properties
    @property
    def cef_transport(self) -> str:
        """CEF transport protocol: http, tcp, or udp."""
        return str(self.extra.get("transport", "http"))

    @property
    def cef_port(self) -> int:
        """Syslog port for CEF (default: 514 for UDP, 6514 for TLS)."""
        return int(self.extra.get("port", 514))

    @property
    def cef_facility(self) -> int:
        """Syslog facility code (default: 16 = local0)."""
        return int(self.extra.get("facility", 16))

    @property
    def cef_use_tls(self) -> bool:
        """Whether to use TLS for TCP syslog connections."""
        return bool(self.extra.get("use_tls", False))

    # ArcSight-specific properties
    @property
    def arcsight_device_vendor(self) -> str:
        """ArcSight device vendor field."""
        return str(self.extra.get("device_vendor", "RAXE"))

    @property
    def arcsight_device_product(self) -> str:
        """ArcSight device product field."""
        return str(self.extra.get("device_product", "ThreatDetection"))

    @property
    def arcsight_device_version(self) -> str:
        """ArcSight device version field."""
        from raxe import __version__

        return str(self.extra.get("device_version", __version__))

    @property
    def arcsight_smart_connector_id(self) -> str | None:
        """ArcSight SmartConnector ID for routing."""
        return self.extra.get("smart_connector_id")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "siem_type": self.siem_type.value,
            "endpoint_url": self.endpoint_url,
            "auth_token": self.auth_token,
            "enabled": self.enabled,
            "batch_size": self.batch_size,
            "flush_interval_seconds": self.flush_interval_seconds,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SIEMConfig:
        """Create from dictionary."""
        siem_type = data.get("siem_type", "")
        if isinstance(siem_type, str):
            siem_type = SIEMType.from_string(siem_type)

        return cls(
            siem_type=siem_type,
            endpoint_url=data.get("endpoint_url", ""),
            auth_token=data.get("auth_token", ""),
            enabled=data.get("enabled", True),
            batch_size=data.get("batch_size", 100),
            flush_interval_seconds=data.get("flush_interval_seconds", 10),
            retry_count=data.get("retry_count", 3),
            timeout_seconds=data.get("timeout_seconds", 30),
            extra=data.get("extra", {}),
        )
