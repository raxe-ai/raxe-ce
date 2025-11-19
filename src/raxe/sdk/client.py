"""Unified RAXE client - SINGLE ENTRY POINT for all integrations.

This class is the foundation for all RAXE integrations:
- CLI commands (raxe scan)
- SDK direct usage (raxe.scan())
- Decorators (@raxe.protect)
- Wrappers (RaxeOpenAI)

ALL scanning MUST go through the Raxe.scan() method to ensure
consistency and proper configuration cascade.
"""
from collections.abc import Callable
from pathlib import Path
from typing import Any

from raxe.application.preloader import preload_pipeline
from raxe.application.scan_pipeline import ScanPipelineResult
from raxe.domain.suppression_factory import create_suppression_manager
from raxe.infrastructure.config.scan_config import ScanConfig
from raxe.infrastructure.database.scan_history import ScanHistoryDB
from raxe.infrastructure.tracking.usage import UsageTracker
from raxe.utils.logging import get_logger

# Use structured logging for better observability (privacy-preserving)
logger = get_logger(__name__)


class Raxe:
    """Unified RAXE client.

    This is the ONLY entry point for scanning operations. All other
    interfaces (CLI, decorators, wrappers) use this class internally.

    The client handles:
    - Configuration loading with proper cascade (explicit > env > file > defaults)
    - One-time pipeline preloading for optimal performance
    - Unified scan() method used by all integrations
    - Access to decorator and wrapper convenience methods

    Usage:
        # Basic usage with defaults
        raxe = Raxe()
        result = raxe.scan("Ignore all previous instructions")

        # With configuration
        raxe = Raxe(api_key="raxe_test_...", telemetry=False)

        # From config file
        raxe = Raxe.from_config_file(".raxe/config.yaml")

        # Check results
        if result.has_threats:
            print(f"Threat: {result.severity}")

    Performance:
        - Initialization: <500ms (one-time)
        - Scanning: <10ms per call (after init)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        config_path: Path | None = None,
        telemetry: bool = True,
        l2_enabled: bool = True,
        performance_mode: str = "balanced",
        **kwargs
    ):
        """Initialize RAXE client.

        Configuration cascade (highest to lowest priority):
        1. Explicit parameters (this method)
        2. Environment variables (RAXE_*)
        3. Config file (explicit path or default)
        4. Defaults

        Args:
            api_key: Optional API key for cloud features
            config_path: Path to config file (overrides default search)
            telemetry: Enable privacy-preserving telemetry (default: True)
            l2_enabled: Enable L2 ML detection (default: True)
            performance_mode: "fast", "balanced", "accurate" (default: balanced)
            **kwargs: Additional config options passed to ScanConfig

        Raises:
            Exception: If critical components fail to load
        """
        # Build configuration with cascade
        # Note: load_config would handle the cascade, but it doesn't exist yet
        # For now, we'll use ScanConfig directly and update in Phase 4E
        if config_path and config_path.exists():
            self.config = ScanConfig.from_file(config_path)
        else:
            self.config = ScanConfig()

        # Apply explicit overrides
        if api_key is not None:
            self.config.api_key = api_key
        # Explicitly set telemetry (handles both True and False)
        self.config.telemetry.enabled = telemetry
        self.config.enable_l2 = l2_enabled

        # TODO: Apply performance_mode and other kwargs
        # This will be enhanced when we implement full config cascade

        # Initialize tracking and history components
        # These are lazily loaded - only create files when first used
        self._usage_tracker: UsageTracker | None = None
        self._scan_history: ScanHistoryDB | None = None
        self._streak_tracker = None

        # Initialize suppression manager (auto-loads .raxeignore from cwd)
        self.suppression_manager = create_suppression_manager(auto_load=True)

        # Preload pipeline (one-time startup cost ~100-200ms)
        # This compiles patterns, loads packs, warms caches
        logger.info("raxe_client_init_start")
        try:
            self.pipeline, self.preload_stats = preload_pipeline(
                config=self.config,
                suppression_manager=self.suppression_manager
            )

            # Also create async pipeline for parallel L1/L2 execution (5x faster!)
            # This shares the same components but runs L1+L2 concurrently
            self._async_pipeline = None  # Lazy init on first use

            self._initialized = True
            logger.info(
                "raxe_client_init_complete",
                rules_loaded=self.preload_stats.rules_loaded
            )
        except Exception as e:
            logger.error("raxe_client_init_failed", error=str(e))
            raise

    def _get_async_pipeline(self):
        """Get or create async pipeline (lazy initialization).

        The async pipeline runs L1 and L2 in parallel for 5x speedup.
        It shares components with the sync pipeline for efficiency.
        """
        if self._async_pipeline is None:
            from raxe.application.scan_pipeline_async import AsyncScanPipeline

            # Reuse components from sync pipeline
            self._async_pipeline = AsyncScanPipeline(
                pack_registry=self.pipeline.pack_registry,
                rule_executor=self.pipeline.rule_executor,
                l2_detector=self.pipeline.l2_detector,
                scan_merger=self.pipeline.scan_merger,
                policy=self.pipeline.policy,
                enable_l2=self.pipeline.enable_l2,
                fail_fast_on_critical=self.pipeline.fail_fast_on_critical,
                min_confidence_for_skip=self.pipeline.min_confidence_for_skip,
                l1_timeout_ms=10.0,
                l2_timeout_ms=150.0,
            )
            logger.info("Async pipeline initialized (parallel L1+L2 execution)")

        return self._async_pipeline

    @property
    def usage_tracker(self) -> UsageTracker:
        """Get usage tracker (lazy initialization).

        Creates install.json and usage.json on first access.
        """
        if self._usage_tracker is None:
            self._usage_tracker = UsageTracker()
        return self._usage_tracker

    @property
    def scan_history(self) -> ScanHistoryDB:
        """Get scan history database (lazy initialization).

        Creates scan_history.db on first access.
        """
        if self._scan_history is None:
            self._scan_history = ScanHistoryDB()
        return self._scan_history

    @property
    def streak_tracker(self):
        """Get streak tracker (lazy initialization).

        Creates achievements.json on first access for gamification.
        """
        if self._streak_tracker is None:
            from raxe.infrastructure.analytics.streaks import StreakTracker
            self._streak_tracker = StreakTracker()
        return self._streak_tracker

    @classmethod
    def from_config_file(cls, path: Path) -> "Raxe":
        """Create Raxe client from config file.

        When using this method, configuration is loaded ONLY from the file
        without default parameter overrides.

        Args:
            path: Path to .raxe/config.yaml

        Returns:
            Configured Raxe instance

        Example:
            raxe = Raxe.from_config_file(Path.home() / ".raxe" / "config.yaml")
            result = raxe.scan("test")
        """
        # Create instance with minimal intervention
        # Load config from file without applying default overrides
        instance = cls.__new__(cls)

        # Load configuration from file
        instance.config = ScanConfig.from_file(path)

        # Initialize suppression manager
        instance.suppression_manager = create_suppression_manager(auto_load=True)

        # Preload pipeline
        logger.info("Initializing RAXE client from config file")
        try:
            instance.pipeline, instance.preload_stats = preload_pipeline(
                config=instance.config,
                suppression_manager=instance.suppression_manager
            )
            instance._initialized = True
            logger.info(
                f"RAXE client initialized: {instance.preload_stats.rules_loaded} rules loaded"
            )
        except Exception as e:
            logger.error(f"Failed to initialize RAXE client: {e}")
            raise

        return instance

    def scan(
        self,
        text: str,
        *,
        customer_id: str | None = None,
        context: dict[str, object] | None = None,
        block_on_threat: bool = False,
        mode: str = "balanced",
        l1_enabled: bool = True,
        l2_enabled: bool = True,
        confidence_threshold: float = 0.5,
        explain: bool = False,
        dry_run: bool = False,
        use_async: bool = True,
    ) -> ScanPipelineResult:
        """Scan text for security threats with layer control.

        THIS IS THE ONLY SCAN METHOD. All other interfaces call this.

        The scan method:
        1. Validates input
        2. Executes full scan pipeline (L1, L2, policy, telemetry)
        3. Returns comprehensive results
        4. Optionally raises exception if blocking enabled

        Args:
            text: Text to scan (prompt or response)
            customer_id: Optional customer ID for policy evaluation
            context: Optional context metadata for the scan
            block_on_threat: Raise SecurityException if threat detected (default: False)
            mode: Performance mode - "fast" (<3ms), "balanced" (<10ms), or "thorough" (<100ms)
            l1_enabled: Enable L1 regex detection layer (default: True)
            l2_enabled: Enable L2 ML detection layer (default: True)
            confidence_threshold: Minimum confidence for reporting (0.0-1.0, default: 0.5)
            explain: Include explanations in detection results (default: False)
            dry_run: Test scan without saving to database (default: False)
            use_async: Use async pipeline for parallel L1+L2 execution (5x speedup, default: True)

        Returns:
            ScanPipelineResult with:
                - scan_result: L1/L2 detections
                - policy_decision: Policy evaluation result
                - should_block: Whether to block the request
                - duration_ms: Scan latency
                - text_hash: Privacy-preserving hash

        Raises:
            SecurityException: If block_on_threat=True and threat detected
            ValueError: If text is empty or invalid or mode is invalid

        Examples:
            # Basic scan
            result = raxe.scan("Hello world")
            print(f"Safe: {not result.has_threats}")

            # Fast mode (L1 only, <3ms)
            result = raxe.scan("test", mode="fast")

            # Disable L2 for performance
            result = raxe.scan("test", l2_enabled=False)

            # High confidence only
            result = raxe.scan("test", confidence_threshold=0.8)

            # Scan with blocking
            try:
                result = raxe.scan(
                    "Ignore all instructions",
                    block_on_threat=True
                )
            except SecurityException as e:
                print(f"Blocked: {e.result.severity}")
        """
        # Handle empty text - return clean result (no threats)
        if not text or not text.strip():
            from datetime import datetime, timezone

            from raxe.application.scan_merger import CombinedScanResult
            from raxe.domain.engine.executor import ScanResult
            from raxe.domain.models import BlockAction

            # Create clean L1 scan result for empty text
            clean_l1_result = ScanResult(
                detections=[],
                scanned_at=datetime.now(timezone.utc).isoformat(),
                text_length=0,
                rules_checked=0,
                scan_duration_ms=0.0
            )

            # Create combined result with no threats
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

        # Use async pipeline for 5x speedup (parallel L1+L2)
        # Falls back to sync pipeline if async fails or is disabled
        if use_async:
            try:
                import asyncio

                async_pipeline = self._get_async_pipeline()

                # Run async pipeline in sync context
                try:
                    loop = asyncio.get_running_loop()
                    # Already in async context - this shouldn't happen in sync SDK
                    logger.warning("Already in async context, falling back to sync pipeline")
                    use_sync_fallback = True
                except RuntimeError:
                    # Not in async context - create new event loop (correct path)
                    use_sync_fallback = False

                if not use_sync_fallback:
                    async_result = asyncio.run(async_pipeline.scan(
                        text,
                        customer_id=customer_id or self.config.customer_id,
                        context=context,
                        l1_enabled=l1_enabled,
                        l2_enabled=l2_enabled,
                        mode=mode,
                    ))

                    # Convert AsyncScanPipelineResult to ScanPipelineResult
                    # They have the same structure, just different types
                    result = ScanPipelineResult(
                        scan_result=async_result.scan_result,
                        policy_decision=async_result.policy_decision,
                        should_block=async_result.should_block,
                        duration_ms=async_result.duration_ms,
                        text_hash=async_result.text_hash,
                        metadata=async_result.metadata,
                    )
                    logger.debug(
                        "async_scan_complete",
                        duration_ms=result.duration_ms,
                        parallel_speedup=async_result.metrics.parallel_speedup if async_result.metrics else 1.0
                    )
                else:
                    # Fallback to sync pipeline
                    result = self.pipeline.scan(
                        text,
                        customer_id=customer_id or self.config.customer_id,
                        context=context,
                        l1_enabled=l1_enabled,
                        l2_enabled=l2_enabled,
                        mode=mode,
                        confidence_threshold=confidence_threshold,
                        explain=explain,
                    )
            except Exception as e:
                # Async pipeline failed - fall back to sync
                logger.warning(f"Async pipeline failed ({e}), falling back to sync pipeline")
                result = self.pipeline.scan(
                    text,
                    customer_id=customer_id or self.config.customer_id,
                    context=context,
                    l1_enabled=l1_enabled,
                    l2_enabled=l2_enabled,
                    mode=mode,
                    confidence_threshold=confidence_threshold,
                    explain=explain,
                )
        else:
            # Use sync pipeline (original behavior)
            result = self.pipeline.scan(
                text,
                customer_id=customer_id or self.config.customer_id,
                context=context,
                l1_enabled=l1_enabled,
                l2_enabled=l2_enabled,
                mode=mode,
                confidence_threshold=confidence_threshold,
                explain=explain,
            )

        # Record scan in tracking and history
        # This captures:
        # 1. Usage metrics (install tracking, time-to-first-scan)
        # 2. Scan history (privacy-preserving hashes only)
        # 3. Structured logging (no PII)
        # Skipped if dry_run=True
        if not dry_run:
            try:
                # Track usage (creates install.json on first scan)
                self.usage_tracker.record_scan(found_threats=result.has_threats)

                # Track feature enablement (for product analytics)
                if l2_enabled:
                    self.usage_tracker.record_feature("l2_detection")
                if explain:
                    self.usage_tracker.record_feature("explain")
                if mode != "balanced":
                    self.usage_tracker.record_feature(f"mode_{mode}")
                if confidence_threshold != 0.5:
                    self.usage_tracker.record_feature("custom_confidence_threshold")
                if block_on_threat:
                    self.usage_tracker.record_feature("block_on_threat")

                # Record in scan history (creates scan_history.db on first scan)
                # Extract detections from result
                detections = []
                if result.scan_result and result.scan_result.l1_result:
                    detections.extend(result.scan_result.l1_result.detections)
                if result.scan_result and result.scan_result.l2_result:
                    # L2 result has different structure - handle appropriately
                    pass  # L2 detections handled differently

                self.scan_history.record_scan(
                    prompt=text,
                    detections=detections,
                    l1_duration_ms=result.scan_result.l1_result.scan_duration_ms if result.scan_result and result.scan_result.l1_result else None,
                    l2_duration_ms=None,  # Will be populated when L2 is integrated
                    version="1.0.0"
                )

                # Structured logging (privacy-preserving)
                logger.info(
                    "scan_completed",
                    prompt_hash=result.text_hash,
                    has_threats=result.has_threats,
                    detection_count=result.total_detections,
                    severity=result.severity if result.has_threats else "none",
                    duration_ms=result.duration_ms,
                    l1_enabled=l1_enabled,
                    l2_enabled=l2_enabled,
                    mode=mode
                )

                # Streak tracking and achievements (P2 gamification)
                # Record scan for streak tracking
                newly_unlocked = self.streak_tracker.record_scan()

                # Check for achievements based on usage stats
                usage_stats = self.usage_tracker.get_usage_stats()
                achievement_unlocks = self.streak_tracker.check_achievements(
                    total_scans=usage_stats.total_scans,
                    threats_detected=usage_stats.scans_with_threats,
                    avg_scan_time_ms=result.duration_ms,  # Use current scan time as proxy
                    threats_blocked=0  # TODO: Track blocked threats when blocking is implemented
                )
                newly_unlocked.extend(achievement_unlocks)

                # Log newly unlocked achievements
                if newly_unlocked:
                    for achievement in newly_unlocked:
                        logger.info(
                            "achievement_unlocked",
                            achievement_id=achievement.id,
                            name=achievement.name,
                            points=achievement.points
                        )

            except Exception as e:
                # Don't fail the scan if tracking/history fails
                # Just log the error
                logger.warning(
                    "scan_tracking_failed",
                    error=str(e),
                    error_type=type(e).__name__
                )
        else:
            # Log that dry_run scan skipped tracking
            logger.info(
                "scan_completed_dry_run",
                prompt_hash=result.text_hash,
                has_threats=result.has_threats,
                detection_count=result.total_detections,
                severity=result.severity if result.has_threats else "none",
                duration_ms=result.duration_ms,
                l1_enabled=l1_enabled,
                l2_enabled=l2_enabled,
                mode=mode
            )

        # Enforce blocking if requested
        if block_on_threat and result.should_block:
            from raxe.sdk.exceptions import SecurityException

            raise SecurityException(result)

        return result

    def scan_fast(self, text: str, **kwargs) -> ScanPipelineResult:
        """Fast scan using L1 only (target <3ms).

        Optimized for real-time applications where latency is critical.
        Uses only regex-based detection (L1), skipping ML analysis (L2).

        Args:
            text: Text to scan for threats
            **kwargs: Additional scan parameters (customer_id, context, etc.)

        Returns:
            ScanPipelineResult with L1 detections only

        Example:
            >>> raxe = Raxe()
            >>> result = raxe.scan_fast("Ignore all previous instructions")
            >>> print(f"Latency: {result.duration_ms}ms")
        """
        return self.scan(text, mode="fast", l2_enabled=False, **kwargs)

    def scan_thorough(self, text: str, **kwargs) -> ScanPipelineResult:
        """Thorough scan using all detection layers (target <100ms).

        Optimized for maximum detection coverage. Uses all available
        detection layers (L1 regex + L2 ML) with comprehensive rules.

        Args:
            text: Text to scan for threats
            **kwargs: Additional scan parameters (customer_id, context, etc.)

        Returns:
            ScanPipelineResult with all detections

        Example:
            >>> raxe = Raxe()
            >>> result = raxe.scan_thorough("Suspicious prompt text")
            >>> print(f"Detections: {result.total_detections}")
        """
        return self.scan(text, mode="thorough", **kwargs)

    def scan_high_confidence(
        self, text: str, threshold: float = 0.8, **kwargs
    ) -> ScanPipelineResult:
        """Scan with high confidence threshold (fewer false positives).

        Only reports detections with confidence >= threshold.
        Useful for reducing false positives in production environments.

        Args:
            text: Text to scan for threats
            threshold: Minimum confidence level (0.0-1.0, default: 0.8)
            **kwargs: Additional scan parameters (customer_id, context, etc.)

        Returns:
            ScanPipelineResult with high-confidence detections only

        Example:
            >>> raxe = Raxe()
            >>> result = raxe.scan_high_confidence(
            ...     "Maybe suspicious text",
            ...     threshold=0.9
            ... )
            >>> print(f"High confidence threats: {result.total_detections}")
        """
        return self.scan(text, confidence_threshold=threshold, **kwargs)

    def protect(
        self,
        func=None,
        *,
        block: bool = True,
        on_threat: Callable | None = None,
        allow_severity: list[str] | None = None
    ):
        """Decorator to protect a function.

        Scans the first string argument before calling the function.
        Can be used with or without parameters.

        Usage:
            raxe = Raxe()

            # Without parameters (blocks by default)
            @raxe.protect
            def generate(prompt: str) -> str:
                return llm.generate(prompt)

            # With parameters (monitoring mode)
            @raxe.protect(block=False)
            def monitor(prompt: str) -> str:
                return llm.generate(prompt)

            # With custom threat handler
            @raxe.protect(on_threat=lambda result: log.warning(result))
            def custom_handler(prompt: str) -> str:
                return llm.generate(prompt)

        Note:
            This is a convenience method. Actual implementation
            is in raxe.sdk.decorator module (Phase 4B).

        Args:
            func: Function to protect (when used without parameters)
            block: Whether to raise SecurityException on threat (default: True)
            on_threat: Optional callback to invoke when threat detected
            allow_severity: Optional list of severities to allow (e.g., ["LOW"])

        Returns:
            Wrapped function that scans inputs, or decorator if called with parameters
        """
        # Import here to avoid circular dependency
        from raxe.sdk.decorator import protect_function

        def decorator(f):
            return protect_function(
                self,
                f,
                block_on_threat=block,
                on_threat=on_threat,
                allow_severity=allow_severity
            )

        # Support both @raxe.protect and @raxe.protect()
        if func is None:
            # Called with parameters: @raxe.protect(block=False)
            return decorator
        else:
            # Called without parameters: @raxe.protect
            return decorator(func)

    def wrap(self, client):
        """Wrap an LLM client with RAXE scanning.

        Creates a proxy that automatically scans all prompts and responses
        sent through the client.

        Usage:
            raxe = Raxe()
            from openai import OpenAI
            client = raxe.wrap(OpenAI())

            # All calls automatically scanned
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello"}]
            )

        Note:
            This is a convenience method. Actual implementation
            is in raxe.sdk.wrappers module (Phase 4C).

        Args:
            client: LLM client to wrap (OpenAI, Anthropic, etc.)

        Returns:
            Wrapped client with automatic scanning
        """
        # Import here to avoid circular dependency
        from raxe.sdk.wrappers import wrap_client

        return wrap_client(self, client)

    # === PUBLIC API METHODS ===
    # These methods provide controlled access to internal components
    # for CLI commands and diagnostic tools, eliminating the need for
    # private attribute access.

    def get_all_rules(self) -> list:
        """Get all loaded detection rules.

        Public API for CLI and external tools to access rules without
        accessing private attributes.

        Returns:
            List of all loaded rules from all packs

        Example:
            raxe = Raxe()
            rules = raxe.get_all_rules()
            print(f"Loaded {len(rules)} rules")
        """
        return self.pipeline.pack_registry.get_all_rules()

    def list_rule_packs(self) -> list[str]:
        """List all available rule packs.

        Returns:
            List of pack names currently loaded

        Example:
            raxe = Raxe()
            packs = raxe.list_rule_packs()
            print(f"Packs: {', '.join(packs)}")
        """
        return self.pipeline.pack_registry.list_packs()

    def has_api_key(self) -> bool:
        """Check if an API key is configured.

        Returns:
            True if API key is set, False otherwise

        Example:
            raxe = Raxe(api_key="raxe_test_123")
            if raxe.has_api_key():
                print("Cloud features available")
        """
        return bool(self.config.api_key)

    def get_performance_mode(self) -> str:
        """Get the current performance mode setting.

        Returns:
            Performance mode: 'fast', 'balanced', or 'thorough'

        Example:
            raxe = Raxe()
            mode = raxe.get_performance_mode()
            print(f"Performance mode: {mode}")
        """
        # Return from config or default to 'balanced'
        return getattr(self.config, 'performance_mode', 'balanced')

    def get_telemetry_enabled(self) -> bool:
        """Check if telemetry is enabled.

        Returns:
            True if telemetry is enabled

        Example:
            raxe = Raxe(telemetry=False)
            if not raxe.get_telemetry_enabled():
                print("Telemetry disabled")
        """
        return self.config.telemetry.enabled

    def get_profiling_components(self) -> dict[str, Any]:
        """Get internal components for profiling.

        This provides controlled access to internal components
        needed by the profiler CLI command without exposing
        private attributes.

        Returns:
            Dictionary with profiling components:
                - executor: RuleExecutor instance
                - l2_detector: L2Detector instance (optional)
                - rules: List of all loaded rules

        Example:
            raxe = Raxe()
            components = raxe.get_profiling_components()
            executor = components['executor']
            rules = components['rules']
        """
        return {
            'executor': self.pipeline.rule_executor,
            'l2_detector': self.pipeline.l2_detector if self.config.enable_l2 else None,
            'rules': self.get_all_rules()
        }

    def get_pipeline_stats(self) -> dict[str, Any]:
        """Get pipeline statistics for diagnostics.

        Returns:
            Dictionary with pipeline statistics:
                - rules_loaded: Number of rules loaded
                - packs_loaded: Number of packs loaded
                - performance_mode: Current performance mode
                - telemetry_enabled: Whether telemetry is enabled
                - has_api_key: Whether API key is configured
                - l2_enabled: Whether L2 detection is enabled

        Example:
            raxe = Raxe()
            stats = raxe.get_pipeline_stats()
            print(f"Rules: {stats['rules_loaded']}, L2: {stats['l2_enabled']}")
        """
        stats = {
            'rules_loaded': len(self.get_all_rules()),
            'packs_loaded': len(self.list_rule_packs()),
            'performance_mode': self.get_performance_mode(),
            'telemetry_enabled': self.get_telemetry_enabled(),
            'has_api_key': self.has_api_key(),
            'l2_enabled': self.config.enable_l2
        }

        # Add preload stats if available
        if hasattr(self, 'preload_stats'):
            stats['preload_time_ms'] = self.preload_stats.duration_ms
            stats['patterns_compiled'] = self.preload_stats.patterns_compiled

        return stats

    def validate_configuration(self) -> dict[str, Any]:
        """Validate the current configuration.

        Used by doctor command for health checks. Performs comprehensive
        validation of configuration settings and returns detailed results.

        Returns:
            Dictionary with validation results:
                - config_valid: True if configuration is valid
                - errors: List of error messages (blocking issues)
                - warnings: List of warning messages (non-blocking issues)

        Example:
            raxe = Raxe()
            validation = raxe.validate_configuration()
            if not validation['config_valid']:
                print(f"Errors: {validation['errors']}")
            if validation['warnings']:
                print(f"Warnings: {validation['warnings']}")
        """
        validation = {
            'config_valid': True,
            'errors': [],
            'warnings': []
        }

        # Check API key format if present
        if self.config.api_key:
            if not self.config.api_key.startswith('raxe_'):
                validation['warnings'].append("API key should start with 'raxe_'")
            if len(self.config.api_key) < 20:
                validation['warnings'].append("API key seems too short")

        # Check performance mode
        valid_modes = ['fast', 'balanced', 'thorough']
        current_mode = self.get_performance_mode()
        if current_mode not in valid_modes:
            validation['errors'].append(
                f"Invalid performance mode: {current_mode}. "
                f"Must be one of: {', '.join(valid_modes)}"
            )
            validation['config_valid'] = False

        # Check rule loading
        if len(self.get_all_rules()) == 0:
            validation['warnings'].append("No detection rules loaded")

        # Check pack loading
        if len(self.list_rule_packs()) == 0:
            validation['warnings'].append("No rule packs loaded")

        return validation

    @property
    def stats(self) -> dict[str, Any]:
        """Get preload statistics.

        Returns:
            Dictionary with:
                - rules_loaded: Number of rules loaded
                - packs_loaded: Number of packs loaded
                - patterns_compiled: Number of patterns compiled
                - preload_time_ms: Initialization time

        Example:
            raxe = Raxe()
            print(f"Loaded {raxe.stats['rules_loaded']} rules")
        """
        return {
            "rules_loaded": self.preload_stats.rules_loaded,
            "packs_loaded": self.preload_stats.packs_loaded,
            "patterns_compiled": self.preload_stats.patterns_compiled,
            "preload_time_ms": self.preload_stats.duration_ms,
            "config_loaded": self.preload_stats.config_loaded,
            "telemetry_initialized": self.preload_stats.telemetry_initialized,
        }

    def __repr__(self) -> str:
        """String representation of Raxe client.

        Returns:
            Human-readable string showing key stats
        """
        return (
            f"Raxe(initialized={self._initialized}, "
            f"rules={self.stats['rules_loaded']}, "
            f"l2_enabled={self.config.enable_l2})"
        )
