"""Splunk HTTP Event Collector (HEC) adapter.

Sends RAXE events to Splunk via the HEC API endpoint.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from raxe.infrastructure.siem.base import BaseSIEMAdapter, SIEMDeliveryResult


class SplunkHECAdapter(BaseSIEMAdapter):
    """Splunk HTTP Event Collector (HEC) adapter.

    Sends events to Splunk via the HEC API endpoint.

    HEC Endpoint Format:
        https://<splunk-host>:8088/services/collector/event

    Authentication:
        Authorization: Splunk <HEC-token>

    Example:
        >>> from raxe.domain.siem.config import SIEMConfig, SIEMType
        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.SPLUNK,
        ...     endpoint_url="https://splunk.company.com:8088/services/collector/event",
        ...     auth_token="your-hec-token",
        ...     extra={"index": "security", "source": "raxe"}
        ... )
        >>> adapter = SplunkHECAdapter(config)
        >>> event = adapter.transform_event(raxe_event)
        >>> result = adapter.send_event(event)
    """

    @property
    def name(self) -> str:
        return "splunk"

    @property
    def display_name(self) -> str:
        return "Splunk (HEC)"

    def _configure_session(self, session: requests.Session) -> None:
        """Configure session with Splunk HEC authentication."""
        session.headers.update(
            {
                "Authorization": f"Splunk {self._config.auth_token}",
                "Content-Type": "application/json",
            }
        )

    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Transform RAXE event to Splunk HEC format.

        Splunk HEC format:
        {
            "time": <epoch_timestamp>,
            "host": <hostname>,
            "source": <source>,
            "sourcetype": <sourcetype>,
            "index": <index>,
            "event": <event_data>
        }
        """
        payload = event.get("payload", {})
        metadata = event.get("_metadata", {})

        hec_event = {
            "time": self._extract_timestamp_epoch(event),
            "host": metadata.get("installation_id", "raxe-agent"),
            "source": self._config.splunk_source,
            "sourcetype": self._config.splunk_sourcetype,
            "event": {
                "event_type": event.get("event_type"),
                "event_id": event.get("event_id"),
                "priority": event.get("priority"),
                "severity": self._extract_severity(event),
                "threat_detected": payload.get("threat_detected", False),
                "rule_ids": self._extract_rule_ids(event),
                "families": self._extract_families(event),
                "prompt_hash": payload.get("prompt_hash"),
                "prompt_length": payload.get("prompt_length"),
                "action_taken": payload.get("action_taken"),
                "scan_duration_ms": payload.get("scan_duration_ms"),
                "entry_point": payload.get("entry_point"),
                "client_version": metadata.get("version"),
                # MSSP context
                "mssp_id": payload.get("mssp_id"),
                "customer_id": payload.get("customer_id"),
                "agent_id": payload.get("agent_id"),
                # L1 detection summary
                "l1_hit": payload.get("l1", {}).get("hit", False),
                "l1_detection_count": payload.get("l1", {}).get("detection_count", 0),
                # L2 ML summary
                "l2_hit": payload.get("l2", {}).get("hit", False),
                "l2_confidence": payload.get("l2", {}).get("voting", {}).get("confidence"),
            },
        }

        # Add index if configured
        if self._config.splunk_index:
            hec_event["index"] = self._config.splunk_index

        # Include full MSSP data if present (for full data mode)
        mssp_data = payload.get("_mssp_data")
        if mssp_data:
            hec_event["event"]["_mssp_data"] = mssp_data

        return hec_event

    def send_event(self, event: dict[str, Any]) -> SIEMDeliveryResult:
        """Send a single event to Splunk HEC."""
        return self.send_batch([event])

    def send_batch(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        """Send batch of events to Splunk HEC.

        HEC supports newline-delimited JSON for batches.
        """
        if not events:
            return SIEMDeliveryResult(success=True, events_accepted=0)

        try:
            # Splunk HEC batch format: newline-delimited JSON
            batch_data = "\n".join(json.dumps(e) for e in events)

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

    def _parse_response(self, response: requests.Response, batch_size: int) -> SIEMDeliveryResult:
        """Parse Splunk HEC response.

        Splunk HEC returns:
        - 200 OK: {"text": "Success", "code": 0}
        - 400 Bad Request: {"text": "...", "code": 6}
        - 403 Forbidden: Token invalid
        - 503 Service Unavailable: Indexer busy
        """
        if response.status_code == 200:
            return SIEMDeliveryResult(
                success=True,
                status_code=200,
                events_accepted=batch_size,
            )

        # Parse error response
        try:
            error_data = response.json()
            error_text = error_data.get("text", "Unknown error")
            error_code = error_data.get("code", -1)
            error_message = f"Splunk HEC error {error_code}: {error_text}"
        except (ValueError, KeyError):
            error_message = f"HTTP {response.status_code}: {response.text[:200]}"

        # Check for rate limiting
        retry_after = None
        if response.status_code == 503:
            retry_after = int(response.headers.get("Retry-After", 30))

        return SIEMDeliveryResult(
            success=False,
            status_code=response.status_code,
            error_message=error_message,
            retry_after=retry_after,
        )

    def health_check(self) -> bool:
        """Check Splunk HEC endpoint health.

        Uses the /services/collector/health endpoint if available,
        otherwise attempts a minimal event submission.
        """
        try:
            # Splunk HEC health check endpoint (Splunk 7.3+)
            health_url = self._config.endpoint_url.replace(
                "/services/collector/event", "/services/collector/health"
            )
            response = self._get_session().get(
                health_url,
                timeout=10,
            )
            return bool(response.status_code == 200)

        except requests.RequestException:
            return False
