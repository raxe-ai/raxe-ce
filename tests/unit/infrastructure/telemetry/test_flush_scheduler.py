"""Unit tests for flush_scheduler module.

Tests for:
- FlushConfig creation and factory methods
- FlushScheduler lifecycle (start/stop)
- Timer-based flushing (critical and standard)
- Graceful shutdown
- Statistics tracking
- Thread safety
"""

import threading
import time
from typing import Any

import pytest

from raxe.infrastructure.telemetry.flush_scheduler import (
    FlushConfig,
    FlushScheduler,
    FlushStats,
)

# =============================================================================
# Test Fixtures
# =============================================================================


class MockDualQueue:
    """Mock dual queue for testing."""

    def __init__(self) -> None:
        """Initialize mock queue with separate critical and standard queues."""
        self.critical_queue: list[dict[str, Any]] = []
        self.standard_queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def add_critical_event(self, event: dict[str, Any]) -> None:
        """Add event to critical queue."""
        with self._lock:
            self.critical_queue.append(event)

    def add_standard_event(self, event: dict[str, Any]) -> None:
        """Add event to standard queue."""
        with self._lock:
            self.standard_queue.append(event)

    def dequeue_critical_batch(self, batch_size: int) -> list[dict[str, Any]]:
        """Dequeue batch from critical queue."""
        with self._lock:
            batch = self.critical_queue[:batch_size]
            self.critical_queue = self.critical_queue[batch_size:]
            return batch

    def dequeue_standard_batch(self, batch_size: int) -> list[dict[str, Any]]:
        """Dequeue batch from standard queue."""
        with self._lock:
            batch = self.standard_queue[:batch_size]
            self.standard_queue = self.standard_queue[batch_size:]
            return batch

    def get_critical_count(self) -> int:
        """Get critical queue depth."""
        return len(self.critical_queue)

    def get_standard_count(self) -> int:
        """Get standard queue depth."""
        return len(self.standard_queue)


class MockShipper:
    """Mock shipper for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        """Initialize mock shipper.

        Args:
            should_fail: If True, ship_batch will return failure
        """
        self.should_fail = should_fail
        self.shipped_batches: list[list[dict[str, Any]]] = []
        self.call_count = 0
        self._lock = threading.Lock()

    def ship_batch(self, events: list[dict[str, Any]], no_retry: bool = False) -> dict[str, Any]:
        """Mock ship batch.

        Args:
            events: List of events to ship.
            no_retry: If True, skip retries (ignored in mock but matches real signature).
        """
        with self._lock:
            self.call_count += 1
            self.shipped_batches.append(events)

        if self.should_fail:
            return {
                "success": False,
                "error": "Mock error",
            }
        return {
            "success": True,
            "events_accepted": len(events),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get mock shipper stats."""
        return {
            "total_batches": len(self.shipped_batches),
            "total_events_shipped": sum(len(b) for b in self.shipped_batches),
        }


@pytest.fixture
def mock_queue() -> MockDualQueue:
    """Create mock dual queue."""
    return MockDualQueue()


@pytest.fixture
def mock_shipper() -> MockShipper:
    """Create mock shipper."""
    return MockShipper()


@pytest.fixture
def test_config() -> FlushConfig:
    """Create test configuration with short intervals."""
    return FlushConfig(
        critical_interval_seconds=0.1,  # 100ms for fast tests
        standard_interval_seconds=0.2,  # 200ms for fast tests
        max_batch_size=10,
        shutdown_timeout_seconds=1.0,
    )


# =============================================================================
# FlushConfig Tests
# =============================================================================


