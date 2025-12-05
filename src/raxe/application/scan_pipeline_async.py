"""Async parallel scan pipeline with concurrent L1/L2 execution.

This module provides async scanning that runs L1 (regex) and L2 (ML) detection
in parallel, reducing total latency from ~53ms (sequential) to ~50ms (parallel).

Key benefits:
- L1 and L2 run concurrently (not sequentially)
- Total latency = max(L1, L2) instead of L1 + L2
- Smart cancellation: L2 cancelled if CRITICAL detected in L1
- Graceful degradation: timeouts don't block the scan
- Better resource utilization: CPU and GPU work in parallel

Performance:
- Sequential (current): L1 (3ms) + L2 (50ms) = 53ms
- Parallel (async): max(L1: 3ms, L2: 50ms) = 50ms (5.6% faster)
- CRITICAL fast path: 3ms (L2 cancelled)

Example:
    async with AsyncRaxe() as raxe:
        result = await raxe.scan("Ignore all instructions")
        print(f"Latency: {result.duration_ms}ms")  # ~50ms
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from raxe.application.scan_merger import CombinedScanResult, ScanMerger
from raxe.domain.engine.executor import RuleExecutor, ScanResult
from raxe.domain.ml.protocol import L2Detector, L2Result
from raxe.domain.rules.models import Severity
from raxe.infrastructure.packs.registry import PackRegistry
from raxe.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AsyncScanMetrics:
    """Performance metrics for async parallel scan."""
    l1_start_time: float
    l1_end_time: float
    l1_duration_ms: float
    l2_start_time: float | None
    l2_end_time: float | None
    l2_duration_ms: float
    l2_cancelled: bool
    l2_timeout: bool
    parallel_speedup: float  # (L1 + L2) / max(L1, L2)
    total_duration_ms: float


@dataclass(frozen=True)
class AsyncScanPipelineResult:
    """Result from async parallel scan pipeline."""
    scan_result: CombinedScanResult
    duration_ms: float
    text_hash: str
    metadata: dict[str, Any]
    metrics: AsyncScanMetrics | None = None

    @property
    def has_threats(self) -> bool:
        """True if any threats detected."""
        return self.scan_result.has_threats

    @property
    def l1_detections(self) -> int:
        """Count of L1 detections."""
        return len(self.scan_result.l1_detections or [])

    @property
    def l2_detections(self) -> int:
        """Count of L2 predictions."""
        return len(self.scan_result.l2_predictions or [])


class AsyncScanPipeline:
    """Async parallel scan pipeline with concurrent L1/L2 execution.

    This pipeline runs L1 (regex) and L2 (ML) detection concurrently to minimize
    total latency. Results are merged after both complete.

    Architecture:
        1. Start L1 and L2 tasks in parallel
        2. Wait for L1 first (fast path)
        3. Check if L2 should be cancelled (CRITICAL optimization)
        4. Wait for L2 or timeout
        5. Merge results and return

    Performance targets:
        - fast mode: <5ms (L1 only)
        - balanced mode: <55ms (parallel L1+L2)
        - thorough mode: <160ms (parallel L1+L2 with timeout)
    """

    def __init__(
        self,
        pack_registry: PackRegistry,
        rule_executor: RuleExecutor,
        l2_detector: L2Detector,
        scan_merger: ScanMerger,
        *,
        enable_l2: bool = True,
        fail_fast_on_critical: bool = True,
        min_confidence_for_skip: float = 0.7,
        l1_timeout_ms: float = 10.0,
        l2_timeout_ms: float = 150.0,
    ):
        """Initialize async scan pipeline.

        Args:
            pack_registry: Pack registry for loading rules
            rule_executor: L1 rule execution engine
            l2_detector: L2 ML detector
            scan_merger: Result merger
            enable_l2: Enable L2 analysis (default: True)
            fail_fast_on_critical: Cancel L2 if CRITICAL detected (optimization)
            min_confidence_for_skip: Minimum L1 confidence to skip L2 on CRITICAL
            l1_timeout_ms: L1 timeout in milliseconds (default: 10ms)
            l2_timeout_ms: L2 timeout in milliseconds (default: 150ms)
        """
        self.pack_registry = pack_registry
        self.rule_executor = rule_executor
        self.l2_detector = l2_detector
        self.scan_merger = scan_merger
        self.enable_l2 = enable_l2
        self.fail_fast_on_critical = fail_fast_on_critical
        self.min_confidence_for_skip = min_confidence_for_skip
        self.l1_timeout_ms = l1_timeout_ms
        self.l2_timeout_ms = l2_timeout_ms

        logger.info(
            "AsyncScanPipeline initialized",
            enable_l2=enable_l2,
            fail_fast_on_critical=fail_fast_on_critical,
            l1_timeout_ms=l1_timeout_ms,
            l2_timeout_ms=l2_timeout_ms,
        )

    async def scan(
        self,
        text: str,
        *,
        customer_id: str | None = None,
        context: dict[str, Any] | None = None,
        l1_enabled: bool = True,
        l2_enabled: bool = True,
        mode: str = "balanced",
    ) -> AsyncScanPipelineResult:
        """Execute async parallel scan with L1 and L2 running concurrently.

        Args:
            text: Text to scan
            customer_id: Optional customer ID
            context: Optional context metadata
            l1_enabled: Enable L1 detection (default: True)
            l2_enabled: Enable L2 detection (default: True)
            mode: Performance mode (fast/balanced/thorough)

        Returns:
            AsyncScanPipelineResult with scan results and metrics

        Raises:
            ValueError: If text is empty or mode is invalid
        """
        if not text:
            raise ValueError("Text cannot be empty")

        if mode not in ("fast", "balanced", "thorough"):
            raise ValueError(f"Invalid mode: {mode}")

        # Apply mode-specific settings
        if mode == "fast":
            l1_enabled = True
            l2_enabled = False
        elif mode == "thorough":
            l1_enabled = True
            l2_enabled = True

        start_time = time.perf_counter()
        scan_timestamp = datetime.now(timezone.utc).isoformat()

        # Load rules
        rules = self.pack_registry.get_all_rules()

        # Track metrics
        l1_start = time.perf_counter()
        l1_end = 0.0
        l2_start = 0.0
        l2_end = 0.0
        l2_cancelled = False
        l2_timeout = False

        # Create tasks for parallel execution
        tasks = {}

        if l1_enabled:
            tasks["l1"] = asyncio.create_task(
                self._run_l1_async(text, rules),
                name="L1-detection"
            )

        if l2_enabled and self.enable_l2 and mode != "fast":
            l2_start = time.perf_counter()
            tasks["l2"] = asyncio.create_task(
                self._run_l2_async(text, context),
                name="L2-detection"
            )

        # Wait for L1 first (fast path)
        l1_result = None
        if "l1" in tasks:
            try:
                l1_result = await asyncio.wait_for(
                    tasks["l1"],
                    timeout=self.l1_timeout_ms / 1000
                )
                l1_end = time.perf_counter()
            except asyncio.TimeoutError:
                logger.warning(f"L1 timeout after {self.l1_timeout_ms}ms")
                l1_result = self._create_empty_l1_result(text, scan_timestamp)
                l1_end = time.perf_counter()
        else:
            # L1 disabled - create empty result
            l1_result = self._create_empty_l1_result(text, scan_timestamp)

        # Check if we should cancel L2 (CRITICAL optimization)
        l2_result = None
        if "l2" in tasks:
            should_cancel = self._should_cancel_l2(l1_result)

            if should_cancel:
                # Cancel L2 task
                tasks["l2"].cancel()
                l2_cancelled = True
                l2_end = time.perf_counter()
                logger.info(
                    "l2_cancelled_critical",
                    reason="high_confidence_critical_detected",
                    l1_severity="CRITICAL",
                    text_hash=self._hash_text(text),
                )
            else:
                # Wait for L2 with timeout
                try:
                    l2_result = await asyncio.wait_for(
                        tasks["l2"],
                        timeout=self.l2_timeout_ms / 1000
                    )
                    l2_end = time.perf_counter()
                except asyncio.TimeoutError:
                    logger.warning(f"L2 timeout after {self.l2_timeout_ms}ms")
                    l2_timeout = True
                    l2_end = time.perf_counter()
                except asyncio.CancelledError:
                    l2_cancelled = True
                    l2_end = time.perf_counter()

        # Calculate timings
        l1_duration_ms = (l1_end - l1_start) * 1000 if l1_end > 0 else 0.0
        l2_duration_ms = (l2_end - l2_start) * 1000 if l2_start > 0 and l2_end > 0 else 0.0

        # Calculate parallel speedup
        sequential_time = l1_duration_ms + l2_duration_ms
        parallel_time = max(l1_duration_ms, l2_duration_ms)
        parallel_speedup = sequential_time / parallel_time if parallel_time > 0 else 1.0

        # Merge results
        metadata: dict[str, Any] = {
            "customer_id": customer_id,
            "scan_timestamp": scan_timestamp,
            "rules_loaded": len(rules),
            "l2_skipped": self.enable_l2 and l2_result is None,
            "l1_duration_ms": l1_duration_ms,
            "l2_duration_ms": l2_duration_ms,
            "mode": mode,
            "l1_enabled": l1_enabled,
            "l2_enabled": l2_enabled,
            "l2_cancelled": l2_cancelled,
            "l2_timeout": l2_timeout,
            "execution_mode": "async_parallel",
        }

        if context:
            metadata["context"] = context

        combined_result = self.scan_merger.merge(
            l1_result=l1_result,
            l2_result=l2_result,
            metadata=metadata,
        )

        # Calculate total duration
        total_duration_ms = (time.perf_counter() - start_time) * 1000

        # Create metrics
        metrics = AsyncScanMetrics(
            l1_start_time=l1_start,
            l1_end_time=l1_end,
            l1_duration_ms=l1_duration_ms,
            l2_start_time=l2_start if l2_start > 0 else None,
            l2_end_time=l2_end if l2_end > 0 else None,
            l2_duration_ms=l2_duration_ms,
            l2_cancelled=l2_cancelled,
            l2_timeout=l2_timeout,
            parallel_speedup=parallel_speedup,
            total_duration_ms=total_duration_ms,
        )

        # Log async performance
        logger.info(
            "async_scan_complete",
            total_duration_ms=total_duration_ms,
            l1_duration_ms=l1_duration_ms,
            l2_duration_ms=l2_duration_ms,
            parallel_speedup=parallel_speedup,
            l2_cancelled=l2_cancelled,
            l2_timeout=l2_timeout,
            has_threats=combined_result.has_threats,
        )

        return AsyncScanPipelineResult(
            scan_result=combined_result,
            duration_ms=total_duration_ms,
            text_hash=self._hash_text(text),
            metadata=metadata,
            metrics=metrics,
        )

    async def _run_l1_async(self, text: str, rules: list) -> ScanResult:
        """Run L1 detection asynchronously in thread pool.

        L1 is CPU-bound (regex), so we run it in a thread pool executor
        to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Use default thread pool executor
            self.rule_executor.execute_rules,
            text,
            rules
        )

    async def _run_l2_async(self, text: str, context: dict[str, Any] | None) -> L2Result:
        """Run L2 ML detection asynchronously in thread pool.

        L2 embedding generation is CPU-bound, so we run it in a thread pool
        executor to avoid blocking the event loop.

        Note: L1 results are not needed by the current bundle detector,
        so we pass None to avoid waiting for L1 to complete.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Use default thread pool executor
            self.l2_detector.analyze,
            text,
            None,  # L1 results not needed for bundle detector
            context
        )

    def _should_cancel_l2(self, l1_result: ScanResult | None) -> bool:
        """Check if L2 should be cancelled based on L1 results.

        Cancels L2 if:
        - L1 detected CRITICAL severity
        - L1 has high confidence (>= min_confidence_for_skip)
        - fail_fast_on_critical is enabled

        This optimization saves ~50ms when high-confidence CRITICAL is detected.
        """
        if not l1_result or not self.fail_fast_on_critical:
            return False

        if l1_result.highest_severity == Severity.CRITICAL:
            # Check confidence of CRITICAL detections
            max_confidence = max(
                (d.confidence for d in l1_result.detections
                 if d.severity == Severity.CRITICAL),
                default=0.0
            )

            return max_confidence >= self.min_confidence_for_skip

        return False

    def _create_empty_l1_result(self, text: str, timestamp: str) -> ScanResult:
        """Create empty L1 result when L1 is disabled or times out."""
        return ScanResult(
            detections=[],
            scanned_at=timestamp,
            text_length=len(text),
            rules_checked=0,
            scan_duration_ms=0.0,
        )

    def _hash_text(self, text: str) -> str:
        """Create privacy-preserving hash of text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
