"""Performance monitoring and degradation strategies.

Provides circuit breaker pattern and performance tracking
to ensure system stability under load.

Performance degradation modes:
- fail_open: Allow requests through unchecked on overload
- fail_closed: Block requests on overload (safe but strict)
- sample: Check every Nth request
- adaptive: Smart sampling based on load

Performance targets:
- P95 scan latency: <10ms
- Average scan: <5ms
- Circuit breaker response: <1ms
"""
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar('T')


class PerformanceMode(Enum):
    """Performance degradation strategies."""

    FAIL_OPEN = "fail_open"       # Allow through on overload
    FAIL_CLOSED = "fail_closed"   # Block on overload
    SAMPLE = "sample"             # Check every Nth request
    ADAPTIVE = "adaptive"         # Smart sampling


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"         # Normal operation
    OPEN = "open"             # Failing, reject requests
    HALF_OPEN = "half_open"   # Testing if recovered


@dataclass
class PerformanceConfig:
    """Performance degradation configuration.

    Attributes:
        mode: Degradation strategy
        failure_threshold: Open circuit after N consecutive failures
        reset_timeout_seconds: Wait time before trying half-open
        half_open_requests: Requests to test in half-open state
        sample_rate: For SAMPLE mode, check 1 in N requests
        latency_threshold_ms: Max acceptable latency before degradation
    """
    mode: PerformanceMode = PerformanceMode.FAIL_OPEN
    failure_threshold: int = 5
    reset_timeout_seconds: float = 30.0
    half_open_requests: int = 3
    sample_rate: int = 10  # Check every 10th request
    latency_threshold_ms: float = 10.0


class CircuitBreakerError(Exception):
    """Circuit breaker is open (too many failures)."""
    pass


class PerformanceDegradedError(Exception):
    """System overloaded, degraded mode activated."""
    pass


class CircuitBreaker(Generic[T]):
    """Circuit breaker pattern implementation.

    Prevents cascade failures by failing fast when errors accumulate.

    States:
    - CLOSED: Normal operation, all calls proceed
    - OPEN: Too many failures, reject immediately
    - HALF_OPEN: Testing recovery with limited requests

    Thread-safe for concurrent use.

    Example usage:
        breaker = CircuitBreaker(
            failure_threshold=5,
            reset_timeout=30.0,
        )

        try:
            result = breaker.call(risky_operation, arg1, arg2)
        except CircuitBreakerError:
            # Circuit is open, fail fast
            return fallback_value
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_requests: int = 3,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Open after N consecutive failures
            reset_timeout: Seconds to wait before half-open
            half_open_requests: Requests to test in half-open
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_requests = half_open_requests

        # State tracking (protected by lock)
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_attempts = 0

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Any exception raised by func
        """
        with self._lock:
            # Check if circuit is open
            if self._state == CircuitState.OPEN:
                # Check if we should try half-open
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_attempts = 0
                else:
                    raise CircuitBreakerError(
                        f"Circuit breaker OPEN (failures: {self._failure_count}, "
                        f"retry in {self._time_until_reset():.1f}s)"
                    )

            # Check if we're at capacity in half-open
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_attempts >= self.half_open_requests:
                    raise CircuitBreakerError(
                        "Circuit breaker HALF_OPEN at capacity"
                    )
                self._half_open_attempts += 1

        # Execute function (outside lock to avoid deadlock)
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Record successful call."""
        with self._lock:
            self._failure_count = 0
            self._success_count += 1

            # If half-open and enough successes, close circuit
            if self._state == CircuitState.HALF_OPEN:
                if self._success_count >= self.half_open_requests:
                    self._state = CircuitState.CLOSED
                    self._half_open_attempts = 0

    def _on_failure(self) -> None:
        """Record failed call."""
        with self._lock:
            self._failure_count += 1
            self._success_count = 0
            self._last_failure_time = datetime.now(timezone.utc)

            # Open circuit if threshold exceeded
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self._last_failure_time is None:
            return False

        elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
        return elapsed >= self.reset_timeout

    def _time_until_reset(self) -> float:
        """Seconds until reset attempt."""
        if self._last_failure_time is None:
            return 0.0

        elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
        return max(0.0, self.reset_timeout - elapsed)

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        """True if circuit is open."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """True if circuit is closed."""
        return self.state == CircuitState.CLOSED

    def reset(self) -> None:
        """Manually reset circuit to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_attempts = 0

    def get_stats(self) -> dict[str, object]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": (
                    self._last_failure_time.isoformat()
                    if self._last_failure_time else None
                ),
                "time_until_reset": self._time_until_reset(),
            }