class TestFlushConfig:
    """Tests for FlushConfig class."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = FlushConfig()

        assert config.critical_interval_seconds == 5.0
        assert config.standard_interval_seconds == 300.0
        assert config.max_batch_size == 100
        assert config.shutdown_timeout_seconds == 10.0

    def test_for_production(self) -> None:
        """Test production configuration factory."""
        config = FlushConfig.for_production()

        assert config.critical_interval_seconds == 5.0
        assert config.standard_interval_seconds == 300.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = FlushConfig(
            critical_interval_seconds=2.0,
            standard_interval_seconds=60.0,
            max_batch_size=50,
            shutdown_timeout_seconds=5.0,
        )

        assert config.critical_interval_seconds == 2.0
        assert config.standard_interval_seconds == 60.0
        assert config.max_batch_size == 50
        assert config.shutdown_timeout_seconds == 5.0


# =============================================================================
# FlushStats Tests
# =============================================================================


class TestFlushStats:
    """Tests for FlushStats dataclass."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = FlushStats()

        assert stats.critical_flushes == 0
        assert stats.standard_flushes == 0
        assert stats.events_shipped == 0
        assert stats.errors == 0
        assert stats.last_critical_flush is None
        assert stats.last_standard_flush is None


# =============================================================================
# FlushScheduler Tests
# =============================================================================


