"""Tests for Agent Heartbeat Scheduler.

TDD: These tests define expected behavior for the heartbeat system.
Implementation should make these tests pass.

The HeartbeatScheduler is responsible for:
1. Sending periodic heartbeat events to track agent health
2. Configurable interval (per customer settings)
3. Tracking uptime and scan counts since last heartbeat
4. Non-blocking operation
"""

import time
from unittest.mock import MagicMock


class TestHeartbeatSchedulerInit:
    """Tests for HeartbeatScheduler initialization."""

    def test_scheduler_initializes_with_defaults(self):
        """Scheduler should initialize with sensible defaults."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        assert scheduler is not None
        assert scheduler.interval_seconds == 60  # Default 1 minute

    def test_scheduler_accepts_custom_interval(self):
        """Scheduler should accept custom heartbeat interval."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler(interval_seconds=30)
        assert scheduler.interval_seconds == 30

    def test_scheduler_starts_not_running(self):
        """Scheduler should not be running until explicitly started."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        assert scheduler.is_running is False


class TestHeartbeatSchedulerLifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_begins_heartbeat_loop(self):
        """Start should begin the heartbeat scheduling."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler(interval_seconds=60)

        scheduler.start()
        try:
            assert scheduler.is_running is True
        finally:
            scheduler.stop()

    def test_stop_halts_heartbeat_loop(self):
        """Stop should halt the heartbeat scheduling."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler(interval_seconds=60)

        scheduler.start()
        scheduler.stop()

        assert scheduler.is_running is False

    def test_double_start_is_safe(self):
        """Starting an already running scheduler should be a no-op."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler(interval_seconds=60)

        scheduler.start()
        scheduler.start()  # Should not raise
        try:
            assert scheduler.is_running is True
        finally:
            scheduler.stop()

    def test_double_stop_is_safe(self):
        """Stopping an already stopped scheduler should be a no-op."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler(interval_seconds=60)

        scheduler.start()
        scheduler.stop()
        scheduler.stop()  # Should not raise

        assert scheduler.is_running is False


class TestHeartbeatSchedulerTracking:
    """Tests for scan/threat counting."""

    def test_record_scan_increments_counter(self):
        """Recording a scan should increment scan counter."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        assert scheduler.scans_since_last_heartbeat == 0

        scheduler.record_scan()
        assert scheduler.scans_since_last_heartbeat == 1

        scheduler.record_scan()
        assert scheduler.scans_since_last_heartbeat == 2

    def test_record_threat_increments_counter(self):
        """Recording a threat should increment threat counter."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        assert scheduler.threats_since_last_heartbeat == 0

        scheduler.record_threat()
        assert scheduler.threats_since_last_heartbeat == 1

    def test_counters_reset_after_heartbeat(self):
        """Counters should reset after heartbeat is sent."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler()

        scheduler.record_scan()
        scheduler.record_scan()
        scheduler.record_threat()

        assert scheduler.scans_since_last_heartbeat == 2
        assert scheduler.threats_since_last_heartbeat == 1

        # Simulate heartbeat send
        scheduler._reset_counters()

        assert scheduler.scans_since_last_heartbeat == 0
        assert scheduler.threats_since_last_heartbeat == 0


class TestHeartbeatSchedulerMSSPContext:
    """Tests for MSSP context in heartbeats."""

    def test_scheduler_accepts_mssp_context(self):
        """Scheduler should accept MSSP context for heartbeat events."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler(
            mssp_id="mssp_test",
            customer_id="cust_test",
            agent_id="agent_test",
        )

        assert scheduler.mssp_id == "mssp_test"
        assert scheduler.customer_id == "cust_test"
        assert scheduler.agent_id == "agent_test"

    def test_heartbeat_includes_mssp_context(self):
        """Heartbeat event should include MSSP context when configured."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler(
            mssp_id="mssp_test",
            customer_id="cust_test",
            agent_id="agent_test",
        )

        # Mock the orchestrator
        mock_orchestrator = MagicMock()
        scheduler._orchestrator = mock_orchestrator

        # Trigger a heartbeat
        scheduler._send_heartbeat()

        # Verify heartbeat was called with MSSP context
        assert mock_orchestrator.track_heartbeat.called
        call_kwargs = mock_orchestrator.track_heartbeat.call_args.kwargs
        assert call_kwargs.get("mssp_id") == "mssp_test"
        assert call_kwargs.get("customer_id") == "cust_test"
        assert call_kwargs.get("agent_id") == "agent_test"


class TestHeartbeatSchedulerUptimeTracking:
    """Tests for uptime tracking."""

    def test_uptime_tracked_from_start(self):
        """Uptime should be tracked from when scheduler started."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler()

        scheduler.start()
        time.sleep(0.1)  # Small delay

        uptime = scheduler.uptime_seconds
        assert uptime >= 0.1
        assert uptime < 1.0  # Should not be more than a second

        scheduler.stop()

    def test_uptime_zero_before_start(self):
        """Uptime should be zero before scheduler is started."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        assert scheduler.uptime_seconds == 0.0


class TestHeartbeatSchedulerIntegration:
    """Integration tests for heartbeat sending."""

    def test_heartbeat_sent_on_interval(self):
        """Heartbeat should be sent at configured interval."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        # Use very short interval for testing
        scheduler = HeartbeatScheduler(interval_seconds=0.1)

        mock_orchestrator = MagicMock()
        scheduler._orchestrator = mock_orchestrator

        scheduler.start()
        time.sleep(0.25)  # Wait for at least 2 heartbeats
        scheduler.stop()

        # Should have sent at least 2 heartbeats
        assert mock_orchestrator.track_heartbeat.call_count >= 2

    def test_heartbeat_includes_scan_count(self):
        """Heartbeat should include scan count since last heartbeat."""
        from raxe.application.heartbeat_scheduler import HeartbeatScheduler

        scheduler = HeartbeatScheduler()

        scheduler.record_scan()
        scheduler.record_scan()
        scheduler.record_scan()

        mock_orchestrator = MagicMock()
        scheduler._orchestrator = mock_orchestrator

        scheduler._send_heartbeat()

        call_kwargs = mock_orchestrator.track_heartbeat.call_args.kwargs
        assert call_kwargs.get("scans_since_last_heartbeat") == 3
