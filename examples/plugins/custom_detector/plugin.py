"""Custom Regex Detector Plugin.

Example detector plugin that uses user-defined regex patterns
for threat detection. Patterns are configured in config.yaml.

Configuration (~/.raxe/config.yaml):
    ```yaml
    plugins:
      custom_detector:
        patterns:
          - name: "api_key"
            pattern: "sk-[a-zA-Z0-9]{48}"
            severity: "HIGH"
            message: "OpenAI API key detected"
          - name: "password"
            pattern: "password\\s*=\\s*['\"][^'\"]+['\"]"
            severity: "CRITICAL"
            message: "Hardcoded password detected"
          - name: "internal_url"
            pattern: "https?://internal\\."
            severity: "MEDIUM"
            message: "Internal URL detected"
    ```

Usage:
    1. Copy this directory to ~/.raxe/plugins/custom_detector/
    2. Add configuration to ~/.raxe/config.yaml
    3. Enable in plugins.enabled list
    4. Run: raxe scan "your text here"
"""

import re
from typing import Any, Optional

from raxe.domain.engine.executor import Detection
from raxe.domain.rules.models import Severity
from raxe.plugins import DetectorPlugin, PluginMetadata, PluginPriority


class PatternConfig:
    """Single pattern configuration."""

    def __init__(
        self,
        name: str,
        pattern: str,
        severity: str,
        message: str,
    ):
        """Initialize pattern.

        Args:
            name: Pattern identifier
            pattern: Regex pattern string
            severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
            message: Detection message
        """
        self.name = name
        self.pattern = re.compile(pattern)
        self.severity = Severity[severity.upper()]
        self.message = message


class CustomRegexDetector(DetectorPlugin):
    """Custom regex-based detector plugin.

    Allows users to define custom regex patterns for detecting
    organization-specific threats like:
    - Custom API key formats
    - Internal URLs or hostnames
    - Proprietary identifiers
    - Company-specific PII patterns
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="custom_detector",
            version="1.0.0",
            author="RAXE Community",
            description="Custom regex-based threat detection",
            priority=PluginPriority.NORMAL,
            requires=("raxe>=1.0.0",),
            tags=("detector", "regex", "custom"),
        )

    def on_init(self, config: dict[str, Any]) -> None:
        """Initialize with custom patterns from config.

        Args:
            config: Plugin configuration from config.yaml
        """
        self.patterns: list[PatternConfig] = []

        # Load patterns from config
        pattern_configs = config.get("patterns", [])
        if not pattern_configs:
            raise ValueError(
                "No patterns configured. Add patterns in config.yaml under "
                "[plugins.custom_detector]"
            )

        for pattern_config in pattern_configs:
            try:
                pattern = PatternConfig(
                    name=pattern_config["name"],
                    pattern=pattern_config["pattern"],
                    severity=pattern_config.get("severity", "MEDIUM"),
                    message=pattern_config.get(
                        "message", f"Custom pattern '{pattern_config['name']}' matched"
                    ),
                )
                self.patterns.append(pattern)
            except Exception as e:
                raise ValueError(
                    f"Invalid pattern config '{pattern_config.get('name', 'unknown')}': {e}"
                ) from e

    def detect(
        self, text: str, context: Optional[dict[str, Any]] = None
    ) -> list[Detection]:
        """Detect threats using custom patterns.

        Args:
            text: Text to scan
            context: Optional context metadata

        Returns:
            List of detections for any pattern matches
        """
        detections: list[Detection] = []

        for pattern in self.patterns:
            if pattern.pattern.search(text):
                detection = Detection(
                    rule_id=f"custom_{pattern.name}",
                    severity=pattern.severity,
                    confidence=0.95,  # High confidence for exact regex match
                    message=pattern.message,
                    metadata={
                        "plugin": "custom_detector",
                        "pattern_name": pattern.name,
                        "category": "CUSTOM",
                    },
                )
                detections.append(detection)

        return detections

    def on_shutdown(self) -> None:
        """Cleanup on shutdown."""
        # No cleanup needed for this simple plugin
        pass


# Required: Export plugin instance
plugin = CustomRegexDetector()
