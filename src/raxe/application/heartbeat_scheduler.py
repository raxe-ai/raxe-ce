"""Agent Heartbeat Scheduler for MSSP ecosystem.

Responsible for:
1. Sending periodic heartbeat events to track agent health
2. Configurable interval (per customer settings)
3. Tracking uptime and scan counts since last heartbeat
4. Non-blocking operation with background thread

The heartbeat system enables:
- MSSP SOC visibility into agent health
- Configurable offline detection thresholds per customer
- Agent status tracking (online/offline/degraded)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raxe.application.telemetry_orchestrator import TelemetryOrchestrator

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Scheduler for periodic heartbeat events.

    Sends heartbeat events at configurable intervals to indicate agent health.
    Tracks scan counts, threat counts, and uptime between heartbeats.

    Thread-safe for recording scans/threats from multiple threads.

    Example:
        >>> scheduler = HeartbeatScheduler(interval_seconds=60)
        >>> scheduler.start()
        >>> # ... agent does work ...
        >>> scheduler.record_scan()
        >>> scheduler.record_threat()
        >>> # ... later ...
        >>> scheduler.stop()
    """

    def __init__(
        self,
        interval_seconds: int = 60,
        *,
        mssp_id: str | None = None,
        customer_id: str | None = None,
        agent_id: str | None = None,
        orchestrator: TelemetryOrchestrator | None = None,
    ) -> None:
        """Initialize heartbeat scheduler.

        Args:
            interval_seconds: Interval between heartbeats (default 60s)
            mssp_id: MSSP identifier (optional)
            customer_id: Customer identifier (optional)
            agent_id: Agent identifier (optional)
            orchestrator: Telemetry orchestrator (lazy-loaded if None)
        """
        self.interval_seconds = interval_seconds
        self.mssp_id = mssp_id
        self.customer_id = customer_id
        self.agent_id = agent_id

        # Orchestrator for sending heartbeat events
        self._orchestrator = orchestrator

        # Counters (thread-safe)
        self._scans_since_last_heartbeat = 0
        self._threats_since_last_heartbeat = 0
        self._counter_lock = threading.Lock()

        # Uptime tracking
        self._start_time: float | None = None

        # Background thread
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    @property
    def scans_since_last_heartbeat(self) -> int:
        """Get scans counted since last heartbeat."""
        with self._counter_lock:
            return self._scans_since_last_heartbeat

    @property
    def threats_since_last_heartbeat(self) -> int:
        """Get threats counted since last heartbeat."""
        with self._counter_lock:
            return self._threats_since_last_heartbeat

    @property
    def uptime_seconds(self) -> float:
        """Get uptime since scheduler started."""
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def orchestrator(self) -> TelemetryOrchestrator:
        """Lazy-load telemetry orchestrator."""
        if self._orchestrator is None:
            from raxe.application.telemetry_orchestrator import get_orchestrator

            self._orchestrator = get_orchestrator()
        return self._orchestrator

    def record_scan(self) -> None:
        """Record a scan for the next heartbeat.

        Thread-safe: can be called from multiple threads.
        """
        with self._counter_lock:
            self._scans_since_last_heartbeat += 1

    def record_threat(self) -> None:
        """Record a threat detection for the next heartbeat.

        Thread-safe: can be called from multiple threads.
        """
        with self._counter_lock:
            self._threats_since_last_heartbeat += 1

    def start(self) -> None:
        """Start the heartbeat scheduler.

        Begins sending periodic heartbeats in a background thread.
        Safe to call multiple times (subsequent calls are no-ops).
        """
        if self._running:
            logger.debug("HeartbeatScheduler already running")
            return

        self._running = True
        self._stop_event.clear()
        self._start_time = time.monotonic()

        # Start background thread
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="heartbeat-scheduler",
        )
        self._thread.start()

        logger.info(
            f"HeartbeatScheduler started (interval={self.interval_seconds}s, "
            f"mssp_id={self.mssp_id}, customer_id={self.customer_id})"
        )

    def stop(self) -> None:
        """Stop the heartbeat scheduler.

        Signals the background thread to stop. Safe to call multiple times.
        """
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        # Wait for thread to finish (with timeout)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        logger.info("HeartbeatScheduler stopped")

    def _heartbeat_loop(self) -> None:
        """Background loop that sends periodic heartbeats."""
        while not self._stop_event.is_set():
            # Wait for interval or stop signal
            if self._stop_event.wait(timeout=self.interval_seconds):
                # Stop was requested
                break

            # Send heartbeat
            try:
                self._send_heartbeat()
            except Exception as e:
                # Never crash the heartbeat loop
                logger.warning(f"Heartbeat send failed: {e}")

    def _send_heartbeat(self) -> None:
        """Send a heartbeat event and reset counters."""
        import sys

        from raxe import __version__

        # Get current counters
        with self._counter_lock:
            scans = self._scans_since_last_heartbeat
            threats = self._threats_since_last_heartbeat

        # Send heartbeat via orchestrator
        self.orchestrator.track_heartbeat(
            uptime_seconds=self.uptime_seconds,
            scans_since_last_heartbeat=scans,
            threats_since_last_heartbeat=threats,
            mssp_id=self.mssp_id,
            customer_id=self.customer_id,
            agent_id=self.agent_id,
        )

        # Register heartbeat in AgentRegistry (for MSSP agent tracking)
        if self.mssp_id and self.customer_id and self.agent_id:
            try:
                from raxe.infrastructure.agent.registry import get_agent_registry

                registry = get_agent_registry()
                status_change = registry.register_heartbeat(
                    agent_id=self.agent_id,
                    mssp_id=self.mssp_id,
                    customer_id=self.customer_id,
                    version=__version__,
                    platform=sys.platform,
                    uptime_seconds=self.uptime_seconds,
                    scans=scans,
                    threats=threats,
                )

                # Send status change event if status changed
                if status_change:
                    self.orchestrator.track_agent_status_change(
                        agent_id=status_change["agent_id"],
                        previous_status=status_change["previous_status"],
                        new_status=status_change["new_status"],
                        reason=status_change["reason"],
                        mssp_id=status_change.get("mssp_id"),
                        customer_id=status_change.get("customer_id"),
                        agent_version=status_change.get("agent_version"),
                        platform=status_change.get("platform"),
                    )
            except Exception as e:
                # Never let registry issues block heartbeat
                logger.debug(f"AgentRegistry update failed: {e}")

        # Reset counters
        self._reset_counters()

        logger.debug(
            f"Heartbeat sent: uptime={self.uptime_seconds:.1f}s, scans={scans}, threats={threats}"
        )

    def _reset_counters(self) -> None:
        """Reset scan and threat counters after heartbeat."""
        with self._counter_lock:
            self._scans_since_last_heartbeat = 0
            self._threats_since_last_heartbeat = 0


def create_heartbeat_scheduler(
    interval_seconds: int = 60,
    *,
    mssp_id: str | None = None,
    customer_id: str | None = None,
    agent_id: str | None = None,
) -> HeartbeatScheduler:
    """Factory function to create a heartbeat scheduler.

    Args:
        interval_seconds: Interval between heartbeats
        mssp_id: MSSP identifier
        customer_id: Customer identifier
        agent_id: Agent identifier

    Returns:
        HeartbeatScheduler instance
    """
    return HeartbeatScheduler(
        interval_seconds=interval_seconds,
        mssp_id=mssp_id,
        customer_id=customer_id,
        agent_id=agent_id,
    )


__all__ = [
    "HeartbeatScheduler",
    "create_heartbeat_scheduler",
]
