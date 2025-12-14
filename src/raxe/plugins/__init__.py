"""RAXE Plugin System.

Enables extensibility through custom detectors, actions, and transforms.

The plugin system allows users to extend RAXE with:
- Custom detection logic (DetectorPlugin)
- Custom actions (ActionPlugin) - webhooks, logging, alerts
- Text transformation (TransformPlugin)
- Custom YAML-based rules (CustomRule)

Quick Start:
    Creating a detector plugin:

    ```python
    # ~/.raxe/plugins/my_detector/plugin.py
    from raxe.plugins import DetectorPlugin, PluginMetadata, PluginPriority
    from raxe.domain.models import Detection, Severity

    class MyDetector(DetectorPlugin):
        @property
        def metadata(self):
            return PluginMetadata(
                name="my_detector",
                version="0.0.1",
                author="Me",
                description="My custom detector",
                priority=PluginPriority.NORMAL,
                requires=["raxe>=1.0.0"],
                tags=["detector"]
            )

        def on_init(self, config):
            self.enabled = config.get("enabled", True)

        def detect(self, text, context=None):
            if "bad_pattern" in text:
                return [Detection(
                    rule_id="my_001",
                    severity=Severity.HIGH,
                    confidence=0.9,
                    message="Bad pattern detected"
                )]
            return []

    plugin = MyDetector()  # Required!
    ```

    Enable in config (~/.raxe/config.yaml):

    ```yaml
    plugins:
      enabled:
        - my_detector
      my_detector:
        enabled: true
    ```

Architecture:
    - Protocol-based design (typing.Protocol)
    - Clean separation from domain layer
    - Fail-safe error handling
    - Performance tracking
    - Timeout enforcement

For more information, see docs/plugins/README.md
"""

from raxe.plugins.custom_rules import CustomRule, CustomRuleLoader
from raxe.plugins.loader import PluginInfo, PluginLoader
from raxe.plugins.manager import PluginManager, PluginMetrics
from raxe.plugins.protocol import (
    ActionPlugin,
    DetectorPlugin,
    PluginMetadata,
    PluginPriority,
    RaxePlugin,
    TransformPlugin,
)

__all__ = [
    "ActionPlugin",
    # Custom rules
    "CustomRule",
    "CustomRuleLoader",
    "DetectorPlugin",
    "PluginInfo",
    # Loading
    "PluginLoader",
    # Management
    "PluginManager",
    # Metadata
    "PluginMetadata",
    "PluginMetrics",
    "PluginPriority",
    # Core protocols
    "RaxePlugin",
    "TransformPlugin",
]
