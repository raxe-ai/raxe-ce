"""Microsoft Sentinel adapter via Data Collector API.

Sends RAXE events to Azure Log Analytics workspace.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
from typing import Any

import requests

from raxe.infrastructure.siem.base import BaseSIEMAdapter, SIEMDeliveryResult


class SentinelAdapter(BaseSIEMAdapter):
    """Microsoft Sentinel adapter via Data Collector API.

    Sends events to Azure Log Analytics workspace which is the backend
    for Microsoft Sentinel.

    Endpoint Format:
        https://<workspace_id>.ods.opinsights.azure.com/api/logs?api-version=2016-04-01

    Authentication:
        SharedKey authentication with HMAC-SHA256 signature

    Note:
        The auth_token should be the Log Analytics workspace shared key
        (primary or secondary key from Agents management).

    Example:
        >>> from raxe.domain.siem.config import SIEMConfig, SIEMType
        >>> config = SIEMConfig(
        ...     siem_type=SIEMType.SENTINEL,
        ...     endpoint_url="https://xxx.ods.opinsights.azure.com/api/logs",
        ...     auth_token="your-shared-key",
        ...     extra={
        ...         "workspace_id": "your-workspace-id",
        ...         "log_type": "RaxeThreatDetection"
        ...     }
        ... )
        >>> adapter = SentinelAdapter(config)
    """

    API_VERSION = "2016-04-01"

    @property
    def name(self) -> str:
        return "sentinel"

    @property
    def display_name(self) -> str:
        return "Microsoft Sentinel"

    def _build_signature(
        self,
        date: str,
        content_length: int,
        method: str = "POST",
        content_type: str = "application/json",
        resource: str = "/api/logs",
    ) -> str:
        """Build Azure SharedKey signature for authentication.

        The signature format is:
        POST\n<content-length>\napplication/json\nx-ms-date:<date>\n/api/logs

        Args:
            date: RFC 7231 formatted date string
            content_length: Length of request body in bytes
            method: HTTP method (POST)
            content_type: Content type header value
            resource: API resource path

        Returns:
            Authorization header value: "SharedKey <workspace_id>:<signature>"
        """
        x_headers = f"x-ms-date:{date}"
        string_to_sign = f"{method}\n{content_length}\n{content_type}\n{x_headers}\n{resource}"

        # Decode the base64 shared key
        decoded_key = base64.b64decode(self._config.auth_token)

        # Create HMAC-SHA256 signature
        encoded_hash = base64.b64encode(
            hmac.new(decoded_key, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")

        workspace_id = self._config.sentinel_workspace_id
        return f"SharedKey {workspace_id}:{encoded_hash}"

    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Transform RAXE event to Sentinel/Log Analytics format.

        Sentinel expects flat JSON with specific field naming:
        - TimeGenerated: ISO 8601 timestamp (used for time-based queries)
        - Custom fields become columns in the custom log table

        The log type name determines the table: {LogType}_CL
        e.g., "RaxeThreatDetection" creates "RaxeThreatDetection_CL"
        """
        payload = event.get("payload", {})
        metadata = event.get("_metadata", {})
        l1 = payload.get("l1", {})
        l2 = payload.get("l2", {})

        sentinel_event = {
            # Required time field for Log Analytics
            "TimeGenerated": event.get("timestamp"),
            # Event identification
            "EventType": event.get("event_type"),
            "EventId": event.get("event_id"),
            "Priority": event.get("priority"),
            # Threat detection
            "ThreatDetected": payload.get("threat_detected", False),
            "Severity": self._extract_severity(event),
            "ActionTaken": payload.get("action_taken"),
            # Detection details (as JSON strings for complex types)
            "RuleIds": json.dumps(self._extract_rule_ids(event)),
            "Families": json.dumps(self._extract_families(event)),
            # Scan context
            "PromptHash": payload.get("prompt_hash"),
            "PromptLength": payload.get("prompt_length"),
            "ScanDurationMs": payload.get("scan_duration_ms"),
            "EntryPoint": payload.get("entry_point"),
            # L1 detection summary
            "L1Hit": l1.get("hit", False),
            "L1DetectionCount": l1.get("detection_count", 0),
            "L1HighestSeverity": l1.get("highest_severity", "none"),
            # L2 ML summary
            "L2Hit": l2.get("hit", False),
            "L2Severity": l2.get("severity", "none"),
            "L2Confidence": l2.get("voting", {}).get("confidence"),
            # MSSP context
            "MsspId": payload.get("mssp_id"),
            "CustomerId": payload.get("customer_id"),
            "AgentId": payload.get("agent_id"),
            # Agent/client info
            "ClientVersion": metadata.get("version"),
            "InstallationId": metadata.get("installation_id"),
        }

        # Include full MSSP data if present (as JSON string)
        mssp_data = payload.get("_mssp_data")
        if mssp_data:
            sentinel_event["MsspData"] = json.dumps(mssp_data)

        return sentinel_event

    def send_event(self, event: dict[str, Any]) -> SIEMDeliveryResult:
        """Send a single event to Sentinel."""
        return self.send_batch([event])

    def send_batch(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        """Send batch of events to Sentinel.

        Log Analytics expects a JSON array of events.
        """
        if not events:
            return SIEMDeliveryResult(success=True, events_accepted=0)

        try:
            body = json.dumps(events)
            content_length = len(body)

            # RFC 7231 date format required by Azure
            rfc7231_date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

            # Build authorization header
            signature = self._build_signature(
                date=rfc7231_date,
                content_length=content_length,
            )

            headers = {
                "Content-Type": "application/json",
                "Authorization": signature,
                "Log-Type": self._config.sentinel_log_type,
                "x-ms-date": rfc7231_date,
                "time-generated-field": "TimeGenerated",
            }

            url = f"{self._config.endpoint_url}?api-version={self.API_VERSION}"

            # Don't use session with pre-configured auth for Sentinel
            # as it needs per-request signature
            response = requests.post(
                url,
                data=body,
                headers=headers,
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

        except Exception as e:
            # Handle signature building errors (invalid key format, etc.)
            result = SIEMDeliveryResult(
                success=False,
                error_message=f"Request preparation failed: {e}",
            )
            self._update_stats(result, batch_size=len(events))
            return result

    def _parse_response(self, response: requests.Response, batch_size: int) -> SIEMDeliveryResult:
        """Parse Log Analytics response.

        Log Analytics returns:
        - 200/202: Success (data accepted for processing)
        - 400: Bad request (invalid format, missing fields)
        - 401: Unauthorized (invalid signature/key)
        - 403: Forbidden (workspace not accessible)
        - 429: Rate limited
        """
        if response.status_code in (200, 202):
            return SIEMDeliveryResult(
                success=True,
                status_code=response.status_code,
                events_accepted=batch_size,
            )

        # Parse error response
        error_message = f"HTTP {response.status_code}"
        if response.text:
            error_message = f"{error_message}: {response.text[:200]}"

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
        """Check Sentinel endpoint accessibility.

        Log Analytics doesn't have a dedicated health endpoint.
        We verify the workspace URL is reachable and the workspace exists.
        A 400/401/403 response means the endpoint exists (auth required).
        """
        try:
            response = requests.head(
                self._config.endpoint_url,
                timeout=10,
            )
            # These status codes indicate the endpoint exists
            return response.status_code in (200, 400, 401, 403, 405)

        except requests.RequestException:
            return False
