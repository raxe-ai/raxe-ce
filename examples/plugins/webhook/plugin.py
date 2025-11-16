"""Generic Webhook Plugin.

Example action plugin that sends scan results to a custom HTTP endpoint.
Useful for integrating RAXE with external systems like SIEM, logging
platforms, or custom alerting systems.

Configuration (~/.raxe/config.toml):
    ```toml
    [plugins.webhook]
    url = "https://your-endpoint.com/api/raxe/events"
    on_threat_only = true  # Only send when threats detected
    headers = { "Authorization" = "Bearer YOUR_TOKEN", "X-Custom" = "value" }
    timeout_seconds = 5
    retry_on_failure = false
    ```

Usage:
    1. Copy this directory to ~/.raxe/plugins/webhook/
    2. Configure your endpoint URL in config.toml
    3. Enable in plugins.enabled list
    4. RAXE will POST scan results as JSON to your endpoint
"""

import json
from typing import Any, Optional
from urllib import request
from urllib.error import HTTPError, URLError

from raxe.application.scan_pipeline import ScanPipelineResult
from raxe.plugins import ActionPlugin, PluginMetadata, PluginPriority


class WebhookPlugin(ActionPlugin):
    """Send scan results to HTTP webhook endpoint.

    POSTs scan results as JSON to a configured URL. Useful for:
    - SIEM integration
    - Custom alerting systems
    - Logging aggregation
    - Metrics collection
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="webhook",
            version="1.0.0",
            author="RAXE",
            description="Send scan results to HTTP webhook",
            priority=PluginPriority.LOW,
            requires=("raxe>=1.0.0",),
            tags=("action", "webhook", "integration"),
        )

    def on_init(self, config: dict[str, Any]) -> None:
        """Initialize with webhook configuration.

        Args:
            config: Plugin configuration from config.toml

        Raises:
            ValueError: If URL is missing or invalid
        """
        self.url = config.get("url")
        if not self.url:
            raise ValueError(
                "Webhook URL is required. "
                "Add 'url' in [plugins.webhook] config"
            )

        if not self.url.startswith(("http://", "https://")):
            raise ValueError(
                f"Invalid webhook URL: {self.url}. "
                "Must start with http:// or https://"
            )

        self.on_threat_only = config.get("on_threat_only", True)
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout_seconds", 5)
        self.retry_on_failure = config.get("retry_on_failure", False)

    def should_execute(self, result: ScanPipelineResult) -> bool:
        """Determine if webhook should be sent.

        Args:
            result: Scan pipeline result

        Returns:
            True if webhook should be sent
        """
        if self.on_threat_only:
            return result.has_threats
        return True

    def execute(self, result: ScanPipelineResult) -> None:
        """Send scan result to webhook.

        Args:
            result: Scan pipeline result

        Raises:
            Exception: If webhook fails and retry_on_failure is False
        """
        # Build payload
        payload = self._build_payload(result)

        # Send request
        try:
            self._send_webhook(payload)
        except (HTTPError, URLError) as e:
            if self.retry_on_failure:
                # Try once more
                try:
                    self._send_webhook(payload)
                except Exception:
                    # Give up
                    raise RuntimeError(f"Webhook failed after retry: {e}") from e
            else:
                raise RuntimeError(f"Webhook failed: {e}") from e

    def _build_payload(self, result: ScanPipelineResult) -> dict[str, Any]:
        """Build webhook payload from scan result.

        Args:
            result: Scan pipeline result

        Returns:
            JSON-serializable payload
        """
        # Build detections list
        detections = []
        for detection in result.scan_result.l1_result.detections:
            detections.append(
                {
                    "rule_id": detection.rule_id,
                    "severity": detection.severity.name,
                    "confidence": detection.confidence,
                    "message": detection.message,
                }
            )

        # Build complete payload
        payload = {
            "event": "scan_complete",
            "timestamp": result.metadata.get("scan_timestamp"),
            "has_threats": result.has_threats,
            "should_block": result.should_block,
            "policy_decision": result.policy_decision.value,
            "severity": result.severity,
            "total_detections": result.total_detections,
            "detections": detections,
            "performance": {
                "duration_ms": result.duration_ms,
                "l1_duration_ms": result.metadata.get("l1_duration_ms"),
                "l2_duration_ms": result.metadata.get("l2_duration_ms"),
            },
            "text_hash": result.text_hash,  # Privacy-preserving hash
        }

        return payload

    def _send_webhook(self, payload: dict[str, Any]) -> None:
        """Send HTTP POST request to webhook URL.

        Args:
            payload: JSON payload to send

        Raises:
            HTTPError: If server returns error status
            URLError: If network error occurs
        """
        # Prepare request
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            **self.headers,
        }

        req = request.Request(self.url, data=data, headers=headers)

        # Send request
        with request.urlopen(req, timeout=self.timeout) as response:
            if response.status not in (200, 201, 202):
                raise HTTPError(
                    self.url,
                    response.status,
                    f"Webhook returned status {response.status}",
                    response.headers,
                    None,
                )

    def on_shutdown(self) -> None:
        """Cleanup on shutdown."""
        # No cleanup needed
        pass


# Required: Export plugin instance
plugin = WebhookPlugin()
