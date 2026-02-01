"""Tests for SIEM event dispatcher."""

import threading
import time
from typing import Any

import pytest

from raxe.domain.siem.config import SIEMConfig, SIEMType
from raxe.infrastructure.siem.base import BaseSIEMAdapter, SIEMDeliveryResult
from raxe.infrastructure.siem.dispatcher import (
    DispatcherStats,
    SIEMDispatcher,
    SIEMDispatcherConfig,
)


class MockSIEMAdapter(BaseSIEMAdapter):
    """Mock SIEM adapter for testing."""

    def __init__(
        self,
        config: SIEMConfig,
        adapter_name: str = "mock",
        fail: bool = False,
    ):
        super().__init__(config)
        self._name = adapter_name
        self._fail = fail
        self.events_received: list[dict] = []
        self.send_calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return f"Mock SIEM ({self._name})"

    def transform_event(self, event: dict[str, Any]) -> dict[str, Any]:
        return {"transformed": True, **event}

    def send_event(self, event: dict[str, Any]) -> SIEMDeliveryResult:
        self.send_calls += 1
        self.events_received.append(event)
        if self._fail:
            return SIEMDeliveryResult(success=False, error_message="Mock failure")
        return SIEMDeliveryResult(success=True, events_accepted=1)

    def send_batch(self, events: list[dict[str, Any]]) -> SIEMDeliveryResult:
        self.send_calls += 1
        self.events_received.extend(events)
        if self._fail:
            return SIEMDeliveryResult(success=False, error_message="Mock failure")
        return SIEMDeliveryResult(success=True, events_accepted=len(events))

    def health_check(self) -> bool:
        return not self._fail


@pytest.fixture
def mock_config() -> SIEMConfig:
    """Create mock SIEM configuration."""
    return SIEMConfig(
        siem_type=SIEMType.SPLUNK,
        endpoint_url="https://mock.example.com/events",
        auth_token="test-token",
    )


@pytest.fixture
def sample_event() -> dict[str, Any]:
    """Create sample event."""
    return {
        "event_id": "evt_test123",
        "event_type": "scan",
        "timestamp": "2024-01-15T10:30:00Z",
        "payload": {
            "threat_detected": True,
            "customer_id": "cust_123",
            "mssp_id": "mssp_test",
        },
    }


