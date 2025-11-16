"""Dual-priority telemetry sender.

Implements two separate queues for efficient telemetry:

1. Threat Queue (High Priority):
   - Scans with detections
   - Shipped immediately (async, non-blocking)
   - Retry with exponential backoff
   - Critical for threat intelligence

2. Clean Queue (Low Priority):
   - Scans with no threats
   - Batched (50 events or 5 minutes)
   - Non-blocking background processing
   - Provides baseline metrics

This architecture ensures threat detection is fast while maintaining
efficient telemetry for clean scans.
"""
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Empty, Full, Queue
from typing import Any

from raxe.infrastructure.telemetry.async_sender import AsyncBatchSender, run_async_send
from raxe.infrastructure.telemetry.sender import BatchSender, CircuitBreaker
from raxe.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TelemetryEvent:
    """Telemetry event to be sent.

    Attributes:
        event_type: Type of event (scan_completed, threat_detected)
        event_id: Unique event ID
        payload: Event data
        priority: Priority (threat or clean)
    """
    event_type: str
    event_id: str
    payload: dict[str, Any]
    priority: str  # "threat" or "clean"


class DualPriorityTelemetrySender:
    """Dual-priority telemetry sender with separate queues.

    Features:
    - Immediate shipping for threats (non-blocking)
    - Batched shipping for clean scans
    - Circuit breaker for reliability
    - Background thread for batch processing
    - Graceful shutdown
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        threat_batch_size: int = 1,  # Send immediately
        clean_batch_size: int = 50,  # Batch up to 50
        flush_interval: int = 300,  # 5 minutes
        max_queue_size: int = 1000,
        circuit_breaker: CircuitBreaker | None = None,
        use_async: bool = True,  # Use async sender by default for better performance
    ):
        """Initialize dual-priority sender.

        Args:
            endpoint: Telemetry endpoint URL
            api_key: API key for authentication
            threat_batch_size: Batch size for threat queue (1 = immediate)
            clean_batch_size: Batch size for clean queue
            flush_interval: Flush interval in seconds for clean queue
            max_queue_size: Maximum queue size per queue
            circuit_breaker: Circuit breaker instance
            use_async: Use async sender (httpx) instead of sync (urllib)
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.threat_batch_size = threat_batch_size
        self.clean_batch_size = clean_batch_size
        self.flush_interval = flush_interval
        self.max_queue_size = max_queue_size
        self.use_async = use_async

        # Choose sender based on mode
        if use_async:
            # Async sender for better performance
            self.async_sender = AsyncBatchSender(
                endpoint=endpoint,
                api_key=api_key,
                circuit_breaker=circuit_breaker,
            )
            self.sender = None
        else:
            # Sync sender for compatibility
            self.sender = BatchSender(
                endpoint=endpoint,
                api_key=api_key,
                circuit_breaker=circuit_breaker,
            )
            self.async_sender = None

        # Separate queues for threat and clean events
        self.threat_queue: Queue[TelemetryEvent] = Queue(maxsize=max_queue_size)
        self.clean_queue: Queue[TelemetryEvent] = Queue(maxsize=max_queue_size)

        # Background processing
        self._running = False
        self._worker_thread: threading.Thread | None = None
        self._last_flush_time = time.time()

        # Statistics
        self._stats = {
            "threats_sent": 0,
            "clean_sent": 0,
            "threats_dropped": 0,
            "clean_dropped": 0,
            "send_errors": 0,
        }

    def start(self) -> None:
        """Start background worker thread."""
        if self._running:
            logger.warning("telemetry_already_running")
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker,
            name="TelemetryWorker",
            daemon=True,
        )
        self._worker_thread.start()

        logger.info("telemetry_sender_started")

    def stop(self, timeout: float = 10.0) -> None:
        """Stop background worker and flush remaining events.

        Args:
            timeout: Maximum time to wait for shutdown
        """
        if not self._running:
            return

        logger.info("telemetry_sender_stopping")
        self._running = False

        # Wait for worker thread
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout)

        # Attempt final flush
        try:
            self._flush_clean_queue(force=True)
        except Exception as e:
            logger.error("telemetry_final_flush_failed", error=str(e))

        logger.info(
            "telemetry_sender_stopped",
            threats_sent=self._stats["threats_sent"],
            clean_sent=self._stats["clean_sent"],
        )

    def send_threat(self, event: TelemetryEvent) -> None:
        """Send threat event (high priority, immediate).

        Args:
            event: Telemetry event with threat data
        """
        try:
            # Try to queue (non-blocking)
            self.threat_queue.put_nowait(event)
            logger.debug("threat_event_queued", event_id=event.event_id)
        except Full:
            # Queue full, drop event
            self._stats["threats_dropped"] += 1
            logger.warning(
                "threat_queue_full",
                event_id=event.event_id,
                queue_size=self.threat_queue.qsize(),
            )

    def send_clean(self, event: TelemetryEvent) -> None:
        """Send clean event (low priority, batched).

        Args:
            event: Telemetry event with clean scan data
        """
        try:
            # Try to queue (non-blocking)
            self.clean_queue.put_nowait(event)
            logger.debug("clean_event_queued", event_id=event.event_id)

            # Check if should flush
            if self.clean_queue.qsize() >= self.clean_batch_size:
                self._flush_clean_queue()

        except Full:
            # Queue full, drop oldest event and try again
            try:
                self.clean_queue.get_nowait()
                self._stats["clean_dropped"] += 1
                self.clean_queue.put_nowait(event)
            except Exception as e:
                logger.warning("clean_queue_overflow", error=str(e))

    def _worker(self) -> None:
        """Background worker thread.

        Processes:
        1. Threat queue (immediate shipping)
        2. Clean queue (periodic flushing)
        """
        logger.info("telemetry_worker_started")

        while self._running:
            try:
                # Process threat queue (high priority)
                self._process_threat_queue()

                # Check if clean queue needs flushing
                time_since_flush = time.time() - self._last_flush_time
                if time_since_flush >= self.flush_interval:
                    self._flush_clean_queue()

                # Sleep briefly to avoid busy loop
                time.sleep(0.1)

            except Exception as e:
                logger.error("telemetry_worker_error", error=str(e))
                time.sleep(1.0)  # Back off on errors

        logger.info("telemetry_worker_stopped")

    def _process_threat_queue(self) -> None:
        """Process threat queue (send immediately)."""
        batch = []

        # Collect events up to batch size
        while len(batch) < self.threat_batch_size:
            try:
                event = self.threat_queue.get_nowait()
                batch.append(event.payload)
            except Empty:
                break

        # Send batch if we have events
        if batch:
            self._send_batch(batch, priority="threat")

    def _flush_clean_queue(self, force: bool = False) -> None:
        """Flush clean queue (batched sending).

        Args:
            force: Force flush even if batch not full
        """
        batch = []

        # Collect events from queue
        while len(batch) < self.clean_batch_size:
            try:
                event = self.clean_queue.get_nowait()
                batch.append(event.payload)
            except Empty:
                break

        # Send batch if we have events (or force flush)
        if batch and (len(batch) >= self.clean_batch_size or force):
            self._send_batch(batch, priority="clean")
            self._last_flush_time = time.time()

    def _send_batch(self, events: list[dict[str, Any]], priority: str) -> None:
        """Send batch of events to telemetry endpoint.

        Args:
            events: List of event payloads
            priority: Priority level (threat or clean)
        """
        if not events:
            return

        try:
            # Add batch metadata
            batch_payload = {
                "events": events,
                "batch_size": len(events),
                "priority": priority,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Send via appropriate sender
            if self.use_async and self.async_sender:
                # Use async sender (better performance)
                run_async_send(self.async_sender, batch_payload["events"])
            elif self.sender:
                # Use sync sender (compatibility)
                self.sender.send_batch(batch_payload["events"])
            else:
                raise RuntimeError("No sender available")

            # Update statistics
            if priority == "threat":
                self._stats["threats_sent"] += len(events)
            else:
                self._stats["clean_sent"] += len(events)

            logger.info(
                "telemetry_batch_sent",
                priority=priority,
                batch_size=len(events),
                total_sent=(
                    self._stats["threats_sent"] + self._stats["clean_sent"]
                ),
            )

        except Exception as e:
            self._stats["send_errors"] += 1
            logger.error(
                "telemetry_send_failed",
                priority=priority,
                batch_size=len(events),
                error=str(e),
            )

    def get_stats(self) -> dict[str, Any]:
        """Get telemetry sender statistics.

        Returns:
            Dictionary with statistics
        """
        # Get circuit state from appropriate sender
        if self.use_async and self.async_sender:
            circuit_state = self.async_sender.get_circuit_state()
        elif self.sender:
            circuit_state = self.sender.get_circuit_state()
        else:
            circuit_state = "unknown"

        return {
            **self._stats,
            "threat_queue_size": self.threat_queue.qsize(),
            "clean_queue_size": self.clean_queue.qsize(),
            "circuit_state": circuit_state,
            "sender_mode": "async" if self.use_async else "sync",
        }

    def clear_queues(self) -> None:
        """Clear all queues (for testing/reset)."""
        while not self.threat_queue.empty():
            try:
                self.threat_queue.get_nowait()
            except Empty:
                break

        while not self.clean_queue.empty():
            try:
                self.clean_queue.get_nowait()
            except Empty:
                break

        logger.info("telemetry_queues_cleared")


class TelemetryManager:
    """Manages telemetry lifecycle with dual-priority sender.

    Singleton manager for application-wide telemetry.
    """

    _instance: "TelemetryManager | None" = None

    def __init__(
        self,
        endpoint: str = "https://telemetry.raxe.ai/v1/events",
        api_key: str | None = None,
        enabled: bool = True,
        **kwargs: Any,
    ):
        """Initialize telemetry manager.

        Args:
            endpoint: Telemetry endpoint URL
            api_key: API key for authentication
            enabled: Enable telemetry
            **kwargs: Additional arguments for DualPriorityTelemetrySender
        """
        self.enabled = enabled
        self.sender: DualPriorityTelemetrySender | None = None

        if enabled:
            self.sender = DualPriorityTelemetrySender(
                endpoint=endpoint,
                api_key=api_key,
                **kwargs,
            )
            self.sender.start()

    @classmethod
    def get_instance(cls) -> "TelemetryManager":
        """Get singleton instance.

        Returns:
            TelemetryManager instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def send_scan_event(
        self,
        scan_id: str,
        found_threats: bool,
        threat_count: int = 0,
        highest_severity: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Send scan event with appropriate priority.

        Args:
            scan_id: Unique scan ID
            found_threats: Whether threats were found
            threat_count: Number of threats
            highest_severity: Highest severity level
            duration_ms: Scan duration in milliseconds
        """
        if not self.enabled or not self.sender:
            return

        event = TelemetryEvent(
            event_type="scan_completed",
            event_id=scan_id,
            payload={
                "scan_id": scan_id,
                "found_threats": found_threats,
                "threat_count": threat_count,
                "highest_severity": highest_severity,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            priority="threat" if found_threats else "clean",
        )

        if found_threats:
            self.sender.send_threat(event)
        else:
            self.sender.send_clean(event)

    def shutdown(self, timeout: float = 10.0) -> None:
        """Shutdown telemetry manager.

        Args:
            timeout: Maximum time to wait for shutdown
        """
        if self.sender:
            self.sender.stop(timeout=timeout)
