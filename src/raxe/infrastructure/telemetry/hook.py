"""Privacy-first telemetry hook.

Sends privacy-preserving telemetry to RAXE cloud (optional).

CRITICAL PRIVACY REQUIREMENTS:
- NEVER send actual prompt/response text
- ONLY send hashes (SHA256, non-reversible)
- ONLY send aggregated metadata (counts, severities, latencies)
- User must explicitly opt-in
- Graceful failure - never break scans

What we send:
✅ Text hash (SHA256)
✅ Detection counts
✅ Severity levels
✅ Performance metrics
✅ Customer ID (for analytics)
✅ Timestamp

What we NEVER send:
❌ Actual text content
❌ Pattern matches
❌ PII of any kind
❌ User data
"""
import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TelemetryConfig:
    """Telemetry configuration.

    Attributes:
        enabled: Enable telemetry sending
        api_key: RAXE API key (optional)
        endpoint: Cloud endpoint for telemetry (uses centralized config if empty)
        batch_size: Events to batch before sending
        flush_interval_seconds: Max time to wait before flushing batch
        max_queue_size: Max events to queue before dropping
        async_send: Send in background thread
    """
    enabled: bool = False
    api_key: str | None = None
    endpoint: str = ""  # Will use centralized config if empty
    batch_size: int = 10
    flush_interval_seconds: float = 30.0
    max_queue_size: int = 1000
    async_send: bool = True


