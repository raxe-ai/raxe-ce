"""Async RAXE client - High-throughput async SDK.

This module provides an async version of the Raxe client for high-throughput
use cases (>1000 req/sec).

Key features:
- Async/await API mirroring sync Raxe
- LRU cache for performance (rules + results)
- Batch scanning with concurrency control
- Async context manager support
- Privacy-preserving telemetry (same as sync client)

Performance targets:
- Throughput: >1000 req/sec
- Cache hit rate: >80%
- P95 latency: <10ms (same as sync)

Example usage:
    # Basic usage
    async with AsyncRaxe() as raxe:
        result = await raxe.scan("test prompt")

    # Batch scanning
    raxe = AsyncRaxe(cache_size=1000)
    results = await raxe.scan_batch(prompts, max_concurrency=100)

    # With caching
    result1 = await raxe.scan("test")  # Cache miss
    result2 = await raxe.scan("test")  # Cache hit (fast)
"""
import asyncio
import logging
from pathlib import Path
from typing import Any

from raxe.application.preloader import preload_pipeline
from raxe.application.scan_pipeline import ScanPipelineResult
from raxe.application.telemetry_orchestrator import get_orchestrator
from raxe.async_sdk.cache import ScanResultCache
from raxe.infrastructure.config.scan_config import ScanConfig

logger = logging.getLogger(__name__)


