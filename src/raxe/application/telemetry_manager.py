"""
Telemetry manager - orchestrates telemetry components in the application layer.

This module coordinates between:
- Domain layer (pure event creation)
- Infrastructure layer (queue, sender, config)
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from raxe.domain.telemetry import create_scan_event
from raxe.infrastructure.telemetry.config import TelemetryConfig
from raxe.infrastructure.telemetry.queue import EventPriority, EventQueue
from raxe.infrastructure.telemetry.sender import BatchSender, CircuitBreaker, RetryPolicy

logger = logging.getLogger(__name__)


class TelemetryManager:
    """
    Manages telemetry collection and transmission.

    Responsibilities:
    - Coordinates event creation, queuing, and sending
    - Manages background flush thread
    - Ensures privacy compliance
    - Handles graceful shutdown
    """

    def __init__(
        self,
        config: TelemetryConfig | None = None,
        db_path: Path | None = None,
        api_key: str | None = None
    ):
        """
        Initialize telemetry manager.

        Args:
            config: Telemetry configuration
            db_path: Path to SQLite database
            api_key: RAXE API key
        """
        self.config = config or TelemetryConfig.load()
        self.api_key = api_key
        self._shutdown_event = threading.Event()
        self._flush_thread: threading.Thread | None = None

        if not self.config.enabled:
            logger.info("Telemetry disabled by configuration")
            self.queue = None
            self.sender = None
            return

        # Initialize components
        self._init_components(db_path)

        # Start background flush thread
        if self.config.flush_interval_ms > 0:
            self._start_flush_thread()

        logger.info("TelemetryManager initialized successfully")

    def _init_components(self, db_path: Path | None) -> None:
        """Initialize telemetry components."""
        # Create event queue
        self.queue = EventQueue(
            db_path=db_path,
            max_queue_size=self.config.max_queue_size
        )

        # Create batch sender with circuit breaker
        circuit_breaker = CircuitBreaker()
        retry_policy = RetryPolicy(
            max_retries=self.config.retry_policy.max_retries,
            initial_delay_ms=self.config.retry_policy.initial_delay_ms,
            max_delay_ms=self.config.retry_policy.max_delay_ms,
            backoff_multiplier=self.config.retry_policy.backoff_multiplier,
            retry_on_status=self.config.retry_policy.retry_on_status
        )

        # Resolve endpoint (fallback to centralized config if empty)
        endpoint = self.config.endpoint
        if not endpoint:
            from raxe.infrastructure.config.endpoints import get_telemetry_endpoint
            endpoint = get_telemetry_endpoint()

        self.sender = BatchSender(
            endpoint=endpoint,
            api_key=self.api_key,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            compression=self.config.compression
        )

    def _start_flush_thread(self) -> None:
        """Start background thread for periodic flushing."""
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="telemetry-flush"
        )
        self._flush_thread.start()
        logger.debug("Started telemetry flush thread")

    def _flush_loop(self) -> None:
        """Background loop for periodic batch sending."""
        flush_interval = self.config.flush_interval_ms / 1000.0

        while not self._shutdown_event.is_set():
            try:
                # Wait for interval or shutdown signal
                if self._shutdown_event.wait(flush_interval):
                    break

                # Flush batch
                self._flush_batch()

            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    def _flush_batch(self) -> None:
        """Flush a batch of events to telemetry endpoint."""
        if not self.queue:
            return

        try:
            # Dequeue batch
            batch_id, events = self.queue.dequeue_batch(
                batch_size=self.config.batch_size
            )

            if not events:
                return

            # Convert to event dictionaries
            event_dicts = [event.to_dict() for event in events]

            # Send batch
            try:
                self.sender.send_batch(event_dicts)
                self.queue.mark_batch_sent(batch_id)
                logger.debug(f"Successfully sent batch {batch_id} with {len(events)} events")

            except Exception as e:
                # Mark batch as failed for retry
                retry_delay = min(
                    self.config.retry_policy.initial_delay_ms / 1000,
                    60
                )
                self.queue.mark_batch_failed(
                    batch_id,
                    str(e),
                    int(retry_delay)
                )
                logger.warning(f"Failed to send batch {batch_id}: {e}")

        except Exception as e:
            logger.error(f"Error flushing batch: {e}")

    def track_scan(
        self,
        scan_result: dict[str, Any],
        customer_id: str,
        context: dict[str, Any] | None = None
    ) -> str | None:
        """
        Track a scan event.

        Args:
            scan_result: Result from scan pipeline
            customer_id: Customer identifier
            context: Additional context

        Returns:
            Event ID if queued, None if disabled or sampled out
        """
        if not self.config.enabled or not self.queue:
            return None

        # Check sampling
        if not self.config.should_sample():
            return None

        try:
            # Extract performance metrics if enabled
            performance_metrics = None
            if self.config.send_performance_metrics:
                performance_metrics = self._extract_performance_metrics(scan_result)

            # Create privacy-preserving event (pure function)
            event = create_scan_event(
                scan_result=scan_result,
                customer_id=customer_id,
                api_key_id=self.api_key,
                context=context,
                performance_metrics=performance_metrics,
                hash_algorithm=self.config.hash_algorithm
            )

            # Calculate priority
            priority = self._calculate_priority(event)

            # Queue event
            event_id = self.queue.enqueue(
                event_type="scan_performed",
                payload=event,
                priority=priority
            )

            # If critical, flush immediately
            if priority == EventPriority.CRITICAL:
                self._flush_batch()

            return event_id

        except Exception as e:
            logger.error(f"Failed to track scan event: {e}")
            if self.config.send_error_reports:
                self._track_error(e, "track_scan")
            return None

    def _extract_performance_metrics(self, scan_result: dict[str, Any]) -> dict[str, Any]:
        """Extract performance metrics from scan result."""
        metrics = {}

        # Extract timing from scan result
        if "performance" in scan_result:
            perf = scan_result["performance"]
            metrics["total_ms"] = perf.get("total_ms", 0)
            metrics["l1_ms"] = perf.get("l1_ms", 0)
            metrics["l2_ms"] = perf.get("l2_ms", 0)
            metrics["policy_ms"] = perf.get("policy_ms", 0)

        # Add queue depth
        if self.queue:
            stats = self.queue.get_stats()
            metrics["queue_depth"] = stats.get("queue_depth", 0)

        # Add circuit breaker state
        if self.sender:
            metrics["circuit_breaker_status"] = self.sender.get_circuit_state()

        return metrics

    def _calculate_priority(self, event: dict[str, Any]) -> EventPriority:
        """Calculate event priority."""
        if "scan_result" in event:
            scan_result = event["scan_result"]

            # Critical threats get highest priority
            if scan_result.get("highest_severity") == "critical":
                return EventPriority.CRITICAL

            # Policy blocks are high priority
            if "policy_decision" in scan_result:
                if scan_result["policy_decision"].get("action") == "BLOCK":
                    return EventPriority.HIGH

            # High severity threats
            if scan_result.get("highest_severity") == "high":
                return EventPriority.HIGH

            # Any threat is medium
            if scan_result.get("threat_detected"):
                return EventPriority.MEDIUM

        return EventPriority.LOW

    def _track_error(self, error: Exception, context: str) -> None:
        """Track an error event."""
        if not self.config.send_error_reports or not self.queue:
            return

        try:
            error_event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context
            }

            self.queue.enqueue(
                event_type="error",
                payload=error_event,
                priority=EventPriority.LOW
            )
        except Exception as e:
            logger.debug(f"Failed to track error event: {e}")

    def get_stats(self) -> dict[str, Any]:
        """
        Get telemetry statistics.

        Returns:
            Dictionary with telemetry metrics
        """
        if not self.config.enabled or not self.queue:
            return {"enabled": False}

        stats = {
            "enabled": True,
            "endpoint": self.config.endpoint,
            "privacy_mode": self.config.privacy_mode,
            "queue_stats": self.queue.get_stats() if self.queue else {},
            "circuit_breaker_state": self.sender.get_circuit_state() if self.sender else "unknown"
        }

        return stats

    def flush(self) -> None:
        """Force flush of pending events."""
        if self.config.enabled and self.queue:
            self._flush_batch()

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shutdown telemetry.

        Args:
            timeout: Maximum time to wait for shutdown
        """
        if not self.config.enabled:
            return

        logger.info("Shutting down telemetry manager")

        # Signal shutdown
        self._shutdown_event.set()

        # Final flush attempt
        try:
            self.flush()
        except Exception as e:
            logger.error(f"Error during final flush: {e}")

        # Wait for flush thread to stop
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=timeout)
            if self._flush_thread.is_alive():
                logger.warning("Telemetry flush thread did not stop cleanly")

        logger.info("Telemetry manager shutdown complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.shutdown()