class TelemetryHook:
    """Privacy-first telemetry sender.

    Queues and batches telemetry events for efficient sending.
    All events are privacy-preserving (hashes only, no PII).

    Thread-safe for concurrent use.

    Example usage:
        config = TelemetryConfig(
            enabled=True,
            api_key="raxe_live_...",
        )
        hook = TelemetryHook(config)

        # Send telemetry (async, batched)
        hook.send({
            "text_hash": hash_text(prompt),
            "detections": 2,
            "severity": "high",
        })

        # Flush and shutdown
        hook.shutdown()
    """

    def __init__(self, config: TelemetryConfig):
        """Initialize telemetry hook.

        Args:
            config: Telemetry configuration
        """
        self.config = config
        self._queue: Queue = Queue(maxsize=config.max_queue_size)
        self._batch: list[dict[str, Any]] = []
        self._last_flush_time = time.time()
        self._lock = threading.Lock()
        self._shutdown = False

        # Statistics
        self._events_sent = 0
        self._events_dropped = 0
        self._send_errors = 0

        # Background sender thread (if async)
        self._sender_thread: threading.Thread | None = None
        if config.async_send and config.enabled:
            self._sender_thread = threading.Thread(
                target=self._background_sender,
                daemon=True,
                name="telemetry-sender"
            )
            self._sender_thread.start()

    def send(self, payload: dict[str, Any]) -> None:
        """Send telemetry event.

        Queues event for batched sending. Never blocks scanning.

        Args:
            payload: Event payload (must be privacy-preserving)

        Note:
            This method never raises exceptions. Errors are logged.
        """
        if not self.config.enabled:
            return

        # Validate payload is privacy-safe
        if not self._is_privacy_safe(payload):
            logger.error(
                "Attempted to send unsafe telemetry payload (contains PII?). "
                "Payload rejected."
            )
            return

        try:
            # Add timestamp
            payload["telemetry_timestamp"] = datetime.now(timezone.utc).isoformat()

            # Add to queue (non-blocking)
            self._queue.put_nowait(payload)

        except Exception as e:
            # Queue full or other error - drop event
            self._events_dropped += 1
            logger.warning(
                f"Failed to queue telemetry event: {e}. "
                f"Dropped {self._events_dropped} events so far."
            )

    def _is_privacy_safe(self, payload: dict[str, Any]) -> bool:
        """Validate payload doesn't contain PII.

        Checks for suspicious keys that might contain actual text.

        Args:
            payload: Event payload

        Returns:
            True if payload appears safe (no PII)
        """
        # Forbidden keys that might contain PII
        forbidden_keys = {
            "text", "prompt", "response", "message", "content",
            "input", "output", "data", "body", "user_input",
        }

        # Check for forbidden keys
        for key in payload.keys():
            if key.lower() in forbidden_keys:
                logger.error(
                    f"Payload contains forbidden key '{key}' that may contain PII"
                )
                return False

        # Check for suspiciously long string values (might be text)
        for key, value in payload.items():
            if isinstance(value, str) and len(value) > 200:
                # Hashes are 64 chars (SHA256), UUIDs are 36 chars
                # Anything >200 chars is suspicious
                if key not in {"text_hash", "hash"}:
                    logger.error(
                        f"Payload contains suspiciously long string in '{key}' "
                        f"({len(value)} chars). Possible PII?"
                    )
                    return False

        return True

    def _background_sender(self) -> None:
        """Background thread for sending batches.

        Runs continuously, flushing batches when:
        - Batch size reached
        - Flush interval elapsed
        - Shutdown requested
        """
        logger.info("Telemetry background sender started")

        while not self._shutdown:
            try:
                # Wait for events with timeout
                try:
                    event = self._queue.get(timeout=1.0)
                    with self._lock:
                        self._batch.append(event)
                except Empty:
                    # No events, check if we should flush anyway
                    pass

                # Check if we should flush
                should_flush = False
                with self._lock:
                    # Flush if batch size reached
                    if len(self._batch) >= self.config.batch_size:
                        should_flush = True

                    # Flush if interval elapsed (and batch not empty)
                    elapsed = time.time() - self._last_flush_time
                    if self._batch and elapsed >= self.config.flush_interval_seconds:
                        should_flush = True

                if should_flush:
                    self._flush_batch()

            except Exception as e:
                logger.error(f"Error in telemetry background sender: {e}")
                time.sleep(1.0)  # Back off on errors

        logger.info("Telemetry background sender stopped")

    def _flush_batch(self) -> None:
        """Flush current batch to cloud.

        Sends batched events to RAXE cloud API.
        """
        with self._lock:
            if not self._batch:
                return

            batch = self._batch.copy()
            self._batch.clear()
            self._last_flush_time = time.time()

        # Send batch (outside lock)
        try:
            self._send_batch(batch)
            self._events_sent += len(batch)
            logger.debug(f"Sent telemetry batch of {len(batch)} events")
        except Exception as e:
            self._send_errors += 1
            logger.error(f"Failed to send telemetry batch: {e}")
            # Events are lost (fail_open behavior for telemetry)

    def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        """Send batch to cloud API.

        Args:
            batch: List of events to send

        Note:
            This is a stub implementation. Real version would use
            HTTP client to POST to cloud endpoint.
        """
        # TODO: Replace with real HTTP client (Phase 3d)
        # For now, just log (MVP behavior)
        logger.debug(
            f"[STUB] Would send {len(batch)} telemetry events to {self.config.endpoint}"
        )

        # Future implementation:
        # import requests
        # headers = {
        #     "Authorization": f"Bearer {self.config.api_key}",
        #     "Content-Type": "application/json",
        # }
        # response = requests.post(
        #     self.config.endpoint,
        #     json={"events": batch},
        #     headers=headers,
        #     timeout=5.0,
        # )
        # response.raise_for_status()

    def flush(self) -> None:
        """Force flush current batch immediately.

        Blocks until batch is sent.
        """
        self._flush_batch()

    def shutdown(self, timeout: float = 5.0) -> None:
        """Shutdown telemetry hook gracefully.

        Flushes remaining events and stops background thread.

        Args:
            timeout: Max seconds to wait for shutdown
        """
        logger.info("Shutting down telemetry hook")
        self._shutdown = True

        # Flush remaining events
        self.flush()

        # Wait for background thread
        if self._sender_thread and self._sender_thread.is_alive():
            self._sender_thread.join(timeout=timeout)

        logger.info(
            f"Telemetry shutdown complete. "
            f"Sent: {self._events_sent}, Dropped: {self._events_dropped}, "
            f"Errors: {self._send_errors}"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get telemetry statistics.

        Returns:
            Dictionary with telemetry metrics
        """
        with self._lock:
            queue_size = self._queue.qsize()
            batch_size = len(self._batch)

        return {
            "enabled": self.config.enabled,
            "events_sent": self._events_sent,
            "events_dropped": self._events_dropped,
            "send_errors": self._send_errors,
            "queue_size": queue_size,
            "batch_size": batch_size,
        }


def hash_text(text: str) -> str:
    """Create privacy-preserving hash of text.

    Uses SHA256 to create non-reversible hash.

    Args:
        text: Text to hash

    Returns:
        Hex-encoded SHA256 hash (64 chars)
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
