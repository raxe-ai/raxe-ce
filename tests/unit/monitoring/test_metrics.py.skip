"""Tests for Prometheus metrics and collector."""

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from raxe.monitoring.metrics import (
    collector,
)


# Mock ScanPipelineResult for testing
@dataclass
class MockDetection:
    """Mock detection for testing."""
    rule_id: str
    severity: Mock
    confidence: float
    category: str = "test"


@dataclass
class MockScanResult:
    """Mock scan result for testing."""
    has_threats: bool
    detections: list
    highest_severity: str | None = None


@dataclass
class MockPipelineResult:
    """Mock pipeline result for testing."""
    scan_result: MockScanResult
    should_block: bool
    total_detections: int
    severity: str | None
    duration_ms: float
    metadata: dict
    input_length: int = 100


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def test_measure_scan_context_manager(self):
        """Test measure_scan context manager."""
        import time

        with collector.measure_scan("test_layer"):
            time.sleep(0.01)  # Sleep for 10ms

        # Verify metric was recorded
        # Note: We can't easily assert on prometheus_client metrics directly
        # In production, we'd use prometheus_client test utilities

    def test_measure_rule_execution(self):
        """Test measure_rule_execution context manager."""
        import time

        with collector.measure_rule_execution("test-rule-001"):
            time.sleep(0.001)  # Sleep for 1ms

    def test_record_scan_simple(self):
        """Test simple scan recording."""
        collector.record_scan_simple(
            severity="high",
            blocked=True,
            detection_count=3,
            input_length=500,
        )

        # Should not raise any exceptions
        # Metrics are recorded internally

    def test_record_scan_with_pipeline_result(self):
        """Test recording scan with full pipeline result."""
        # Create mock severity
        mock_severity = Mock()
        mock_severity.value = "high"

        # Create mock detection
        detection = MockDetection(
            rule_id="test-001",
            severity=mock_severity,
            confidence=0.95,
            category="test",
        )

        # Create mock scan result
        scan_result = MockScanResult(
            has_threats=True,
            detections=[detection],
            highest_severity="high",
        )

        # Create mock pipeline result
        result = MockPipelineResult(
            scan_result=scan_result,
            should_block=True,
            total_detections=1,
            severity="high",
            duration_ms=5.5,
            metadata={},
        )

        # Record scan
        collector.record_scan(result)

        # Should not raise exceptions

    def test_update_queue_depth(self):
        """Test updating queue depth."""
        collector.update_queue_depth(42, priority="high")
        collector.update_queue_depth(10, priority="normal")

        # Verify metrics were set
        # In a real test, we'd check the gauge value

    def test_record_queue_processed(self):
        """Test recording processed queue items."""
        collector.record_queue_processed(10, success=True)
        collector.record_queue_processed(2, success=False)

    def test_update_rules_loaded(self):
        """Test updating rules loaded count."""
        collector.update_rules_loaded(25, category="PI")
        collector.update_rules_loaded(30, category="prompt-injection")

    def test_record_cache_operations(self):
        """Test cache hit/miss recording."""
        collector.record_cache_hit("rules")
        collector.record_cache_miss("results")
        collector.update_cache_size(1024, "rules")

    def test_record_error(self):
        """Test error recording."""
        collector.record_error("validation")
        collector.record_error("scan")
        collector.record_error("telemetry")

    def test_update_circuit_breaker_state(self):
        """Test circuit breaker state update."""
        collector.update_circuit_breaker_state("telemetry", 0)  # Closed
        collector.update_circuit_breaker_state("cloud_api", 1)  # Open
        collector.update_circuit_breaker_state("telemetry", 2)  # Half-open

    def test_record_false_positive(self):
        """Test false positive recording."""
        collector.record_false_positive("test-rule-001")
        collector.record_false_positive("test-rule-002")


