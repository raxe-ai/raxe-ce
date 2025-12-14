"""RAXE Plugin Protocol Definitions.

Defines the base protocol and specialized plugin types for extending RAXE.

This module provides the core protocols that all RAXE plugins must implement.
Plugins can extend RAXE with custom detection logic, actions, and transformations
while maintaining clean separation from the core domain layer.

Example:
    Creating a custom detector plugin:

    ```python
    from raxe.plugins import DetectorPlugin, PluginMetadata, PluginPriority
    from raxe.domain.models import Detection, Severity

    class MyDetector(DetectorPlugin):
        @property
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                name="my_detector",
                version="0.0.1",
                author="Me",
                description="My custom detector",
                priority=PluginPriority.NORMAL,
                requires=["raxe>=1.0.0"],
                tags=["detector"]
            )

        def on_init(self, config: dict) -> None:
            self.pattern = config.get("pattern", "")

        def detect(self, text: str, context=None) -> list[Detection]:
            # Custom detection logic
            return []

    plugin = MyDetector()  # Required export
    ```
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum

# Conditional import for scan pipeline result
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from raxe.application.scan_pipeline import ScanPipelineResult
    from raxe.domain.engine.executor import Detection
    from raxe.domain.rules.models import Rule


class PluginPriority(Enum):
    """Execution priority for plugins.

    Plugins with higher priority (lower numeric value) execute first.
    Use CRITICAL for security-critical plugins that must run before others.
    """

    CRITICAL = 0  # Security-critical, runs first
    HIGH = 10  # Important functionality
    NORMAL = 50  # Standard priority (default)
    LOW = 100  # Nice-to-have, runs last


@dataclass(frozen=True)
class PluginMetadata:
    """Plugin identification and metadata.

    All plugins must provide metadata to identify themselves and declare
    dependencies. This information is used for plugin discovery, loading,
    and compatibility checking.

    Attributes:
        name: Unique plugin identifier (lowercase, no spaces)
        version: Semantic version (e.g., "0.0.1")
        author: Plugin author name or organization
        description: Human-readable description
        priority: Execution priority (default: NORMAL)
        requires: List of required RAXE versions (semver format)
        tags: Categorization tags for discovery
    """

    name: str
    version: str
    author: str
    description: str
    priority: PluginPriority = PluginPriority.NORMAL
    requires: tuple[str, ...] = ("raxe>=1.0.0",)
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate metadata."""
        if not self.name:
            raise ValueError("Plugin name cannot be empty")
        if not self.version:
            raise ValueError("Plugin version cannot be empty")
        if " " in self.name:
            raise ValueError(f"Plugin name cannot contain spaces: {self.name}")


class RaxePlugin(Protocol):
    """Base protocol for all RAXE plugins.

    All plugins must implement this protocol. It defines the lifecycle hooks
    that plugins can use to integrate with the RAXE scan pipeline.

    Lifecycle Hook Execution Order:
        1. on_init() - Called once when plugin is loaded
        2. on_scan_start() - Called before each scan
        3. [Scan execution happens]
        4. on_scan_complete() - Called after each scan
        5. on_threat_detected() - Called if threats found
        6. on_shutdown() - Called when RAXE is shutting down

    Note:
        Plugins should be defensive - all methods may raise exceptions
        which will be caught and logged by the plugin manager.
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin metadata.

        Returns:
            PluginMetadata with name, version, author, etc.
        """
        ...

    @abstractmethod
    def on_init(self, config: dict[str, Any]) -> None:
        """Initialize plugin with configuration.

        Called once when the plugin is loaded. Configuration comes from
        the plugins.{name} section of the user's config.yaml file.

        Args:
            config: Plugin-specific configuration dictionary

        Raises:
            ValueError: If configuration is invalid
            Exception: If initialization fails

        Example:
            ```python
            def on_init(self, config: dict) -> None:
                self.webhook_url = config.get("webhook_url")
                if not self.webhook_url:
                    raise ValueError("webhook_url is required")
            ```
        """
        ...

    def on_scan_start(
        self, text: str, context: dict[str, Any] | None = None
    ) -> str | None:
        """Called before scanning begins.

        Plugins can use this hook to:
        - Transform/normalize text before scanning
        - Log scan attempts
        - Perform pre-scan validation

        Args:
            text: Text that will be scanned
            context: Optional context metadata

        Returns:
            Modified text (if transformation needed) or None to use original

        Note:
            Only the first plugin's transformation is used if multiple
            plugins return modified text.
        """
        return None

    def on_scan_complete(self, result: "ScanPipelineResult") -> None:
        """Called after scan completes.

        Use this hook to:
        - Log scan results
        - Update metrics
        - Trigger notifications

        Args:
            result: Complete scan pipeline result

        Note:
            Cannot modify the result. This is read-only notification.
        """
        pass

    def on_threat_detected(self, result: "ScanPipelineResult") -> None:
        """Called when threats are detected.

        Only invoked if result.has_threats is True.

        Use this hook to:
        - Send alerts
        - Log threats
        - Update threat databases

        Args:
            result: Scan result with detected threats

        Note:
            This is called after on_scan_complete when threats exist.
        """
        pass

    def on_shutdown(self) -> None:
        """Called when RAXE is shutting down.

        Use this hook to:
        - Close connections
        - Flush buffers
        - Clean up resources

        Note:
            Plugins are shut down in reverse initialization order.
        """
        pass


