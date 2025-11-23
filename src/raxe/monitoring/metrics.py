"""
Prometheus metrics definitions and collector for RAXE CE.

This module defines all Prometheus metrics used by RAXE for observability:
- Scan performance metrics (duration, throughput)
- Detection metrics (counts by severity, rule, category)
- Queue metrics (depth, processing time)
- Rule execution metrics
- Cache metrics (for async SDK)
- Error metrics

All metrics follow Prometheus naming conventions and include appropriate labels
for filtering and aggregation.
"""

import platform
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge, Histogram, Info

if TYPE_CHECKING:
    from raxe.application.scan_pipeline import ScanPipelineResult

# Import version safely
try:
    from raxe import __version__
except ImportError:
    __version__ = "unknown"


# ============================================================================
# Scan Metrics
# ============================================================================

scans_total = Counter(
    "raxe_scans_total",
    "Total number of scans performed",
    ["severity", "action"],  # Labels: severity level, action taken (blocked/allowed)
)

scan_duration_seconds = Histogram(
    "raxe_scan_duration_seconds",
    "Scan duration in seconds by layer",
    ["layer"],  # Labels: detection layer (regex, ml, combined)
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

scan_input_length = Histogram(
    "raxe_scan_input_length_bytes",
    "Length of scanned input in bytes",
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000],
)


# ============================================================================
# Detection Metrics
# ============================================================================

detections_total = Counter(
    "raxe_detections_total",
    "Total number of detections by rule, severity, and category",
    ["rule_id", "severity", "category"],
)

false_positives_total = Counter(
    "raxe_false_positives_total",
    "User-reported false positives",
    ["rule_id"],
)


# ============================================================================
# Queue Metrics
# ============================================================================

queue_depth = Gauge(
    "raxe_queue_depth",
    "Current telemetry queue depth",
    ["priority"],  # Labels: priority level (high, normal, low)
)

queue_processing_duration = Histogram(
    "raxe_queue_processing_duration_seconds",
    "Time to process a queue batch",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
)

queue_items_processed = Counter(
    "raxe_queue_items_processed_total",
    "Total number of queue items processed",
    ["status"],  # Labels: success, failed
)


# ============================================================================
# Rule Metrics
# ============================================================================

rules_loaded = Gauge(
    "raxe_rules_loaded",
    "Number of detection rules currently loaded",
    ["category"],  # Labels: PI, prompt-injection, etc.
)

rule_execution_duration = Histogram(
    "raxe_rule_execution_duration_seconds",
    "Individual rule execution duration",
    ["rule_id"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1],
)

rule_matches = Counter(
    "raxe_rule_matches_total",
    "Number of times each rule matched",
    ["rule_id", "severity"],
)


# ============================================================================
# Cache Metrics (for async SDK)
# ============================================================================

cache_hits = Counter(
    "raxe_cache_hits_total",
    "Number of cache hits by cache type",
    ["cache_type"],  # Labels: rules, results
)

cache_misses = Counter(
    "raxe_cache_misses_total",
    "Number of cache misses by cache type",
    ["cache_type"],
)

cache_size = Gauge(
    "raxe_cache_size_bytes",
    "Current cache size in bytes",
    ["cache_type"],
)


# ============================================================================
# Error Metrics
# ============================================================================

errors_total = Counter(
    "raxe_errors_total",
    "Total number of errors by type",
    ["error_type"],  # Labels: validation, scan, telemetry, etc.
)

circuit_breaker_state = Gauge(
    "raxe_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["component"],
)


# ============================================================================
# System Metrics
# ============================================================================

system_info = Info(
    "raxe_system",
    "RAXE system information",
)

# Initialize system info
system_info.info(
    {
        "version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
    }
)


# ============================================================================
# Metrics Collector
# ============================================================================