class TestSIEMDispatcherConfig:
    """Tests for dispatcher configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SIEMDispatcherConfig()

        assert config.batch_size == 100
        assert config.flush_interval_seconds == 10.0
        assert config.max_queue_size == 10000
        assert config.worker_threads == 2

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SIEMDispatcherConfig(
            batch_size=50,
            flush_interval_seconds=5.0,
            max_queue_size=5000,
            worker_threads=4,
        )

        assert config.batch_size == 50
        assert config.flush_interval_seconds == 5.0

    def test_batch_size_validation(self):
        """Test batch_size bounds."""
        with pytest.raises(ValueError, match="batch_size"):
            SIEMDispatcherConfig(batch_size=0)

        with pytest.raises(ValueError, match="batch_size"):
            SIEMDispatcherConfig(batch_size=1001)

    def test_flush_interval_validation(self):
        """Test flush_interval_seconds bounds."""
        with pytest.raises(ValueError, match="flush_interval_seconds"):
            SIEMDispatcherConfig(flush_interval_seconds=0.05)

    def test_max_queue_size_validation(self):
        """Test max_queue_size bounds."""
        with pytest.raises(ValueError, match="max_queue_size"):
            SIEMDispatcherConfig(max_queue_size=50)

    def test_worker_threads_validation(self):
        """Test worker_threads bounds."""
        with pytest.raises(ValueError, match="worker_threads"):
            SIEMDispatcherConfig(worker_threads=0)

        with pytest.raises(ValueError, match="worker_threads"):
            SIEMDispatcherConfig(worker_threads=11)


class TestDispatcherStats:
    """Tests for dispatcher statistics."""

    def test_default_stats(self):
        """Test default statistics values."""
        stats = DispatcherStats()

        assert stats.events_queued == 0
        assert stats.events_delivered == 0
        assert stats.events_failed == 0
        assert stats.events_dropped == 0
        assert stats.batches_sent == 0
        assert stats.adapters_registered == 0

    def test_to_dict(self):
        """Test statistics to dictionary conversion."""
        stats = DispatcherStats(
            events_queued=100,
            events_delivered=95,
            events_failed=5,
        )
        data = stats.to_dict()

        assert data["events_queued"] == 100
        assert data["events_delivered"] == 95
        assert data["events_failed"] == 5


class TestSIEMDispatcher:
    """Tests for SIEM dispatcher."""

    def test_dispatcher_initialization(self):
        """Test dispatcher initializes correctly."""
        dispatcher = SIEMDispatcher()

        assert dispatcher.is_running is False
        assert dispatcher.queue_size == 0
        assert dispatcher.stats["adapters_registered"] == 0

    def test_register_adapter_global(self, mock_config: SIEMConfig):
        """Test registering global adapter."""
        dispatcher = SIEMDispatcher()
        adapter = MockSIEMAdapter(mock_config, "global")

        dispatcher.register_adapter(adapter)

        assert dispatcher.stats["adapters_registered"] == 1
        adapters = dispatcher.get_registered_adapters()
        assert "global" in adapters[None]

    def test_register_adapter_per_customer(self, mock_config: SIEMConfig):
        """Test registering customer-specific adapter."""
        dispatcher = SIEMDispatcher()
        adapter = MockSIEMAdapter(mock_config, "customer_adapter")

        dispatcher.register_adapter(adapter, customer_id="cust_123")

        adapters = dispatcher.get_registered_adapters()
        assert "cust_123" in adapters
        assert "customer_adapter" in adapters["cust_123"]

    def test_unregister_adapter(self, mock_config: SIEMConfig):
        """Test unregistering adapter."""
        dispatcher = SIEMDispatcher()
        adapter = MockSIEMAdapter(mock_config, "to_remove")

        dispatcher.register_adapter(adapter)
        assert dispatcher.stats["adapters_registered"] == 1

        result = dispatcher.unregister_adapter("to_remove")

        assert result is True
        assert dispatcher.stats["adapters_registered"] == 0

    def test_unregister_nonexistent_adapter(self):
        """Test unregistering adapter that doesn't exist."""
        dispatcher = SIEMDispatcher()
        result = dispatcher.unregister_adapter("nonexistent")
        assert result is False

    def test_dispatch_queues_event(self, mock_config: SIEMConfig, sample_event: dict):
        """Test that dispatch queues events."""
        dispatcher = SIEMDispatcher()

        result = dispatcher.dispatch(sample_event)

        assert result is True
        assert dispatcher.queue_size == 1
        assert dispatcher.stats["events_queued"] == 1

    def test_dispatch_full_queue(self, sample_event: dict):
        """Test dispatch when queue is full."""
        config = SIEMDispatcherConfig(max_queue_size=100)
        dispatcher = SIEMDispatcher(config)

        # Fill queue
        for _ in range(100):
            dispatcher.dispatch(sample_event)

        # Next dispatch should fail
        result = dispatcher.dispatch(sample_event)
        assert result is False
        assert dispatcher.stats["events_dropped"] == 1

    def test_dispatch_sync(self, mock_config: SIEMConfig, sample_event: dict):
        """Test synchronous dispatch."""
        dispatcher = SIEMDispatcher()
        adapter = MockSIEMAdapter(mock_config, "sync_test")
        dispatcher.register_adapter(adapter)

        results = dispatcher.dispatch_sync(sample_event)

        assert "sync_test" in results
        assert results["sync_test"].success is True
        assert adapter.send_calls == 1

    def test_dispatch_sync_with_failure(self, mock_config: SIEMConfig, sample_event: dict):
        """Test synchronous dispatch with adapter failure."""
        dispatcher = SIEMDispatcher()
        adapter = MockSIEMAdapter(mock_config, "failing", fail=True)
        dispatcher.register_adapter(adapter)

        results = dispatcher.dispatch_sync(sample_event)

        assert results["failing"].success is False

    def test_per_customer_routing(self, mock_config: SIEMConfig, sample_event: dict):
        """Test events are routed to correct customer adapter."""
        dispatcher = SIEMDispatcher()

        # Register adapters for different customers
        adapter_123 = MockSIEMAdapter(mock_config, "adapter_123")
        adapter_456 = MockSIEMAdapter(mock_config, "adapter_456")

        dispatcher.register_adapter(adapter_123, customer_id="cust_123")
        dispatcher.register_adapter(adapter_456, customer_id="cust_456")

        # Event for cust_123
        event_123 = {
            **sample_event,
            "payload": {**sample_event["payload"], "customer_id": "cust_123"},
        }

        results = dispatcher.dispatch_sync(event_123)

        # Only adapter_123 should receive the event
        assert "adapter_123" in results
        assert "adapter_456" not in results
        assert adapter_123.send_calls == 1
        assert adapter_456.send_calls == 0

    def test_global_adapter_receives_all(self, mock_config: SIEMConfig, sample_event: dict):
        """Test global adapter receives all events."""
        dispatcher = SIEMDispatcher()

        global_adapter = MockSIEMAdapter(mock_config, "global")
        customer_adapter = MockSIEMAdapter(mock_config, "customer")

        dispatcher.register_adapter(global_adapter)  # Global
        dispatcher.register_adapter(customer_adapter, customer_id="cust_123")

        results = dispatcher.dispatch_sync(sample_event)

        # Both should receive the event
        assert "global" in results
        assert "customer" in results
        assert global_adapter.send_calls == 1
        assert customer_adapter.send_calls == 1

    def test_health_check(self, mock_config: SIEMConfig):
        """Test health check for all adapters."""
        dispatcher = SIEMDispatcher()

        healthy_adapter = MockSIEMAdapter(mock_config, "healthy")
        unhealthy_adapter = MockSIEMAdapter(mock_config, "unhealthy", fail=True)

        dispatcher.register_adapter(healthy_adapter)
        dispatcher.register_adapter(unhealthy_adapter)

        health = dispatcher.health_check()

        assert health["healthy"] is True
        assert health["unhealthy"] is False


