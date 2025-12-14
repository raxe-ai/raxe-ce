"""Tests for SessionTracker.

This module tests the SessionTracker class which handles:
- Session ID management (consistent within process, unique across processes)
- Session number increment tracking
- Session start/end event creation
- Activation tracking (first-time feature usage)
- Installation time tracking
- First session detection
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from unittest.mock import MagicMock, Mock, patch

import pytest

from raxe.domain.telemetry.events import (
    EventType,
    TelemetryEvent,
    create_session_end_event,
    create_session_start_event,
    generate_session_id,
)
from raxe.infrastructure.telemetry.dual_queue import DualQueue, StateKey

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# SessionTracker Mock Implementation
# =============================================================================
# Note: SessionTracker may not exist yet in the codebase. These tests define
# the expected behavior and can be used as a specification for implementation.


class SessionTracker:
    """Session and activation tracker for telemetry.

    This class manages:
    - Session lifecycle (start/end events)
    - Session counting across restarts
    - Feature activation tracking (first-time usage)
    - Time-to-value metrics

    Note: This is a test implementation. The actual implementation should
    be in src/raxe/application/session_tracker.py or similar.
    """

    _instance: SessionTracker | None = None
    _session_id: str | None = None

    def __init__(self, queue: DualQueue) -> None:
        """Initialize session tracker.

        Args:
            queue: DualQueue for state persistence and event queuing.
        """
        self._queue = queue
        self._session_started = False
        self._scans_in_session = 0
        self._threats_in_session = 0
        self._session_start_time: datetime | None = None
        self._features_used: set[str] = set()

    @classmethod
    def get_session_id(cls) -> str:
        """Get or create the session ID for this process.

        Returns:
            Session ID (consistent within process, unique per process).
        """
        if cls._session_id is None:
            cls._session_id = generate_session_id()
        return cls._session_id

    @classmethod
    def reset_session_id(cls) -> None:
        """Reset session ID (for testing only)."""
        cls._session_id = None

    def get_session_number(self) -> int:
        """Get current session number from persistent state.

        Returns:
            Current session number (1-indexed).
        """
        value = self._queue.get_state(StateKey.SESSION_COUNT)
        return int(value) if value else 0

    def start_session(
        self,
        entry_point: Literal["cli", "sdk", "wrapper", "integration", "repl"] | None = None,
    ) -> TelemetryEvent | None:
        """Start a new session and create session_start event.

        Args:
            entry_point: How RAXE was invoked.

        Returns:
            TelemetryEvent for session_start, or None if session already started.
        """
        if self._session_started:
            return None

        # Increment session count
        session_number = self._queue.increment_state(StateKey.SESSION_COUNT, default=0)

        self._session_started = True
        self._session_start_time = datetime.now(timezone.utc)
        self._scans_in_session = 0
        self._threats_in_session = 0
        self._features_used = set()

        # Calculate gap since last session if available
        gap_hours: float | None = None
        last_end = self._queue.get_state("last_session_end")
        if last_end:
            try:
                last_end_dt = datetime.fromisoformat(last_end.replace("Z", "+00:00"))
                delta = self._session_start_time - last_end_dt
                gap_hours = delta.total_seconds() / 3600
            except (ValueError, TypeError):
                pass

        # Detect environment
        environment = self._detect_environment()

        event = create_session_start_event(
            session_id=self.get_session_id(),
            session_number=session_number,
            entry_point=entry_point,
            previous_session_gap_hours=gap_hours,
            environment=environment,
        )

        self._queue.enqueue(event)
        return event

    def end_session(
        self,
        end_reason: Literal["normal", "error", "timeout", "interrupt", "unknown"] = "normal",
        peak_memory_mb: float | None = None,
    ) -> TelemetryEvent | None:
        """End the current session and create session_end event.

        Args:
            end_reason: How the session ended.
            peak_memory_mb: Peak memory usage during session.

        Returns:
            TelemetryEvent for session_end, or None if session not started.
        """
        if not self._session_started:
            return None

        duration_seconds = 0.0
        if self._session_start_time:
            delta = datetime.now(timezone.utc) - self._session_start_time
            duration_seconds = delta.total_seconds()

        event = create_session_end_event(
            session_id=self.get_session_id(),
            duration_seconds=duration_seconds,
            scans_in_session=self._scans_in_session,
            threats_in_session=self._threats_in_session,
            end_reason=end_reason,
            peak_memory_mb=peak_memory_mb,
            features_used=list(self._features_used) if self._features_used else None,
        )

        # Store last session end time
        self._queue.set_state("last_session_end", datetime.now(timezone.utc).isoformat())

        self._session_started = False
        self._queue.enqueue(event)
        return event

    def track_activation(
        self,
        feature: Literal[
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
        ],
        context: dict[str, Any] | None = None,
    ) -> TelemetryEvent | None:
        """Track first-time feature activation.

        Only fires once per feature per installation.

        Args:
            feature: Feature being activated (canonical backend values).
            context: Additional context about the activation.

        Returns:
            TelemetryEvent for activation, or None if already activated.
        """
        # Map feature to state key (aligned with backend canonical values)
        state_key_map = {
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

        state_key = state_key_map.get(feature)
        if not state_key:
            return None

        # Check if already activated
        if self._queue.has_state(state_key):
            return None

        # Mark as activated
        self._queue.set_state(state_key, "true")

        # Calculate seconds since install
        seconds_since_install = self.seconds_since_install()

        # Create activation event using domain function
        from raxe.domain.telemetry.events import create_activation_event

        event = create_activation_event(
            feature=feature,
            seconds_since_install=seconds_since_install,
            activation_context=context,
        )

        self._queue.enqueue(event)
        return event

    def seconds_since_install(self) -> float:
        """Calculate seconds elapsed since installation.

        Returns:
            Seconds since install, or 0.0 if install time unknown.
        """
        install_time_str = self._queue.get_state(StateKey.INSTALL_TIMESTAMP)
        if not install_time_str:
            return 0.0

        try:
            install_time = datetime.fromisoformat(install_time_str.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - install_time
            return delta.total_seconds()
        except (ValueError, TypeError):
            return 0.0

    def is_first_session(self) -> bool:
        """Check if this is the first session for this installation.

        Returns:
            True if session_number is 1, False otherwise.
        """
        return self.get_session_number() <= 1

    def record_scan(self, threat_detected: bool) -> None:
        """Record a scan in the current session.

        Args:
            threat_detected: Whether a threat was detected.
        """
        self._scans_in_session += 1
        if threat_detected:
            self._threats_in_session += 1

    def record_feature_used(self, feature: str) -> None:
        """Record a feature used in the current session.

        Args:
            feature: Name of the feature used.
        """
        self._features_used.add(feature)

    def _detect_environment(self) -> dict[str, bool]:
        """Detect the session environment.

        Returns:
            Dictionary with environment flags.
        """
        import os

        return {
            "is_ci": os.environ.get("CI", "").lower() in ("true", "1", "yes"),
            "is_interactive": sys.stdin.isatty() if hasattr(sys.stdin, "isatty") else False,
            "is_notebook": "ipykernel" in sys.modules,
        }


# =============================================================================
# Session ID Tests
# =============================================================================


class TestSessionId:
    """Tests for session ID management."""

    def test_session_id_consistent_within_process(
        self, mock_queue: DualQueue
    ) -> None:
        """Session ID remains consistent within the same process."""
        SessionTracker.reset_session_id()

        tracker1 = SessionTracker(mock_queue)
        tracker2 = SessionTracker(mock_queue)

        id1 = tracker1.get_session_id()
        id2 = tracker2.get_session_id()

        assert id1 == id2
        assert id1.startswith("sess_")

    def test_session_id_format(self, mock_queue: DualQueue) -> None:
        """Session ID has correct format (sess_ prefix + hex chars)."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        session_id = tracker.get_session_id()

        assert session_id.startswith("sess_")
        assert len(session_id) == 21  # sess_ (5) + 16 hex chars
        # Verify hex portion
        hex_part = session_id[5:]
        int(hex_part, 16)  # Should not raise

    def test_session_id_persists_across_calls(
        self, mock_queue: DualQueue
    ) -> None:
        """Session ID is cached and reused."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        id1 = tracker.get_session_id()
        id2 = tracker.get_session_id()
        id3 = tracker.get_session_id()

        assert id1 == id2 == id3

    def test_session_id_different_after_reset(
        self, mock_queue: DualQueue
    ) -> None:
        """New session ID generated after reset."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        id1 = tracker.get_session_id()
        SessionTracker.reset_session_id()
        id2 = tracker.get_session_id()

        assert id1 != id2


