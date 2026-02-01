"""SIEM integration infrastructure.

Provides adapters for sending RAXE events to SIEM platforms:
- Splunk (via HTTP Event Collector)
- CrowdStrike Falcon LogScale (Humio)
- Microsoft Sentinel (via Data Collector API)
- CEF (Common Event Format) via HTTP or Syslog
- ArcSight SmartConnector

Example:
    >>> from raxe.infrastructure.siem import create_siem_adapter, SIEMDispatcher
    >>> from raxe.domain.siem.config import SIEMConfig, SIEMType
    >>>
    >>> # Create adapter from configuration
    >>> config = SIEMConfig(
    ...     siem_type=SIEMType.SPLUNK,
    ...     endpoint_url="https://splunk:8088/services/collector/event",
    ...     auth_token="your-token",
    ... )
    >>> adapter = create_siem_adapter(config)
    >>>
    >>> # Use dispatcher for multi-adapter routing
    >>> dispatcher = SIEMDispatcher()
    >>> dispatcher.register_adapter(adapter)
    >>> dispatcher.start()
    >>> dispatcher.dispatch(event)
    >>> dispatcher.stop()
"""

from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem.base import (
    BaseSIEMAdapter,
    SIEMAdapter,
    SIEMDeliveryResult,
)
from raxe.infrastructure.siem.cef import (
    ArcSightAdapter,
    CEFFormatter,
    CEFHTTPAdapter,
    CEFSyslogAdapter,
)
from raxe.infrastructure.siem.crowdstrike import CrowdStrikeAdapter
from raxe.infrastructure.siem.dispatcher import (
    DispatcherStats,
    SIEMDispatcher,
    SIEMDispatcherConfig,
)
from raxe.infrastructure.siem.sentinel import SentinelAdapter
from raxe.infrastructure.siem.splunk import SplunkHECAdapter


def create_siem_adapter(config: SIEMConfig) -> SIEMAdapter:
    """Factory function to create SIEM adapter from configuration.

    Args:
        config: SIEM configuration

    Returns:
        Configured SIEM adapter instance

    Raises:
        ValueError: If SIEM type is not supported

    Example:
        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.SPLUNK,
        ...     endpoint_url="https://splunk:8088/services/collector/event",
        ...     auth_token="token",
        ... )
        >>> adapter = create_siem_adapter(config)
        >>> adapter.name
        'splunk'

        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.CEF,
        ...     endpoint_url="https://collector.example.com/cef",
        ...     auth_token="token",
        ... )
        >>> adapter = create_siem_adapter(config)
        >>> adapter.name
        'cef'
    """
    # CEF adapter selection based on transport
    if config.siem_type == SIEMType.CEF:
        if config.cef_transport in ("tcp", "udp"):
            return CEFSyslogAdapter(config)
        return CEFHTTPAdapter(config)

    # ArcSight uses HTTP transport
    if config.siem_type == SIEMType.ARCSIGHT:
        return ArcSightAdapter(config)

    adapters: dict[SIEMType, type[SIEMAdapter]] = {
        SIEMType.SPLUNK: SplunkHECAdapter,
        SIEMType.CROWDSTRIKE: CrowdStrikeAdapter,
        SIEMType.SENTINEL: SentinelAdapter,
    }

    adapter_class = adapters.get(config.siem_type)
    if adapter_class is None:
        supported = ", ".join(t.value for t in adapters.keys())
        raise ValueError(
            f"Unsupported SIEM type: {config.siem_type.value}. " f"Supported types: {supported}"
        )

    return adapter_class(config)


__all__ = [
    "ArcSightAdapter",
    "BaseSIEMAdapter",
    "CEFFormatter",
    "CEFHTTPAdapter",
    "CEFSyslogAdapter",
    "CrowdStrikeAdapter",
    "DispatcherStats",
    "SIEMAdapter",
    "SIEMConfig",
    "SIEMDeliveryResult",
    "SIEMDispatcher",
    "SIEMDispatcherConfig",
    "SIEMType",
    "SentinelAdapter",
    "SplunkHECAdapter",
    "create_siem_adapter",
]
