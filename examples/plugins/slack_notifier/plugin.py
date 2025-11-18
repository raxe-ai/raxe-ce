"""Slack Notification Plugin.

Example action plugin that sends threat alerts to a Slack channel
via incoming webhook.

Configuration (~/.raxe/config.yaml):
    ```yaml
    plugins:
      slack_notifier:
        webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
        channel: "#security-alerts"
        min_severity: "HIGH"  # Only alert on HIGH or CRITICAL
        on_threat_only: true  # Only send when threats detected
    ```

Setup:
    1. Create Slack incoming webhook at https://api.slack.com/messaging/webhooks
    2. Copy this directory to ~/.raxe/plugins/slack_notifier/
    3. Add configuration to ~/.raxe/config.yaml with your webhook URL
    4. Enable in plugins.enabled list

Security Note:
    Never commit webhook URLs to version control!
    Use environment variables or secure config files.
"""

import json
import time
from typing import Any, Optional
from urllib import request
from urllib.error import URLError

from raxe.application.scan_pipeline import ScanPipelineResult
from raxe.domain.rules.models import Severity
from raxe.plugins import ActionPlugin, PluginMetadata, PluginPriority


class SlackNotifierPlugin(ActionPlugin):
    """Send threat alerts to Slack channel.

    Sends formatted messages to Slack when threats are detected.
    Includes severity, detection count, and policy decision.
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="slack_notifier",
            version="1.0.0",
            author="RAXE",
            description="Send security alerts to Slack channel",
            priority=PluginPriority.LOW,  # Run after other plugins
            requires=("raxe>=1.0.0",),
            tags=("action", "notification", "slack"),
        )

    def on_init(self, config: dict[str, Any]) -> None:
        """Initialize with Slack configuration.

        Args:
            config: Plugin configuration from config.yaml

        Raises:
            ValueError: If webhook_url is missing
        """
        self.webhook_url = config.get("webhook_url")
        if not self.webhook_url:
            raise ValueError(
                "Slack webhook URL is required. "
                "Add 'webhook_url' in [plugins.slack_notifier] config"
            )

        self.channel = config.get("channel", "#security-alerts")
        self.on_threat_only = config.get("on_threat_only", True)

        # Parse minimum severity
        min_severity_str = config.get("min_severity", "LOW")
        try:
            self.min_severity = Severity[min_severity_str.upper()]
        except KeyError:
            raise ValueError(
                f"Invalid min_severity: {min_severity_str}. "
                f"Must be one of: {[s.name for s in Severity]}"
            ) from None

    def should_execute(self, result: ScanPipelineResult) -> bool:
        """Determine if alert should be sent.

        Args:
            result: Scan pipeline result

        Returns:
            True if alert should be sent
        """
        # Skip if no threats and on_threat_only is enabled
        if self.on_threat_only and not result.has_threats:
            return False

        # Skip if no threats detected
        if not result.has_threats:
            return False

        # Check if any detection meets minimum severity
        for detection in result.scan_result.l1_result.detections:
            if detection.severity.value >= self.min_severity.value:
                return True

        return False

    def execute(self, result: ScanPipelineResult) -> None:
        """Send alert to Slack.

        Args:
            result: Scan pipeline result
        """
        # Build Slack message
        message = self._build_message(result)

        # Send to Slack
        try:
            self._send_to_slack(message)
        except URLError as e:
            # Log error but don't crash
            raise RuntimeError(f"Failed to send Slack notification: {e}") from e

    def _build_message(self, result: ScanPipelineResult) -> dict[str, Any]:
        """Build Slack message payload.

        Args:
            result: Scan pipeline result

        Returns:
            Slack message payload
        """
        # Severity emoji mapping
        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🔵",
        }

        severity = result.severity or "NONE"
        emoji = severity_emoji.get(severity, "⚪")

        # Message color
        color = "danger" if result.should_block else "warning"

        # Build message
        message = {
            "channel": self.channel,
            "username": "RAXE Security",
            "icon_emoji": ":shield:",
            "text": f"{emoji} *Security Threat Detected*",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": severity,
                            "short": True,
                        },
                        {
                            "title": "Detections",
                            "value": str(result.total_detections),
                            "short": True,
                        },
                        {
                            "title": "Action",
                            "value": result.policy_decision.value,
                            "short": True,
                        },
                        {
                            "title": "Duration",
                            "value": f"{result.duration_ms:.2f}ms",
                            "short": True,
                        },
                    ],
                    "footer": "RAXE CE",
                    "ts": int(time.time()),
                }
            ],
        }

        return message

    def _send_to_slack(self, message: dict[str, Any]) -> None:
        """Send message to Slack webhook.

        Args:
            message: Slack message payload

        Raises:
            URLError: If HTTP request fails
        """
        # Prepare request
        data = json.dumps(message).encode("utf-8")
        req = request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        # Send request
        with request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Slack API returned status {response.status}"
                )

    def on_shutdown(self) -> None:
        """Cleanup on shutdown."""
        # No cleanup needed
        pass


# Required: Export plugin instance
plugin = SlackNotifierPlugin()
