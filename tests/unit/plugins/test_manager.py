"""Tests for plugin manager.

Tests plugin lifecycle management, hook execution, and metrics tracking.
"""

from unittest.mock import Mock

import pytest

from raxe.plugins.loader import PluginLoader
from raxe.plugins.manager import PluginManager, PluginMetrics
from raxe.plugins.protocol import PluginMetadata


class TestPluginMetrics:
    """Test PluginMetrics tracking."""

    def test_record_execution(self):
        """Test recording successful execution."""
        metrics = PluginMetrics()

        metrics.record_execution("on_init", 10.5)
        metrics.record_execution("detect", 5.2)

        assert metrics.total_executions == 2
        assert metrics.total_duration_ms == pytest.approx(15.7)
        assert metrics.hook_counts["on_init"] == 1
        assert metrics.hook_counts["detect"] == 1

    def test_record_error(self):
        """Test recording errors."""
        metrics = PluginMetrics()

        metrics.record_error("detect")
        metrics.record_error("detect")

        assert metrics.error_count == 2

    def test_record_timeout(self):
        """Test recording timeouts."""
        metrics = PluginMetrics()

        metrics.record_timeout("detect")

        assert metrics.timeout_count == 1

    def test_average_duration(self):
        """Test average duration calculation."""
        metrics = PluginMetrics()

        metrics.record_execution("hook1", 10.0)
        metrics.record_execution("hook2", 20.0)
        metrics.record_execution("hook3", 30.0)

        assert metrics.average_duration_ms == 20.0

    def test_success_rate(self):
        """Test success rate calculation."""
        metrics = PluginMetrics()

        metrics.record_execution("hook1", 1.0)
        metrics.record_execution("hook2", 1.0)
        metrics.record_error("hook3")
        metrics.record_timeout("hook4")

        # 2 successes out of 4 total
        assert metrics.success_rate == 0.5


class TestPluginManager:
    """Test PluginManager functionality."""

    def test_initialize_categorizes_plugins(self):
        """Test that plugins are categorized by type."""
        # Create mock plugins
        detector_plugin = Mock()
        detector_plugin.metadata = PluginMetadata(
            name="detector",
            version="1.0.0",
            author="Test",
            description="Detector",
        )
        detector_plugin.detect = Mock(return_value=[])

        action_plugin = Mock()
        action_plugin.metadata = PluginMetadata(
            name="action",
            version="1.0.0",
            author="Test",
            description="Action",
        )
        action_plugin.should_execute = Mock(return_value=True)
        action_plugin.execute = Mock()

        # Mock loader
        loader = Mock(spec=PluginLoader)
        loader.load_all_enabled.return_value = {
            "detector": detector_plugin,
            "action": action_plugin,
        }

        # Initialize manager
        manager = PluginManager(loader)
        manager.initialize(
            enabled_plugins=["detector", "action"],
            plugin_configs={"detector": {}, "action": {}},
        )

        assert len(manager.all_plugins) == 2
        assert len(manager.detector_plugins) == 1
        assert len(manager.action_plugins) == 1

    def test_execute_hook_calls_plugins(self):
        """Test that execute_hook calls all plugins."""
        # Create mock plugin
        plugin = Mock()
        plugin.metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            author="Test",
            description="Test",
        )
        plugin.on_scan_start = Mock(return_value="transformed")

        # Create manager with plugin
        loader = Mock(spec=PluginLoader)
        manager = PluginManager(loader)
        manager.all_plugins = [plugin]
        manager.plugin_metrics = {"test": PluginMetrics()}

        # Execute hook
        results = manager.execute_hook("on_scan_start", "original text")

        assert len(results) == 1
        assert results[0] == "transformed"
        plugin.on_scan_start.assert_called_once_with("original text")

    def test_execute_hook_handles_errors(self):
        """Test that plugin errors are isolated."""
        # Create plugin that raises error
        plugin = Mock()
        plugin.metadata = PluginMetadata(
            name="failing",
            version="1.0.0",
            author="Test",
            description="Test",
        )
        plugin.on_init = Mock(side_effect=RuntimeError("Plugin failed"))

        # Create manager
        loader = Mock(spec=PluginLoader)
        manager = PluginManager(loader)
        manager.all_plugins = [plugin]
        manager.plugin_metrics = {"failing": PluginMetrics()}

        # Execute should not crash
        results = manager.execute_hook("on_init", {})

        assert len(results) == 0  # No results due to error

    def test_run_detectors(self):
        """Test running detector plugins."""
        from raxe.domain.engine.executor import Detection
        from raxe.domain.rules.models import Severity

        # Create detector plugin
        detector = Mock()
        detector.metadata = PluginMetadata(
            name="test_detector",
            version="1.0.0",
            author="Test",
            description="Test",
        )
        detector.detect = Mock(
            return_value=[
                Detection(
                    rule_id="custom_001",
                    severity=Severity.HIGH,
                    confidence=0.9,
                    message="Test detection",
                )
            ]
        )

        # Create manager
        loader = Mock(spec=PluginLoader)
        manager = PluginManager(loader)
        manager.detector_plugins = [detector]
        manager.plugin_metrics = {"test_detector": PluginMetrics()}

        # Run detectors
        detections = manager.run_detectors("test text")

        assert len(detections) == 1
        assert detections[0].rule_id == "custom_001"
        detector.detect.assert_called_once()

    def test_run_actions(self):
        """Test running action plugins."""
        # Create action plugin
        action = Mock()
        action.metadata = PluginMetadata(
            name="test_action",
            version="1.0.0",
            author="Test",
            description="Test",
        )
        action.should_execute = Mock(return_value=True)
        action.execute = Mock()

        # Create manager
        loader = Mock(spec=PluginLoader)
        manager = PluginManager(loader)
        manager.action_plugins = [action]
        manager.plugin_metrics = {"test_action": PluginMetrics()}

        # Run actions
        mock_result = Mock()
        manager.run_actions(mock_result)

        action.should_execute.assert_called_once_with(mock_result)
        action.execute.assert_called_once_with(mock_result)

    def test_shutdown(self):
        """Test plugin shutdown."""
        # Create plugin
        plugin = Mock()
        plugin.metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            author="Test",
            description="Test",
        )
        plugin.on_shutdown = Mock()

        # Create manager
        loader = Mock(spec=PluginLoader)
        manager = PluginManager(loader)
        manager.all_plugins = [plugin]
        manager.plugin_metrics = {"test": PluginMetrics()}

        # Shutdown
        manager.shutdown()

        plugin.on_shutdown.assert_called_once()
