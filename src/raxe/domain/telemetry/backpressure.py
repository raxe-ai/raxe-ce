"""
Pure functions for calculating telemetry backpressure.

This module contains ONLY pure functions - no I/O operations.
All functions take data and return data without side effects.

Backpressure prevents queue overflow by:
1. Never dropping critical events (safety guarantee)
2. Sampling standard events when queues are filling up
3. Using deterministic sampling based on event hash for consistency

See specification section 9.5 for backpressure rules.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class QueueMetrics:
    """Current queue state for backpressure calculation.

    Immutable snapshot of queue metrics used to calculate
    whether new events should be queued or sampled.

    Attributes:
        critical_queue_size: Current number of events in critical queue.
        standard_queue_size: Current number of events in standard queue.
        critical_queue_max: Maximum capacity of critical queue.
        standard_queue_max: Maximum capacity of standard queue.
        dlq_size: Current size of dead letter queue (events that failed delivery).
    """

    critical_queue_size: int
    standard_queue_size: int
    critical_queue_max: int = 10_000
    standard_queue_max: int = 50_000
    dlq_size: int = 0

    def __post_init__(self) -> None:
        """Validate queue metrics after construction.

        Raises:
            ValueError: If any metric is negative or max is less than current.
        """
        if self.critical_queue_size < 0:
            raise ValueError(
                f"critical_queue_size cannot be negative, got {self.critical_queue_size}"
            )
        if self.standard_queue_size < 0:
            raise ValueError(
                f"standard_queue_size cannot be negative, got {self.standard_queue_size}"
            )
        if self.critical_queue_max <= 0:
            raise ValueError(
                f"critical_queue_max must be positive, got {self.critical_queue_max}"
            )
        if self.standard_queue_max <= 0:
            raise ValueError(
                f"standard_queue_max must be positive, got {self.standard_queue_max}"
            )
        if self.dlq_size < 0:
            raise ValueError(f"dlq_size cannot be negative, got {self.dlq_size}")

    @property
    def critical_queue_fill_ratio(self) -> float:
        """Calculate fill ratio for critical queue (0.0 to 1.0+)."""
        return self.critical_queue_size / self.critical_queue_max

    @property
    def standard_queue_fill_ratio(self) -> float:
        """Calculate fill ratio for standard queue (0.0 to 1.0+)."""
        return self.standard_queue_size / self.standard_queue_max


@dataclass(frozen=True)
class BackpressureThresholds:
    """Thresholds for backpressure calculation.

    Immutable configuration for when to start sampling events.

    Attributes:
        elevated_threshold: Queue fill ratio to start reduced sampling (default 0.8).
        critical_threshold: Queue fill ratio for aggressive sampling (default 0.9).
        elevated_sample_rate: Sample rate when above elevated threshold (default 0.5).
        critical_sample_rate: Sample rate when above critical threshold (default 0.2).
    """

    elevated_threshold: float = 0.8
    critical_threshold: float = 0.9
    elevated_sample_rate: float = 0.5
    critical_sample_rate: float = 0.2

    def __post_init__(self) -> None:
        """Validate thresholds after construction.

        Raises:
            ValueError: If thresholds are invalid.
        """
        if not (0.0 < self.elevated_threshold < 1.0):
            raise ValueError(
                f"elevated_threshold must be between 0 and 1, got {self.elevated_threshold}"
            )
        if not (0.0 < self.critical_threshold <= 1.0):
            raise ValueError(
                f"critical_threshold must be between 0 and 1, got {self.critical_threshold}"
            )
        if self.elevated_threshold >= self.critical_threshold:
            raise ValueError(
                f"elevated_threshold ({self.elevated_threshold}) must be less than "
                f"critical_threshold ({self.critical_threshold})"
            )
        if not (0.0 < self.elevated_sample_rate <= 1.0):
            raise ValueError(
                f"elevated_sample_rate must be between 0 and 1, got {self.elevated_sample_rate}"
            )
        if not (0.0 < self.critical_sample_rate <= 1.0):
            raise ValueError(
                f"critical_sample_rate must be between 0 and 1, got {self.critical_sample_rate}"
            )


# Default thresholds per specification section 9.5
DEFAULT_THRESHOLDS = BackpressureThresholds()


@dataclass(frozen=True)
class BackpressureDecision:
    """Result of backpressure calculation.

    Immutable decision object indicating whether to queue an event
    and what sampling rate to apply.

    Attributes:
        should_queue: Whether the event should be added to the queue.
        sample_rate: The sampling rate applied (1.0 = no sampling).
        pressure_level: Current pressure level based on queue fill.
        reason: Human-readable explanation of the decision.
    """

    should_queue: bool
    sample_rate: float
    pressure_level: Literal["normal", "elevated", "critical"]
    reason: str

    def __post_init__(self) -> None:
        """Validate decision after construction.

        Raises:
            ValueError: If sample_rate is invalid.
        """
        if not (0.0 <= self.sample_rate <= 1.0):
            raise ValueError(
                f"sample_rate must be between 0 and 1, got {self.sample_rate}"
            )


def calculate_backpressure(
    metrics: QueueMetrics,
    is_critical_event: bool,
    thresholds: BackpressureThresholds | None = None,
) -> BackpressureDecision:
    """
    Calculate whether to queue an event based on backpressure.

    This is a PURE function - no I/O, deterministic output.

    Backpressure Rules (per spec section 9.5):
        1. Critical events are NEVER dropped (always should_queue=True)
        2. Standard events sampled at 0.5 when queue >80% full
        3. Standard events sampled at 0.2 when queue >90% full
        4. Normal operation (no sampling) when queue <80% full

    Args:
        metrics: Current queue metrics snapshot.
        is_critical_event: Whether this is a critical priority event.
        thresholds: Optional backpressure thresholds configuration.
            Uses DEFAULT_THRESHOLDS if not provided.

    Returns:
        BackpressureDecision with queuing recommendation and sampling rate.

    Examples:
        >>> metrics = QueueMetrics(critical_queue_size=100, standard_queue_size=1000)
        >>> calculate_backpressure(metrics, is_critical_event=True)
        BackpressureDecision(should_queue=True, sample_rate=1.0, ...)

        >>> metrics = QueueMetrics(critical_queue_size=100, standard_queue_size=45000)
        >>> calculate_backpressure(metrics, is_critical_event=False)
        BackpressureDecision(should_queue=True, sample_rate=0.2, pressure_level='critical', ...)
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    # Rule 1: Critical events are NEVER dropped
    if is_critical_event:
        return _calculate_critical_event_decision(metrics)

    # For standard events, check queue fill ratio
    return _calculate_standard_event_decision(metrics, thresholds)


