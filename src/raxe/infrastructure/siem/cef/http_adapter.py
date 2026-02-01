"""CEF HTTP adapter.

Sends CEF-formatted events over HTTP(S) as plain text.
Suitable for generic CEF collectors that accept HTTP POST.
"""

from __future__ import annotations

from typing import Any

import requests

from raxe.domain.siem.config import SIEMConfig
from raxe.infrastructure.siem.base import BaseSIEMAdapter, SIEMDeliveryResult
from raxe.infrastructure.siem.cef.formatter import CEFFormatter


class CEFHTTPAdapter(BaseSIEMAdapter):
    """CEF over HTTP adapter.

    Sends CEF-formatted events as plain text HTTP POST requests.
    Uses Bearer token authentication by default.

    Example:
        >>> from raxe.domain.siem.config import SIEMConfig, SIEMType
        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.CEF,
        ...     endpoint_url="https://collector.example.com/cef",
        ...     auth_token="your-token",
        ... )
        >>> adapter = CEFHTTPAdapter(config)
        >>> event = adapter.transform_event(raxe_event)
        >>> result = adapter.send_event(event)
    """

    def __init__(self, config: SIEMConfig) -> None:
        """Initialize CEF HTTP adapter.

        Args:
            config: SIEM configuration
        """
        super().__init__(config)
        self._formatter = CEFFormatter(
            device_vendor=config.arcsight_device_vendor,
            device_product=config.arcsight_device_product,
            device_version=config.arcsight_device_version,
        )

    @property
    def name(self) -> str:
        return "cef"

    @property
    def display_name(self) -> str:
        return "CEF (HTTP)"

    def _configure_session(self, session: requests.Session) -> None:
        """Configure session with Bearer token authentication."""
        session.headers.update(
            {
                "Authorization": f"Bearer {self._config.auth_token}",
                "Content-Type": "text/plain; charset=utf-8",
            }
        )

    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Transform RAXE event to CEF format.

        Returns a dict with:
        - cef_message: The CEF-formatted string
        - original_event: The original event for reference

        Args:
            event: RAXE telemetry event

        Returns:
            Dict with cef_message and original_event
        """
        cef_message = self._formatter.format_event(event)
        return {
            "cef_message": cef_message,
            "original_event": event,
        }

    def send_event(self, event: dict[str, Any]) -> SIEMDeliveryResult:
        """Send a single CEF event over HTTP.

        Args:
            event: Transformed event (from transform_event)

        Returns:
            Delivery result
        """
        return self.send_batch([event])

    def send_batch(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        """Send batch of CEF events over HTTP.

        Events are newline-delimited in the request body.

        Args:
            events: List of transformed events

        Returns:
            Aggregate delivery result
        """
        if not events:
            return SIEMDeliveryResult(success=True, events_accepted=0)

        try:
            # Build newline-delimited CEF messages
            cef_messages = [e["cef_message"] for e in events]
            batch_data = "\n".join(cef_messages)

            response = self._get_session().post(
                self._config.endpoint_url,
                data=batch_data,
                timeout=self._config.timeout_seconds,
            )

            result = self._parse_response(response, len(events))
            self._update_stats(result, batch_size=len(events))
            return result

        except requests.Timeout:
            result = SIEMDeliveryResult(
                success=False,
                error_message="Request timeout",
            )
            self._update_stats(result, batch_size=len(events))
            return result

        except requests.RequestException as e:
            result = SIEMDeliveryResult(
                success=False,
                error_message=str(e),
            )
            self._update_stats(result, batch_size=len(events))
            return result

    def _parse_response(
        self,
        response: requests.Response,
        batch_size: int,
    ) -> SIEMDeliveryResult:
        """Parse HTTP response from CEF collector.

        Most CEF collectors return:
        - 200/201: Success
        - 400: Bad request
        - 401/403: Authentication error
        - 500/503: Server error

        Args:
            response: HTTP response
            batch_size: Number of events in batch

        Returns:
            Parsed delivery result
        """
        if response.status_code in (200, 201, 202, 204):
            return SIEMDeliveryResult(
                success=True,
                status_code=response.status_code,
                events_accepted=batch_size,
            )

        # Parse error
        error_message: str = f"HTTP {response.status_code}"
        try:
            error_data = response.json()
            if isinstance(error_data, dict):
                error_val = error_data.get("error", error_data.get("message", str(error_data)))
                error_message = str(error_val) if error_val else error_message
        except ValueError:
            if response.text:
                error_message = f"HTTP {response.status_code}: {response.text[:200]}"

        # Check for rate limiting
        retry_after = None
        if response.status_code in (429, 503):
            retry_after = int(response.headers.get("Retry-After", 30))

        return SIEMDeliveryResult(
            success=False,
            status_code=response.status_code,
            error_message=error_message,
            retry_after=retry_after,
        )

    def health_check(self) -> bool:
        """Check if CEF collector endpoint is reachable.

        Uses HEAD request for minimal overhead.

        Returns:
            True if endpoint is reachable
        """
        try:
            response = self._get_session().head(
                self._config.endpoint_url,
                timeout=10,
            )
            # Accept any 2xx or 405 (Method Not Allowed - endpoint exists)
            return bool(response.status_code < 500 or response.status_code == 405)

        except requests.RequestException:
            return False