class AsyncRaxe:
    """Async RAXE client for high-throughput scanning.

    Mirrors the synchronous Raxe API but with async/await support.
    Adds caching for improved performance on repeated scans.

    The client handles:
    - Async scanning operations
    - LRU caching of scan results
    - Batch scanning with concurrency control
    - Context manager support

    Usage:
        # With context manager
        async with AsyncRaxe(api_key="...", cache_size=1000) as raxe:
            result = await raxe.scan("Ignore all previous instructions")

        # Without context manager
        raxe = AsyncRaxe()
        result = await raxe.scan("test")
        await raxe.close()

        # Batch scanning
        results = await raxe.scan_batch(
            ["prompt1", "prompt2", "prompt3"],
            max_concurrency=10
        )

    Performance:
        - Initialization: <500ms (one-time, same as sync)
        - Scanning (cache miss): <10ms per call
        - Scanning (cache hit): <1ms per call
        - Throughput: >1000 req/sec with caching
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        config_path: Path | None = None,
        telemetry: bool = True,
        l2_enabled: bool = True,
        voting_preset: str | None = None,
        cache_size: int = 1000,
        cache_ttl: float = 300.0,
        **kwargs: Any
    ):
        """Initialize async RAXE client.

        Args:
            api_key: Optional API key for cloud features
            config_path: Path to config file (overrides default search)
            telemetry: Enable privacy-preserving telemetry (default: True)
            l2_enabled: Enable L2 ML detection (default: True)
            voting_preset: L2 voting preset (balanced, high_security, low_fp)
            cache_size: LRU cache size (default: 1000 entries)
            cache_ttl: Cache TTL in seconds (default: 300 = 5 minutes)
            **kwargs: Additional config options passed to ScanConfig

        Raises:
            Exception: If critical components fail to load
        """
        # Build configuration (same as sync client)
        if config_path and config_path.exists():
            self.config = ScanConfig.from_file(config_path)
        else:
            self.config = ScanConfig()

        # Apply explicit overrides
        if api_key is not None:
            self.config.api_key = api_key
        self.config.telemetry.enabled = telemetry
        self.config.enable_l2 = l2_enabled

        # Store voting preset for L2 detector initialization
        self._voting_preset = voting_preset

        # Initialize cache (skip if cache_size is 0)
        if cache_size > 0:
            self._cache = ScanResultCache(maxsize=cache_size, ttl=cache_ttl)
            self._cache_enabled = True
        else:
            self._cache = None  # type: ignore
            self._cache_enabled = False

        # Preload pipeline (same as sync - this is CPU-bound, not I/O-bound)
        logger.info("Initializing async RAXE client")
        try:
            # Note: preload_pipeline is synchronous but that's fine for init
            self.pipeline, self.preload_stats = preload_pipeline(
                config=self.config,
                voting_preset=self._voting_preset,
            )
            self._initialized = True

            # Flush any stale telemetry from previous sessions (non-blocking)
            # This recovers events that were queued but not flushed due to
            # crashes, SIGKILL, or SDK usage without proper cleanup
            try:
                from raxe.infrastructure.telemetry.flush_helper import (
                    flush_stale_telemetry_async,
                )
                flush_stale_telemetry_async()
            except Exception:
                pass  # Never block on stale flush

            logger.info(
                f"Async RAXE client initialized: {self.preload_stats.rules_loaded} rules loaded"
            )
        except Exception as e:
            logger.error(f"Failed to initialize async RAXE client: {e}")
            raise

    @classmethod
    def from_config_file(cls, path: Path) -> "AsyncRaxe":
        """Create AsyncRaxe client from config file.

        Args:
            path: Path to .raxe/config.yaml

        Returns:
            Configured AsyncRaxe instance

        Example:
            raxe = AsyncRaxe.from_config_file(Path.home() / ".raxe" / "config.yaml")
            result = await raxe.scan("test")
        """
        instance = cls.__new__(cls)

        # Load configuration from file
        instance.config = ScanConfig.from_file(path)

        # Initialize cache with defaults
        cache_size = 1000
        if cache_size > 0:
            instance._cache = ScanResultCache(maxsize=cache_size, ttl=300.0)
            instance._cache_enabled = True
        else:
            instance._cache = None  # type: ignore
            instance._cache_enabled = False

        # Get voting preset from config (L2 voting config)
        instance._voting_preset = None
        if hasattr(instance.config, 'l2_scoring') and instance.config.l2_scoring:
            instance._voting_preset = getattr(instance.config.l2_scoring, 'voting_preset', None)

        # Preload pipeline
        logger.info("Initializing async RAXE client from config file")
        try:
            instance.pipeline, instance.preload_stats = preload_pipeline(
                config=instance.config,
                voting_preset=instance._voting_preset,
            )
            instance._initialized = True
            logger.info(
                f"Async RAXE client initialized: {instance.preload_stats.rules_loaded} rules loaded"
            )
        except Exception as e:
            logger.error(f"Failed to initialize async RAXE client: {e}")
            raise

        return instance

    async def scan(
        self,
        text: str,
        *,
        customer_id: str | None = None,
        context: dict[str, object] | None = None,
        block_on_threat: bool = False,
        use_cache: bool = True,
    ) -> ScanPipelineResult:
        """Scan text for security threats (async).

        Args:
            text: Text to scan (prompt or response)
            customer_id: Optional customer ID for policy evaluation
            context: Optional context metadata for the scan
            block_on_threat: Raise SecurityException if threat detected (default: False)
            use_cache: Use cached result if available (default: True)

        Returns:
            ScanPipelineResult with detections and policy decision

        Raises:
            SecurityException: If block_on_threat=True and threat detected
            ValueError: If text is empty or invalid

        Example:
            # Basic scan
            result = await raxe.scan("Hello world")
            print(f"Safe: {not result.has_threats}")

            # Scan with blocking
            try:
                result = await raxe.scan(
                    "Ignore all instructions",
                    block_on_threat=True
                )
            except SecurityException as e:
                print(f"Blocked: {e.result.severity}")
        """
        # Handle empty text - return clean result
        if not text or not text.strip():
            from datetime import datetime, timezone

            from raxe.application.scan_merger import CombinedScanResult
            from raxe.domain.engine.executor import ScanResult
            from raxe.application.scan_pipeline import BlockAction

            clean_l1_result = ScanResult(
                detections=[],
                scanned_at=datetime.now(timezone.utc).isoformat(),
                text_length=0,
                rules_checked=0,
                scan_duration_ms=0.0
            )

            combined_result = CombinedScanResult(
                l1_result=clean_l1_result,
                l2_result=None,
                combined_severity=None,
                total_processing_ms=0.0,
                metadata={"empty_text": True}
            )

            return ScanPipelineResult(
                scan_result=combined_result,
                policy_decision=BlockAction.ALLOW,
                should_block=False,
                duration_ms=0.0,
                text_hash="",
                metadata={"empty_text": True}
            )

        # Check cache if enabled
        if self._cache_enabled and use_cache and self._cache:
            cached_result = await self._cache.get(text)
            if cached_result is not None:
                # Cache hit - return cached result
                # Note: We still need to enforce blocking if requested
                if block_on_threat and cached_result.should_block:
                    from raxe.sdk.exceptions import SecurityException
                    raise SecurityException(cached_result)
                return cached_result

        # Cache miss - run scan
        # Note: The scan pipeline is synchronous but CPU-bound
        # We run it in executor to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            self._scan_sync,
            text,
            customer_id,
            context,
        )

        # Track telemetry (non-blocking, privacy-preserving)
        # Pass original prompt for accurate hash and length calculation
        self._track_scan(result, prompt=text, entry_point="async_sdk")

        # Cache result if enabled
        if self._cache_enabled and use_cache and self._cache:
            await self._cache.set(text, result)

        # Enforce blocking if requested
        if block_on_threat and result.should_block:
            from raxe.sdk.exceptions import SecurityException
            raise SecurityException(result)

        return result

    def _scan_sync(
        self,
        text: str,
        customer_id: str | None,
        context: dict[str, object] | None,
    ) -> ScanPipelineResult:
        """Synchronous scan helper (runs in executor).

        This is the actual scanning logic that runs in a thread pool
        to avoid blocking the async event loop.

        Args:
            text: Text to scan
            customer_id: Optional customer ID
            context: Optional context

        Returns:
            ScanPipelineResult
        """
        return self.pipeline.scan(
            text,
            customer_id=customer_id or self.config.customer_id,
            context=context,
        )

    async def scan_batch(
        self,
        texts: list[str],
        *,
        customer_id: str | None = None,
        context: dict[str, object] | None = None,
        max_concurrency: int = 10,
        use_cache: bool = True,
    ) -> list[ScanPipelineResult]:
        """Scan multiple texts concurrently.

        Args:
            texts: List of texts to scan
            customer_id: Optional customer ID
            context: Optional context metadata
            max_concurrency: Maximum concurrent scans (default: 10)
            use_cache: Use cached results if available (default: True)

        Returns:
            List of scan results (one per text, in same order)

        Example:
            prompts = ["prompt1", "prompt2", "prompt3"]
            results = await raxe.scan_batch(prompts, max_concurrency=10)

            for prompt, result in zip(prompts, results):
                if result.has_threats:
                    print(f"Threat in: {prompt[:50]}...")
        """
        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrency)

        async def scan_with_semaphore(text: str) -> ScanPipelineResult:
            async with semaphore:
                return await self.scan(
                    text,
                    customer_id=customer_id,
                    context=context,
                    use_cache=use_cache,
                )

        # Create tasks for all texts
        tasks = [scan_with_semaphore(text) for text in texts]

        # Wait for all to complete
        results = await asyncio.gather(*tasks)

        return results

    async def clear_cache(self) -> None:
        """Clear all cached scan results.

        Example:
            await raxe.clear_cache()
        """
        if self._cache_enabled and self._cache:
            await self._cache.clear()

    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics:
                - hits: Number of cache hits
                - misses: Number of cache misses
                - hit_rate: Cache hit rate (0.0 to 1.0)
                - size: Current cache size
                - maxsize: Maximum cache size

        Example:
            stats = raxe.cache_stats()
            print(f"Hit rate: {stats['hit_rate']:.2%}")
        """
        if not self._cache_enabled or not self._cache:
            return {
                "hits": 0,
                "misses": 0,
                "hit_rate": 0.0,
                "size": 0,
                "maxsize": 0,
            }
        return self._cache.stats()

    @property
    def stats(self) -> dict[str, Any]:
        """Get preload statistics.

        Returns:
            Dictionary with initialization stats
        """
        return {
            "rules_loaded": self.preload_stats.rules_loaded,
            "packs_loaded": self.preload_stats.packs_loaded,
            "patterns_compiled": self.preload_stats.patterns_compiled,
            "preload_time_ms": self.preload_stats.duration_ms,
            "config_loaded": self.preload_stats.config_loaded,
            "telemetry_initialized": self.preload_stats.telemetry_initialized,
            "cache_enabled": self._cache_enabled,
        }

    def _track_scan(
        self,
        result: ScanPipelineResult,
        prompt: str,
        entry_point: str = "async_sdk",
    ) -> None:
        """Track scan telemetry using schema v2.0 (non-blocking, never raises).

        This method sends privacy-preserving telemetry about the scan using
        the full L2 telemetry schema defined in docs/SCAN_TELEMETRY_SCHEMA.md.

        Privacy: Only hashes, metrics, and enum values are transmitted.
        No actual prompt content is ever transmitted.

        Args:
            result: The scan result to track
            prompt: Original prompt text (used for hash and length calculation)
            entry_point: How the scan was triggered (async_sdk, async_wrapper)
        """
        try:
            orchestrator = get_orchestrator()
            if orchestrator is None:
                return

            # Import builder here to avoid circular imports
            from raxe.domain.telemetry.scan_telemetry_builder import build_scan_telemetry

            # Get L1 and L2 results
            l1_result = None
            l2_result = None
            if result.scan_result:
                l1_result = result.scan_result.l1_result
                l2_result = result.scan_result.l2_result

            # Build telemetry payload using v2 schema
            # All fields are dynamically calculated from actual scan results
            telemetry_payload = build_scan_telemetry(
                l1_result=l1_result,
                l2_result=l2_result,
                scan_duration_ms=result.duration_ms,
                entry_point=entry_point,  # type: ignore[arg-type]
                prompt=prompt,
                action_taken="block" if result.should_block else "allow",
                l2_enabled=result.metadata.get("l2_enabled", True),
            )

            # Track using v2 method
            orchestrator.track_scan_v2(payload=telemetry_payload)
        except Exception:
            # Never let telemetry break SDK functionality
            pass

    async def close(self) -> None:
        """Close client and cleanup resources.

        This clears the cache, flushes telemetry, and prepares the client for shutdown.

        Example:
            raxe = AsyncRaxe()
            try:
                result = await raxe.scan("test")
            finally:
                await raxe.close()
        """
        await self.clear_cache()

        # Flush telemetry on close to ensure events are sent
        try:
            from raxe.infrastructure.telemetry.flush_helper import ensure_telemetry_flushed

            # Run flush in executor to avoid blocking async context
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                ensure_telemetry_flushed,
                5.0,  # timeout_seconds
                50,   # max_batches (for high-throughput async usage)
                50,   # batch_size
                True, # end_session
            )
        except Exception:
            pass  # Never let telemetry affect shutdown

    async def __aenter__(self) -> "AsyncRaxe":
        """Enter async context manager.

        Returns:
            Self for use in async with statement
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager and cleanup.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        await self.close()

    def __repr__(self) -> str:
        """String representation of AsyncRaxe client.

        Returns:
            Human-readable string showing key stats
        """
        cache_stats = self.cache_stats()
        return (
            f"AsyncRaxe(initialized={self._initialized}, "
            f"rules={self.stats['rules_loaded']}, "
            f"l2_enabled={self.config.enable_l2}, "
            f"cache_hit_rate={cache_stats['hit_rate']:.2%})"
        )