def _calculate_critical_event_decision(
    metrics: QueueMetrics,
) -> BackpressureDecision:
    """
    Calculate backpressure decision for critical events.

    Critical events are ALWAYS queued regardless of queue state.
    We still report pressure level for monitoring purposes.

    Args:
        metrics: Current queue metrics.

    Returns:
        BackpressureDecision with should_queue=True.
    """
    fill_ratio = metrics.critical_queue_fill_ratio
    pressure_level = _determine_pressure_level(fill_ratio)

    if fill_ratio >= 1.0:
        reason = "Critical event queued despite queue overflow (critical events never dropped)"
    elif pressure_level == "critical":
        reason = "Critical event queued (critical events never dropped, queue under pressure)"
    elif pressure_level == "elevated":
        reason = "Critical event queued (critical events never dropped)"
    else:
        reason = "Critical event queued normally"

    return BackpressureDecision(
        should_queue=True,
        sample_rate=1.0,
        pressure_level=pressure_level,
        reason=reason,
    )


def _calculate_standard_event_decision(
    metrics: QueueMetrics,
    thresholds: BackpressureThresholds,
) -> BackpressureDecision:
    """
    Calculate backpressure decision for standard events.

    Standard events may be sampled based on queue fill ratio:
    - >90% full: sample at 0.2 (keep 20% of events)
    - >80% full: sample at 0.5 (keep 50% of events)
    - <80% full: no sampling (keep all events)

    Args:
        metrics: Current queue metrics.
        thresholds: Backpressure thresholds configuration.

    Returns:
        BackpressureDecision with appropriate sampling rate.
    """
    fill_ratio = metrics.standard_queue_fill_ratio

    # Queue is at or over capacity - do not queue
    if fill_ratio >= 1.0:
        return BackpressureDecision(
            should_queue=False,
            sample_rate=0.0,
            pressure_level="critical",
            reason="Standard event dropped: queue at capacity",
        )

    # Critical pressure (>90% full) - aggressive sampling
    if fill_ratio >= thresholds.critical_threshold:
        return BackpressureDecision(
            should_queue=True,
            sample_rate=thresholds.critical_sample_rate,
            pressure_level="critical",
            reason=(
                f"Standard event subject to {thresholds.critical_sample_rate:.0%} sampling "
                f"(queue {fill_ratio:.0%} full)"
            ),
        )

    # Elevated pressure (>80% full) - moderate sampling
    if fill_ratio >= thresholds.elevated_threshold:
        return BackpressureDecision(
            should_queue=True,
            sample_rate=thresholds.elevated_sample_rate,
            pressure_level="elevated",
            reason=(
                f"Standard event subject to {thresholds.elevated_sample_rate:.0%} sampling "
                f"(queue {fill_ratio:.0%} full)"
            ),
        )

    # Normal operation - no sampling
    return BackpressureDecision(
        should_queue=True,
        sample_rate=1.0,
        pressure_level="normal",
        reason="Standard event queued normally",
    )


