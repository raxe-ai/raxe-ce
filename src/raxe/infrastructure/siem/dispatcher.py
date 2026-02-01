"""SIEM event dispatcher with batching and multi-adapter support.

Central dispatcher for routing events to multiple SIEM adapters
with batching, queuing, and background delivery.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from queue import Empty, Full, Queue
from typing import Any

from raxe.infrastructure.siem.base import SIEMAdapter, SIEMDeliveryResult


@dataclass
class SIEMDispatcherConfig:
    """Configuration for SIEM dispatcher.

    Attributes:
        batch_size: Maximum events per batch (default: 100)
        flush_interval_seconds: Maximum time between flushes (default: 10.0)
        max_queue_size: Maximum events in queue before dropping (default: 10000)
        worker_threads: Number of background delivery threads (default: 2)
    """

    batch_size: int = 100
    flush_interval_seconds: float = 10.0
    max_queue_size: int = 10000
    worker_threads: int = 2

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.batch_size < 1 or self.batch_size > 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        if self.flush_interval_seconds < 0.1 or self.flush_interval_seconds > 300:
            raise ValueError("flush_interval_seconds must be between 0.1 and 300")
        if self.max_queue_size < 100:
            raise ValueError("max_queue_size must be at least 100")
        if self.worker_threads < 1 or self.worker_threads > 10:
            raise ValueError("worker_threads must be between 1 and 10")


@dataclass
class DispatcherStats:
    """Statistics for SIEM dispatcher."""

    events_queued: int = 0
    events_delivered: int = 0
    events_failed: int = 0
    events_dropped: int = 0
    batches_sent: int = 0
    adapters_registered: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "events_queued": self.events_queued,
            "events_delivered": self.events_delivered,
            "events_failed": self.events_failed,
            "events_dropped": self.events_dropped,
            "batches_sent": self.batches_sent,
            "adapters_registered": self.adapters_registered,
        }


class SIEMDispatcher:
    """Central dispatcher for routing events to SIEM adapters.

    Manages multiple SIEM adapters, batches events, and handles
    delivery with background workers.

    Thread-safe: can be used from multiple threads.

    Example:
        >>> from raxe.infrastructure.siem import SIEMDispatcher, create_siem_adapter
        >>> dispatcher = SIEMDispatcher()
        >>> dispatcher.register_adapter(splunk_adapter)
        >>> dispatcher.register_adapter(sentinel_adapter)
        >>> dispatcher.start()
        >>> dispatcher.dispatch(event)  # Sent to all registered adapters
        >>> dispatcher.stop()

    Per-Customer Routing:
        >>> # Register adapter with customer_id for routing
        >>> dispatcher.register_adapter(splunk_adapter, customer_id="cust_123")
        >>> dispatcher.register_adapter(sentinel_adapter, customer_id="cust_456")
        >>> # Events routed based on customer_id in payload
        >>> dispatcher.dispatch(event_for_cust_123)  # Goes to Splunk
        >>> dispatcher.dispatch(event_for_cust_456)  # Goes to Sentinel
    """

    def __init__(self, config: SIEMDispatcherConfig | None = None) -> None:
        """Initialize dispatcher.

        Args:
            config: Dispatcher configuration (uses defaults if not provided)
        """
        self._config = config or SIEMDispatcherConfig()

        # Adapter registry: customer_id -> adapter
        # None key = default/global adapters (sent all events)
        self._adapters: dict[str | None, list[SIEMAdapter]] = {None: []}
        self._adapter_lock = threading.RLock()

        # Event queue
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=self._config.max_queue_size)

        # Worker management
        self._running = False
        self._workers: list[threading.Thread] = []
        self._shutdown_event = threading.Event()

        # Statistics
        self._stats = DispatcherStats()
        self._stats_lock = threading.Lock()

    def register_adapter(
        self,
        adapter: SIEMAdapter,
        customer_id: str | None = None,
    ) -> None:
        """Register a SIEM adapter for event delivery.

        Args:
            adapter: SIEM adapter instance
            customer_id: Optional customer ID for routing.
                         If None, adapter receives all events.
                         If specified, adapter only receives events
                         for that customer.

        Example:
            >>> # Global adapter - receives all events
            >>> dispatcher.register_adapter(splunk_adapter)

            >>> # Customer-specific adapter
            >>> dispatcher.register_adapter(sentinel_adapter, customer_id="cust_123")
        """
        with self._adapter_lock:
            if customer_id not in self._adapters:
                self._adapters[customer_id] = []
            self._adapters[customer_id].append(adapter)

            with self._stats_lock:
                self._stats.adapters_registered += 1

    def unregister_adapter(
        self,
        adapter_name: str,
        customer_id: str | None = None,
    ) -> bool:
        """Unregister a SIEM adapter.

        Args:
            adapter_name: Name of adapter to remove
            customer_id: Customer ID the adapter was registered for

        Returns:
            True if adapter was found and removed
        """
        with self._adapter_lock:
            if customer_id not in self._adapters:
                return False

            for i, adapter in enumerate(self._adapters[customer_id]):
                if adapter.name == adapter_name:
                    removed = self._adapters[customer_id].pop(i)
                    removed.close()

                    # Clean up empty customer entry
                    if not self._adapters[customer_id] and customer_id is not None:
                        del self._adapters[customer_id]

                    with self._stats_lock:
                        self._stats.adapters_registered -= 1
                    return True

        return False

    def dispatch(self, event: dict[str, Any]) -> bool:
        """Dispatch an event to registered SIEM adapters.

        The event is queued for background delivery. Routing is based
        on the customer_id in the event payload.

        Args:
            event: RAXE telemetry event

        Returns:
            True if queued successfully, False if queue is full
        """
        try:
            self._queue.put_nowait(event)
            with self._stats_lock:
                self._stats.events_queued += 1
            return True
        except Full:
            with self._stats_lock:
                self._stats.events_dropped += 1
            return False

    def dispatch_sync(self, event: dict[str, Any]) -> dict[str, SIEMDeliveryResult]:
        """Dispatch an event synchronously (blocking).

        Useful for testing or when immediate confirmation is needed.

        Args:
            event: RAXE telemetry event

        Returns:
            Dict mapping adapter name to delivery result
        """
        adapters = self._get_adapters_for_event(event)
        results = {}

        for adapter in adapters:
            try:
                transformed = adapter.transform_event(event)
                result = adapter.send_event(transformed)
                results[adapter.name] = result
            except Exception as e:
                results[adapter.name] = SIEMDeliveryResult(
                    success=False,
                    error_message=str(e),
                )

        return results

    def _get_adapters_for_event(self, event: dict[str, Any]) -> list[SIEMAdapter]:
        """Get adapters that should receive an event.

        Returns global adapters plus any customer-specific adapters
        matching the event's customer_id.

        Args:
            event: RAXE telemetry event

        Returns:
            List of adapters to send the event to
        """
        customer_id = event.get("payload", {}).get("customer_id")

        with self._adapter_lock:
            # Always include global adapters
            adapters = list(self._adapters.get(None, []))

            # Add customer-specific adapters if customer_id matches
            if customer_id and customer_id in self._adapters:
                adapters.extend(self._adapters[customer_id])

            return adapters

    def start(self) -> None:
        """Start background worker threads for event delivery.

        Safe to call multiple times - will not start additional workers
        if already running.
        """
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        for i in range(self._config.worker_threads):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"siem-dispatcher-{i}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def stop(self, timeout: float = 30.0, flush: bool = True) -> None:
        """Stop background workers and optionally flush remaining events.

        Args:
            timeout: Maximum seconds to wait for workers to finish
            flush: If True, flush remaining events before stopping
        """
        if not self._running:
            return

        self._running = False
        self._shutdown_event.set()

        # Flush remaining events if requested
        if flush:
            self._flush_all()

        # Wait for workers to finish
        worker_timeout = timeout / max(len(self._workers), 1)
        for worker in self._workers:
            worker.join(timeout=worker_timeout)

        self._workers.clear()

        # Close all adapters
        with self._adapter_lock:
            for customer_adapters in self._adapters.values():
                for adapter in customer_adapters:
                    adapter.close()
            self._adapters = {None: []}

    def _worker_loop(self) -> None:
        """Background worker loop for batching and delivery."""
        batch: list[dict[str, Any]] = []
        last_flush = time.time()

        while self._running or not self._queue.empty():
            try:
                # Try to get event with timeout
                event = self._queue.get(timeout=1.0)
                batch.append(event)

                # Flush if batch is full
                if len(batch) >= self._config.batch_size:
                    self._deliver_batch(batch)
                    batch = []
                    last_flush = time.time()

            except Empty:
                # Check if we need to flush due to time
                elapsed = time.time() - last_flush
                if batch and elapsed >= self._config.flush_interval_seconds:
                    self._deliver_batch(batch)
                    batch = []
                    last_flush = time.time()

                # Check for shutdown
                if self._shutdown_event.is_set() and self._queue.empty():
                    break

        # Flush remaining on shutdown
        if batch:
            self._deliver_batch(batch)

    def _deliver_batch(self, batch: list[dict[str, Any]]) -> None:
        """Deliver a batch of events to appropriate adapters.

        Events are grouped by customer_id for efficient routing.
        """
        if not batch:
            return

        # Group events by the adapters they should go to
        # For simplicity, we deliver each event to its target adapters
        for event in batch:
            adapters = self._get_adapters_for_event(event)

            for adapter in adapters:
                try:
                    transformed = adapter.transform_event(event)
                    result = adapter.send_event(transformed)

                    with self._stats_lock:
                        if result.success:
                            self._stats.events_delivered += 1
                        else:
                            self._stats.events_failed += 1

                except Exception:
                    with self._stats_lock:
                        self._stats.events_failed += 1

        with self._stats_lock:
            self._stats.batches_sent += 1

    def _flush_all(self) -> None:
        """Flush all remaining queued events synchronously."""
        batch: list[dict[str, Any]] = []

        while True:
            try:
                event = self._queue.get_nowait()
                batch.append(event)

                if len(batch) >= self._config.batch_size:
                    self._deliver_batch(batch)
                    batch = []
            except Empty:
                break

        if batch:
            self._deliver_batch(batch)

    @property
    def stats(self) -> dict[str, int]:
        """Get dispatcher statistics."""
        with self._stats_lock:
            return self._stats.to_dict()

    @property
    def is_running(self) -> bool:
        """Check if dispatcher is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def health_check(self) -> dict[str, bool]:
        """Check health of all registered adapters.

        Returns:
            Dict mapping adapter name to health status
        """
        results = {}
        with self._adapter_lock:
            for customer_adapters in self._adapters.values():
                for adapter in customer_adapters:
                    # Use unique key for customer-specific adapters
                    results[adapter.name] = adapter.health_check()
        return results

    def get_registered_adapters(self) -> dict[str | None, list[str]]:
        """Get list of registered adapters by customer.

        Returns:
            Dict mapping customer_id (None for global) to adapter names
        """
        with self._adapter_lock:
            return {
                customer_id: [a.name for a in adapters]
                for customer_id, adapters in self._adapters.items()
            }