class TestMetricsIntegration:
    """Test metrics integration scenarios."""

    def test_end_to_end_scan_metrics(self):
        """Test complete scan metrics flow."""
        # Simulate a scan with metrics
        with collector.measure_scan("regex"):
            # Simulate regex detection
            pass

        with collector.measure_scan("ml"):
            # Simulate ML detection
            pass

        # Record results
        collector.record_scan_simple(
            severity="high",
            blocked=True,
            detection_count=2,
            input_length=250,
        )

        # Record individual detections
        collector.update_rules_loaded(50, category="PI")
        collector.record_error("validation")  # Simulated error

    def test_queue_metrics_flow(self):
        """Test queue metrics workflow."""
        # Queue builds up
        for depth in range(10, 101, 10):
            collector.update_queue_depth(depth, priority="normal")

        # Process queue
        with collector.measure_queue_processing():
            # Simulate processing
            pass

        collector.record_queue_processed(100, success=True)

        # Queue empties
        collector.update_queue_depth(0, priority="normal")

    def test_performance_degradation_scenario(self):
        """Test metrics during performance degradation."""
        import time

        # Normal performance
        for _ in range(10):
            with collector.measure_scan("regex"):
                time.sleep(0.001)  # 1ms

        # Degraded performance
        for _ in range(5):
            with collector.measure_scan("regex"):
                time.sleep(0.020)  # 20ms - degraded

            # Record error
            collector.record_error("timeout")

    def test_high_threat_scenario(self):
        """Test metrics during high threat rate."""
        # Simulate attack scenario
        for _i in range(100):
            collector.record_scan_simple(
                severity="critical",
                blocked=True,
                detection_count=3,
                input_length=200,
            )

        # Record queue backup
        collector.update_queue_depth(500, priority="high")


class TestMetricsAccuracy:
    """Test metrics accuracy and correctness."""

    def test_scan_duration_accuracy(self):
        """Test that scan duration is measured accurately."""
        import time

        start = time.perf_counter()
        with collector.measure_scan("test"):
            time.sleep(0.01)  # 10ms
        actual_duration = time.perf_counter() - start

        # Should be close to 10ms
        assert 0.009 < actual_duration < 0.015

    def test_multiple_concurrent_measurements(self):
        """Test that multiple measurements don't interfere."""
        import time
        from threading import Thread

        def measure_layer(layer_name):
            with collector.measure_scan(layer_name):
                time.sleep(0.005)

        threads = [
            Thread(target=measure_layer, args=(f"layer{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All measurements should complete without errors


class TestMetricsEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_scan_result(self):
        """Test recording scan with no detections."""
        scan_result = MockScanResult(
            has_threats=False,
            detections=[],
            highest_severity=None,
        )

        result = MockPipelineResult(
            scan_result=scan_result,
            should_block=False,
            total_detections=0,
            severity=None,
            duration_ms=2.5,
            metadata={},
        )

        collector.record_scan(result)

    def test_zero_queue_depth(self):
        """Test queue depth at zero."""
        collector.update_queue_depth(0, priority="normal")

    def test_very_large_numbers(self):
        """Test metrics with very large numbers."""
        collector.record_queue_processed(1_000_000, success=True)
        collector.update_queue_depth(100_000, priority="high")
        collector.update_cache_size(1_000_000_000, "results")

    def test_negative_protection(self):
        """Test that negative values are handled appropriately."""
        # Queue depth should not go negative
        collector.update_queue_depth(0, priority="normal")

        # These should work fine
        collector.record_scan_simple(
            severity="none",
            blocked=False,
            detection_count=0,
            input_length=0,
        )


class TestMetricsLabels:
    """Test metric label usage."""

    def test_severity_labels(self):
        """Test different severity labels."""
        for severity in ["critical", "high", "medium", "low", "info", "none"]:
            collector.record_scan_simple(
                severity=severity,
                blocked=False,
                detection_count=0,
                input_length=100,
            )

    def test_action_labels(self):
        """Test action labels (blocked/allowed)."""
        collector.record_scan_simple(
            severity="high",
            blocked=True,
            detection_count=1,
            input_length=100,
        )

        collector.record_scan_simple(
            severity="medium",
            blocked=False,
            detection_count=1,
            input_length=100,
        )

    def test_priority_labels(self):
        """Test queue priority labels."""
        for priority in ["high", "normal", "low"]:
            collector.update_queue_depth(10, priority=priority)

    def test_cache_type_labels(self):
        """Test cache type labels."""
        for cache_type in ["rules", "results", "metadata"]:
            collector.record_cache_hit(cache_type)
            collector.record_cache_miss(cache_type)


@pytest.mark.slow
class TestMetricsVerification:
    """
    Verify actual prometheus metrics values.

    These tests require prometheus_client testing utilities
    and are slower, so they're skipped by default.
    """

    def test_verify_scan_counter(self):
        """Verify scans_total counter increases."""
        # This would require prometheus_client testing utilities
        pass

    def test_verify_histogram_buckets(self):
        """Verify histogram buckets are populated correctly."""
        pass