class TestSIEMDispatcherWorkers:
    """Tests for dispatcher background workers."""

    def test_start_stop(self):
        """Test starting and stopping workers."""
        dispatcher = SIEMDispatcher()

        dispatcher.start()
        assert dispatcher.is_running is True

        dispatcher.stop()
        assert dispatcher.is_running is False

    def test_start_idempotent(self):
        """Test that multiple starts don't create extra workers."""
        config = SIEMDispatcherConfig(worker_threads=2)
        dispatcher = SIEMDispatcher(config)

        dispatcher.start()
        dispatcher.start()  # Should be no-op
        dispatcher.start()

        assert dispatcher.is_running is True
        # Workers count would be internal, but behavior should be correct

        dispatcher.stop()

    def test_background_delivery(self, mock_config: SIEMConfig, sample_event: dict):
        """Test events are delivered by background workers."""
        config = SIEMDispatcherConfig(
            batch_size=1,  # Immediate delivery
            flush_interval_seconds=0.1,
        )
        dispatcher = SIEMDispatcher(config)
        adapter = MockSIEMAdapter(mock_config, "bg_test")
        dispatcher.register_adapter(adapter)

        dispatcher.start()
        dispatcher.dispatch(sample_event)

        # Wait for delivery
        time.sleep(0.5)

        dispatcher.stop()

        assert adapter.send_calls >= 1
        assert len(adapter.events_received) >= 1

    def test_flush_on_stop(self, mock_config: SIEMConfig, sample_event: dict):
        """Test remaining events are flushed on stop."""
        config = SIEMDispatcherConfig(
            batch_size=100,  # Won't trigger batch
            flush_interval_seconds=60,  # Won't trigger time flush
        )
        dispatcher = SIEMDispatcher(config)
        adapter = MockSIEMAdapter(mock_config, "flush_test")
        dispatcher.register_adapter(adapter)

        dispatcher.start()

        # Queue several events
        for _ in range(5):
            dispatcher.dispatch(sample_event)

        # Stop should flush
        dispatcher.stop(flush=True)

        assert len(adapter.events_received) == 5

    def test_stop_without_flush(self, mock_config: SIEMConfig, sample_event: dict):
        """Test stop without flush doesn't deliver queued events."""
        config = SIEMDispatcherConfig(
            batch_size=100,
            flush_interval_seconds=60,
        )
        dispatcher = SIEMDispatcher(config)
        adapter = MockSIEMAdapter(mock_config, "no_flush")
        dispatcher.register_adapter(adapter)

        # Don't start workers, just queue
        for _ in range(5):
            dispatcher.dispatch(sample_event)

        # Stop without flush
        dispatcher.stop(flush=False)

        # Events should still be in queue (not delivered)
        # Since workers never started, nothing was processed


class TestSIEMDispatcherConcurrency:
    """Tests for dispatcher thread safety."""

    def test_concurrent_dispatch(self, mock_config: SIEMConfig, sample_event: dict):
        """Test concurrent dispatch from multiple threads."""
        dispatcher = SIEMDispatcher()
        adapter = MockSIEMAdapter(mock_config, "concurrent")
        dispatcher.register_adapter(adapter)
        dispatcher.start()

        results = []

        def dispatch_worker():
            for _ in range(10):
                result = dispatcher.dispatch(sample_event)
                results.append(result)

        threads = [threading.Thread(target=dispatch_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        dispatcher.stop()

        # All dispatches should succeed
        assert len(results) == 50
        assert all(results)

    def test_concurrent_register_dispatch(self, mock_config: SIEMConfig, sample_event: dict):
        """Test concurrent adapter registration and dispatch."""
        dispatcher = SIEMDispatcher()
        dispatcher.start()

        def register_worker():
            for i in range(5):
                adapter = MockSIEMAdapter(mock_config, f"adapter_{i}")
                dispatcher.register_adapter(adapter, customer_id=f"cust_{i}")

        def dispatch_worker():
            for _ in range(10):
                dispatcher.dispatch(sample_event)

        threads = [
            threading.Thread(target=register_worker),
            threading.Thread(target=dispatch_worker),
            threading.Thread(target=dispatch_worker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        dispatcher.stop()

        # Should complete without errors
        assert dispatcher.stats["events_queued"] == 20
