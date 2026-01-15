"""Fixtures for agentic performance tests.

Provides benchmark utilities and performance baselines.
"""

import json
from pathlib import Path
from typing import Any

import pytest

# Performance baseline file
BASELINE_FILE = Path(__file__).parent / ".agentic_baseline.json"

# Performance thresholds (in seconds)
LATENCY_THRESHOLDS = {
    "mcp_scan": 0.020,  # 20ms
    "mcp_validate": 0.025,  # 25ms
    "tool_input_scan": 0.010,  # 10ms
    "tool_output_scan": 0.010,  # 10ms
    "message_extraction": 0.001,  # 1ms
    "conversation_5msg": 0.050,  # 50ms
    "conversation_20msg": 0.150,  # 150ms
    "wrapper_overhead": 0.005,  # 5ms
}

# Throughput thresholds (operations per second)
THROUGHPUT_THRESHOLDS = {
    "tool_scans": 500,
    "conversations": 100,
    "messages": 1000,
}

# Regression threshold (percentage)
REGRESSION_THRESHOLD = 0.10  # 10%


@pytest.fixture
def latency_thresholds() -> dict[str, float]:
    """Get latency threshold configuration."""
    return LATENCY_THRESHOLDS.copy()


@pytest.fixture
def throughput_thresholds() -> dict[str, int]:
    """Get throughput threshold configuration."""
    return THROUGHPUT_THRESHOLDS.copy()


@pytest.fixture
def baseline() -> dict[str, Any] | None:
    """Load performance baseline if available."""
    if BASELINE_FILE.exists():
        with open(BASELINE_FILE) as f:
            return json.load(f)
    return None


def save_baseline(data: dict[str, Any]) -> None:
    """Save new performance baseline."""
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def check_regression(
    current: float, baseline: float, threshold: float = REGRESSION_THRESHOLD
) -> tuple[bool, float]:
    """Check if current value represents a regression.

    Args:
        current: Current measurement
        baseline: Baseline measurement
        threshold: Maximum allowed regression (fraction)

    Returns:
        Tuple of (is_regression, regression_amount)
    """
    if baseline <= 0:
        return False, 0.0

    regression = (current - baseline) / baseline

    return regression > threshold, regression
