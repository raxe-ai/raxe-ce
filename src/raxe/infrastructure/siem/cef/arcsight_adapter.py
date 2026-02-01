"""ArcSight SmartConnector adapter.

Extends CEF HTTP adapter with ArcSight-specific extensions:
- deviceDirection for traffic analysis
- cat (category) for ArcSight categorization
- dvc/dvchost for SmartConnector routing

Uses same HTTP transport as CEF HTTP adapter.
"""

from __future__ import annotations

import socket
from typing import Any

from raxe.infrastructure.siem.cef.http_adapter import CEFHTTPAdapter


class ArcSightAdapter(CEFHTTPAdapter):
    """ArcSight SmartConnector adapter.

    Extends CEF HTTP adapter with ArcSight-specific fields:
    - deviceDirection: Traffic direction (0=inbound prompts)
    - cat: ArcSight category path (e.g., /Security/Attack/Injection)
    - dvc/dvchost: Device address for SmartConnector routing

    Example:
        >>> from raxe.domain.siem.config import SIEMConfig, SIEMType
        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.ARCSIGHT,
        ...     endpoint_url="https://arcsight.example.com/receiver/v1/events",
        ...     auth_token="your-token",
        ...     extra={"smart_connector_id": "sc-001"}
        ... )
        >>> adapter = ArcSightAdapter(config)
        >>> event = adapter.transform_event(raxe_event)
        >>> result = adapter.send_event(event)
    """

    @property
    def name(self) -> str:
        return "arcsight"

    @property
    def display_name(self) -> str:
        return "ArcSight SmartConnector"

    @property
    def smart_connector_id(self) -> str | None:
        """ArcSight SmartConnector ID for routing."""
        return self._config.arcsight_smart_connector_id

    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Transform RAXE event to ArcSight CEF format.

        Adds ArcSight-specific extensions to the CEF message.

        Args:
            event: RAXE telemetry event

        Returns:
            Dict with cef_message (with ArcSight extensions) and original_event
        """
        # Get base CEF message
        base_result = super().transform_event(event)
        cef_message = base_result["cef_message"]

        # Add ArcSight-specific extensions
        arcsight_extensions = self._build_arcsight_extensions(event)
        if arcsight_extensions:
            cef_message = cef_message + " " + arcsight_extensions

        return {
            "cef_message": cef_message,
            "original_event": event,
        }

    def _build_arcsight_extensions(self, event: dict[str, Any]) -> str:
        """Build ArcSight-specific CEF extension fields.

        Args:
            event: RAXE event

        Returns:
            Space-separated extension string
        """
        payload = event.get("payload", {})
        l1 = payload.get("l1", {})
        families = l1.get("families", [])

        extensions: dict[str, Any] = {}

        # deviceDirection: 0 = inbound (prompts coming in)
        extensions["deviceDirection"] = 0

        # cat: ArcSight category based on threat family
        category = self._formatter._get_arcsight_category(families)
        extensions["cat"] = self._formatter._escape_extension(category)

        # dvchost: Local hostname for SmartConnector routing
        extensions["dvchost"] = socket.gethostname()

        # SmartConnector ID if configured
        if self.smart_connector_id:
            extensions["deviceExternalId"] = self.smart_connector_id

        return self._formatter._build_extension(extensions)