def _determine_pressure_level(
    fill_ratio: float,
    thresholds: BackpressureThresholds | None = None,
) -> Literal["normal", "elevated", "critical"]:
    """
    Determine pressure level based on queue fill ratio.

    Args:
        fill_ratio: Queue fill ratio (0.0 to 1.0+).
        thresholds: Optional thresholds configuration.

    Returns:
        Pressure level as literal string.
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    if fill_ratio >= thresholds.critical_threshold:
        return "critical"
    if fill_ratio >= thresholds.elevated_threshold:
        return "elevated"
    return "normal"


def should_sample_event(
    sample_rate: float,
    event_hash: str,
) -> bool:
    """
    Deterministically decide if event should be sampled (kept).

    Uses event_hash for consistent sampling - the same event will always
    get the same decision. This is important for:
    1. Retry consistency: retried events get same sampling decision
    2. Debugging: reproducible behavior
    3. Fairness: no bias based on timing

    The sampling is based on the hash value modulo 1000, compared against
    the sample rate threshold. This provides ~0.1% granularity.

    Args:
        sample_rate: Probability of keeping the event (0.0 to 1.0).
            - 1.0 = keep all events (no sampling)
            - 0.5 = keep 50% of events
            - 0.2 = keep 20% of events
            - 0.0 = drop all events
        event_hash: Hash string for the event (e.g., SHA-256 hex digest).
            Must be consistent for the same event across retries.

    Returns:
        True if event should be kept (sampled in), False if dropped.

    Raises:
        ValueError: If sample_rate is outside valid range or event_hash is empty.

    Examples:
        >>> should_sample_event(1.0, "abc123")  # Always keep
        True

        >>> should_sample_event(0.0, "abc123")  # Always drop
        False

        >>> # Consistent for same hash
        >>> should_sample_event(0.5, "abc123") == should_sample_event(0.5, "abc123")
        True
    """
    if not (0.0 <= sample_rate <= 1.0):
        raise ValueError(f"sample_rate must be between 0 and 1, got {sample_rate}")

    if not event_hash:
        raise ValueError("event_hash cannot be empty")

    # Edge cases for efficiency
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False

    # Convert hash to a number in range [0, 1000)
    # Use last 8 hex chars to get a 32-bit value, then modulo 1000
    hash_suffix = event_hash[-8:] if len(event_hash) >= 8 else event_hash
    try:
        hash_value = int(hash_suffix, 16)
    except ValueError:
        # Non-hex hash - use simple character sum as fallback
        hash_value = sum(ord(c) for c in event_hash)

    # Map to [0, 1000) range for 0.1% granularity
    bucket = hash_value % 1000
    threshold = int(sample_rate * 1000)

    return bucket < threshold


def calculate_effective_sample_rate(
    metrics: QueueMetrics,
    is_critical_event: bool,
    thresholds: BackpressureThresholds | None = None,
) -> float:
    """
    Calculate the effective sample rate for an event given current queue state.

    Convenience function that combines backpressure calculation
    with sample rate extraction.

    Args:
        metrics: Current queue metrics.
        is_critical_event: Whether this is a critical event.
        thresholds: Optional backpressure thresholds.

    Returns:
        Sample rate (0.0 to 1.0) to apply to the event.

    Examples:
        >>> metrics = QueueMetrics(critical_queue_size=100, standard_queue_size=1000)
        >>> calculate_effective_sample_rate(metrics, is_critical_event=True)
        1.0

        >>> metrics = QueueMetrics(critical_queue_size=100, standard_queue_size=46000)
        >>> calculate_effective_sample_rate(metrics, is_critical_event=False)
        0.2
    """
    decision = calculate_backpressure(metrics, is_critical_event, thresholds)
    return decision.sample_rate