class TestFlushScheduler:
    """Tests for FlushScheduler class."""

    def test_init_with_mock_queue(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test scheduler initialization with mock queue."""
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        assert scheduler.is_running() is False

    def test_init_with_custom_shipper(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper
    ) -> None:
        """Test scheduler initialization with custom shipper."""
        config = FlushConfig()
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=config)

        assert scheduler._shipper == mock_shipper

    def test_start_stop(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test starting and stopping scheduler."""
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        scheduler.start()
        assert scheduler.is_running() is True

        scheduler.stop(graceful=False)
        assert scheduler.is_running() is False

    def test_start_idempotent(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test that multiple start calls are safe."""
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        scheduler.start()
        scheduler.start()  # Should not raise or create duplicate timers

        assert scheduler.is_running() is True
        scheduler.stop(graceful=False)

    def test_stop_idempotent(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test that multiple stop calls are safe."""
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        scheduler.start()
        scheduler.stop(graceful=False)
        scheduler.stop(graceful=False)  # Should not raise

        assert scheduler.is_running() is False

    def test_flush_critical_empty_queue(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test flushing empty critical queue."""
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        count = scheduler.flush_critical()

        assert count == 0

    def test_flush_critical_with_events(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test flushing critical queue with events."""
        mock_queue.add_critical_event({"event_id": "critical1"})
        mock_queue.add_critical_event({"event_id": "critical2"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)
        count = scheduler.flush_critical()

        assert count == 2
        stats = scheduler.get_stats()
        assert stats["critical_flushes"] == 1
        assert stats["events_shipped"] == 2

    def test_flush_standard_empty_queue(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test flushing empty standard queue."""
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        count = scheduler.flush_standard()

        assert count == 0

    def test_flush_standard_with_events(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test flushing standard queue with events."""
        mock_queue.add_standard_event({"event_id": "standard1"})
        mock_queue.add_standard_event({"event_id": "standard2"})
        mock_queue.add_standard_event({"event_id": "standard3"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)
        count = scheduler.flush_standard()

        assert count == 3
        stats = scheduler.get_stats()
        assert stats["standard_flushes"] == 1
        assert stats["events_shipped"] == 3

    def test_flush_all(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test flushing both queues."""
        mock_queue.add_critical_event({"event_id": "critical1"})
        mock_queue.add_standard_event({"event_id": "standard1"})
        mock_queue.add_standard_event({"event_id": "standard2"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)
        total = scheduler.flush_all()

        assert total == 3
        stats = scheduler.get_stats()
        assert stats["critical_flushes"] == 1
        assert stats["standard_flushes"] == 1

    def test_flush_respects_batch_size(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test that flush respects max batch size."""
        # Add more events than batch size
        for i in range(15):
            mock_queue.add_critical_event({"event_id": f"event_{i}"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        # Batch size is 10, so first flush should get 10
        count = scheduler.flush_critical()
        assert count == 10

        # Second flush should get remaining 5
        count = scheduler.flush_critical()
        assert count == 5

    def test_timer_based_flush_critical(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test timer-based critical queue flushing."""
        mock_queue.add_critical_event({"event_id": "critical1"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)
        scheduler.start()

        # Wait for timer to fire (100ms interval + some margin)
        time.sleep(0.25)

        scheduler.stop(graceful=False)

        # Should have flushed at least once
        stats = scheduler.get_stats()
        assert stats["critical_flushes"] >= 1

    def test_timer_based_flush_standard(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test timer-based standard queue flushing."""
        mock_queue.add_standard_event({"event_id": "standard1"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)
        scheduler.start()

        # Wait for timer to fire (200ms interval + some margin)
        time.sleep(0.35)

        scheduler.stop(graceful=False)

        # Should have flushed at least once
        stats = scheduler.get_stats()
        assert stats["standard_flushes"] >= 1

    def test_graceful_shutdown_flushes_queues(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper
    ) -> None:
        """Test that graceful shutdown flushes remaining events."""
        mock_queue.add_critical_event({"event_id": "critical1"})
        mock_queue.add_standard_event({"event_id": "standard1"})

        # Use long intervals so timer doesn't fire during test
        config = FlushConfig(
            critical_interval_seconds=100.0,
            standard_interval_seconds=100.0,
            max_batch_size=10,
            shutdown_timeout_seconds=5.0,
        )

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=config)
        scheduler.start()

        # Stop gracefully - should flush pending events
        scheduler.stop(graceful=True)

        # Both queues should be empty
        assert mock_queue.get_critical_count() == 0
        assert mock_queue.get_standard_count() == 0

    def test_non_graceful_shutdown_does_not_flush(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper
    ) -> None:
        """Test that non-graceful shutdown does not flush."""
        mock_queue.add_critical_event({"event_id": "critical1"})
        mock_queue.add_standard_event({"event_id": "standard1"})

        # Use long intervals so timer doesn't fire during test
        config = FlushConfig(
            critical_interval_seconds=100.0,
            standard_interval_seconds=100.0,
            max_batch_size=10,
            shutdown_timeout_seconds=5.0,
        )

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=config)
        scheduler.start()

        # Stop non-gracefully - should NOT flush pending events
        scheduler.stop(graceful=False)

        # Queues should still have events
        assert mock_queue.get_critical_count() == 1
        assert mock_queue.get_standard_count() == 1

    def test_get_stats(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test statistics retrieval."""
        mock_queue.add_critical_event({"event_id": "critical1"})
        mock_queue.add_standard_event({"event_id": "standard1"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)
        scheduler.flush_critical()
        scheduler.flush_standard()

        stats = scheduler.get_stats()

        assert "is_running" in stats
        assert "critical_flushes" in stats
        assert "standard_flushes" in stats
        assert "events_shipped" in stats
        assert "errors" in stats
        assert "last_critical_flush" in stats
        assert "last_standard_flush" in stats
        assert "config" in stats
        assert "queue_depths" in stats

        assert stats["critical_flushes"] == 1
        assert stats["standard_flushes"] == 1
        assert stats["events_shipped"] == 2

    def test_get_stats_includes_timestamps(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test that stats include flush timestamps."""
        mock_queue.add_critical_event({"event_id": "critical1"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        # Before flush, timestamps should be None
        stats = scheduler.get_stats()
        assert stats["last_critical_flush"] is None

        # After flush, timestamp should be set
        scheduler.flush_critical()
        stats = scheduler.get_stats()
        assert stats["last_critical_flush"] is not None

    def test_shipper_error_increments_error_count(
        self, mock_queue: MockDualQueue
    ) -> None:
        """Test that shipper errors are tracked."""
        mock_queue.add_critical_event({"event_id": "critical1"})

        failing_shipper = MockShipper(should_fail=True)
        config = FlushConfig()
        scheduler = FlushScheduler(
            queue=mock_queue, shipper=failing_shipper, config=config
        )

        count = scheduler.flush_critical()

        assert count == 0  # No events shipped due to failure
        stats = scheduler.get_stats()
        assert stats["errors"] == 1

    def test_get_shipper(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper, test_config: FlushConfig
    ) -> None:
        """Test getting shipper instance."""
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=test_config)

        shipper = scheduler.get_shipper()

        assert shipper == mock_shipper

    def test_thread_safety(self, mock_queue: MockDualQueue, mock_shipper: MockShipper) -> None:
        """Test thread-safe operations."""
        config = FlushConfig(
            critical_interval_seconds=0.05,
            standard_interval_seconds=0.1,
            max_batch_size=5,
        )

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=config)
        scheduler.start()

        # Add events from multiple threads while scheduler is running
        def add_events() -> None:
            for i in range(20):
                mock_queue.add_critical_event({"event_id": f"critical_{i}"})
                mock_queue.add_standard_event({"event_id": f"standard_{i}"})
                time.sleep(0.01)

        threads = [threading.Thread(target=add_events) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Let scheduler process remaining events
        time.sleep(0.3)
        scheduler.stop(graceful=True)

        # Should have processed all events without errors
        stats = scheduler.get_stats()
        assert stats["errors"] == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestFlushSchedulerIntegration:
    """Integration tests for FlushScheduler with real components."""

    def test_full_lifecycle(self, mock_queue: MockDualQueue, mock_shipper: MockShipper) -> None:
        """Test full scheduler lifecycle with events."""
        config = FlushConfig(
            critical_interval_seconds=0.1,
            standard_interval_seconds=0.2,
            max_batch_size=50,
            shutdown_timeout_seconds=5.0,
        )

        # Add events before starting
        for i in range(5):
            mock_queue.add_critical_event({"event_id": f"critical_{i}"})
        for i in range(10):
            mock_queue.add_standard_event({"event_id": f"standard_{i}"})

        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=config)

        # Start scheduler
        scheduler.start()
        assert scheduler.is_running()

        # Wait for timers to fire
        time.sleep(0.5)

        # Stop gracefully
        scheduler.stop(graceful=True)
        assert not scheduler.is_running()

        # Verify all events were shipped
        stats = scheduler.get_stats()
        assert stats["events_shipped"] >= 15
        assert stats["errors"] == 0

        # Queues should be empty
        assert mock_queue.get_critical_count() == 0
        assert mock_queue.get_standard_count() == 0

    def test_with_mock_shipper_inspection(
        self, mock_queue: MockDualQueue, mock_shipper: MockShipper
    ) -> None:
        """Test inspecting MockShipper after flushing."""
        config = FlushConfig(
            critical_interval_seconds=999999.0,  # Effectively disabled
            standard_interval_seconds=999999.0,
            max_batch_size=100,
            shutdown_timeout_seconds=5.0,
        )
        scheduler = FlushScheduler(queue=mock_queue, shipper=mock_shipper, config=config)

        # Add events
        mock_queue.add_critical_event({"event_id": "c1", "type": "threat"})
        mock_queue.add_critical_event({"event_id": "c2", "type": "threat"})
        mock_queue.add_standard_event({"event_id": "s1", "type": "clean"})

        # Manually flush
        scheduler.flush_critical()
        scheduler.flush_standard()

        # Get shipper and inspect
        shipper = scheduler.get_shipper()
        assert shipper == mock_shipper

        stats = shipper.get_stats()
        assert stats["total_batches"] == 2
        assert stats["total_events_shipped"] == 3

        # Verify batch contents
        assert len(mock_shipper.shipped_batches) == 2
        assert len(mock_shipper.shipped_batches[0]) == 2  # Critical events
        assert len(mock_shipper.shipped_batches[1]) == 1  # Standard events
