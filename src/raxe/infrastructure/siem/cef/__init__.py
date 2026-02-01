"""CEF (Common Event Format) SIEM adapters.

Provides adapters for sending RAXE events in CEF format:
- CEFFormatter: Pure formatting logic (no I/O)
- CEFHTTPAdapter: CEF over HTTP
- CEFSyslogAdapter: CEF over Syslog (UDP/TCP/TLS)
- ArcSightAdapter: ArcSight SmartConnector specific
"""

from raxe.infrastructure.siem.cef.arcsight_adapter import ArcSightAdapter
from raxe.infrastructure.siem.cef.formatter import CEFFormatter
from raxe.infrastructure.siem.cef.http_adapter import CEFHTTPAdapter
from raxe.infrastructure.siem.cef.syslog_adapter import CEFSyslogAdapter

__all__ = [
    "ArcSightAdapter",
    "CEFFormatter",
    "CEFHTTPAdapter",
    "CEFSyslogAdapter",
]