class MetricsCollector:
    """
    Centralized metrics collector for RAXE.

    This class provides high-level methods for recording metrics throughout
    the RAXE codebase. It wraps the Prometheus metrics and provides a clean
    API for metric collection.

    Usage:
        from raxe.monitoring import collector

        # Measure scan duration
        with collector.measure_scan("regex"):
            result = run_regex_detection(prompt)

        # Record scan result
        collector.record_scan(result)

        # Update queue depth
        collector.update_queue_depth(42)
    """

    @contextmanager
    def measure_scan(self, layer: str):
        """
        Context manager to measure scan duration.

        Args:
            layer: Detection layer being measured (regex, ml, combined)

        Usage:
            with collector.measure_scan("regex"):
                result = run_detection(prompt)
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            scan_duration_seconds.labels(layer=layer).observe(duration)

    @contextmanager
    def measure_rule_execution(self, rule_id: str):
        """
        Context manager to measure individual rule execution.

        Args:
            rule_id: ID of the rule being executed
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            rule_execution_duration.labels(rule_id=rule_id).observe(duration)

    @contextmanager
    def measure_queue_processing(self):
        """Context manager to measure queue batch processing time."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            queue_processing_duration.observe(duration)

    def record_scan(self, result: "ScanPipelineResult"):
        """
        Record metrics for a completed scan.

        Args:
            result: ScanPipelineResult with detections and metadata
        """
        # Count scan
        action = "blocked" if result.should_block else "allowed"
        severity = result.highest_severity or "none"
        scans_total.labels(severity=severity, action=action).inc()

        # Record input length
        if hasattr(result, "input_length"):
            scan_input_length.observe(result.input_length)

        # Count detections
        for detection in result.detections:
            detections_total.labels(
                rule_id=detection.rule_id,
                severity=detection.severity.value if hasattr(detection.severity, "value") else str(detection.severity),
                category=getattr(detection, "category", "unknown"),
            ).inc()

            # Count rule matches
            rule_matches.labels(
                rule_id=detection.rule_id,
                severity=detection.severity.value if hasattr(detection.severity, "value") else str(detection.severity),
            ).inc()

    def record_scan_simple(
        self,
        severity: str = "none",
        blocked: bool = False,
        detection_count: int = 0,
        input_length: int = 0,
    ):
        """
        Simplified scan recording for cases without full ScanPipelineResult.

        Args:
            severity: Highest severity detected
            blocked: Whether the scan was blocked
            detection_count: Number of detections
            input_length: Length of input in bytes
        """
        action = "blocked" if blocked else "allowed"
        scans_total.labels(severity=severity, action=action).inc()

        if input_length > 0:
            scan_input_length.observe(input_length)

    def update_queue_depth(self, depth: int, priority: str = "normal"):
        """
        Update queue depth gauge.

        Args:
            depth: Current queue depth
            priority: Queue priority (high, normal, low)
        """
        queue_depth.labels(priority=priority).set(depth)

    def record_queue_processed(self, count: int, success: bool = True):
        """
        Record processed queue items.

        Args:
            count: Number of items processed
            success: Whether processing succeeded
        """
        status = "success" if success else "failed"
        queue_items_processed.labels(status=status).inc(count)

    def update_rules_loaded(self, count: int, category: str):
        """
        Update loaded rules count.

        Args:
            count: Number of rules loaded
            category: Rule category (PI, prompt-injection, etc.)
        """
        rules_loaded.labels(category=category).set(count)

    def record_cache_hit(self, cache_type: str):
        """Record cache hit."""
        cache_hits.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str):
        """Record cache miss."""
        cache_misses.labels(cache_type=cache_type).inc()

    def update_cache_size(self, size_bytes: int, cache_type: str):
        """Update cache size gauge."""
        cache_size.labels(cache_type=cache_type).set(size_bytes)

    def record_error(self, error_type: str):
        """
        Record error occurrence.

        Args:
            error_type: Type of error (validation, scan, telemetry, etc.)
        """
        errors_total.labels(error_type=error_type).inc()

    def update_circuit_breaker_state(self, component: str, state: int):
        """
        Update circuit breaker state.

        Args:
            component: Component name (telemetry, cloud_api, etc.)
            state: State (0=closed, 1=open, 2=half-open)
        """
        circuit_breaker_state.labels(component=component).set(state)

    def record_false_positive(self, rule_id: str):
        """Record user-reported false positive."""
        false_positives_total.labels(rule_id=rule_id).inc()


# Global collector instance
collector = MetricsCollector()
