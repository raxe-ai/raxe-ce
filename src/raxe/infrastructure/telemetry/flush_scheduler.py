"""Timer-based flush scheduler for dual queues.

This module implements a timer-based scheduler for flushing telemetry events
from dual priority queues. It manages two independent timers:
- Critical queue timer (5s default) for high-priority threat events
- Standard queue timer (5m default) for batched clean scan events

The scheduler supports:
- Graceful shutdown with timeout
- Thread-safe operations
- Comprehensive statistics tracking
"""

from __future__ import annotations

import atexit
import signal
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from raxe.utils.logging import get_logger

logger = get_logger(__name__)


class DualQueueProtocol(Protocol):
    """Protocol for dual queue implementations.

    This protocol defines the interface that queue implementations must provide
    to work with the FlushScheduler.
    """

    def dequeue_critical_batch(self, batch_size: int) -> list[dict[str, Any]]:
        """Dequeue a batch of critical (threat) events.

        Args:
            batch_size: Maximum number of events to dequeue

        Returns:
            List of event payloads
        """
        ...

    def dequeue_standard_batch(self, batch_size: int) -> list[dict[str, Any]]:
        """Dequeue a batch of standard (clean) events.

        Args:
            batch_size: Maximum number of events to dequeue

        Returns:
            List of event payloads
        """
        ...

    def get_critical_count(self) -> int:
        """Get count of events in critical queue."""
        ...

    def get_standard_count(self) -> int:
        """Get count of events in standard queue."""
        ...


