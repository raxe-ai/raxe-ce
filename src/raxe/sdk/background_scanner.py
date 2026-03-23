"""Background scan worker for non-blocking (fire-and-forget) scanning.

When ``execution_mode="background"`` is set on AgentScannerConfig, scans are
submitted to a BackgroundScanWorker which processes them on a daemon thread.
The caller returns immediately with a clean placeholder result.

Design follows the SIEMDispatcher pattern
(``src/raxe/infrastructure/siem/dispatcher.py``):
- Bounded queue with explicit drop on full
- Daemon worker thread(s) for serial processing
- Graceful drain on shutdown with configurable timeout
- Thread-safe stats

Usage:
    This module is an internal implementation detail of AgentScanner.
    Users configure background mode via ``AgentScannerConfig``:

        config = AgentScannerConfig(
            on_threat="log",
            execution_mode="background",
        )
        scanner = create_agent_scanner(raxe, config)
        result = scanner.scan_prompt("user input")  # returns immediately
"""

from __future__ import annotations

import concurrent.futures
import threading
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Full, Queue
from typing import TYPE_CHECKING, Any

from raxe.utils.logging import get_logger

if TYPE_CHECKING:
    from raxe.sdk.agent_scanner import AgentScanner, ScanType

logger = get_logger(__name__)


@dataclass
class BackgroundScanConfig:
    """Configuration for the background scan worker.

    Attributes:
        max_queue_size: Maximum pending scans before dropping.
        worker_count: Number of worker threads (default 1 = serial).
        drain_timeout_seconds: Max seconds to wait for drain on shutdown.
    """

    max_queue_size: int = 200
    worker_count: int = 1
    drain_timeout_seconds: float = 5.0
    scan_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_queue_size < 1:
            raise ValueError("max_queue_size must be >= 1")
        if self.worker_count < 1 or self.worker_count > 4:
            raise ValueError("worker_count must be between 1 and 4")
        if self.scan_timeout_seconds < 1.0:
            raise ValueError("scan_timeout_seconds must be >= 1.0")


@dataclass
class _ScanRequest:
    """Internal scan request queued for background processing.

    Attributes are frozen at submit-time so background execution sees
    the exact state that existed when the caller submitted the scan.
    """

    text: str
    scan_type: ScanType
    metadata: dict[str, Any] | None
    trace_id: str | None
    step_id: int
    block_on_threat: bool
    on_threat_callback: Callable | None


@dataclass
class BackgroundScanStats:
    """Thread-safe statistics for the background scanner."""

    submitted: int = 0
    completed: int = 0
    threats_found: int = 0
    dropped: int = 0
    errors: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "submitted": self.submitted,
            "completed": self.completed,
            "threats_found": self.threats_found,
            "dropped": self.dropped,
            "errors": self.errors,
        }


