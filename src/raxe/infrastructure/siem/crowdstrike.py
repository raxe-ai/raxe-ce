"""CrowdStrike Falcon LogScale (Humio) adapter.

Sends RAXE events via the HEC-compatible API.
"""

from __future__ import annotations

from typing import Any, ClassVar

import requests

from raxe.infrastructure.siem.base import BaseSIEMAdapter, SIEMDeliveryResult


class CrowdStrikeAdapter(BaseSIEMAdapter):
    """CrowdStrike Falcon LogScale (Humio) adapter.

    Sends events via the HEC-compatible API or native ingest API.

    Endpoint Format:
        https://<region>.humio.com/api/v1/ingest/hec

    Authentication:
        Authorization: Bearer <ingest-token>

    Example:
        >>> from raxe.domain.siem.config import SIEMConfig, SIEMType
        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.CROWDSTRIKE,
        ...     endpoint_url="https://cloud.us.humio.com/api/v1/ingest/hec",
        ...     auth_token="your-ingest-token",
        ...     extra={"repository": "raxe-security", "parser": "raxe"}
        ... )
        >>> adapter = CrowdStrikeAdapter(config)
    """

    # Map RAXE severity to CrowdStrike severity levels
    SEVERITY_MAP: ClassVar[dict[str, str]] = {
        "none": "informational",
        "LOW": "low",
        "MEDIUM": "medium",
        "HIGH": "high",
        "CRITICAL": "critical",
    }

    @property
    def name(self) -> str:
        return "crowdstrike"

    @property
    def display_name(self) -> str:
        return "CrowdStrike Falcon LogScale"

    def _configure_session(self, session: requests.Session) -> None:
        """Configure session with Bearer token authentication."""
        session.headers.update(
            {
                "Authorization": f"Bearer {self._config.auth_token}",
                "Content-Type": "application/json",
            }
        )

    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Transform RAXE event to CrowdStrike LogScale format.

        LogScale HEC format is similar to Splunk but uses millisecond timestamps:
        {
            "time": <epoch_millis>,
            "source": <source>,
            "sourcetype": <sourcetype>,
            "event": <event_data>
        }

        Uses @tags for parser routing in LogScale.
        """
        payload = event.get("payload", {})
        metadata = event.get("_metadata", {})
        timestamp = event.get("timestamp", "")

        # LogScale expects milliseconds
        epoch_millis = int(self._extract_timestamp_epoch(event) * 1000)

        logscale_event = {
            "time": epoch_millis,
            "source": "raxe-agent",
            "sourcetype": "raxe:threat",
            "event": {
                # LogScale parser routing
                "@timestamp": timestamp,
                "@tags": [self._config.crowdstrike_parser],
                # Event identification
                "event_type": event.get("event_type"),
                "event_id": event.get("event_id"),
                "priority": event.get("priority"),
                # Threat detection
                "threat_detected": payload.get("threat_detected", False),
                "severity": self._map_severity(event),
                "action_taken": payload.get("action_taken"),
                # Detection details
                "rule_ids": self._extract_rule_ids(event),
                "families": self._extract_families(event),
                # Scan context
                "prompt_hash": payload.get("prompt_hash"),
                "prompt_length": payload.get("prompt_length"),
                "scan_duration_ms": payload.get("scan_duration_ms"),
                "entry_point": payload.get("entry_point"),
                # Agent/client info
                "client_version": metadata.get("version"),
                "installation_id": metadata.get("installation_id"),
                # MSSP context (nested for cleaner queries)
                "mssp": {
                    "mssp_id": payload.get("mssp_id"),
                    "customer_id": payload.get("customer_id"),
                    "agent_id": payload.get("agent_id"),
                },
                # Detection layer results
                "l1": {
                    "hit": payload.get("l1", {}).get("hit", False),
                    "detection_count": payload.get("l1", {}).get("detection_count", 0),
                    "highest_severity": payload.get("l1", {}).get("highest_severity", "none"),
                    "families": payload.get("l1", {}).get("families", []),
                },
                "l2": {
                    "hit": payload.get("l2", {}).get("hit", False),
                    "severity": payload.get("l2", {}).get("severity", "none"),
                    "confidence": payload.get("l2", {}).get("voting", {}).get("confidence"),
                },
            },
        }

        # Include full MSSP data if present (for full data mode)
        mssp_data = payload.get("_mssp_data")
        if mssp_data:
            event_data = logscale_event["event"]
            if isinstance(event_data, dict):
                event_data["_mssp_data"] = mssp_data

        return logscale_event

    def _map_severity(self, event: dict[str, Any]) -> str:
        """Map RAXE severity to CrowdStrike severity level."""
        raxe_severity = self._extract_severity(event)
        return self.SEVERITY_MAP.get(raxe_severity, "informational")

    def send_event(self, event: dict[str, Any]) -> SIEMDeliveryResult:
        """Send a single event to LogScale."""
        return self.send_batch([event])

    def send_batch(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        """Send batch of events to LogScale.

        LogScale HEC accepts an array of events.
        """
        if not events:
            return SIEMDeliveryResult(success=True, events_accepted=0)

        try:
            response = self._get_session().post(
                self._config.endpoint_url,
                json=events,
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

    def _parse_response(self, response: requests.Response, batch_size: int) -> SIEMDeliveryResult:
        """Parse LogScale response.

        LogScale HEC returns:
        - 200/204: Success
        - 400: Bad request (invalid format)
        - 401: Unauthorized (invalid token)
        - 429: Rate limited
        """
        if response.status_code in (200, 204):
            return SIEMDeliveryResult(
                success=True,
                status_code=response.status_code,
                events_accepted=batch_size,
            )

        # Parse error response
        try:
            error_data = response.json()
            error_message = error_data.get("error", str(error_data))
        except (ValueError, KeyError):
            error_message = f"HTTP {response.status_code}: {response.text[:200]}"

        # Check for rate limiting
        retry_after = None
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))

        return SIEMDeliveryResult(
            success=False,
            status_code=response.status_code,
            error_message=error_message,
            retry_after=retry_after,
        )

    def health_check(self) -> bool:
        """Check LogScale API health.

        Uses the status endpoint to verify connectivity.
        """
        try:
            # LogScale status endpoint
            base_url = self._config.endpoint_url.rsplit("/api/", 1)[0]
            status_url = f"{base_url}/api/v1/status"

            response = self._get_session().get(
                status_url,
                timeout=10,
            )
            return bool(response.status_code == 200)

        except requests.RequestException:
            return False