class TelemetryShipperProtocol(Protocol):
    """Protocol for telemetry shipper implementations.

    This defines the interface for sending batches of events to the
    telemetry backend.
    """

    def ship_batch(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Ship a batch of events to the telemetry backend.

        Args:
            events: List of event payloads to ship

        Returns:
            Response dictionary with status and metadata
        """
        ...


@dataclass
class FlushConfig:
    """Flush scheduler configuration.

    Attributes:
        critical_interval_seconds: Interval between critical queue flushes
        standard_interval_seconds: Interval between standard queue flushes
        max_batch_size: Maximum events per batch
        shutdown_timeout_seconds: Timeout for graceful shutdown
    """

    critical_interval_seconds: float = 5.0
    standard_interval_seconds: float = 300.0  # 5 minutes
    max_batch_size: int = 100
    shutdown_timeout_seconds: float = 10.0

    @classmethod
    def for_production(cls) -> FlushConfig:
        """Production mode with standard intervals.

        Returns:
            FlushConfig configured for production
        """
        return cls(
            critical_interval_seconds=5.0,
            standard_interval_seconds=300.0,
        )


class SQLiteDualQueueAdapter:
    """Adapter to make DualQueue (SQLite-based) work with FlushScheduler.

    This adapter wraps the SQLite-based DualQueue to provide the
    DualQueueProtocol interface expected by FlushScheduler.
    """

    def __init__(self, queue: Any) -> None:
        """Initialize the adapter.

        Args:
            queue: The DualQueue instance to wrap
        """
        self._queue = queue
        self._pending_event_ids: list[str] = []

    def dequeue_critical_batch(self, batch_size: int) -> list[dict[str, Any]]:
        """Dequeue a batch of critical (threat) events.

        Args:
            batch_size: Maximum number of events to dequeue

        Returns:
            List of event payloads
        """
        events = self._queue.dequeue_critical(batch_size)
        # Store event IDs for marking as sent later
        self._pending_event_ids = [e["event_id"] for e in events]
        return events

    def dequeue_standard_batch(self, batch_size: int) -> list[dict[str, Any]]:
        """Dequeue a batch of standard (clean) events.

        Args:
            batch_size: Maximum number of events to dequeue

        Returns:
            List of event payloads
        """
        events = self._queue.dequeue_standard(batch_size)
        # Store event IDs for marking as sent later
        self._pending_event_ids = [e["event_id"] for e in events]
        return events

    def get_critical_count(self) -> int:
        """Get count of events in critical queue."""
        stats = self._queue.get_stats()
        return stats.get("critical_count", 0)

    def get_standard_count(self) -> int:
        """Get count of events in standard queue."""
        stats = self._queue.get_stats()
        return stats.get("standard_count", 0)

    def mark_sent(self) -> None:
        """Mark pending events as successfully sent."""
        if self._pending_event_ids:
            self._queue.mark_batch_sent(self._pending_event_ids)
            self._pending_event_ids = []

    def mark_failed(self, error: str, retry_delay_seconds: int = 60) -> None:
        """Mark pending events as failed."""
        if self._pending_event_ids:
            self._queue.mark_batch_failed(
                self._pending_event_ids, error, retry_delay_seconds
            )
            self._pending_event_ids = []


class HttpShipper:
    """HTTP shipper that uses BatchSender for telemetry transmission.

    This implements TelemetryShipperProtocol and wraps BatchSender to
    provide actual HTTP shipping capability for FlushScheduler.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        installation_id: str | None = None,
        queue_adapter: SQLiteDualQueueAdapter | None = None,
        api_key_id: str | None = None,
    ) -> None:
        """Initialize the HTTP shipper.

        Args:
            endpoint: Telemetry endpoint URL
            api_key: API key for authentication
            installation_id: Installation ID for batch envelope
            queue_adapter: Optional queue adapter for marking events sent/failed
            api_key_id: Pre-computed key ID for batch envelope (optional).
                If not provided, will be computed from api_key when sending.
        """
        from raxe.infrastructure.telemetry.sender import BatchSender, CircuitBreaker

        self._endpoint = endpoint
        self._api_key = api_key
        self._installation_id = installation_id or "inst_unknown"
        self._queue_adapter = queue_adapter
        self._api_key_id = api_key_id

        self._sender = BatchSender(
            endpoint=endpoint,
            api_key=api_key,
            installation_id=installation_id,
            circuit_breaker=CircuitBreaker(),
            api_key_id=api_key_id,
        )

        self._stats = {
            "batches_sent": 0,
            "events_sent": 0,
            "errors": 0,
        }

    def ship_batch(self, events: list[dict[str, Any]], no_retry: bool = False) -> dict[str, Any]:
        """Ship a batch of events to the telemetry backend.

        Args:
            events: List of event payloads to ship
            no_retry: If True, skip retries (useful for shutdown scenarios)

        Returns:
            Response dictionary with status and metadata
        """
        if not events:
            return {"success": True, "events_accepted": 0}

        try:
            response = self._sender.send_batch(events, no_retry=no_retry)

            self._stats["batches_sent"] += 1
            self._stats["events_sent"] += len(events)

            # Mark events as sent in the queue
            if self._queue_adapter:
                self._queue_adapter.mark_sent()

            logger.info(
                "http_shipper_batch_sent",
                event_count=len(events),
                total_sent=self._stats["events_sent"],
            )

            return {
                "success": True,
                "events_accepted": len(events),
                "response": response,
            }

        except Exception as e:
            self._stats["errors"] += 1

            # Mark events as failed in the queue
            if self._queue_adapter:
                self._queue_adapter.mark_failed(str(e))

            logger.error(
                "http_shipper_batch_failed",
                event_count=len(events),
                error=str(e),
            )

            return {
                "success": False,
                "events_accepted": 0,
                "error": str(e),
            }

    def update_credentials(
        self,
        api_key: str | None = None,
        installation_id: str | None = None,
        api_key_id: str | None = None,
    ) -> None:
        """Update API key, installation_id, and api_key_id (for credential rotation).

        Args:
            api_key: New API key
            installation_id: New installation ID
            api_key_id: New pre-computed key ID
        """
        if api_key is not None:
            self._api_key = api_key
            self._sender.api_key = api_key
        if installation_id is not None:
            self._installation_id = installation_id
            self._sender.installation_id = installation_id
        if api_key_id is not None:
            self._api_key_id = api_key_id
            self._sender.api_key_id = api_key_id

    def get_stats(self) -> dict[str, Any]:
        """Get shipper statistics.

        Returns:
            Dictionary with shipping statistics
        """
        return {
            **self._stats,
            "circuit_state": self._sender.get_circuit_state(),
            "endpoint": self._endpoint,
        }


