"""
Unified telemetry flush helper.

This module provides a centralized function for flushing telemetry events
that can be used by all entry points (CLI commands, SDK, decorators, etc.).

The goal is to ensure telemetry is NEVER lost regardless of how scans are invoked.

Usage:
    from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

    # At the end of any scan-producing code path:
    ensure_telemetry_flushed()

    # For batch operations with more events:
    ensure_telemetry_flushed(timeout_seconds=5.0, max_batches=50)

    # On startup, flush stale events from previous sessions:
    flush_stale_telemetry_async()
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def ensure_telemetry_flushed(
    timeout_seconds: float = 2.0,
    max_batches: int = 10,
    batch_size: int = 50,
    end_session: bool = True,
) -> None:
    """Ensure all queued telemetry events are flushed before process exit.

    This is the UNIFIED function that should be called by all entry points
    to ensure telemetry is sent. It handles:
    - Ending the active session (if any)
    - Flushing critical queue first (high-severity threats)
    - Flushing standard queue second (clean scans, etc.)
    - Graceful timeout to keep CLI responsive

    Args:
        timeout_seconds: Maximum time to wait for flush (default: 2s).
            Increase for batch operations with many events.
        max_batches: Maximum number of batches to flush per queue (default: 10).
            Each batch is up to batch_size events. Increase for large batches.
        batch_size: Events per batch (default: 50).
        end_session: Whether to end the telemetry session first (default: True).
            This ensures session_end event is queued before flush.

    Features:
    - Thread-safe: Uses non-daemon thread with timeout
    - Critical-first: Flushes threat events before clean scans
    - Best-effort: Failures are silently ignored (never breaks caller)
    - Configurable: Adjust timeout/batches for different use cases

    Example:
        # CLI command (short-lived)
        ensure_telemetry_flushed(timeout_seconds=2.0)

        # Batch command (many events)
        ensure_telemetry_flushed(timeout_seconds=10.0, max_batches=100)

        # SDK cleanup
        ensure_telemetry_flushed(timeout_seconds=5.0, end_session=True)
    """
    def _do_flush() -> None:
        try:
            # End session first (if requested) to queue session_end event
            if end_session:
                _end_telemetry_session()

            # Get credentials and check if telemetry is enabled
            api_key, installation_id, config = _get_telemetry_context()
            if not api_key or not config or not config.telemetry.enabled:
                return

            # Get queue and check if there's anything to flush
            queue = _get_queue()
            if not queue:
                return

            stats = queue.get_stats()
            total = stats.get("critical_count", 0) + stats.get("standard_count", 0)

            if total == 0:
                # Nothing to flush - queue stays open for future events
                return

            # Create sender
            sender = _create_sender(config, api_key, installation_id, queue)
            if not sender:
                return

            # Flush critical events first (high-severity threats)
            _flush_queue(queue, sender, "critical", max_batches, batch_size)

            # Then standard events (clean scans, etc.)
            _flush_queue(queue, sender, "standard", max_batches, batch_size)

            # NOTE: Do NOT close the queue here. The queue is a singleton
            # managed by the orchestrator and should persist for the process lifetime.
        except Exception:
            pass  # Best effort - NEVER fail or break caller

    # Start flush in non-daemon thread (ensures completion with timeout)
    thread = threading.Thread(target=_do_flush, name="TelemetryFlush")
    thread.start()

    # Wait with timeout to keep caller responsive
    thread.join(timeout=timeout_seconds)


def _end_telemetry_session() -> None:
    """End the active telemetry session (if any).

    This queues a session_end event before the flush.
    """
    try:
        from raxe.application.telemetry_orchestrator import get_orchestrator

        orchestrator = get_orchestrator()
        if orchestrator:
            tracker = orchestrator._session_tracker
            if tracker and tracker.is_session_active:
                tracker.end_session(end_reason="normal")
    except Exception:
        pass  # Never fail


def _get_telemetry_context():
    """Get telemetry credentials and config.

    Returns:
        Tuple of (api_key, installation_id, config) or (None, None, None) on error.
    """
    try:
        from raxe.cli.telemetry import _get_api_credentials, _get_config

        api_key, installation_id, _ = _get_api_credentials()
        config = _get_config()
        return api_key, installation_id, config
    except Exception:
        return None, None, None


def _get_queue():
    """Get the telemetry queue instance.

    Returns:
        DualPriorityQueue instance or None on error.
    """
    try:
        from raxe.cli.telemetry import _get_queue_instance

        return _get_queue_instance()
    except Exception:
        return None


def _create_sender(config, api_key: str, installation_id: str, queue):
    """Create a BatchSender for sending telemetry.

    Args:
        config: ScanConfig instance
        api_key: API key for authentication
        installation_id: Installation ID
        queue: Queue instance (unused, kept for API compatibility)

    Returns:
        BatchSender instance or None on error.
    """
    try:
        from raxe.infrastructure.config.endpoints import get_telemetry_endpoint
        from raxe.infrastructure.telemetry.sender import BatchSender

        # Resolve endpoint (fallback to centralized config if empty)
        endpoint = config.telemetry.endpoint
        if not endpoint:
            endpoint = get_telemetry_endpoint()

        # NOTE: Don't pass api_key_id - let the sender compute it from api_key.
        # This ensures events are tagged with the CURRENT key's ID, not a stale
        # ID from queue state. The backend uses the authenticated key's ID for
        # event correlation (key_info.key_id), so client_api_key_id is only needed
        # during explicit key upgrade migrations.
        return BatchSender(
            endpoint=endpoint,
            api_key=api_key,
            installation_id=installation_id,
        )
    except Exception:
        return None


def _flush_queue(queue, sender, queue_type: str, max_batches: int, batch_size: int) -> None:
    """Flush events from a specific queue.

    Args:
        queue: DualPriorityQueue instance
        sender: BatchSender instance
        queue_type: "critical" or "standard"
        max_batches: Maximum batches to flush
        batch_size: Events per batch
    """
    try:
        dequeue_fn = queue.dequeue_critical if queue_type == "critical" else queue.dequeue_standard
        consecutive_errors = 0
        max_consecutive_errors = 3  # Stop after 3 consecutive failures

        for _ in range(max_batches):
            events = dequeue_fn(batch_size=batch_size)
            if not events:
                break
            try:
                sender.send_batch(events)
                event_ids = [str(e.get("event_id")) for e in events if e.get("event_id")]
                queue.mark_batch_sent(event_ids)
                consecutive_errors = 0  # Reset on success
            except Exception as e:
                consecutive_errors += 1
                # Mark events for retry instead of abandoning them
                event_ids = [str(e.get("event_id")) for e in events if e.get("event_id")]
                queue.mark_batch_failed(event_ids, f"send_error: {e}", 60)
                if consecutive_errors >= max_consecutive_errors:
                    break  # Stop only after multiple consecutive failures
    except Exception:
        pass  # Never fail


def flush_stale_telemetry_async(
    stale_threshold_minutes: float = 15.0,
    timeout_seconds: float = 10.0,
    max_batches: int = 50,
) -> None:
    """Flush stale telemetry events from previous sessions (non-blocking).

    This function should be called on startup (SDK init, CLI startup) to recover
    events that were queued but never flushed due to:
    - Process killed (SIGKILL)
    - Crash before flush
    - SDK used without proper cleanup (no context manager, no close())

    The function first checks if there are stale events (fast, <10ms), then
    spawns a background thread only if flushing is needed. The flush thread
    is non-daemon with a short join timeout, ensuring events are sent even
    for short-lived CLI commands.

    Args:
        stale_threshold_minutes: Only flush if oldest event is older than this (default: 15).
            This prevents flushing events that would be flushed normally by the 5-minute timer.
        timeout_seconds: Maximum time for the flush operation (default: 10s).
            Allows more time since this is recovering potentially many events.
        max_batches: Maximum batches to flush (default: 50).
            Higher than normal to recover large backlogs.

    Example:
        # In SDK __init__:
        flush_stale_telemetry_async()

        # In CLI startup:
        flush_stale_telemetry_async(stale_threshold_minutes=10.0)
    """
    try:
        # Quick check if there are stale events (fast, synchronous)
        queue = _get_queue()
        if not queue:
            return

        stats = queue.get_stats()
        total_queued = stats.get("total_queued", 0)

        if total_queued == 0:
            # No stale events - queue stays open for future events
            return

        # Check if events are stale
        oldest_critical = stats.get("oldest_critical")
        oldest_standard = stats.get("oldest_standard")

        # Find the oldest event timestamp
        oldest = None
        if oldest_critical and oldest_standard:
            oldest = min(oldest_critical, oldest_standard)
        elif oldest_critical:
            oldest = oldest_critical
        elif oldest_standard:
            oldest = oldest_standard

        if not oldest:
            # No timestamp info - queue stays open
            return

        # Parse timestamp if it's a string
        from datetime import datetime, timezone

        if isinstance(oldest, str):
            # Handle ISO format with timezone
            oldest = datetime.fromisoformat(oldest.replace("Z", "+00:00"))

        # Calculate age
        now = datetime.now(timezone.utc)
        age_minutes = (now - oldest).total_seconds() / 60

        # NOTE: Do NOT close the queue here. The queue is a singleton
        # managed by the orchestrator and should persist for the process lifetime.

        # Only flush if events are stale (older than threshold)
        if age_minutes < stale_threshold_minutes:
            return  # Events are not stale yet

        # Events are stale - flush them
        # Use ensure_telemetry_flushed which handles the threading
        # and waits for completion with timeout
        def _do_stale_flush() -> None:
            try:
                ensure_telemetry_flushed(
                    timeout_seconds=timeout_seconds,
                    max_batches=max_batches,
                    batch_size=50,
                    end_session=False,  # Don't end session on startup
                )
            except Exception:
                pass

        # Run flush in background but wait briefly to ensure it starts
        # Using non-daemon thread so it can complete even if main exits quickly
        thread = threading.Thread(
            target=_do_stale_flush,
            name="TelemetryStaleFlush",
            daemon=False,  # Non-daemon: let it complete
        )
        thread.start()

        # Wait briefly to let flush get started and make progress
        # This balance: don't block startup too long, but give flush a chance
        thread.join(timeout=min(timeout_seconds, 5.0))

    except Exception:
        pass  # Never fail or block startup