# =============================================================================
# Session Number Tests
# =============================================================================


class TestSessionNumber:
    """Tests for session number tracking."""

    def test_session_number_starts_at_zero(
        self, mock_queue: DualQueue
    ) -> None:
        """Session number starts at 0 for new installation."""
        tracker = SessionTracker(mock_queue)
        assert tracker.get_session_number() == 0

    def test_session_number_increments_on_start(
        self, mock_queue: DualQueue
    ) -> None:
        """Session number increments when session starts."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        assert tracker.get_session_number() == 0

        tracker.start_session()
        assert tracker.get_session_number() == 1

    def test_session_number_persists(
        self, queue_with_state: DualQueue
    ) -> None:
        """Session number persists across tracker instances."""
        # queue_with_state has SESSION_COUNT = 5
        tracker = SessionTracker(queue_with_state)
        assert tracker.get_session_number() == 5

    def test_multiple_sessions_increment_correctly(
        self, mock_queue: DualQueue
    ) -> None:
        """Multiple session starts increment correctly."""
        tracker = SessionTracker(mock_queue)

        for expected in range(1, 4):
            SessionTracker.reset_session_id()
            tracker._session_started = False  # Reset for testing
            tracker.start_session()
            assert tracker.get_session_number() == expected


# =============================================================================
# Session Start Tests
# =============================================================================


class TestSessionStart:
    """Tests for session start functionality."""

    def test_start_session_creates_event(
        self, mock_queue: DualQueue
    ) -> None:
        """Starting session creates session_start event."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        event = tracker.start_session(entry_point="cli")

        assert event is not None
        assert event.event_type == EventType.SESSION_START.value
        assert event.priority == "standard"
        assert "session_id" in event.payload
        assert "session_number" in event.payload
        assert event.payload["entry_point"] == "cli"

    def test_start_session_only_once(
        self, mock_queue: DualQueue
    ) -> None:
        """Starting session twice returns None on second call."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        event1 = tracker.start_session()
        event2 = tracker.start_session()

        assert event1 is not None
        assert event2 is None

    def test_start_session_enqueues_event(
        self, mock_queue: DualQueue
    ) -> None:
        """Session start event is enqueued."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        tracker.start_session()

        stats = mock_queue.get_stats()
        assert stats["standard_count"] >= 1

    def test_start_session_includes_environment(
        self, mock_queue: DualQueue
    ) -> None:
        """Session start includes environment detection."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        event = tracker.start_session()

        assert "environment" in event.payload
        env = event.payload["environment"]
        assert "is_ci" in env
        assert "is_interactive" in env
        assert "is_notebook" in env

    def test_start_session_calculates_gap(
        self, mock_queue: DualQueue
    ) -> None:
        """Session start calculates gap since last session."""
        SessionTracker.reset_session_id()

        # Set last session end time
        last_end = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        mock_queue.set_state("last_session_end", last_end)

        tracker = SessionTracker(mock_queue)
        event = tracker.start_session()

        assert "previous_session_gap_hours" in event.payload
        gap = event.payload["previous_session_gap_hours"]
        assert 23 < gap < 25  # Approximately 24 hours


# =============================================================================
# Session End Tests
# =============================================================================


class TestSessionEnd:
    """Tests for session end functionality."""

    def test_end_session_creates_event(
        self, mock_queue: DualQueue
    ) -> None:
        """Ending session creates session_end event."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)
        tracker.start_session()

        event = tracker.end_session()

        assert event is not None
        assert event.event_type == EventType.SESSION_END.value
        assert event.priority == "critical"
        assert "session_id" in event.payload
        assert "duration_seconds" in event.payload
        assert "scans_in_session" in event.payload
        assert "threats_in_session" in event.payload

    def test_end_session_requires_start(
        self, mock_queue: DualQueue
    ) -> None:
        """Ending session without start returns None."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        event = tracker.end_session()

        assert event is None

    def test_end_session_is_critical_priority(
        self, mock_queue: DualQueue
    ) -> None:
        """Session end event has critical priority."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)
        tracker.start_session()

        event = tracker.end_session()

        assert event.priority == "critical"

    def test_end_session_tracks_duration(
        self, mock_queue: DualQueue
    ) -> None:
        """Session end calculates correct duration."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)
        tracker.start_session()

        time.sleep(0.1)  # Small delay

        event = tracker.end_session()

        assert event.payload["duration_seconds"] >= 0.1

    def test_end_session_includes_scan_counts(
        self, mock_queue: DualQueue
    ) -> None:
        """Session end includes scan and threat counts."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)
        tracker.start_session()

        # Record some scans
        tracker.record_scan(threat_detected=False)
        tracker.record_scan(threat_detected=True)
        tracker.record_scan(threat_detected=True)

        event = tracker.end_session()

        assert event.payload["scans_in_session"] == 3
        assert event.payload["threats_in_session"] == 2

    def test_end_session_includes_features_used(
        self, mock_queue: DualQueue
    ) -> None:
        """Session end includes list of features used."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)
        tracker.start_session()

        tracker.record_feature_used("cli_scan")
        tracker.record_feature_used("cli_explain")
        tracker.record_feature_used("cli_scan")  # Duplicate

        event = tracker.end_session()

        features = event.payload["features_used"]
        assert len(features) == 2
        assert "cli_scan" in features
        assert "cli_explain" in features

    def test_end_session_stores_timestamp(
        self, mock_queue: DualQueue
    ) -> None:
        """Session end stores timestamp for gap calculation."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)
        tracker.start_session()
        tracker.end_session()

        last_end = mock_queue.get_state("last_session_end")
        assert last_end is not None

        # Should be parseable
        dt = datetime.fromisoformat(last_end.replace("Z", "+00:00"))
        assert isinstance(dt, datetime)


