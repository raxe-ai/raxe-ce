"""
Session tracker for telemetry coordination.

Tracks session lifecycle and first-use activation events for analytics.
This module is part of the application layer - it orchestrates between
domain-level event creation and infrastructure-level persistence.

Key Responsibilities:
- Generate and manage session IDs (one per Python interpreter instance)
- Track session start/end events
- Fire activation events (first_scan, first_threat, etc.)
- Calculate time-to-first-scan metrics for onboarding analytics
"""

from __future__ import annotations

import atexit
import logging
import sys
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from raxe.domain.telemetry.events import (
    TelemetryEvent,
    create_activation_event,
    create_session_end_event,
    create_session_start_event,
    generate_session_id,
)
from raxe.infrastructure.telemetry.dual_queue import DualQueue, StateKey

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Activation feature to StateKey mapping
# Aligned with backend canonical values
_FEATURE_TO_STATE_KEY: dict[str, StateKey] = {
    "first_scan": StateKey.ACTIVATED_FIRST_SCAN,
    "first_threat": StateKey.ACTIVATED_FIRST_THREAT,
    "first_block": StateKey.ACTIVATED_FIRST_BLOCK,
    "first_cli": StateKey.ACTIVATED_FIRST_CLI,
    "first_sdk": StateKey.ACTIVATED_FIRST_SDK,
    "first_decorator": StateKey.ACTIVATED_FIRST_DECORATOR,
    "first_wrapper": StateKey.ACTIVATED_FIRST_WRAPPER,
    "first_langchain": StateKey.ACTIVATED_FIRST_LANGCHAIN,
    "first_l2_detection": StateKey.ACTIVATED_FIRST_L2_DETECTION,
    "first_custom_rule": StateKey.ACTIVATED_FIRST_CUSTOM_RULE,
}

# Type alias for valid activation features (aligned with backend)
ActivationFeature = Literal[
    "first_scan",
    "first_threat",
    "first_block",
    "first_cli",
    "first_sdk",
    "first_decorator",
    "first_wrapper",
    "first_langchain",
    "first_l2_detection",
    "first_custom_rule",
]


