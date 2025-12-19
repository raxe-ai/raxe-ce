"""Unified RAXE client - SINGLE ENTRY POINT for all integrations.

This class is the foundation for all RAXE integrations:
- CLI commands (raxe scan)
- SDK direct usage (raxe.scan())
- Decorators (@raxe.protect)
- Wrappers (RaxeOpenAI)

ALL scanning MUST go through the Raxe.scan() method to ensure
consistency and proper configuration cascade.
"""
from __future__ import annotations

import atexit
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

from raxe.application.preloader import preload_pipeline
from raxe.application.scan_merger import ScanMerger
from raxe.application.scan_pipeline import ScanPipelineResult
from raxe.application.telemetry_orchestrator import get_orchestrator
from raxe.domain.engine.executor import Detection
from raxe.domain.engine.matcher import Match
from raxe.domain.inline_suppression import parse_inline_suppressions
from raxe.domain.ml.protocol import L2Prediction
from raxe.domain.rules.models import Severity
from raxe.domain.suppression import SuppressionAction, check_suppressions
from raxe.domain.suppression_factory import create_suppression_manager
from raxe.domain.telemetry.events import generate_event_id
from raxe.infrastructure.config.scan_config import ScanConfig
from raxe.infrastructure.database.scan_history import ScanHistoryDB
from raxe.infrastructure.tracking.usage import UsageTracker
from raxe.sdk.suppression_context import SuppressedContext, get_scoped_suppressions
from raxe.utils.logging import get_logger

# Use structured logging for better observability (privacy-preserving)
logger = get_logger(__name__)

# Reuse ScanMerger for consistent severity mapping
_scan_merger = ScanMerger()