# =============================================================================
# Activation Tracking Tests
# =============================================================================


class TestActivationTracking:
    """Tests for first-time feature activation tracking."""

    def test_track_activation_fires_once(
        self, mock_queue: DualQueue
    ) -> None:
        """Activation only fires once per feature."""
        tracker = SessionTracker(mock_queue)

        event1 = tracker.track_activation("first_scan")
        event2 = tracker.track_activation("first_scan")

        assert event1 is not None
        assert event2 is None

    def test_track_activation_returns_none_on_second_call(
        self, mock_queue: DualQueue
    ) -> None:
        """Second activation call returns None."""
        tracker = SessionTracker(mock_queue)

        tracker.track_activation("first_cli")
        result = tracker.track_activation("first_cli")

        assert result is None

    def test_different_features_fire_independently(
        self, mock_queue: DualQueue
    ) -> None:
        """Different features can each be activated once."""
        tracker = SessionTracker(mock_queue)

        event1 = tracker.track_activation("first_scan")
        event2 = tracker.track_activation("first_cli")
        event3 = tracker.track_activation("first_sdk")

        assert event1 is not None
        assert event2 is not None
        assert event3 is not None

        # But not again
        assert tracker.track_activation("first_scan") is None
        assert tracker.track_activation("first_cli") is None
        assert tracker.track_activation("first_sdk") is None

    def test_activation_event_structure(
        self, mock_queue: DualQueue
    ) -> None:
        """Activation event has correct structure."""
        # Set install time for seconds_since_install
        mock_queue.set_state(
            StateKey.INSTALL_TIMESTAMP,
            (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        )

        tracker = SessionTracker(mock_queue)
        event = tracker.track_activation(
            "first_threat",
            context={"rule_id": "pi-001"},
        )

        assert event.event_type == EventType.ACTIVATION.value
        assert event.priority == "critical"
        assert event.payload["feature"] == "first_threat"
        assert "seconds_since_install" in event.payload
        assert event.payload["activation_context"]["rule_id"] == "pi-001"

    def test_activation_calculates_time_since_install(
        self, mock_queue: DualQueue
    ) -> None:
        """Activation calculates seconds since install."""
        # Set install time 2 minutes ago
        install_time = datetime.now(timezone.utc) - timedelta(minutes=2)
        mock_queue.set_state(StateKey.INSTALL_TIMESTAMP, install_time.isoformat())

        tracker = SessionTracker(mock_queue)
        event = tracker.track_activation("first_scan")

        seconds = event.payload["seconds_since_install"]
        assert 110 < seconds < 130  # Approximately 2 minutes

    def test_activation_persists_across_instances(
        self, mock_queue: DualQueue
    ) -> None:
        """Activation state persists across tracker instances."""
        tracker1 = SessionTracker(mock_queue)
        tracker1.track_activation("first_scan")

        # New tracker instance
        tracker2 = SessionTracker(mock_queue)
        result = tracker2.track_activation("first_scan")

        assert result is None  # Already activated

    def test_all_activation_features(
        self, mock_queue: DualQueue
    ) -> None:
        """All activation features can be tracked (canonical backend values)."""
        tracker = SessionTracker(mock_queue)

        features = [
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

        for feature in features:
            event = tracker.track_activation(feature)
            assert event is not None, f"Failed for feature: {feature}"
            assert event.payload["feature"] == feature


# =============================================================================
# Seconds Since Install Tests
# =============================================================================


class TestSecondsSinceInstall:
    """Tests for install time tracking."""

    def test_seconds_since_install_with_timestamp(
        self, mock_queue: DualQueue
    ) -> None:
        """Calculates seconds since install correctly."""
        install_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_queue.set_state(StateKey.INSTALL_TIMESTAMP, install_time.isoformat())

        tracker = SessionTracker(mock_queue)
        seconds = tracker.seconds_since_install()

        # Should be approximately 3600 seconds (1 hour)
        assert 3500 < seconds < 3700

    def test_seconds_since_install_no_timestamp(
        self, mock_queue: DualQueue
    ) -> None:
        """Returns 0 when no install timestamp."""
        tracker = SessionTracker(mock_queue)
        seconds = tracker.seconds_since_install()

        assert seconds == 0.0

    def test_seconds_since_install_invalid_timestamp(
        self, mock_queue: DualQueue
    ) -> None:
        """Returns 0 for invalid timestamp."""
        mock_queue.set_state(StateKey.INSTALL_TIMESTAMP, "invalid-date")

        tracker = SessionTracker(mock_queue)
        seconds = tracker.seconds_since_install()

        assert seconds == 0.0


# =============================================================================
# First Session Detection Tests
# =============================================================================


class TestFirstSessionDetection:
    """Tests for first session detection."""

    def test_is_first_session_true_initially(
        self, mock_queue: DualQueue
    ) -> None:
        """is_first_session returns True before any session."""
        tracker = SessionTracker(mock_queue)
        assert tracker.is_first_session() is True

    def test_is_first_session_true_after_first_start(
        self, mock_queue: DualQueue
    ) -> None:
        """is_first_session returns True during first session."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)
        tracker.start_session()

        assert tracker.is_first_session() is True

    def test_is_first_session_false_after_second_start(
        self, mock_queue: DualQueue
    ) -> None:
        """is_first_session returns False after second session starts."""
        tracker = SessionTracker(mock_queue)

        # First session
        SessionTracker.reset_session_id()
        tracker._session_started = False
        tracker.start_session()
        assert tracker.is_first_session() is True

        # Second session
        SessionTracker.reset_session_id()
        tracker._session_started = False
        tracker.start_session()
        assert tracker.is_first_session() is False


# =============================================================================
# State Persistence Tests
# =============================================================================


class TestStatePersistence:
    """Tests for state persistence via DualQueue."""

    def test_session_count_persists(
        self, mock_queue: DualQueue
    ) -> None:
        """Session count persists in queue state."""
        tracker = SessionTracker(mock_queue)
        SessionTracker.reset_session_id()
        tracker.start_session()

        # Check directly in queue
        count = mock_queue.get_state(StateKey.SESSION_COUNT)
        assert int(count) == 1

    def test_activation_state_persists(
        self, mock_queue: DualQueue
    ) -> None:
        """Activation state persists in queue state."""
        tracker = SessionTracker(mock_queue)
        tracker.track_activation("first_scan")

        # Check directly in queue
        assert mock_queue.has_state(StateKey.ACTIVATED_FIRST_SCAN)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_end_session_twice(
        self, mock_queue: DualQueue
    ) -> None:
        """Ending session twice returns None second time."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)
        tracker.start_session()

        event1 = tracker.end_session()
        event2 = tracker.end_session()

        assert event1 is not None
        assert event2 is None

    def test_record_scan_without_session(
        self, mock_queue: DualQueue
    ) -> None:
        """Recording scan without session doesn't crash."""
        tracker = SessionTracker(mock_queue)

        # Should not raise
        tracker.record_scan(threat_detected=True)
        tracker.record_feature_used("cli_scan")

    def test_multiple_trackers_share_session_id(
        self, mock_queue: DualQueue
    ) -> None:
        """Multiple tracker instances share the same session ID."""
        SessionTracker.reset_session_id()

        tracker1 = SessionTracker(mock_queue)
        tracker2 = SessionTracker(mock_queue)

        assert tracker1.get_session_id() == tracker2.get_session_id()

    def test_closed_queue_graceful_handling(
        self, mock_queue: DualQueue
    ) -> None:
        """Tracker handles closed queue gracefully."""
        tracker = SessionTracker(mock_queue)
        mock_queue.close()

        # These should not raise
        session_num = tracker.get_session_number()
        assert session_num == 0

        result = tracker.track_activation("first_scan")
        # May return None due to closed queue

    def test_environment_detection(
        self, mock_queue: DualQueue
    ) -> None:
        """Environment detection works correctly."""
        SessionTracker.reset_session_id()
        tracker = SessionTracker(mock_queue)

        env = tracker._detect_environment()

        assert "is_ci" in env
        assert "is_interactive" in env
        assert "is_notebook" in env
        assert isinstance(env["is_ci"], bool)
        assert isinstance(env["is_interactive"], bool)
        assert isinstance(env["is_notebook"], bool)

    @patch.dict("os.environ", {"CI": "true"})
    def test_ci_environment_detection(
        self, mock_queue: DualQueue
    ) -> None:
        """CI environment is detected from environment variable."""
        tracker = SessionTracker(mock_queue)
        env = tracker._detect_environment()

        assert env["is_ci"] is True
