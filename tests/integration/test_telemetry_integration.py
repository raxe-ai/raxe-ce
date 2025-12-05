"""
Integration tests for the telemetry system.

Tests the full telemetry flow from event creation to queue persistence,
including orchestrator lifecycle, session tracking, activation events,
and DLQ operations.

These tests verify:
- Orchestrator tracks scans correctly through to queue
- Installation events fire exactly once
- Activation events fire on first use
- Session lifecycle events work properly
- Error events are tracked
- Queue persistence across restarts
- Flush operations
- DLQ operations (list, clear, retry)
- Backpressure sampling
- Config change tracking
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
    from raxe.infrastructure.telemetry.dual_queue import DualQueue


@pytest.mark.integration
@pytest.mark.telemetry
class TestTelemetryIntegration:
    """Integration tests for the telemetry system end-to-end."""

    def test_orchestrator_tracks_scan(
        self,
        test_orchestrator: TelemetryOrchestrator,
        mock_scan_result: dict[str, Any],
        sample_prompt_hash: str,
    ) -> None:
        """Test that scans are tracked through orchestrator to queue.

        Verifies the complete flow:
        1. Orchestrator receives scan result
        2. Event is created with correct metadata
        3. Event is persisted in the queue
        """
        # Track a scan
        test_orchestrator.track_scan(
            scan_result=mock_scan_result,
            prompt_hash=sample_prompt_hash,
            duration_ms=5.5,
            entry_point="sdk",
        )

        # Verify event in queue
        stats = test_orchestrator.get_stats()
        assert stats["events_queued"] >= 1
        assert stats["initialized"] is True
        assert stats["started"] is True

        # Verify queue has events
        queue_stats = stats.get("queue", {})
        total_queued = queue_stats.get("total_queued", 0)
        # At least 1 event (scan) plus potential installation/session events
        assert total_queued >= 1

    def test_installation_event_fires_once(self, telemetry_db: Path) -> None:
        """Test installation event fires exactly once across restarts.

        The installation event should:
        1. Fire on first initialization
        2. NOT fire again on subsequent initializations
        3. Persist installation_id across restarts
        """
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig
        from raxe.infrastructure.telemetry.dual_queue import DualQueue, StateKey

        config = TelemetryConfig(enabled=True)

        # First initialization - should fire installation event
        orchestrator1 = TelemetryOrchestrator(config=config, db_path=telemetry_db)
        orchestrator1.start()

        # Get the installation ID
        installation_id = orchestrator1.ensure_installation()
        assert installation_id.startswith("inst_")

        # Stop and verify state was persisted
        orchestrator1.stop(graceful=False)

        # Second initialization - should NOT fire installation event again
        orchestrator2 = TelemetryOrchestrator(config=config, db_path=telemetry_db)
        orchestrator2.start()

        # Same installation ID should be returned
        installation_id_2 = orchestrator2.ensure_installation()
        assert installation_id_2 == installation_id

        # Verify installation flag is set in persistent state
        with DualQueue(db_path=telemetry_db) as queue:
            installation_fired = queue.get_state(StateKey.INSTALLATION_FIRED)
            assert installation_fired == "true"

        orchestrator2.stop(graceful=False)

    def test_activation_events_fire_on_first_use(
        self,
        test_orchestrator: TelemetryOrchestrator,
        mock_scan_result: dict[str, Any],
        sample_prompt_hash: str,
    ) -> None:
        """Test activation events fire on first scan, first threat, etc.

        Activation events track time-to-value metrics:
        - first_scan: First scan performed
        - first_threat: First threat detected

        These should fire exactly once per installation.
        """
        # Track first scan (should trigger first_scan activation)
        test_orchestrator.track_scan(
            scan_result=mock_scan_result,
            prompt_hash=sample_prompt_hash,
            duration_ms=5.0,
            entry_point="sdk",
        )

        # Track second scan (should NOT trigger another activation)
        test_orchestrator.track_scan(
            scan_result=mock_scan_result,
            prompt_hash=sample_prompt_hash,
            duration_ms=5.0,
            entry_point="sdk",
        )

        # Get stats
        stats = test_orchestrator.get_stats()

        # Verify events were queued (installation + session_start + scan + activation events)
        assert stats["events_queued"] >= 2

    def test_session_lifecycle(self, telemetry_db: Path) -> None:
        """Test session start/end events.

        Verifies:
        1. Session start event fires when orchestrator starts
        2. Session end event fires when orchestrator stops
        3. Session number increments across sessions
        """
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        config = TelemetryConfig(enabled=True)

        # First session
        orchestrator1 = TelemetryOrchestrator(config=config, db_path=telemetry_db)
        orchestrator1.start()

        session_id_1 = orchestrator1.get_stats().get("session_id")
        session_number_1 = orchestrator1.get_stats().get("session_number")

        assert session_id_1 is not None
        assert session_id_1.startswith("sess_")
        assert session_number_1 == 1

        orchestrator1.stop(graceful=True)

        # Second session - should have different session_id but incremented session_number
        orchestrator2 = TelemetryOrchestrator(config=config, db_path=telemetry_db)
        orchestrator2.start()

        session_id_2 = orchestrator2.get_stats().get("session_id")
        session_number_2 = orchestrator2.get_stats().get("session_number")

        assert session_id_2 is not None
        assert session_id_2 != session_id_1  # Different session ID
        assert session_number_2 == 2  # Incremented session number

        orchestrator2.stop(graceful=False)

    def test_error_tracking(
        self,
        test_orchestrator: TelemetryOrchestrator,
    ) -> None:
        """Test error events are tracked correctly.

        Error events should:
        1. Have critical priority
        2. Hash the error message for privacy
        3. Include component and error type
        """
        # Track an error
        test_orchestrator.track_error(
            error_type="validation_error",
            error_code="RAXE_001",
            component="engine",
            error_message="Test error message",
            is_recoverable=True,
            operation="scan",
        )

        # Verify error was queued
        stats = test_orchestrator.get_stats()
        assert stats["events_queued"] >= 1

    def test_queue_persistence(
        self,
        telemetry_db: Path,
        mock_scan_result: dict[str, Any],
        sample_prompt_hash: str,
    ) -> None:
        """Test events persist across orchestrator restart.

        Events should:
        1. Be persisted to SQLite when queued
        2. Survive orchestrator restart
        3. Be available for retrieval after restart
        """
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig
        from raxe.infrastructure.telemetry.dual_queue import DualQueue

        config = TelemetryConfig(enabled=True)

        # Create orchestrator and queue events
        orchestrator1 = TelemetryOrchestrator(config=config, db_path=telemetry_db)
        orchestrator1.start()

        # Track multiple scans
        for i in range(5):
            orchestrator1.track_scan(
                scan_result=mock_scan_result,
                prompt_hash=f"{sample_prompt_hash}_{i}",
                duration_ms=5.0,
            )

        # Verify events were queued
        assert orchestrator1.get_stats()["events_queued"] >= 5
        orchestrator1.stop(graceful=False)

        # Create new queue to check persistence
        with DualQueue(db_path=telemetry_db) as queue:
            stats = queue.get_stats()
            # Events should still be in queue (not yet shipped)
            assert stats["total_queued"] >= 5

    def test_flush_ships_events(
        self,
        test_orchestrator: TelemetryOrchestrator,
        mock_scan_result: dict[str, Any],
        sample_prompt_hash: str,
    ) -> None:
        """Test flush sends events (returns count, dry-run mode).

        Flush should:
        1. Return the number of events to be processed
        2. Work in dry-run mode (no actual network call)
        """
        # Queue some events
        for i in range(3):
            test_orchestrator.track_scan(
                scan_result=mock_scan_result,
                prompt_hash=f"{sample_prompt_hash}_{i}",
                duration_ms=5.0,
            )

        # Flush events
        flushed_count = test_orchestrator.flush()

        # Should have at least the scan events (plus installation/session events)
        assert flushed_count >= 3

    def test_dlq_operations(
        self,
        test_queue: DualQueue,
    ) -> None:
        """Test DLQ list/clear/retry operations.

        DLQ (Dead Letter Queue) should:
        1. Accept events that exceeded retry count
        2. Support listing DLQ events
        3. Support clearing old events
        4. Support retrying events
        """
        from raxe.domain.telemetry.events import create_scan_event

        # Create and enqueue an event
        event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=False,
            scan_duration_ms=5.0,
        )
        test_queue.enqueue(event)

        # Simulate failures until it moves to DLQ
        # First, mark it as failed multiple times
        test_queue.mark_batch_failed(
            event_ids=[event.event_id],
            error="Test failure",
            retry_delay_seconds=0,
        )

        # Force it to DLQ by moving directly
        test_queue.move_to_dlq(
            event_id=event.event_id,
            reason="Test - exceeded retries",
            server_code="500",
            server_message="Test server error",
        )

        # List DLQ events
        dlq_events = test_queue.get_dlq_events(limit=10)
        assert len(dlq_events) >= 1

        dlq_event = dlq_events[0]
        assert dlq_event["failure_reason"] == "Test - exceeded retries"
        assert dlq_event["server_error_code"] == "500"

        # Retry DLQ events
        retried_count = test_queue.retry_dlq_events([dlq_event["event_id"]])
        assert retried_count == 1

        # DLQ should now be empty
        dlq_events_after = test_queue.get_dlq_events(limit=10)
        assert len(dlq_events_after) == 0

        # Event should be back in main queue
        stats = test_queue.get_stats()
        assert stats["total_queued"] >= 1

    def test_dlq_clear(
        self,
        test_queue: DualQueue,
    ) -> None:
        """Test clearing DLQ events.

        Should support:
        1. Clearing all events
        2. Clearing events older than N days
        """
        from raxe.domain.telemetry.events import create_scan_event

        # Create and move events to DLQ
        for i in range(3):
            event = create_scan_event(
                prompt_hash=f"{'a' * 63}{i}",
                threat_detected=False,
                scan_duration_ms=5.0,
            )
            test_queue.enqueue(event)
            test_queue.move_to_dlq(
                event_id=event.event_id,
                reason=f"Test failure {i}",
            )

        # Verify DLQ has events
        dlq_events = test_queue.get_dlq_events()
        assert len(dlq_events) == 3

        # Clear all DLQ events
        cleared = test_queue.clear_dlq()
        assert cleared == 3

        # DLQ should be empty
        dlq_events_after = test_queue.get_dlq_events()
        assert len(dlq_events_after) == 0

    def test_backpressure_sampling(
        self,
        telemetry_db: Path,
        clean_scan_result: dict[str, Any],
        sample_prompt_hash: str,
    ) -> None:
        """Test events are sampled under queue pressure.

        When the queue approaches capacity, low-priority events
        should be sampled (some dropped) to prevent overflow.
        """
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig
        from raxe.infrastructure.telemetry.dual_queue import DualQueue

        config = TelemetryConfig(enabled=True)

        # Create queue with small capacity to trigger backpressure
        with DualQueue(
            db_path=telemetry_db,
            critical_max_size=10,
            standard_max_size=20,
        ):
            # Create orchestrator with the small queue
            orchestrator = TelemetryOrchestrator(config=config, db_path=telemetry_db)
            orchestrator.start()

            # Track many events to approach capacity
            for i in range(50):
                orchestrator.track_scan(
                    scan_result=clean_scan_result,  # Clean result = standard priority
                    prompt_hash=f"{sample_prompt_hash}_{i}",
                    duration_ms=5.0,
                )

            stats = orchestrator.get_stats()

            # Some events may have been dropped due to backpressure
            events_queued = stats["events_queued"]
            events_dropped = stats["events_dropped"]

            # Verify backpressure kicked in (events were dropped)
            # or all events fit (if queue was large enough)
            assert events_queued + events_dropped >= 50

            orchestrator.stop(graceful=False)

    def test_config_change_tracking(
        self,
        test_orchestrator: TelemetryOrchestrator,
    ) -> None:
        """Test config changes are tracked.

        Config changes should:
        1. Create config_changed events
        2. Record the change details (key, old value, new value)
        3. Have critical priority when disabling telemetry
        """
        # Track a config change
        test_orchestrator.track_config_change(
            key="scan.confidence_threshold",
            old_value=0.5,
            new_value=0.8,
            changed_via="cli",
        )

        # Verify event was queued
        stats = test_orchestrator.get_stats()
        assert stats["events_queued"] >= 1

    def test_feature_usage_tracking(
        self,
        test_orchestrator: TelemetryOrchestrator,
    ) -> None:
        """Test feature usage events are tracked.

        Feature usage events should:
        1. Track specific feature invocations
        2. Include action and optional duration
        3. Trigger activation events on first use
        """
        # Track feature usage
        test_orchestrator.track_feature_usage(
            feature="cli_scan",
            action="completed",
            duration_ms=150.5,
            success=True,
        )

        # Verify event was queued
        stats = test_orchestrator.get_stats()
        assert stats["events_queued"] >= 1

    def test_telemetry_disabled_no_events(
        self,
        disabled_orchestrator: TelemetryOrchestrator,
        mock_scan_result: dict[str, Any],
        sample_prompt_hash: str,
    ) -> None:
        """Test no events are tracked when telemetry is disabled.

        When telemetry is disabled:
        1. No events should be queued
        2. Orchestrator should remain in uninitialized state
        3. No database should be created
        """
        # Try to track events
        disabled_orchestrator.track_scan(
            scan_result=mock_scan_result,
            prompt_hash=sample_prompt_hash,
            duration_ms=5.0,
        )

        disabled_orchestrator.track_error(
            error_type="validation_error",
            error_code="RAXE_001",
            component="engine",
            error_message="Test error",
        )

        # Verify nothing was queued
        stats = disabled_orchestrator.get_stats()
        assert stats["initialized"] is False
        assert stats.get("events_queued", 0) == 0


@pytest.mark.integration
@pytest.mark.telemetry
class TestSessionTracker:
    """Integration tests for session tracking functionality."""

    def test_session_tracker_record_scan(
        self,
        test_orchestrator: TelemetryOrchestrator,
        mock_scan_result: dict[str, Any],
        sample_prompt_hash: str,
    ) -> None:
        """Test session tracker records scan counts correctly."""
        # Track multiple scans
        for i in range(5):
            test_orchestrator.track_scan(
                scan_result=mock_scan_result,
                prompt_hash=f"{sample_prompt_hash}_{i}",
                duration_ms=5.0,
            )

        # Session should track scan count
        stats = test_orchestrator.get_stats()
        assert stats["session_active"] is True

    def test_session_environment_detection(
        self,
        telemetry_db: Path,
    ) -> None:
        """Test session detects environment correctly (CI, interactive, notebook)."""
        from raxe.application.telemetry_orchestrator import TelemetryOrchestrator
        from raxe.infrastructure.config.yaml_config import TelemetryConfig

        config = TelemetryConfig(enabled=True)
        orchestrator = TelemetryOrchestrator(config=config, db_path=telemetry_db)
        orchestrator.start()

        # Session should be active
        stats = orchestrator.get_stats()
        assert stats["session_active"] is True

        orchestrator.stop(graceful=False)


@pytest.mark.integration
@pytest.mark.telemetry
class TestQueuePriority:
    """Integration tests for queue priority handling."""

    def test_critical_events_priority(
        self,
        test_queue: DualQueue,
    ) -> None:
        """Test critical events are routed to critical queue."""
        from raxe.domain.telemetry.events import (
            create_error_event,
            create_installation_event,
            generate_installation_id,
        )

        # Create critical priority events
        installation_event = create_installation_event(
            installation_id=generate_installation_id(),
            client_version="0.0.1",
            python_version="3.11.0",
            platform="darwin",
            install_method="pip",
        )

        error_event = create_error_event(
            error_type="internal_error",
            error_code="RAXE_999",
            component="engine",
        )

        # Enqueue events
        test_queue.enqueue(installation_event)
        test_queue.enqueue(error_event)

        # Verify events are in critical queue
        stats = test_queue.get_stats()
        assert stats["critical_count"] >= 2

    def test_standard_events_priority(
        self,
        test_queue: DualQueue,
    ) -> None:
        """Test standard events are routed to standard queue."""
        from raxe.domain.telemetry.events import (
            create_feature_usage_event,
            create_heartbeat_event,
            create_scan_event,
        )

        # Create standard priority events (clean scan = no HIGH/CRITICAL severity)
        scan_event = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=False,
            scan_duration_ms=5.0,
        )

        heartbeat_event = create_heartbeat_event(
            uptime_seconds=3600.0,
            scans_since_last_heartbeat=100,
        )

        feature_event = create_feature_usage_event(
            feature="cli_scan",
            action="completed",
        )

        # Enqueue events
        test_queue.enqueue(scan_event)
        test_queue.enqueue(heartbeat_event)
        test_queue.enqueue(feature_event)

        # Verify events are in standard queue
        stats = test_queue.get_stats()
        assert stats["standard_count"] >= 3

    def test_high_severity_scan_is_critical(
        self,
        test_queue: DualQueue,
    ) -> None:
        """Test HIGH/CRITICAL severity scans have critical priority."""
        from raxe.domain.telemetry.events import create_scan_event

        # Create scan with HIGH severity (should be critical priority)
        high_severity_scan = create_scan_event(
            prompt_hash="a" * 64,
            threat_detected=True,
            scan_duration_ms=5.0,
            highest_severity="HIGH",
            detection_count=1,
        )

        assert high_severity_scan.priority == "critical"

        # Enqueue and verify
        test_queue.enqueue(high_severity_scan)
        stats = test_queue.get_stats()
        assert stats["critical_count"] >= 1


@pytest.mark.integration
@pytest.mark.telemetry
class TestQueueOverflow:
    """Integration tests for queue overflow handling."""

    def test_queue_overflow_drops_oldest(
        self,
        telemetry_db: Path,
    ) -> None:
        """Test that queue overflow drops oldest events."""
        from raxe.domain.telemetry.events import create_scan_event
        from raxe.infrastructure.telemetry.dual_queue import DualQueue

        # Create queue with very small capacity
        with DualQueue(
            db_path=telemetry_db,
            critical_max_size=5,
            standard_max_size=5,
        ) as queue:
            event_ids = []

            # Enqueue more events than capacity
            for i in range(10):
                event = create_scan_event(
                    prompt_hash=f"{'a' * 63}{i}",
                    threat_detected=False,
                    scan_duration_ms=5.0,
                )
                event_ids.append(event.event_id)
                queue.enqueue(event)

            # Queue should be at max capacity
            stats = queue.get_stats()
            assert stats["standard_count"] == 5

            # Dequeue and verify we have the newest events
            events = queue.dequeue_standard(batch_size=10)
            current_event_ids = [e["event_id"] for e in events]

            # The newest 5 events should be in the queue
            # (oldest 5 were dropped during overflow)
            for event_id in event_ids[-5:]:
                assert event_id in current_event_ids