class SessionTracker:
    """
    Tracks session lifecycle and first-use activations.

    Responsibilities:
    - Generate session_id per Python interpreter instance
    - Track session start/end
    - Fire activation events (first_scan, first_threat, etc.)
    - Calculate time-to-first-scan metric

    The session tracker maintains state in the DualQueue's persistent
    state table, ensuring activation events are only fired once per
    installation (not per session).

    Example:
        >>> queue = DualQueue()
        >>> tracker = SessionTracker(queue, installation_id="inst_abc123")
        >>> event = tracker.start_session(entry_point="cli")
        >>> # ... perform operations ...
        >>> activation = tracker.track_activation("first_scan")
        >>> end_event = tracker.end_session(scans_in_session=10, threats_in_session=2)

    Thread Safety:
        This class is NOT thread-safe. Access should be synchronized externally
        if used from multiple threads.
    """

    def __init__(
        self,
        queue: DualQueue,
        installation_id: str,
    ) -> None:
        """
        Initialize the session tracker.

        Args:
            queue: DualQueue instance for state persistence and event queuing.
            installation_id: Unique installation identifier (inst_ prefix).
                This is obtained from the telemetry orchestrator.
        """
        self._queue = queue
        self._installation_id = installation_id
        self._session_id: str | None = None
        self._session_number: int = 0
        self._session_start_time: float | None = None
        self._entry_point: str | None = None
        self._session_started = False
        self._features_used: set[str] = set()
        self._scans_count = 0
        self._threats_count = 0

        # Register atexit handler for graceful shutdown
        atexit.register(self._atexit_handler)

        logger.debug(f"SessionTracker initialized for installation {installation_id}")

    @property
    def session_id(self) -> str:
        """
        Get current session ID (generated once per process).

        The session ID is lazily generated on first access and remains
        constant for the lifetime of the Python interpreter instance.

        Returns:
            Session ID with sess_ prefix.
        """
        if self._session_id is None:
            self._session_id = generate_session_id()
        return self._session_id

    @property
    def session_number(self) -> int:
        """
        Get session count for this installation.

        This is the sequential session number across all sessions for
        this installation, persisted in the database.

        Returns:
            Session number (1-indexed, 0 if session not started).
        """
        return self._session_number

    @property
    def is_session_active(self) -> bool:
        """
        Check if a session is currently active.

        Returns:
            True if session has been started and not ended.
        """
        return self._session_started

    def start_session(
        self,
        entry_point: Literal["cli", "sdk", "wrapper", "integration", "repl"] = "sdk",
    ) -> TelemetryEvent:
        """
        Start a new session. Called on first RAXE usage.

        This should be called once per Python interpreter instance,
        typically on the first scan or API call.

        Args:
            entry_point: How RAXE was invoked (cli, sdk, wrapper, etc.).

        Returns:
            TelemetryEvent for session_start.

        Raises:
            RuntimeError: If session was already started.
        """
        if self._session_started:
            raise RuntimeError("Session already started")

        # Increment session count in persistent state
        self._session_number = self._queue.increment_state(StateKey.SESSION_COUNT, 0)

        # Record session start time
        self._session_start_time = time.monotonic()
        self._entry_point = entry_point
        self._session_started = True

        # Calculate gap since last session (if available)
        previous_session_gap_hours: float | None = None
        last_session_end = self._queue.get_state("last_session_end_timestamp")
        if last_session_end:
            try:
                last_end_dt = datetime.fromisoformat(last_session_end)
                now = datetime.now(timezone.utc)
                gap_seconds = (now - last_end_dt).total_seconds()
                previous_session_gap_hours = gap_seconds / 3600.0
            except (ValueError, TypeError):
                pass  # Invalid timestamp, skip gap calculation

        # Detect environment
        environment = self._detect_environment()

        # Create session start event
        event = create_session_start_event(
            session_id=self.session_id,
            session_number=self._session_number,
            entry_point=entry_point,
            previous_session_gap_hours=previous_session_gap_hours,
            environment=environment,
        )

        # Enqueue the event
        self._queue.enqueue(event)

        logger.info(
            f"Session started: {self.session_id} (session #{self._session_number})"
        )

        return event

    def end_session(
        self,
        scans_in_session: int | None = None,
        threats_in_session: int | None = None,
        end_reason: Literal["normal", "error", "timeout", "interrupt", "unknown"] = "normal",
    ) -> TelemetryEvent:
        """
        End current session. Called on process exit.

        This creates a session_end event with aggregate session metrics.
        The event has critical priority to ensure delivery before shutdown.

        Args:
            scans_in_session: Number of scans performed (uses internal count if None).
            threats_in_session: Number of threats detected (uses internal count if None).
            end_reason: How session ended.

        Returns:
            TelemetryEvent for session_end (critical priority).

        Raises:
            RuntimeError: If no session was started.
        """
        if not self._session_started:
            raise RuntimeError("No session to end - session was not started")

        # Use internal counts if not provided
        if scans_in_session is None:
            scans_in_session = self._scans_count
        if threats_in_session is None:
            threats_in_session = self._threats_count

        # Calculate session duration
        duration_seconds = 0.0
        if self._session_start_time is not None:
            duration_seconds = time.monotonic() - self._session_start_time

        # Get memory usage if available
        peak_memory_mb: float | None = None
        try:
            import resource
            # getrusage returns memory in kilobytes on some systems
            usage = resource.getrusage(resource.RUSAGE_SELF)
            peak_memory_mb = usage.ru_maxrss / 1024.0  # Convert to MB
        except (ImportError, AttributeError):
            pass  # resource module not available (Windows)

        # Create session end event
        event = create_session_end_event(
            session_id=self.session_id,
            duration_seconds=duration_seconds,
            scans_in_session=scans_in_session,
            threats_in_session=threats_in_session,
            end_reason=end_reason,
            peak_memory_mb=peak_memory_mb,
            features_used=list(self._features_used) if self._features_used else None,
        )

        # Enqueue the event (critical priority)
        self._queue.enqueue(event)

        # Store session end timestamp for gap calculation
        self._queue.set_state(
            "last_session_end_timestamp",
            datetime.now(timezone.utc).isoformat(),
        )

        # Mark session as ended
        self._session_started = False

        logger.info(
            f"Session ended: {self.session_id} "
            f"(duration={duration_seconds:.1f}s, scans={scans_in_session}, "
            f"threats={threats_in_session})"
        )

        return event

    def track_activation(
        self,
        feature: ActivationFeature,
        activation_context: dict[str, Any] | None = None,
    ) -> TelemetryEvent | None:
        """
        Track first use of a feature.

        Returns activation event if first time, None if already activated.
        Activation events are per-installation, not per-session.

        Args:
            feature: Feature being activated for the first time.
            activation_context: Additional context about the activation.

        Returns:
            TelemetryEvent for activation if first time, None otherwise.
        """
        # Get the state key for this feature
        state_key = _FEATURE_TO_STATE_KEY.get(feature)
        if state_key is None:
            logger.warning(f"Unknown activation feature: {feature}")
            return None

        # Check if already activated
        if self._queue.has_state(state_key):
            logger.debug(f"Feature {feature} already activated")
            return None

        # Calculate seconds since install
        seconds_since_install = self.get_seconds_since_install()

        # Build activation context
        full_context = activation_context.copy() if activation_context else {}
        if self._entry_point:
            full_context["entry_point"] = self._entry_point
        if self._session_number > 0:
            full_context["session_number"] = self._session_number

        # Create activation event
        event = create_activation_event(
            feature=feature,
            seconds_since_install=seconds_since_install,
            activation_context=full_context if full_context else None,
        )

        # Mark as activated in persistent state
        self._queue.set_state(state_key, datetime.now(timezone.utc).isoformat())

        # Enqueue the event (critical priority)
        self._queue.enqueue(event)

        logger.info(
            f"Activation event: {feature} "
            f"(time_to_value={seconds_since_install:.1f}s)"
        )

        return event

    def get_seconds_since_install(self) -> float:
        """
        Get time elapsed since installation (for time-to-value metrics).

        Returns:
            Seconds since installation event was fired.
            Returns 0.0 if install timestamp is not available.
        """
        install_timestamp = self._queue.get_state(StateKey.INSTALL_TIMESTAMP)
        if not install_timestamp:
            return 0.0

        try:
            install_dt = datetime.fromisoformat(install_timestamp)
            now = datetime.now(timezone.utc)
            return (now - install_dt).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    def is_first_session(self) -> bool:
        """
        Check if this is the first session.

        Returns:
            True if session_number is 1 or session hasn't started.
        """
        return self._session_number <= 1

    def record_scan(self) -> None:
        """
        Record that a scan was performed in this session.

        This increments the internal scan counter for session_end event.
        """
        self._scans_count += 1

    def record_threat(self) -> None:
        """
        Record that a threat was detected in this session.

        This increments the internal threat counter for session_end event.
        """
        self._threats_count += 1

    def record_feature_used(self, feature: str) -> None:
        """
        Record that a feature was used in this session.

        This is tracked for the features_used list in session_end event.

        Args:
            feature: Name of the feature used.
        """
        self._features_used.add(feature)

    def _detect_environment(self) -> dict[str, bool]:
        """
        Detect the execution environment.

        Returns:
            Dictionary with environment flags (is_ci, is_interactive, is_notebook).
        """
        import os

        environment: dict[str, bool] = {}

        # Detect CI environment
        ci_env_vars = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "CIRCLECI"]
        environment["is_ci"] = any(os.environ.get(var) for var in ci_env_vars)

        # Detect interactive session
        has_isatty = hasattr(sys.stdin, "isatty")
        environment["is_interactive"] = sys.stdin.isatty() if has_isatty else False

        # Detect Jupyter notebook
        try:
            from IPython import get_ipython
            ipython = get_ipython()
            environment["is_notebook"] = ipython is not None and "IPKernelApp" in str(type(ipython))
        except (ImportError, NameError):
            environment["is_notebook"] = False

        return environment

    def _atexit_handler(self) -> None:
        """
        Handle process exit for graceful session end.

        This is registered with atexit to ensure session_end is sent
        even if the user doesn't explicitly call end_session.
        """
        if self._session_started:
            try:
                self.end_session(end_reason="normal")
            except Exception as e:
                logger.debug(f"Error ending session at exit: {e}")