class LatencyTracker:
    """Track latency percentiles for performance monitoring.

    Tracks P50, P95, P99 latencies with rolling window.
    Thread-safe for concurrent updates.
    """

    def __init__(self, window_size: int = 1000):
        """Initialize latency tracker.

        Args:
            window_size: Number of samples to keep in rolling window
        """
        self.window_size = window_size
        self._lock = threading.Lock()
        self._latencies: list[float] = []
        self._total_count = 0
        self._total_latency_ms = 0.0

    def record(self, latency_ms: float) -> None:
        """Record a latency sample.

        Args:
            latency_ms: Latency in milliseconds
        """
        with self._lock:
            self._latencies.append(latency_ms)
            self._total_count += 1
            self._total_latency_ms += latency_ms

            # Keep only last N samples
            if len(self._latencies) > self.window_size:
                self._latencies.pop(0)

    def get_percentile(self, percentile: float) -> float:
        """Get latency percentile.

        Args:
            percentile: Percentile (0.0-1.0), e.g., 0.95 for P95

        Returns:
            Latency at percentile in milliseconds
        """
        with self._lock:
            if not self._latencies:
                return 0.0

            sorted_latencies = sorted(self._latencies)
            index = int(len(sorted_latencies) * percentile)
            index = min(index, len(sorted_latencies) - 1)
            return sorted_latencies[index]

    @property
    def p50(self) -> float:
        """P50 (median) latency."""
        return self.get_percentile(0.50)

    @property
    def p95(self) -> float:
        """P95 latency."""
        return self.get_percentile(0.95)

    @property
    def p99(self) -> float:
        """P99 latency."""
        return self.get_percentile(0.99)

    @property
    def average(self) -> float:
        """Average latency across all samples."""
        with self._lock:
            if self._total_count == 0:
                return 0.0
            return self._total_latency_ms / self._total_count

    def get_stats(self) -> dict[str, float]:
        """Get latency statistics."""
        return {
            "p50_ms": self.p50,
            "p95_ms": self.p95,
            "p99_ms": self.p99,
            "average_ms": self.average,
            "sample_count": len(self._latencies),
            "total_count": self._total_count,
        }


class PerformanceMonitor:
    """Monitor and enforce performance degradation strategies.

    Combines circuit breaker with latency tracking to
    implement performance degradation modes.
    """

    def __init__(self, config: PerformanceConfig):
        """Initialize performance monitor.

        Args:
            config: Performance configuration
        """
        self.config = config
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.failure_threshold,
            reset_timeout=config.reset_timeout_seconds,
            half_open_requests=config.half_open_requests,
        )
        self.latency_tracker = LatencyTracker()
        self._request_counter = 0
        self._lock = threading.Lock()

    def should_check(self) -> bool:
        """Determine if request should be checked.

        Implements sampling based on performance mode.

        Returns:
            True if request should be scanned
        """
        if self.config.mode == PerformanceMode.FAIL_CLOSED:
            # Always check
            return True

        if self.config.mode == PerformanceMode.FAIL_OPEN:
            # Check unless circuit is open
            if self.circuit_breaker.is_open:
                return False  # Skip check, allow through
            return True

        if self.config.mode == PerformanceMode.SAMPLE:
            # Sample 1 in N requests
            with self._lock:
                self._request_counter += 1
                return self._request_counter % self.config.sample_rate == 0

        if self.config.mode == PerformanceMode.ADAPTIVE:
            # Adaptive: sample more under high load
            p95 = self.latency_tracker.p95
            if p95 > self.config.latency_threshold_ms:
                # High latency - sample less
                sample_rate = self.config.sample_rate * 2
            else:
                # Normal latency - sample normally
                sample_rate = self.config.sample_rate

            with self._lock:
                self._request_counter += 1
                return self._request_counter % int(sample_rate) == 0

        return True

    def record_latency(self, latency_ms: float) -> None:
        """Record scan latency.

        Args:
            latency_ms: Latency in milliseconds
        """
        self.latency_tracker.record(latency_ms)

    def get_stats(self) -> dict[str, object]:
        """Get comprehensive performance statistics."""
        return {
            "mode": self.config.mode.value,
            "circuit_breaker": self.circuit_breaker.get_stats(),
            "latency": self.latency_tracker.get_stats(),
            "request_count": self._request_counter,
        }