def _l2_prediction_to_detection(
    prediction: L2Prediction,
    processing_time_ms: float = 0.0,
) -> Detection:
    """Convert an L2Prediction to a Detection object for storage.

    Maps L2 ML predictions to the Detection format used by scan history.
    This enables consistent storage and display of L2 threats alongside L1.

    Args:
        prediction: L2 prediction from ML detector
        processing_time_ms: L2 processing time for this detection

    Returns:
        Detection object compatible with scan history storage
    """
    # Map L2 confidence to severity using the same thresholds as ScanMerger
    severity = _scan_merger._map_confidence_to_severity(prediction.confidence)
    if severity is None:
        severity = Severity.INFO  # Default to INFO for low-confidence predictions

    # Extract category from threat_type or metadata
    threat_type_value = prediction.threat_type.value if prediction.threat_type else "unknown"
    category = prediction.metadata.get("family", threat_type_value) if prediction.metadata else threat_type_value

    # Create a synthetic match for L2 detections
    # L2 detections don't have pattern matches, so we create a placeholder
    synthetic_match = Match(
        pattern_index=0,
        start=0,
        end=0,
        matched_text="[ML Detection]",
        groups=(),
        context_before="",
        context_after="",
    )

    # Build rule_id from L2 threat type
    rule_id = f"L2-{threat_type_value}"

    # Use explanation or build a default message
    explanation = prediction.explanation or f"ML detected: {threat_type_value}"
    sub_family = prediction.metadata.get("sub_family", "") if prediction.metadata else ""
    message = f"L2 ML Detection: {threat_type_value}"
    if sub_family:
        message = f"L2 ML Detection: {sub_family}"

    return Detection(
        rule_id=rule_id,
        rule_version="0.0.1",
        severity=severity,
        confidence=prediction.confidence,
        matches=[synthetic_match],
        detected_at=datetime.now(timezone.utc).isoformat(),
        detection_layer="L2",
        layer_latency_ms=processing_time_ms,
        category=category,
        message=message,
        explanation=explanation,
        risk_explanation=f"ML model detected potential {threat_type_value} attack pattern",
        remediation_advice="Review the prompt for suspicious content",
        docs_url="",
    )


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

        # Context manager for automatic cleanup
        with Raxe() as raxe:
            raxe.scan("test")

    Performance:
        - Initialization: <500ms (one-time)
        - Scanning: <10ms per call (after init)
    """

    # Class-level state for atexit management
    _atexit_registered: ClassVar[bool] = False
    _flushed: ClassVar[bool] = False
    _flush_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        *,
        api_key: str | None = None,
        config_path: Path | None = None,
        telemetry: bool = True,
        l2_enabled: bool = True,
        voting_preset: str | None = None,
        progress_callback = None,
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
            voting_preset: L2 voting preset (balanced, high_security, low_fp)
            progress_callback: Optional progress indicator for initialization
            **kwargs: Additional config options passed to ScanConfig

        Raises:
            Exception: If critical components fail to load
        """
        # Store progress callback (use NullProgress if none provided)
        from raxe.cli.progress import NullProgress
        self._progress = progress_callback or NullProgress()

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

        # Validate telemetry disable against server permissions
        if not telemetry:
            # Check cached server permissions before disabling
            can_disable = self._check_telemetry_disable_permission()
            if not can_disable:
                logger.warning(
                    "telemetry_disable_denied",
                    reason="tier_not_allowed",
                    message="Your tier does not allow disabling telemetry. "
                    "Upgrade to Pro via 'raxe auth login'"
                )
                # Keep telemetry enabled (ignore the disable request)
                telemetry = True

        # Explicitly set telemetry (handles both True and False)
        self.config.telemetry.enabled = telemetry
        self.config.enable_l2 = l2_enabled

        # Store voting preset for L2 detector initialization
        self._voting_preset = voting_preset

        # Initialize tracking and history components
        # These are lazily loaded - only create files when first used
        self._usage_tracker: UsageTracker | None = None
        self._scan_history: ScanHistoryDB | None = None
        self._streak_tracker = None

        # Initialize suppression manager (auto-loads .raxe/suppressions.yaml from cwd)
        self.suppression_manager = create_suppression_manager(auto_load=True)

        # Preload pipeline (one-time startup cost ~100-200ms)
        # This compiles patterns, loads packs, warms caches
        logger.info("raxe_client_init_start")

        # Start progress indicator
        self._progress.start("Initializing RAXE...")

        try:
            self.pipeline, self.preload_stats = preload_pipeline(
                config=self.config,
                suppression_manager=self.suppression_manager,
                progress_callback=self._progress,
                voting_preset=self._voting_preset,
            )

            # Also create async pipeline for parallel L1/L2 execution (5x faster!)
            # This shares the same components but runs L1+L2 concurrently
            self._async_pipeline = None  # Lazy init on first use

            self._initialized = True

            # Initialize telemetry (non-blocking, never raises)
            self._init_telemetry()

            # Register atexit handler (once per process)
            if not Raxe._atexit_registered:
                atexit.register(Raxe._atexit_flush)
                Raxe._atexit_registered = True

            # Complete progress
            self._progress.complete(
                total_duration_ms=self.preload_stats.duration_ms
            )

            logger.info(
                "raxe_client_init_complete",
                rules_loaded=self.preload_stats.rules_loaded
            )
        except Exception as e:
            # Report error to progress
            self._progress.error("initialization", str(e))
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
                apply_policy=self.pipeline.apply_policy,
                enable_l2=self.pipeline.enable_l2,
                fail_fast_on_critical=self.pipeline.fail_fast_on_critical,
                min_confidence_for_skip=self.pipeline.min_confidence_for_skip,
                l1_timeout_ms=10.0,
                l2_timeout_ms=150.0,
            )
            logger.info("Async pipeline initialized (parallel L1+L2 execution)")

        return self._async_pipeline

    def _check_telemetry_disable_permission(self) -> bool:
        """Check if telemetry can be disabled based on cached server permissions.

        This method checks the locally cached server permissions from the
        credential store. If no cached permissions exist or they are stale,
        it defaults to allowing disable (non-blocking behavior).

        Returns:
            True if telemetry can be disabled, False if tier does not allow it.

        Note:
            This is a client-side validation for user experience. The server
            will enforce the actual restriction regardless of this check.
        """
        try:
            from raxe.infrastructure.telemetry.credential_store import CredentialStore

            store = CredentialStore()
            credentials = store.load()

            if credentials is None:
                # No credentials yet - allow disable (server will enforce)
                return True

            # Check cached permission
            # If health check is stale, default to allowing (non-blocking)
            if credentials.is_health_check_stale(max_age_hours=24):
                # Cache is stale - allow but server will enforce
                return True

            # Check the cached permission
            return credentials.can_disable_telemetry

        except Exception:
            # On any error, allow (non-blocking, server enforces)
            return True

    def _init_telemetry(self) -> None:
        """Initialize telemetry on SDK instantiation.

        This method:
        1. Ensures installation event is fired (first install tracking)
        2. Tracks SDK initialization as feature usage
        3. Starts the telemetry session

        All operations are non-blocking and never raise exceptions.
        Telemetry failures should never affect SDK functionality.

        If credentials are expired, telemetry is disabled gracefully
        and a warning is logged. The SDK continues to function normally
        for scanning operations.
        """
        try:
            # Check for expired credentials before initializing telemetry
            # This provides a clear warning without breaking SDK functionality
            from raxe.infrastructure.telemetry.credential_store import (
                CredentialExpiredError,
                CredentialStore,
            )

            store = CredentialStore()
            try:
                # Use raise_on_expired=True to get the error
                store.get_or_create(raise_on_expired=True)
            except CredentialExpiredError as e:
                # Log warning but continue without telemetry
                logger.warning(
                    "telemetry_disabled_expired_key",
                    extra={
                        "days_expired": e.days_expired,
                        "console_url": e.console_url,
                    },
                )
                logger.warning(
                    f"Telemetry disabled: {e}. "
                    "Scanning will continue to work normally."
                )
                return

            orchestrator = get_orchestrator()
            if orchestrator is None:
                return

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

            # Start the orchestrator (lazy initialization)
            orchestrator.start()

            # Ensure installation event fired
            orchestrator.ensure_installation()

            # Track SDK initialization
            if orchestrator.is_enabled():
                orchestrator.track_feature_usage(
                    feature="sdk_scan",
                    action="invoked",
                )
        except Exception:
            # Never let telemetry break SDK initialization
            pass

    def _track_scan(
        self,
        result: ScanPipelineResult,
        prompt: str,
        entry_point: str = "sdk",
        event_id: str | None = None,
        wrapper_type: str | None = None,
    ) -> None:
        """Track scan telemetry using schema v2.0 (non-blocking, never raises).

        This method sends privacy-preserving telemetry about the scan using
        the full L2 telemetry schema defined in docs/SCAN_TELEMETRY_SCHEMA.md.

        Privacy: Only hashes, metrics, and enum values are transmitted.
        No actual prompt content is ever transmitted.

        Args:
            result: The scan result to track
            prompt: Original prompt text (used for hash and length calculation)
            entry_point: How the scan was triggered (sdk, cli, wrapper)
            event_id: Pre-generated event ID for portal-CLI correlation
            wrapper_type: SDK wrapper type if applicable (openai, anthropic, etc.)
        """
        try:
            orchestrator = get_orchestrator()
            if orchestrator is None:
                return
            # Don't check is_enabled() here - let track_scan_v2() handle initialization
            # is_enabled() returns False before initialization, blocking the lazy init

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
                wrapper_type=wrapper_type,  # type: ignore[arg-type]
                action_taken="block" if result.should_block else "allow",
                l2_enabled=result.metadata.get("l2_enabled", True),
            )

            # Track using v2 method
            orchestrator.track_scan_v2(
                payload=telemetry_payload,
                event_id=event_id,
            )
        except Exception:
            # Never let telemetry break SDK functionality
            pass

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
    def from_config_file(cls, path: Path) -> Raxe:
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

    def _apply_inline_suppressions(
        self,
        result: ScanPipelineResult,
        inline_suppress: list[str | dict[str, Any]] | None,
    ) -> ScanPipelineResult:
        """Apply inline and scoped suppressions to scan result.

        This method processes suppressions in order of precedence:
        1. Scoped suppressions (from context manager)
        2. Inline suppressions (from suppress parameter)
        3. Config file suppressions (already applied by pipeline)

        Actions are handled as follows:
        - SUPPRESS: Remove detection from results
        - FLAG: Keep detection with is_flagged=True
        - LOG: Keep detection in results (for logging only)

        Args:
            result: Original scan result from pipeline
            inline_suppress: Inline suppression specs from scan() call

        Returns:
            Modified ScanPipelineResult with suppressions applied
        """
        # Parse inline suppressions
        inline_suppressions = parse_inline_suppressions(inline_suppress)

        # Get scoped suppressions from context manager
        scoped_suppressions = get_scoped_suppressions()

        # If no inline or scoped suppressions, return original result
        if not inline_suppressions and not scoped_suppressions:
            return result

        # Merge all suppressions (scoped + inline take precedence)
        # Config file suppressions are already handled by the pipeline
        all_suppressions = scoped_suppressions + inline_suppressions

        # No detections to process
        if not result.scan_result or not result.scan_result.l1_result:
            return result

        # Process detections
        from raxe.domain.engine.executor import ScanResult

        processed_detections: list[Detection] = []
        suppressed_count = 0
        flagged_count = 0

        for detection in result.scan_result.l1_result.detections:
            check_result = check_suppressions(detection.rule_id, all_suppressions)

            if check_result.is_suppressed:
                if check_result.action == SuppressionAction.SUPPRESS:
                    # Remove from results
                    suppressed_count += 1
                    logger.debug(
                        "inline_suppression_applied",
                        rule_id=detection.rule_id,
                        action="SUPPRESS",
                        reason=check_result.reason,
                    )
                elif check_result.action == SuppressionAction.FLAG:
                    # Keep with is_flagged=True
                    flagged_detection = detection.with_flag(check_result.reason)
                    processed_detections.append(flagged_detection)
                    flagged_count += 1
                    logger.debug(
                        "inline_suppression_applied",
                        rule_id=detection.rule_id,
                        action="FLAG",
                        reason=check_result.reason,
                    )
                elif check_result.action == SuppressionAction.LOG:
                    # Keep in results (LOG action just logs, doesn't modify)
                    processed_detections.append(detection)
                    logger.debug(
                        "inline_suppression_applied",
                        rule_id=detection.rule_id,
                        action="LOG",
                        reason=check_result.reason,
                    )
            else:
                # No suppression matched, keep detection
                processed_detections.append(detection)

        # Create new L1 result with processed detections
        new_l1_result = ScanResult(
            detections=processed_detections,
            scanned_at=result.scan_result.l1_result.scanned_at,
            text_length=result.scan_result.l1_result.text_length,
            rules_checked=result.scan_result.l1_result.rules_checked,
            scan_duration_ms=result.scan_result.l1_result.scan_duration_ms,
        )

        # Create new combined result
        from raxe.application.scan_merger import CombinedScanResult

        new_combined = CombinedScanResult(
            l1_result=new_l1_result,
            l2_result=result.scan_result.l2_result,
            combined_severity=result.scan_result.combined_severity,
            total_processing_ms=result.scan_result.total_processing_ms,
            metadata={
                **result.scan_result.metadata,
                "inline_suppressed_count": suppressed_count,
                "inline_flagged_count": flagged_count,
            },
        )

        # Recalculate combined severity based on remaining detections
        if new_l1_result.has_detections:
            new_combined = CombinedScanResult(
                l1_result=new_l1_result,
                l2_result=result.scan_result.l2_result,
                combined_severity=new_l1_result.highest_severity,
                total_processing_ms=result.scan_result.total_processing_ms,
                metadata=new_combined.metadata,
            )

        # Create new pipeline result
        new_metadata = dict(result.metadata) if result.metadata else {}
        new_metadata["inline_suppressed_count"] = suppressed_count
        new_metadata["inline_flagged_count"] = flagged_count


        return ScanPipelineResult(
            scan_result=new_combined,
            policy_decision=result.policy_decision,
            should_block=result.should_block,
            duration_ms=result.duration_ms,
            text_hash=result.text_hash,
            metadata=new_metadata,
            l1_detections=len([d for d in processed_detections if d.detection_layer == "L1"]),
            l2_detections=result.l2_detections,
            plugin_detections=result.plugin_detections,
            l1_duration_ms=result.l1_duration_ms,
            l2_duration_ms=result.l2_duration_ms,
        )

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
        suppress: list[str | dict[str, Any]] | None = None,
    ) -> ScanPipelineResult:
        """Scan text for security threats with layer control.

        THIS IS THE ONLY SCAN METHOD. All other interfaces call this.

        The scan method:
        1. Validates input
        2. Executes full scan pipeline (L1, L2, policy, telemetry)
        3. Applies suppressions (inline + config file + scoped)
        4. Returns comprehensive results
        5. Optionally raises exception if blocking enabled

        Response Scanning Warning:
            RAXE can DETECT threats in LLM responses but CANNOT MODIFY them.
            Response scanning is for monitoring and alerting only. Implement
            application-level fallbacks when threats are detected in responses.

            Example:
                response = llm.generate(prompt)
                scan_result = raxe.scan(response)
                if scan_result.has_threats:
                    logger.warning(f"Response threat: {scan_result.combined_severity}")
                    return "I cannot provide that information."  # Fallback

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
            suppress: Optional list of inline suppressions. Can be:
                - String patterns: ["pi-001", "jb-*"]
                - Dicts with action: [{"pattern": "jb-*", "action": "FLAG", "reason": "..."}]
                Actions: SUPPRESS (remove), FLAG (keep with is_flagged=True), LOG (keep)
                Inline suppressions take precedence over config file suppressions.

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

            # Suppress specific rules
            result = raxe.scan(text, suppress=["pi-001", "jb-*"])

            # Suppress with action override (FLAG instead of remove)
            result = raxe.scan(text, suppress=[
                "pi-001",  # Remove from results
                {"pattern": "jb-*", "action": "FLAG", "reason": "Under review"}
            ])
        """
        # Handle empty text - return clean result (no threats)
        if not text or not text.strip():
            from datetime import datetime, timezone

            from raxe.application.scan_merger import CombinedScanResult
            from raxe.application.scan_pipeline import BlockAction
            from raxe.domain.engine.executor import ScanResult

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
                    _ = asyncio.get_running_loop()
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

        # Apply inline and scoped suppressions (takes precedence over config file)
        # This must happen after the scan but before tracking
        result = self._apply_inline_suppressions(result, suppress)

        # Record scan in tracking and history
        # This captures:
        # 1. Usage metrics (install tracking, time-to-first-scan)
        # 2. Scan history (privacy-preserving hashes only)
        # 3. Structured logging (no PII)
        # Skipped if dry_run=True
        if not dry_run:
            try:
                # Generate event_id FIRST for portal-CLI correlation
                # This ID links local scan history to telemetry events
                # IMPORTANT: Same event_id is used for both local storage and telemetry
                event_id = generate_event_id()

                # Track telemetry (non-blocking, privacy-preserving)
                # Pass event_id to ensure telemetry uses the same ID as local storage
                # Pass original prompt for accurate hash and length calculation
                self._track_scan(result, prompt=text, entry_point="sdk", event_id=event_id)

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
                # Extract detections from result (both L1 and L2)
                detections = []
                if result.scan_result and result.scan_result.l1_result:
                    detections.extend(result.scan_result.l1_result.detections)

                # Convert L2 predictions to Detection objects for consistent storage
                l2_duration_ms = None
                if result.scan_result and result.scan_result.l2_result:
                    l2_result = result.scan_result.l2_result
                    l2_duration_ms = l2_result.processing_time_ms
                    # Calculate per-prediction latency (distribute evenly)
                    per_prediction_ms = (
                        l2_result.processing_time_ms / len(l2_result.predictions)
                        if l2_result.predictions else 0.0
                    )
                    for prediction in l2_result.predictions:
                        l2_detection = _l2_prediction_to_detection(
                            prediction,
                            processing_time_ms=per_prediction_ms
                        )
                        detections.append(l2_detection)

                self.scan_history.record_scan(
                    prompt=text,
                    detections=detections,
                    l1_duration_ms=result.scan_result.l1_result.scan_duration_ms if result.scan_result and result.scan_result.l1_result else None,
                    l2_duration_ms=l2_duration_ms,
                    version="0.0.1",
                    event_id=event_id,
                )

                # Attach event_id to result metadata for external access
                if result.metadata is None:
                    result.metadata = {}
                result.metadata["event_id"] = event_id

                # Structured logging (privacy-preserving)
                # Include initialization timing (separate from scan timing)
                init_stats = self.initialization_stats
                logger.info(
                    "scan_completed",
                    prompt_hash=result.text_hash,
                    has_threats=result.has_threats,
                    detection_count=result.total_detections,
                    severity=result.severity if result.has_threats else "none",
                    scan_duration_ms=result.duration_ms,  # Actual scan time (not including init)
                    initialization_ms=init_stats.get("total_init_time_ms", 0),  # One-time init cost
                    l2_init_ms=init_stats.get("l2_init_time_ms", 0),  # ML model loading time
                    l2_model_type=init_stats.get("l2_model_type", "none"),  # onnx_int8, sentence_transformers, stub
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
            # Include initialization timing (separate from scan timing)
            init_stats = self.initialization_stats
            logger.info(
                "scan_completed_dry_run",
                prompt_hash=result.text_hash,
                has_threats=result.has_threats,
                detection_count=result.total_detections,
                severity=result.severity if result.has_threats else "none",
                scan_duration_ms=result.duration_ms,  # Actual scan time (not including init)
                initialization_ms=init_stats.get("total_init_time_ms", 0),  # One-time init cost
                l2_init_ms=init_stats.get("l2_init_time_ms", 0),  # ML model loading time
                l2_model_type=init_stats.get("l2_model_type", "none"),  # onnx_int8, sentence_transformers, stub
                l1_enabled=l1_enabled,
                l2_enabled=l2_enabled,
                mode=mode
            )

        # Enforce blocking if requested
        # When block_on_threat=True, the user explicitly wants blocking on ANY threat
        # This overrides the policy-based should_block (which may be WARN/ALLOW)
        if block_on_threat and result.has_threats:
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

    def suppressed(
        self,
        *patterns: str,
        action: str = "SUPPRESS",
        reason: str = "Scoped suppression",
    ) -> SuppressedContext:
        """Context manager for scoped suppression.

        All scans within the context will have the specified patterns suppressed.
        This is useful for temporarily disabling specific rules during testing
        or for specific code paths where false positives are known.

        The context manager is thread-safe using contextvars.

        Args:
            *patterns: One or more rule ID patterns to suppress (e.g., "pi-*", "jb-001")
            action: Action to take - "SUPPRESS" (remove), "FLAG" (mark), or "LOG" (keep)
            reason: Reason for suppression (for audit trail)

        Returns:
            Context manager that applies suppressions within its scope

        Example:
            # Suppress all prompt injection rules during testing
            with raxe.suppressed("pi-*", reason="Testing auth flow"):
                result = raxe.scan(text)
                # pi-* patterns are suppressed in this scan

            # Suppress multiple patterns
            with raxe.suppressed("pi-*", "jb-*", reason="Known false positives"):
                result = raxe.scan(text)

            # Flag instead of suppress (keeps detection with is_flagged=True)
            with raxe.suppressed("pi-*", action="FLAG", reason="Under review"):
                result = raxe.scan(text)
                # Detections have is_flagged=True instead of being removed
        """
        return SuppressedContext(
            self,
            *patterns,
            action=action,
            reason=reason,
        )

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
            'telemetry_enabled': self.get_telemetry_enabled(),
            'has_api_key': self.has_api_key(),
            'l2_enabled': self.config.enable_l2
        }

        # Add preload stats if available
        if hasattr(self, 'preload_stats'):
            stats['preload_time_ms'] = self.preload_stats.duration_ms
            stats['patterns_compiled'] = self.preload_stats.patterns_compiled
            stats['l2_init_time_ms'] = self.preload_stats.l2_init_time_ms
            stats['l2_model_type'] = self.preload_stats.l2_model_type

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

        # Check rule loading
        if len(self.get_all_rules()) == 0:
            validation['warnings'].append("No detection rules loaded")

        # Check pack loading
        if len(self.list_rule_packs()) == 0:
            validation['warnings'].append("No rule packs loaded")

        return validation

    @property
    def initialization_stats(self) -> dict[str, Any]:
        """Get initialization statistics (separate from scan timing).

        This property provides detailed initialization metrics separated
        from scan performance metrics. Useful for understanding startup costs.

        Returns:
            Dictionary with:
                - total_init_time_ms: Total initialization time (preload + L2)
                - preload_time_ms: Core preload time (rules, packs, patterns)
                - l2_init_time_ms: L2 model initialization time
                - l2_model_type: Type of L2 model loaded
                - rules_loaded: Number of rules loaded
                - packs_loaded: Number of packs loaded
                - patterns_compiled: Number of patterns compiled
                - config_loaded: True if config loaded successfully
                - telemetry_initialized: True if telemetry initialized

        Example:
            raxe = Raxe()
            init_stats = raxe.initialization_stats
            print(f"Total init: {init_stats['total_init_time_ms']}ms")
            print(f"L2 init: {init_stats['l2_init_time_ms']}ms ({init_stats['l2_model_type']})")
        """
        return {
            "total_init_time_ms": self.preload_stats.duration_ms,
            "preload_time_ms": self.preload_stats.duration_ms - self.preload_stats.l2_init_time_ms,
            "l2_init_time_ms": self.preload_stats.l2_init_time_ms,
            "l2_model_type": self.preload_stats.l2_model_type,
            "rules_loaded": self.preload_stats.rules_loaded,
            "packs_loaded": self.preload_stats.packs_loaded,
            "patterns_compiled": self.preload_stats.patterns_compiled,
            "config_loaded": self.preload_stats.config_loaded,
            "telemetry_initialized": self.preload_stats.telemetry_initialized,
        }

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
            "l2_init_time_ms": self.preload_stats.l2_init_time_ms,
            "l2_model_type": self.preload_stats.l2_model_type,
        }

    def close(self) -> None:
        """Close client and flush pending telemetry.

        This method ensures all queued telemetry events are sent before
        the client is closed. It's safe to call multiple times.

        For long-running applications, consider using the context manager
        pattern instead:
            with Raxe() as raxe:
                raxe.scan("test")
        """
        self._flush_telemetry()

    def _flush_telemetry(self) -> None:
        """Internal method to flush telemetry (thread-safe)."""
        with Raxe._flush_lock:
            if Raxe._flushed:
                return

            try:
                from raxe.infrastructure.telemetry.flush_helper import (
                    ensure_telemetry_flushed,
                )
                ensure_telemetry_flushed(
                    timeout_seconds=2.0,
                    max_batches=50,
                    batch_size=50,
                    end_session=True,
                )
                Raxe._flushed = True
            except Exception:
                pass  # Never fail on telemetry cleanup

    @classmethod
    def _atexit_flush(cls) -> None:
        """Class method for atexit handler."""
        with cls._flush_lock:
            if cls._flushed:
                return
            try:
                from raxe.infrastructure.telemetry.flush_helper import (
                    ensure_telemetry_flushed,
                )
                ensure_telemetry_flushed(
                    timeout_seconds=2.0,
                    max_batches=50,
                    batch_size=50,
                    end_session=True,
                )
                cls._flushed = True
            except Exception:
                pass  # Never fail on atexit

    @classmethod
    def _reset_flush_state(cls) -> None:
        """Reset flush state (for testing only)."""
        with cls._flush_lock:
            cls._flushed = False
            cls._atexit_registered = False

    def __enter__(self) -> Raxe:
        """Enter context manager.

        Returns:
            Self for use in with statement
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager and cleanup.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        self.close()

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