class DetectorPlugin(RaxePlugin, Protocol):
    """Plugin that adds custom detection logic.

    Detector plugins extend RAXE's threat detection capabilities with
    custom logic. They run during the L1 detection phase and their
    results are merged with core detection results.

    Example:
        ```python
        class CustomRegexDetector(DetectorPlugin):
            def detect(self, text: str, context=None) -> list[Detection]:
                detections = []
                if "malicious_pattern" in text:
                    detections.append(Detection(
                        rule_id="custom_001",
                        severity=Severity.HIGH,
                        confidence=0.9,
                        message="Custom pattern detected"
                    ))
                return detections
        ```
    """

    @abstractmethod
    def detect(
        self, text: str, context: dict[str, Any] | None = None
    ) -> list["Detection"]:
        """Execute custom detection logic.

        Called during the L1 detection phase. Runs in parallel with
        core rule-based detection.

        Args:
            text: Text to scan for threats
            context: Optional context metadata

        Returns:
            List of Detection objects for any threats found

        Note:
            - Should complete quickly (<5ms target)
            - Will be subject to timeout (5s default)
            - Exceptions are caught and logged
        """
        ...

    def get_rules(self) -> list["Rule"]:
        """Provide custom rules to register.

        Optional method to provide rules that will be registered
        with the rule executor.

        Returns:
            List of custom rules to add

        Note:
            Rules are loaded once during initialization.
        """
        return []


class ActionPlugin(RaxePlugin, Protocol):
    """Plugin that performs actions on scan results.

    Action plugins execute after scanning completes. They can send
    notifications, log to files, trigger webhooks, or perform any
    other action based on scan results.

    Example:
        ```python
        class SlackNotifier(ActionPlugin):
            def should_execute(self, result: ScanPipelineResult) -> bool:
                # Only notify on high severity threats
                return result.severity in ["HIGH", "CRITICAL"]

            def execute(self, result: ScanPipelineResult) -> None:
                # Send Slack notification
                requests.post(self.webhook_url, json={"text": "Threat!"})
        ```
    """

    @abstractmethod
    def should_execute(self, result: "ScanPipelineResult") -> bool:
        """Determine if action should execute.

        Called before execute() to check if the action should run
        based on the scan result.

        Args:
            result: Scan pipeline result

        Returns:
            True if action should execute, False to skip

        Example:
            ```python
            def should_execute(self, result):
                # Only execute for threats
                if not result.has_threats:
                    return False
                # Only execute for high severity
                return result.severity in ["HIGH", "CRITICAL"]
            ```
        """
        ...

    @abstractmethod
    def execute(self, result: "ScanPipelineResult") -> None:
        """Execute action based on scan result.

        Called after scanning if should_execute() returns True.

        Args:
            result: Scan pipeline result

        Raises:
            Exception: Any errors are caught and logged

        Example:
            ```python
            def execute(self, result):
                # Send webhook
                requests.post(
                    self.webhook_url,
                    json=result.to_dict(),
                    timeout=5
                )
            ```
        """
        ...


class TransformPlugin(RaxePlugin, Protocol):
    """Plugin that transforms text before/after scanning.

    Transform plugins can modify text before scanning or transform
    results after scanning. Use cases include:
    - Text normalization
    - Redaction
    - Format conversion
    - Result enrichment

    Example:
        ```python
        class TextNormalizer(TransformPlugin):
            def transform_input(self, text: str, context=None) -> str:
                # Normalize whitespace
                return " ".join(text.split())

            def transform_output(self, result):
                # Add metadata
                new_metadata = {**result.metadata, "normalized": True}
                return dataclasses.replace(result, metadata=new_metadata)
        ```
    """

    def transform_input(
        self, text: str, context: dict[str, Any] | None = None
    ) -> str:
        """Transform text before scanning.

        Called before detection starts. Can normalize, clean, or
        otherwise transform the input text.

        Args:
            text: Original text to transform
            context: Optional context metadata

        Returns:
            Transformed text

        Note:
            Only the first plugin's transformation is applied.
        """
        return text

    def transform_output(self, result: "ScanPipelineResult") -> "ScanPipelineResult":
        """Transform results after scanning.

        Called after scanning completes. Can modify, enrich, or
        filter the scan results.

        Args:
            result: Original scan pipeline result

        Returns:
            Modified scan pipeline result

        Note:
            Should return a new object, not modify the original.
            Multiple plugins' transformations are chained.
        """
        return result


__all__ = [
    "ActionPlugin",
    "DetectorPlugin",
    "PluginMetadata",
    "PluginPriority",
    "RaxePlugin",
    "TransformPlugin",
]
