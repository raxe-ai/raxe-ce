"""
RAXE Monitoring - Performance metrics and observability.

This module provides Prometheus metrics export, performance profiling,
and observability tools for RAXE CE.

Key components:
- Prometheus metrics (scans, detections, queue, rules)
- Performance profiler for identifying bottlenecks
- Optional metrics HTTP server
- Metrics collector for integration
"""

from raxe.monitoring.metrics import (
    MetricsCollector,
    cache_hits,
    cache_misses,
    # Collectors
    collector,
    detections_total,
    errors_total,
    queue_depth,
    queue_processing_duration,
    rule_execution_duration,
    rules_loaded,
    scan_duration_seconds,
    # Metrics (for advanced use)
    scans_total,
    system_info,
)
from raxe.monitoring.profiler import PerformanceProfiler

__all__ = [
    "MetricsCollector",
    # Profiler
    "PerformanceProfiler",
    "cache_hits",
    "cache_misses",
    # Main collector
    "collector",
    "detections_total",
    "errors_total",
    "queue_depth",
    "queue_processing_duration",
    "rule_execution_duration",
    "rules_loaded",
    "scan_duration_seconds",
    # Individual metrics (for advanced usage)
    "scans_total",
    "system_info",
]