@dataclass
class FlushStats:
    """Statistics for flush operations.

    Attributes:
        critical_flushes: Number of critical queue flush operations
        standard_flushes: Number of standard queue flush operations
        events_shipped: Total events shipped across all flushes
        errors: Number of errors encountered
        last_critical_flush: Timestamp of last critical flush
        last_standard_flush: Timestamp of last standard flush
    """

    critical_flushes: int = 0
    standard_flushes: int = 0
    events_shipped: int = 0
    errors: int = 0
    last_critical_flush: datetime | None = None
    last_standard_flush: datetime | None = None


class FlushScheduler:
    """Timer-based flush scheduler for dual queues.

    Runs two independent timers:
    - Critical queue timer (5s default) for high-priority threat events
    - Standard queue timer (5m default) for batched clean scan events

    The scheduler supports graceful shutdown and comprehensive statistics tracking.

    Example:
        >>> from raxe.infrastructure.telemetry.flush_scheduler import (
        ...     FlushScheduler, FlushConfig, HttpShipper
        ... )
        >>> config = FlushConfig.for_production()
        >>> shipper = HttpShipper(endpoint="https://...", api_key="...")
        >>> scheduler = FlushScheduler(queue=my_queue, shipper=shipper, config=config)
        >>> scheduler.start()
        >>> # ... events are flushed automatically ...
        >>> scheduler.stop(graceful=True)
    """

    def __init__(
        self,
        queue: DualQueueProtocol,
        shipper: TelemetryShipperProtocol,
        config: FlushConfig | None = None,
    ) -> None:
        """Initialize the flush scheduler.

        Args:
            queue: Dual queue implementation (must implement DualQueueProtocol)
            shipper: Telemetry shipper (must implement TelemetryShipperProtocol)
            config: Flush configuration (uses defaults if None)
        """
        self._config = config or FlushConfig()
        self._queue = queue
        self._shipper = shipper

        # State management
        self._running = False
        self._lock = threading.RLock()
        self._stop_event = threading.Event()

        # Timers
        self._critical_timer: threading.Timer | None = None
        self._standard_timer: threading.Timer | None = None

        # Statistics
        self._stats = FlushStats()

        # Session tracking (for session_end events)
        self._session_start: datetime | None = None
        self._session_id: str | None = None

        # Register shutdown handlers
        self._register_shutdown_handlers()

    def _register_shutdown_handlers(self) -> None:
        """Register atexit and signal handlers for graceful shutdown."""
        # atexit handler for normal program termination
        atexit.register(self._atexit_handler)

        # Signal handlers for SIGTERM/SIGINT (if running in main thread)
        try:
            if threading.current_thread() is threading.main_thread():
                # Store original handlers to chain
                self._original_sigterm = signal.signal(
                    signal.SIGTERM, self._signal_handler
                )
                self._original_sigint = signal.signal(
                    signal.SIGINT, self._signal_handler
                )
        except ValueError:
            # Can't set signal handlers in non-main thread
            logger.debug("flush_scheduler_signal_handlers_skipped", reason="not_main_thread")

    def _atexit_handler(self) -> None:
        """Handler called on program exit."""
        if self._running:
            logger.info("flush_scheduler_atexit_triggered")
            self.stop(graceful=True)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handler for SIGTERM/SIGINT signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(
            "flush_scheduler_signal_received",
            signal=signal.Signals(signum).name,
        )
        self.stop(graceful=True)

        # Chain to original handler
        handler_attr = "_original_sigterm" if signum == signal.SIGTERM else "_original_sigint"
        original_handler = getattr(self, handler_attr, None)
        if original_handler and callable(original_handler):
            original_handler(signum, frame)

    def start(self) -> None:
        """Start background flush timers.

        Starts two independent timer threads for critical and standard queues.
        Safe to call multiple times - subsequent calls are no-ops if already running.
        """
        with self._lock:
            if self._running:
                logger.warning("flush_scheduler_already_running")
                return

            self._running = True
            self._stop_event.clear()
            self._session_start = datetime.now(timezone.utc)

            # Start timers
            self._schedule_critical_flush()
            self._schedule_standard_flush()

            logger.info(
                "flush_scheduler_started",
                critical_interval=self._config.critical_interval_seconds,
                standard_interval=self._config.standard_interval_seconds,
                max_batch_size=self._config.max_batch_size,
            )

    def stop(self, graceful: bool = True) -> None:
        """Stop scheduler.

        Args:
            graceful: If True, flush pending events before stopping
        """
        with self._lock:
            if not self._running:
                return

            logger.info(
                "flush_scheduler_stopping",
                graceful=graceful,
            )

            self._running = False
            self._stop_event.set()

            # Cancel timers
            if self._critical_timer:
                self._critical_timer.cancel()
                self._critical_timer = None
            if self._standard_timer:
                self._standard_timer.cancel()
                self._standard_timer = None

        # Flush remaining events if graceful shutdown
        if graceful:
            self._graceful_shutdown()

        logger.info(
            "flush_scheduler_stopped",
            critical_flushes=self._stats.critical_flushes,
            standard_flushes=self._stats.standard_flushes,
            events_shipped=self._stats.events_shipped,
            errors=self._stats.errors,
        )

    def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown - NON-BLOCKING.

        Events remain in SQLite queue for delivery on next CLI run.
        This ensures the CLI never hangs waiting for network operations.
        """
        # Check remaining events in queues
        try:
            critical_remaining = self._queue.get_critical_count()
            standard_remaining = self._queue.get_standard_count()

            if critical_remaining > 0 or standard_remaining > 0:
                logger.debug(
                    "flush_scheduler_shutdown_events_pending",
                    critical_remaining=critical_remaining,
                    standard_remaining=standard_remaining,
                    message="Events will be delivered on next CLI run",
                )
            else:
                logger.debug("flush_scheduler_shutdown_queues_empty")

        except Exception as e:
            logger.debug(
                "flush_scheduler_shutdown_check_error",
                error=str(e),
            )

    def _schedule_critical_flush(self) -> None:
        """Schedule the next critical queue flush."""
        if not self._running or self._stop_event.is_set():
            return

        self._critical_timer = threading.Timer(
            self._config.critical_interval_seconds,
            self._critical_flush_callback,
        )
        self._critical_timer.daemon = True
        self._critical_timer.name = "FlushScheduler-Critical"
        self._critical_timer.start()

    def _schedule_standard_flush(self) -> None:
        """Schedule the next standard queue flush."""
        if not self._running or self._stop_event.is_set():
            return

        self._standard_timer = threading.Timer(
            self._config.standard_interval_seconds,
            self._standard_flush_callback,
        )
        self._standard_timer.daemon = True
        self._standard_timer.name = "FlushScheduler-Standard"
        self._standard_timer.start()

    def _critical_flush_callback(self) -> None:
        """Timer callback for critical queue flush."""
        if not self._running:
            return

        try:
            self.flush_critical()
        except Exception as e:
            logger.error(
                "flush_scheduler_critical_callback_error",
                error=str(e),
            )
            self._stats.errors += 1
        finally:
            # Reschedule
            self._schedule_critical_flush()

    def _standard_flush_callback(self) -> None:
        """Timer callback for standard queue flush."""
        if not self._running:
            return

        try:
            self.flush_standard()
        except Exception as e:
            logger.error(
                "flush_scheduler_standard_callback_error",
                error=str(e),
            )
            self._stats.errors += 1
        finally:
            # Reschedule
            self._schedule_standard_flush()

    def flush_critical(self, no_retry: bool = False) -> int:
        """Flush critical queue immediately.

        Args:
            no_retry: If True, skip retries (useful for shutdown scenarios)

        Returns:
            Number of events sent
        """
        events = self._queue.dequeue_critical_batch(self._config.max_batch_size)
        if not events:
            return 0

        events_sent = self._ship_batch(events, queue_type="critical", no_retry=no_retry)

        with self._lock:
            self._stats.critical_flushes += 1
            self._stats.events_shipped += events_sent
            self._stats.last_critical_flush = datetime.now(timezone.utc)

        logger.info(
            "flush_scheduler_critical_flushed",
            events_sent=events_sent,
            total_critical_flushes=self._stats.critical_flushes,
        )

        return events_sent

    def flush_standard(self, no_retry: bool = False) -> int:
        """Flush standard queue immediately.

        Args:
            no_retry: If True, skip retries (useful for shutdown scenarios)

        Returns:
            Number of events sent
        """
        events = self._queue.dequeue_standard_batch(self._config.max_batch_size)
        if not events:
            return 0

        events_sent = self._ship_batch(events, queue_type="standard", no_retry=no_retry)

        with self._lock:
            self._stats.standard_flushes += 1
            self._stats.events_shipped += events_sent
            self._stats.last_standard_flush = datetime.now(timezone.utc)

        logger.info(
            "flush_scheduler_standard_flushed",
            events_sent=events_sent,
            total_standard_flushes=self._stats.standard_flushes,
        )

        return events_sent

    def flush_all(self) -> int:
        """Flush both queues.

        Returns:
            Total events sent across both queues
        """
        critical_count = self.flush_critical()
        standard_count = self.flush_standard()
        return critical_count + standard_count

    def _ship_batch(self, events: list[dict[str, Any]], queue_type: str, no_retry: bool = False) -> int:
        """Ship a batch of events.

        Args:
            events: List of event payloads to ship
            queue_type: Type of queue (critical/standard) for logging
            no_retry: If True, skip retries (useful for shutdown scenarios)

        Returns:
            Number of events successfully shipped
        """
        if not events:
            return 0

        try:
            response = self._shipper.ship_batch(events, no_retry=no_retry)

            # Check for success
            if response.get("success", False):
                events_accepted = response.get("events_accepted", len(events))
                return int(events_accepted) if events_accepted is not None else len(events)
            else:
                logger.warning(
                    "flush_scheduler_ship_failed",
                    queue_type=queue_type,
                    event_count=len(events),
                    response=response,
                )
                self._stats.errors += 1
                return 0

        except Exception as e:
            logger.error(
                "flush_scheduler_ship_error",
                queue_type=queue_type,
                event_count=len(events),
                error=str(e),
            )
            self._stats.errors += 1
            return 0

    def is_running(self) -> bool:
        """Check if scheduler is running.

        Returns:
            True if scheduler is running, False otherwise
        """
        return self._running

    def get_stats(self) -> dict[str, Any]:
        """Get flush statistics.

        Returns:
            Dictionary with scheduler statistics including:
            - is_running: Whether scheduler is currently running
            - critical_flushes: Count of critical queue flushes
            - standard_flushes: Count of standard queue flushes
            - events_shipped: Total events shipped
            - errors: Error count
            - last_critical_flush: Timestamp of last critical flush
            - last_standard_flush: Timestamp of last standard flush
            - queue_depths: Current queue depths
        """
        with self._lock:
            stats = {
                "is_running": self._running,
                "critical_flushes": self._stats.critical_flushes,
                "standard_flushes": self._stats.standard_flushes,
                "events_shipped": self._stats.events_shipped,
                "errors": self._stats.errors,
                "last_critical_flush": (
                    self._stats.last_critical_flush.isoformat()
                    if self._stats.last_critical_flush
                    else None
                ),
                "last_standard_flush": (
                    self._stats.last_standard_flush.isoformat()
                    if self._stats.last_standard_flush
                    else None
                ),
                "config": {
                    "critical_interval_seconds": self._config.critical_interval_seconds,
                    "standard_interval_seconds": self._config.standard_interval_seconds,
                    "max_batch_size": self._config.max_batch_size,
                    "shutdown_timeout_seconds": self._config.shutdown_timeout_seconds,
                },
            }

            # Add queue depths if available
            try:
                stats["queue_depths"] = {
                    "critical": self._queue.get_critical_count(),
                    "standard": self._queue.get_standard_count(),
                }
            except Exception:
                stats["queue_depths"] = {"critical": -1, "standard": -1}

            return stats

    def get_shipper(self) -> TelemetryShipperProtocol:
        """Get the shipper instance.

        Returns:
            The telemetry shipper instance
        """
        return self._shipper


__all__ = [
    "DualQueueProtocol",
    "FlushConfig",
    "FlushScheduler",
    "FlushStats",
    "HttpShipper",
    "SQLiteDualQueueAdapter",
    "TelemetryShipperProtocol",
]