class BackgroundScanWorker:
    """Background worker that processes scan requests off the main thread.

    The worker uses a bounded queue. When the queue is full, new scans are
    dropped (logged at warning level) rather than blocking the caller.

    Each scan is executed via a dedicated timeout executor to prevent a
    hung ``raxe.scan()`` from stalling the worker indefinitely. The
    timeout is controlled by ``BackgroundScanConfig.scan_timeout_seconds``.

    Thread-safety: All public methods are safe to call from any thread.
    """

    def __init__(
        self,
        scanner: AgentScanner,
        config: BackgroundScanConfig | None = None,
    ) -> None:
        self._scanner = scanner
        self._config = config or BackgroundScanConfig()
        self._queue: Queue[_ScanRequest | None] = Queue(
            maxsize=self._config.max_queue_size,
        )
        self._running = False
        self._workers: list[threading.Thread] = []
        self._stats = BackgroundScanStats()
        self._stats_lock = threading.Lock()
        # Dedicated executor for timeout-guarded scans. Bounded to
        # worker_count+1 so at most one scan per worker can be in-flight,
        # plus one for a timed-out scan draining. This avoids creating a
        # new executor per request.
        self._timeout_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._config.worker_count + 1,
            thread_name_prefix="raxe-bg-timeout",
        )

    def start(self) -> None:
        """Start worker thread(s). Idempotent."""
        if self._running:
            return
        self._running = True
        for i in range(self._config.worker_count):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"raxe-bg-scan-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)

    def submit(self, request: _ScanRequest) -> bool:
        """Submit a scan request.

        Returns True if queued, False if dropped (queue full).
        """
        try:
            self._queue.put_nowait(request)
            with self._stats_lock:
                self._stats.submitted += 1
            return True
        except Full:
            with self._stats_lock:
                self._stats.dropped += 1
            logger.warning(
                "background_scan_dropped",
                extra={
                    "queue_size": self._queue.qsize(),
                    "max_queue_size": self._config.max_queue_size,
                },
            )
            return False

    def stop(self, flush: bool = True) -> None:
        """Stop worker thread(s).

        Args:
            flush: If True, drain remaining items before stopping.
        """
        if not self._running:
            return
        self._running = False

        # Send poison pills for each worker
        for _ in self._workers:
            try:
                self._queue.put_nowait(None)
            except Full:
                pass

        timeout_per_worker = self._config.drain_timeout_seconds / max(len(self._workers), 1)
        for w in self._workers:
            w.join(timeout=timeout_per_worker)
        self._workers.clear()

        # Shut down the timeout executor (abandoned futures drain on their own)
        self._timeout_executor.shutdown(wait=False)

    @property
    def stats(self) -> dict[str, int]:
        with self._stats_lock:
            return self._stats.to_dict()

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Drain the queue and process each scan request."""
        while self._running or not self._queue.empty():
            try:
                request = self._queue.get(timeout=1.0)
            except Empty:
                if not self._running:
                    break
                continue

            # Poison pill
            if request is None:
                break

            self._process_request(request)

    def _process_request(self, request: _ScanRequest) -> None:
        """Execute a single scan request with a timeout guard.

        Submits ``raxe.scan()`` into the worker's shared timeout executor
        and waits up to ``scan_timeout_seconds``. On timeout the future
        is abandoned (it will complete eventually on its own thread) and
        the worker moves on to the next queued scan.
        """
        try:
            future = self._timeout_executor.submit(
                self._scanner.raxe.scan,
                request.text,
                block_on_threat=False,  # Background mode never blocks inline
                integration_type=self._scanner.integration_type,
                l2_enabled=self._scanner.config.l2_enabled,
                tenant_id=self._scanner.config.tenant_id,
                app_id=self._scanner.config.app_id,
                policy_id=self._scanner.config.policy_id,
            )
            try:
                scan_result = future.result(timeout=self._config.scan_timeout_seconds)
            except concurrent.futures.TimeoutError:
                with self._stats_lock:
                    self._stats.errors += 1
                logger.warning(
                    "background_scan_timeout",
                    extra={
                        "timeout_seconds": self._config.scan_timeout_seconds,
                    },
                )
                return

            with self._stats_lock:
                self._stats.completed += 1

            if scan_result is not None and scan_result.has_threats:
                with self._stats_lock:
                    self._stats.threats_found += 1

                # Fire on_threat callback from worker thread
                if request.on_threat_callback is not None:
                    try:
                        agent_result = self._scanner._build_result(
                            scan_type=request.scan_type,
                            has_threats=True,
                            should_block=False,  # Background mode never blocks
                            severity=scan_result.severity,
                            detection_count=scan_result.total_detections,
                            duration_ms=0.0,
                            message=f"Background scan: {scan_result.severity}",
                            details=request.metadata,
                            content=request.text,
                            trace_id_override=request.trace_id,
                            step_id_override=request.step_id,
                        )
                        request.on_threat_callback(agent_result)
                    except Exception as e:
                        logger.debug(f"on_threat_callback error: {e}")

        except Exception as e:
            with self._stats_lock:
                self._stats.errors += 1
            logger.debug(f"Background scan error: {e}")
