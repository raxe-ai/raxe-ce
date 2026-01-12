"""Tests for plugin protocol definitions.

Tests the base protocol and specialized plugin types to ensure
proper validation and behavior.
"""

import pytest

from raxe.plugins.protocol import (
    PluginMetadata,
    PluginPriority,
)


class TestPluginMetadata:
    """Test PluginMetadata validation and behavior."""

    def test_create_basic_metadata(self):
        """Test creating basic plugin metadata."""
        metadata = PluginMetadata(
            name="test_plugin",
            version="0.0.1",
            author="Test Author",
            description="Test plugin",
        )

        assert metadata.name == "test_plugin"
        assert metadata.version == "0.0.1"
        assert metadata.author == "Test Author"
        assert metadata.description == "Test plugin"
        assert metadata.priority == PluginPriority.NORMAL  # Default
        assert metadata.requires == ("raxe>=1.0.0",)  # Default
        assert metadata.tags == ()  # Default

    def test_create_metadata_with_custom_values(self):
        """Test creating metadata with custom priority and tags."""
        metadata = PluginMetadata(
            name="critical_plugin",
            version="0.0.1",
            author="Security Team",
            description="Critical security plugin",
            priority=PluginPriority.CRITICAL,
            requires=("raxe>=2.0.0", "pyyaml>=6.0"),
            tags=("security", "critical"),
        )

        assert metadata.priority == PluginPriority.CRITICAL
        assert len(metadata.requires) == 2
        assert "pyyaml>=6.0" in metadata.requires
        assert len(metadata.tags) == 2
        assert "security" in metadata.tags

    def test_empty_name_raises_error(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            PluginMetadata(
                name="",
                version="0.0.1",
                author="Test",
                description="Test",
            )

    def test_empty_version_raises_error(self):
        """Test that empty version raises ValueError."""
        with pytest.raises(ValueError, match="version cannot be empty"):
            PluginMetadata(
                name="test",
                version="",
                author="Test",
                description="Test",
            )

    def test_name_with_spaces_raises_error(self):
        """Test that name with spaces raises ValueError."""
        with pytest.raises(ValueError, match="cannot contain spaces"):
            PluginMetadata(
                name="test plugin",
                version="0.0.1",
                author="Test",
                description="Test",
            )

    def test_metadata_is_frozen(self):
        """Test that metadata is immutable."""
        metadata = PluginMetadata(
            name="test",
            version="0.0.1",
            author="Test",
            description="Test",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            metadata.name = "changed"  # type: ignore


class TestPluginPriority:
    """Test PluginPriority enum."""

    def test_priority_ordering(self):
        """Test that priorities have correct numeric ordering."""
        assert PluginPriority.CRITICAL.value == 0
        assert PluginPriority.HIGH.value == 10
        assert PluginPriority.NORMAL.value == 50
        assert PluginPriority.LOW.value == 100

        # Lower value = higher priority
        assert PluginPriority.CRITICAL.value < PluginPriority.HIGH.value
        assert PluginPriority.HIGH.value < PluginPriority.NORMAL.value
        assert PluginPriority.NORMAL.value < PluginPriority.LOW.value


class TestRaxePlugin:
    """Test RaxePlugin protocol implementation."""

    def test_minimal_plugin_implementation(self):
        """Test minimal plugin that implements required methods."""

        class MinimalPlugin:
            @property
            def metadata(self):
                return PluginMetadata(
                    name="minimal",
                    version="0.0.1",
                    author="Test",
                    description="Minimal plugin",
                )

            def on_init(self, config):
                pass

        plugin = MinimalPlugin()
        assert plugin.metadata.name == "minimal"
        assert callable(plugin.on_init)

    def test_plugin_with_all_hooks(self):
        """Test plugin that implements all lifecycle hooks."""

        class FullPlugin:
            def __init__(self):
                self.init_called = False
                self.scan_start_called = False
                self.scan_complete_called = False
                self.threat_detected_called = False
                self.shutdown_called = False

            @property
            def metadata(self):
                return PluginMetadata(
                    name="full",
                    version="0.0.1",
                    author="Test",
                    description="Full plugin",
                )

            def on_init(self, config):
                self.init_called = True

            def on_scan_start(self, text, context=None):
                self.scan_start_called = True
                return None

            def on_scan_complete(self, result):
                self.scan_complete_called = True

            def on_threat_detected(self, result):
                self.threat_detected_called = True

            def on_shutdown(self):
                self.shutdown_called = True

        plugin = FullPlugin()
        plugin.on_init({})
        plugin.on_scan_start("test")
        plugin.on_scan_complete(None)  # type: ignore
        plugin.on_threat_detected(None)  # type: ignore
        plugin.on_shutdown()

        assert plugin.init_called
        assert plugin.scan_start_called
        assert plugin.scan_complete_called
        assert plugin.threat_detected_called
        assert plugin.shutdown_called


class TestDetectorPlugin:
    """Test DetectorPlugin protocol."""

    def test_detector_plugin_implementation(self):
        """Test basic detector plugin implementation."""
        from raxe.domain.engine.executor import Detection
        from raxe.domain.rules.models import Severity

        class TestDetector:
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test_detector",
                    version="0.0.1",
                    author="Test",
                    description="Test detector",
                )

            def on_init(self, config):
                pass

            def detect(self, text, context=None):
                if "bad" in text:
                    from datetime import datetime, timezone

                    from raxe.domain.engine.matcher import Match

                    return [
                        Detection(
                            rule_id="test_001",
                            rule_version="0.0.1",
                            severity=Severity.HIGH,
                            confidence=0.9,
                            matches=[
                                Match(
                                    pattern_index=0,
                                    start=0,
                                    end=3,
                                    matched_text="bad",
                                    groups=(),
                                    context_before="",
                                    context_after="",
                                )
                            ],
                            detected_at=datetime.now(timezone.utc).isoformat(),
                            message="Bad word detected",
                        )
                    ]
                return []

        detector = TestDetector()
        assert len(detector.detect("bad text")) == 1
        assert len(detector.detect("good text")) == 0

    def test_detector_plugin_with_rules(self):
        """Test detector plugin that provides custom rules."""

        class RuleProviderDetector:
            @property
            def metadata(self):
                return PluginMetadata(
                    name="rule_provider",
                    version="0.0.1",
                    author="Test",
                    description="Provides rules",
                )

            def on_init(self, config):
                pass

            def detect(self, text, context=None):
                return []

            def get_rules(self):
                # Would return actual Rule objects
                return ["rule1", "rule2"]  # Simplified for test

        detector = RuleProviderDetector()
        rules = detector.get_rules()
        assert len(rules) == 2


class TestActionPlugin:
    """Test ActionPlugin protocol."""

    def test_action_plugin_implementation(self):
        """Test basic action plugin implementation."""

        class TestAction:
            def __init__(self):
                self.executed = False

            @property
            def metadata(self):
                return PluginMetadata(
                    name="test_action",
                    version="0.0.1",
                    author="Test",
                    description="Test action",
                )

            def on_init(self, config):
                pass

            def should_execute(self, result):
                return result is not None

            def execute(self, result):
                self.executed = True

        action = TestAction()
        assert action.should_execute("test")
        assert not action.should_execute(None)

        action.execute("test")
        assert action.executed


class TestTransformPlugin:
    """Test TransformPlugin protocol."""

    def test_transform_input(self):
        """Test input transformation."""

        class UpperCaseTransform:
            @property
            def metadata(self):
                return PluginMetadata(
                    name="uppercase",
                    version="0.0.1",
                    author="Test",
                    description="Uppercase transform",
                )

            def on_init(self, config):
                pass

            def transform_input(self, text, context=None):
                return text.upper()

        transform = UpperCaseTransform()
        result = transform.transform_input("hello")
        assert result == "HELLO"

    def test_transform_output(self):
        """Test output transformation."""

        class MetadataEnricher:
            @property
            def metadata(self):
                return PluginMetadata(
                    name="enricher",
                    version="0.0.1",
                    author="Test",
                    description="Metadata enricher",
                )

            def on_init(self, config):
                pass

            def transform_output(self, result):
                # In real implementation, would modify result
                return result

        transform = MetadataEnricher()
        result = transform.transform_output("test")
        assert result == "test"
