"""Complete scan pipeline orchestrator.

Application layer - integrates all components into a unified scanning pipeline:
- L1 rule-based detection (Phase 1b)
- L2 ML-based detection (Phase 1c stub)
- Result merging (Phase 1c)
- Pack loading (Phase 2a)
- Policy evaluation (Phase 3a - if available)
- Privacy-first telemetry (Phase 3b)
- Schema validation (Sprint 3)

Performance targets:
- P95 end-to-end latency: <10ms
- Component breakdown: L1 <5ms, L2 <1ms, overhead <4ms
"""
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from raxe.application.apply_policy import ApplyPolicyUseCase
from raxe.application.scan_merger import CombinedScanResult, ScanMerger
from raxe.application.telemetry_orchestrator import get_orchestrator
from raxe.domain.engine.executor import Detection, RuleExecutor
from raxe.domain.ml.protocol import L2Detector, L2Result
from raxe.domain.policies.models import PolicyAction
from raxe.infrastructure.packs.registry import PackRegistry
from raxe.infrastructure.telemetry.hook import TelemetryHook
from raxe.utils.logging import get_logger

# Temporary BlockAction enum for backward compatibility
from enum import Enum

class BlockAction(Enum):
    """Temporary backward compatibility - maps to PolicyAction."""
    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"
    CHALLENGE = "CHALLENGE"

# Import metrics collector
try:
    from raxe.monitoring.metrics import collector
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    collector = None  # type: ignore

logger = get_logger(__name__)


@dataclass(frozen=True)
class ScanPipelineResult:
    """Complete result from full scan pipeline.

    Attributes:
        scan_result: Combined L1+L2 detection results
        policy_decision: Action determined by policy (ALLOW/WARN/BLOCK)
        should_block: True if request should be blocked
        duration_ms: Total pipeline execution time
        text_hash: SHA256 hash of scanned text (privacy-preserving)
        metadata: Additional pipeline metadata
        l1_detections: Count of L1 detections
        l2_detections: Count of L2 predictions
        plugin_detections: Count of plugin detections
        l1_duration_ms: L1 processing time
        l2_duration_ms: L2 processing time
    """
    scan_result: CombinedScanResult
    policy_decision: BlockAction
    should_block: bool
    duration_ms: float
    text_hash: str
    metadata: dict[str, object]
    l1_detections: int = 0
    l2_detections: int = 0
    plugin_detections: int = 0
    l1_duration_ms: float = 0.0
    l2_duration_ms: float = 0.0

    def __post_init__(self) -> None:
        """Validate pipeline result."""
        if self.duration_ms < 0:
            raise ValueError(f"duration_ms cannot be negative: {self.duration_ms}")

    @property
    def has_threats(self) -> bool:
        """True if any threats detected."""
        return self.scan_result.has_threats

    @property
    def severity(self) -> str | None:
        """Highest severity across all detections."""
        if self.scan_result.combined_severity:
            return self.scan_result.combined_severity.value
        return None

    @property
    def total_detections(self) -> int:
        """Total detections across L1 and L2."""
        return self.scan_result.total_threat_count

    @property
    def detections(self) -> list:
        """All detections from L1 rules as a flat list.

        Convenience property that provides direct access to L1 detection objects
        without requiring deep nesting into scan_result.l1_result.detections.

        Note: L2 predictions are not included here as they have a different
        structure (L2Prediction vs Detection). Use scan_result.l2_predictions
        for ML predictions.

        Returns:
            List of Detection objects from L1 rule matching

        Example:
            # Instead of:
            result.scan_result.l1_result.detections

            # Use:
            result.detections
        """
        return self.scan_result.l1_detections

    def __bool__(self) -> bool:
        """Boolean evaluation: True when safe, False when threats detected.

        Enables intuitive conditional checks:
            if result:      # True when safe (no threats)
            if not result:  # True when threats detected

        This follows the principle that a "good" scan result is truthy.

        Returns:
            True if no threats detected, False if threats present

        Example:
            result = pipeline.scan("Hello world")
            if result:
                print("Safe to proceed")
            else:
                print("Threats detected, blocking")
        """
        return not self.has_threats

    def layer_breakdown(self) -> dict[str, int]:
        """Return detection count by layer.

        Returns:
            Dictionary with layer names and detection counts
        """
        return {
            "L1": self.l1_detections,
            "L2": self.l2_detections,
            "PLUGIN": self.plugin_detections,
        }

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of pipeline result
        """
        return {
            "has_threats": self.has_threats,
            "should_block": self.should_block,
            "policy_decision": self.policy_decision.value,
            "severity": self.severity,
            "total_detections": self.total_detections,
            "duration_ms": self.duration_ms,
            "text_hash": self.text_hash,
            "scan_result": self.scan_result.to_dict(),
            "metadata": self.metadata,
            "layer_breakdown": self.layer_breakdown(),
            "l1_detections": self.l1_detections,
            "l2_detections": self.l2_detections,
            "plugin_detections": self.plugin_detections,
            "l1_duration_ms": self.l1_duration_ms,
            "l2_duration_ms": self.l2_duration_ms,
        }


class ScanPipeline:
    """Complete scan pipeline orchestrator.

    Integrates all scanning components into a unified workflow:
    1. Load rules from pack registry
    2. Execute L1 rule-based detection
    3. Execute L2 ML-based analysis (optional, can skip on CRITICAL)
    4. Merge L1+L2 results
    5. Evaluate policy to determine action
    6. Record telemetry (privacy-preserving)

    This is the main entry point for all scanning operations.

    Example usage:
        pipeline = ScanPipeline(
            pack_registry=registry,
            rule_executor=executor,
            l2_detector=detector,
            scan_merger=merger,
            apply_policy=ApplyPolicyUseCase(),
        )

        result = pipeline.scan("Ignore all previous instructions")
        if result.should_block:
            raise BlockedError(result.policy_decision)
    """

    def __init__(
        self,
        pack_registry: PackRegistry,
        rule_executor: RuleExecutor,
        l2_detector: L2Detector,
        scan_merger: ScanMerger,
        *,
        apply_policy: ApplyPolicyUseCase | None = None,
        telemetry_hook: TelemetryHook | None = None,
        plugin_manager: object | None = None,  # PluginManager type hint circular
        suppression_manager: object | None = None,  # SuppressionManager type hint
        enable_l2: bool = True,
        fail_fast_on_critical: bool = True,
        min_confidence_for_skip: float = 0.7,
        enable_schema_validation: bool = False,
        schema_validation_mode: str = "log_only",
    ):
        """Initialize scan pipeline.

        Args:
            pack_registry: Pack registry for loading rules
            rule_executor: L1 rule execution engine
            l2_detector: L2 ML detector (protocol implementation)
            scan_merger: Result merger
            apply_policy: Policy application use case (None = no policy enforcement)
            telemetry_hook: Optional telemetry sender (legacy)
            plugin_manager: Optional plugin manager for extensibility
            suppression_manager: Optional suppression manager for false positives
            enable_l2: Enable L2 analysis (default: True)
            fail_fast_on_critical: Skip L2 if CRITICAL detected (optimization)
            min_confidence_for_skip: Minimum L1 confidence to skip L2 on CRITICAL (default: 0.7)
            enable_schema_validation: Enable runtime schema validation
            schema_validation_mode: Validation mode (log_only, warn, enforce)
        """
        self.pack_registry = pack_registry
        self.rule_executor = rule_executor
        self.l2_detector = l2_detector
        self.scan_merger = scan_merger
        self.apply_policy = apply_policy or ApplyPolicyUseCase()  # Default policy
        self.telemetry_hook = telemetry_hook
        self.plugin_manager = plugin_manager  # NEW: Plugin system integration
        self.suppression_manager = suppression_manager  # NEW: Suppression system
        self.enable_l2 = enable_l2
        self.fail_fast_on_critical = fail_fast_on_critical
        self.min_confidence_for_skip = min_confidence_for_skip
        self.enable_schema_validation = enable_schema_validation
        self.schema_validation_mode = schema_validation_mode

        # Initialize schema validator if needed
        self._validator = None
        if self.enable_schema_validation:
            try:
                from raxe.infrastructure.schemas.validator import get_validator
                self._validator = get_validator()
                logger.info(f"Schema validation enabled (mode={schema_validation_mode})")
            except Exception as e:
                logger.warning(f"Failed to initialize schema validator: {e}")
                self._validator = None

        # Performance tracking
        self._scan_count = 0
        self._total_duration_ms = 0.0
        self._validation_errors = 0

    def scan(
        self,
        text: str,
        *,
        customer_id: str | None = None,
        context: dict[str, object] | None = None,
        l1_enabled: bool = True,
        l2_enabled: bool = True,
        mode: str = "balanced",
        confidence_threshold: float = 0.5,
        explain: bool = False,
    ) -> ScanPipelineResult:
        """Execute complete scan pipeline with layer control.

        Args:
            text: Text to scan for threats
            customer_id: Optional customer ID for policy lookup
            context: Optional context metadata
            l1_enabled: Run L1 (regex) detection (default: True)
            l2_enabled: Run L2 (ML) detection (default: True)
            mode: Performance mode - "fast", "balanced", or "thorough" (default: "balanced")
                - fast: L1 only, skip expensive rules (<3ms target)
                - balanced: L1 + L2 with default rules (<10ms target)
                - thorough: All layers, all rules (<100ms acceptable)
            confidence_threshold: Minimum confidence to report detections (default: 0.5)
            explain: Include explanation in detections (default: False)

        Returns:
            ScanPipelineResult with complete analysis and policy decision

        Raises:
            ValueError: If text is empty or invalid or mode is invalid
        """
        # Validate mode
        if mode not in ("fast", "balanced", "thorough"):
            error = ValueError(f"mode must be 'fast', 'balanced', or 'thorough', got '{mode}'")
            self._track_scan_error(error, error_code="SCAN_002", is_recoverable=False)
            raise error
        if not text:
            error = ValueError("Text cannot be empty")
            self._track_scan_error(error, error_code="SCAN_003", is_recoverable=False)
            raise error

        # Apply mode-specific configurations
        if mode == "fast":
            # Fast mode: L1 only, no L2
            l1_enabled = True
            l2_enabled = False
        elif mode == "balanced":
            # Balanced mode: use provided settings or defaults
            pass  # Use l1_enabled and l2_enabled as provided
        elif mode == "thorough":
            # Thorough mode: all layers enabled
            l1_enabled = True
            l2_enabled = True

        # Initialize telemetry orchestrator (lazy init, fires installation event if needed)
        try:
            orchestrator = get_orchestrator()
            if orchestrator:
                orchestrator.ensure_installation()
        except Exception as e:
            # Never let telemetry errors break scanning
            logger.debug(f"Telemetry orchestrator init error (non-blocking): {e}")
            orchestrator = None

        start_time = time.perf_counter()
        scan_timestamp = datetime.now(timezone.utc).isoformat()

        # Record input length for metrics
        input_length = len(text.encode('utf-8'))

        # PLUGIN HOOK: on_scan_start (allow text transformation)
        if self.plugin_manager:
            try:
                transformed_results = self.plugin_manager.execute_hook(
                    "on_scan_start", text, context
                )
                # Use first transformation if any plugins returned one
                if transformed_results:
                    text = transformed_results[0]
                    logger.debug("Plugin transformed input text")
            except Exception as e:
                logger.error(f"Plugin on_scan_start hook failed: {e}")

        # 1. Load rules from pack registry
        rules = self.pack_registry.get_all_rules()

        # 2. Execute L1 rule-based detection (if enabled)
        # NOTE: L1 and L2 are NOT run in parallel because:
        # - L1 is very fast (~1ms) while L2 dominates (~110ms)
        # - Thread pool overhead (~0.5ms) cancels out parallelism benefit
        # - Sequential execution is simpler and easier to debug
        # - If L1 becomes slower in future, reconsider parallelization
        l1_duration_ms = 0.0
        if l1_enabled:
            l1_start = time.perf_counter()
            if METRICS_AVAILABLE and collector:
                with collector.measure_scan("regex"):
                    l1_result = self.rule_executor.execute_rules(text, rules)
            else:
                l1_result = self.rule_executor.execute_rules(text, rules)
            l1_duration_ms = (time.perf_counter() - l1_start) * 1000
        else:
            # L1 disabled - create empty result
            from raxe.domain.engine.executor import ScanResult
            l1_result = ScanResult(
                detections=[],
                scanned_at=scan_timestamp,
                text_length=len(text),
                rules_checked=0,
                scan_duration_ms=0.0,
            )

        # PLUGIN HOOK: run detector plugins (merge with L1)
        plugin_detection_count = 0
        if self.plugin_manager:
            try:
                plugin_detections = self.plugin_manager.run_detectors(text, context)
                if plugin_detections:
                    # Merge plugin detections into L1 result
                    from raxe.domain.engine.executor import ScanResult
                    l1_result = ScanResult(
                        detections=l1_result.detections + plugin_detections,
                        has_detections=l1_result.has_detections or len(plugin_detections) > 0,
                        highest_severity=l1_result.highest_severity,  # Will be recalculated
                        total_rules_checked=l1_result.total_rules_checked + len(plugin_detections),
                        execution_time_ms=l1_result.execution_time_ms,
                    )
                    plugin_detection_count = len(plugin_detections)
                    logger.debug(f"Plugins detected {plugin_detection_count} additional threats")
            except Exception as e:
                logger.error(f"Plugin detectors failed: {e}")

        # 3. Execute L2 analysis (with optimizations and layer control)
        l2_result = None
        l2_duration_ms = 0.0
        if l2_enabled and self.enable_l2:
            # Optimization: skip L2 if CRITICAL already detected with high confidence
            should_skip_l2 = False
            if self.fail_fast_on_critical and l1_result.highest_severity:
                from raxe.domain.rules.models import Severity
                if l1_result.highest_severity == Severity.CRITICAL:
                    # Check confidence of CRITICAL detections
                    max_confidence = max(
                        (d.confidence for d in l1_result.detections
                         if d.severity == Severity.CRITICAL),
                        default=0.0
                    )

                    if max_confidence >= self.min_confidence_for_skip:
                        # High confidence CRITICAL - skip L2 for performance
                        should_skip_l2 = True
                        logger.info(
                            "l2_scan_skipped",
                            reason="critical_l1_detection_high_confidence",
                            l1_severity="CRITICAL",
                            l1_max_confidence=max_confidence,
                            skip_threshold=self.min_confidence_for_skip,
                            text_hash=self._hash_text(text),
                        )
                    else:
                        # Low confidence CRITICAL - run L2 for validation
                        logger.debug(
                            f"Running L2 despite CRITICAL: low confidence {max_confidence:.2%} "
                            f"(threshold: {self.min_confidence_for_skip:.2%})"
                        )

            if not should_skip_l2:
                l2_start = time.perf_counter()
                if METRICS_AVAILABLE and collector:
                    with collector.measure_scan("ml"):
                        l2_result = self.l2_detector.analyze(text, l1_result, context)
                else:
                    l2_result = self.l2_detector.analyze(text, l1_result, context)
                l2_duration_ms = (time.perf_counter() - l2_start) * 1000

        # Log L2 inference results
        if l2_result and l2_result.has_predictions:
            # Log each L2 prediction with full context (including new bundle schema fields)
            for prediction in l2_result.predictions:
                # Extract bundle schema fields if available
                log_data = {
                    "threat_type": prediction.threat_type.value,
                    "confidence": prediction.confidence,
                    "explanation": prediction.explanation or "No explanation provided",
                    "features_used": prediction.features_used or [],
                    "text_hash": self._hash_text(text),
                    "processing_time_ms": l2_result.processing_time_ms,
                    "model_version": l2_result.model_version,
                }

                # Add new bundle schema fields (is_attack, family, sub_family, etc.)
                if "is_attack" in prediction.metadata:
                    log_data["is_attack"] = prediction.metadata["is_attack"]
                if "family" in prediction.metadata:
                    log_data["family"] = prediction.metadata["family"]
                if "sub_family" in prediction.metadata:
                    log_data["sub_family"] = prediction.metadata["sub_family"]
                if "scores" in prediction.metadata:
                    log_data["scores"] = prediction.metadata["scores"]
                if "why_it_hit" in prediction.metadata:
                    log_data["why_it_hit"] = prediction.metadata["why_it_hit"]
                if "recommended_action" in prediction.metadata:
                    log_data["recommended_action"] = prediction.metadata["recommended_action"]
                if "trigger_matches" in prediction.metadata:
                    log_data["trigger_matches"] = prediction.metadata["trigger_matches"]
                if "uncertain" in prediction.metadata:
                    log_data["uncertain"] = prediction.metadata["uncertain"]

                # Log with all available data
                logger.info("l2_threat_detected", **log_data)
        elif l2_result:
            # Log clean L2 scan
            logger.debug(
                "l2_scan_clean",
                processing_time_ms=l2_result.processing_time_ms,
                model_version=l2_result.model_version,
                confidence=l2_result.confidence,
                text_hash=self._hash_text(text),
            )

        # 4. Apply confidence threshold filtering
        if confidence_threshold > 0:
            filtered_detections = [
                d for d in l1_result.detections
                if d.confidence >= confidence_threshold
            ]
            from raxe.domain.engine.executor import ScanResult
            l1_result = ScanResult(
                detections=filtered_detections,
                scanned_at=l1_result.scanned_at,
                text_length=l1_result.text_length,
                rules_checked=l1_result.rules_checked,
                scan_duration_ms=l1_result.scan_duration_ms,
            )

        # 4.5. Apply suppressions (Filter, flag, or log detections based on action)
        suppressed_count = 0
        flagged_count = 0
        logged_count = 0
        if self.suppression_manager:
            from raxe.domain.suppression import SuppressionAction

            processed_detections = []
            for detection in l1_result.detections:
                check_result = self.suppression_manager.check_suppression(detection.rule_id)

                if check_result.is_suppressed:
                    if check_result.action == SuppressionAction.SUPPRESS:
                        # Fully suppress - remove from results
                        suppressed_count += 1
                        logger.debug(f"Suppressed {detection.rule_id}: {check_result.reason}")
                    elif check_result.action == SuppressionAction.FLAG:
                        # Flag for review - keep in results but mark as flagged
                        flagged_count += 1
                        logger.debug(f"Flagged {detection.rule_id}: {check_result.reason}")
                        # Use Detection.with_flag() to create flagged copy
                        flagged_detection = detection.with_flag(check_result.reason)
                        processed_detections.append(flagged_detection)
                    elif check_result.action == SuppressionAction.LOG:
                        # Log only - keep in results (for metrics/logging)
                        logged_count += 1
                        logger.debug(f"Logged {detection.rule_id}: {check_result.reason}")
                        processed_detections.append(detection)

                    # Log suppression application to audit log
                    self.suppression_manager.log_suppression_applied(
                        rule_id=detection.rule_id,
                        reason=check_result.reason,
                        action=check_result.action,
                    )
                else:
                    processed_detections.append(detection)

            # Update l1_result with processed detections
            from raxe.domain.engine.executor import ScanResult
            l1_result = ScanResult(
                detections=processed_detections,
                scanned_at=l1_result.scanned_at,
                text_length=l1_result.text_length,
                rules_checked=l1_result.rules_checked,
                scan_duration_ms=l1_result.scan_duration_ms,
            )

        # 5. Merge L1+L2 results
        metadata: dict[str, object] = {
            "customer_id": customer_id,
            "scan_timestamp": scan_timestamp,
            "rules_loaded": len(rules),
            "l2_skipped": self.enable_l2 and l2_result is None,
            "l1_duration_ms": l1_duration_ms,
            "l2_duration_ms": l2_duration_ms,
            "input_length": input_length,
            "mode": mode,
            "l1_enabled": l1_enabled,
            "l2_enabled": l2_enabled,
            "confidence_threshold": confidence_threshold,
            "explain": explain,
            "suppressed_count": suppressed_count,  # Track fully suppressed
            "flagged_count": flagged_count,  # Track flagged for review
            "logged_count": logged_count,  # Track logged for metrics
        }
        if context:
            metadata["context"] = context

        combined_result = self.scan_merger.merge(
            l1_result=l1_result,
            l2_result=l2_result,
            metadata=metadata,
        )

        # 6. Evaluate policy to determine action
        # CRITICAL: Policy must consider BOTH L1 and L2 detections
        # We evaluate using the combined result to include L2 predictions
        policy_decision, should_block = self._evaluate_policy(
            l1_result=l1_result,
            l2_result=l2_result,
            combined_severity=combined_result.combined_severity
        )

        # 7. Calculate text hash (privacy-preserving)
        text_hash = self._hash_text(text)

        # Calculate total duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Calculate layer statistics
        breakdown = combined_result.layer_breakdown()
        l1_count = breakdown.get("L1", 0)
        l2_count = breakdown.get("L2", 0)
        plugin_count = breakdown.get("PLUGIN", 0)

        # Create final result with layer attribution
        result = ScanPipelineResult(
            scan_result=combined_result,
            policy_decision=policy_decision,
            should_block=should_block,
            duration_ms=duration_ms,
            text_hash=text_hash,
            metadata=metadata,
            l1_detections=l1_count,
            l2_detections=l2_count,
            plugin_detections=plugin_count,
            l1_duration_ms=l1_duration_ms,
            l2_duration_ms=l2_duration_ms,
        )

        # Record Prometheus metrics
        if METRICS_AVAILABLE and collector:
            try:
                # Record scan metrics
                severity = result.severity or "none"
                collector.record_scan_simple(
                    severity=severity,
                    blocked=result.should_block,
                    detection_count=result.total_detections,
                    input_length=input_length,
                )

                # Record individual detections
                for detection in l1_result.detections:
                    if METRICS_AVAILABLE:
                        from raxe.monitoring.metrics import detections_total, rule_matches
                        detections_total.labels(
                            rule_id=detection.rule_id,
                            severity=detection.severity.value,
                            category=getattr(detection, "category", "unknown"),
                        ).inc()
                        rule_matches.labels(
                            rule_id=detection.rule_id,
                            severity=detection.severity.value,
                        ).inc()
            except Exception as e:
                # Never fail scan due to metrics errors
                logger.debug(f"Metrics recording error (non-blocking): {e}")

        # 7. Record telemetry (privacy-preserving) - legacy hook only
        # NOTE: Primary telemetry is handled by SDK client via TelemetryOrchestrator
        if self.telemetry_hook:
            self._send_telemetry(result, customer_id)

        # NOTE: Scan telemetry tracking moved to SDK client (sdk/client.py:_track_scan)
        # to avoid duplicate tracking. The SDK is the canonical location for telemetry
        # because it:
        # 1. Generates event_id for portal-CLI correlation
        # 2. Is the "outer layer" with full context
        # 3. Can be called by multiple entry points (CLI, SDK, wrappers)
        #
        # The orchestrator initialization above (lines 335-343) is kept for:
        # - ensure_installation() on first scan
        # - Error tracking via _track_scan_error()

        # PLUGIN HOOK: on_scan_complete
        if self.plugin_manager:
            try:
                self.plugin_manager.execute_hook("on_scan_complete", result)
            except Exception as e:
                logger.error(f"Plugin on_scan_complete hook failed: {e}")

        # PLUGIN HOOK: on_threat_detected (if threats found)
        if self.plugin_manager and result.has_threats:
            try:
                self.plugin_manager.execute_hook("on_threat_detected", result)
            except Exception as e:
                logger.error(f"Plugin on_threat_detected hook failed: {e}")

        # PLUGIN HOOK: run action plugins
        if self.plugin_manager:
            try:
                self.plugin_manager.run_actions(result)
            except Exception as e:
                logger.error(f"Plugin actions failed: {e}")

        # Track performance
        self._scan_count += 1
        self._total_duration_ms += duration_ms

        return result

    def scan_batch(
        self,
        texts: list[str],
        *,
        customer_id: str | None = None,
        context: dict[str, object] | None = None,
    ) -> list[ScanPipelineResult]:
        """Scan multiple texts.

        Args:
            texts: List of texts to scan
            customer_id: Optional customer ID
            context: Optional context metadata

        Returns:
            List of scan results (one per text)
        """
        results = []
        for text in texts:
            result = self.scan(
                text,
                customer_id=customer_id,
                context=context,
            )
            results.append(result)
        return results

    def _evaluate_policy(
        self,
        l1_result: object,
        l2_result: L2Result | None,
        combined_severity: object | None,
    ) -> tuple[BlockAction, bool]:
        """Evaluate policy using ApplyPolicyUseCase for both L1 and L2 detections.

        Applies advanced policies to all detections:
        1. L1 detections (real rules with versioned IDs)
        2. L2 predictions (mapped to virtual rules)

        Args:
            l1_result: L1 scan result with rule detections
            l2_result: L2 scan result with ML predictions (optional)
            combined_severity: Maximum severity across L1 and L2

        Returns:
            Tuple of (policy_decision, should_block)
        """
        from raxe.application.apply_policy import PolicySource
        from raxe.domain.policies.models import PolicyAction as PA

        # Collect all detections (L1 + mapped L2)
        all_detections = []

        # Add L1 detections
        if l1_result.has_detections:
            all_detections.extend(l1_result.detections)

        # Map L2 predictions to virtual detections
        if l2_result and l2_result.has_predictions:
            l2_detections = self._map_l2_to_virtual_rules(l2_result)
            all_detections.extend(l2_detections)

        # If no detections, return ALLOW (passive monitoring)
        if not all_detections:
            return BlockAction.ALLOW, False

        # Apply policies to all detections
        policy_decisions = {}
        for detection in all_detections:
            decision = self.apply_policy.apply_to_detection(
                detection,
                policy_source=PolicySource.LOCAL_FILE,
            )
            policy_decisions[detection.versioned_rule_id] = decision

        # Determine highest action across all decisions
        highest_action = PA.ALLOW
        for decision in policy_decisions.values():
            if decision.action == PA.BLOCK:
                highest_action = PA.BLOCK
                break  # BLOCK is highest priority
            elif decision.action == PA.FLAG and highest_action != PA.BLOCK:
                highest_action = PA.FLAG
            elif decision.action == PA.LOG and highest_action == PA.ALLOW:
                highest_action = PA.LOG

        # Map PolicyAction to BlockAction for backward compatibility
        if highest_action == PA.BLOCK:
            policy_decision = BlockAction.BLOCK
            should_block = True
        elif highest_action == PA.FLAG:
            policy_decision = BlockAction.WARN
            should_block = False
        elif highest_action == PA.LOG:
            policy_decision = BlockAction.WARN
            should_block = False
        else:  # ALLOW
            policy_decision = BlockAction.ALLOW
            should_block = False

        return policy_decision, should_block

    def _map_l2_to_virtual_rules(self, l2_result: L2Result) -> list:
        """Map L2 ML predictions to virtual rule detections.

        Creates Detection objects for L2 predictions with virtual rule IDs
        like "l2-jailbreak" or "l2-prompt-injection".

        Args:
            l2_result: L2 scan result with ML predictions

        Returns:
            List of Detection objects representing L2 predictions
        """
        from datetime import datetime, timezone
        from raxe.domain.engine.executor import Detection
        from raxe.domain.engine.matcher import Match

        detections = []

        for prediction in l2_result.predictions:
            # Create virtual rule ID based on threat type
            rule_id = f"l2-{prediction.threat_type.value.lower().replace('_', '-')}"

            # Map L2 confidence to severity
            severity = self._map_l2_severity(prediction.confidence)

            # Create a single Match object for L2 detection (no actual pattern match)
            match = Match(
                pattern_index=0,
                start=0,
                end=0,
                matched_text="[L2 ML Detection]",  # Privacy: don't expose actual text
                groups=(),
                context_before="",
                context_after="",
            )

            # Create virtual detection
            detection = Detection(
                rule_id=rule_id,
                rule_version="0.0.1",
                severity=severity,
                confidence=prediction.confidence,
                matches=[match],
                detected_at=datetime.now(timezone.utc).isoformat(),
                detection_layer="L2",
                category=prediction.threat_type.value,
                message=f"L2 ML detection: {prediction.threat_type.value}",
                explanation=prediction.explanation if prediction.explanation else f"ML model detected {prediction.threat_type.value}",
            )
            detections.append(detection)

        return detections

    def _map_l2_severity(self, confidence: float) -> object:
        """Map L2 confidence score to severity level.

        Uses conservative thresholds - L2 must be confident to trigger high severity.

        Args:
            confidence: L2 confidence score (0.0 to 1.0)

        Returns:
            Severity level
        """
        from raxe.domain.rules.models import Severity

        if confidence >= 0.95:
            return Severity.CRITICAL
        elif confidence >= 0.85:
            return Severity.HIGH
        elif confidence >= 0.70:
            return Severity.MEDIUM
        elif confidence >= 0.50:
            return Severity.LOW
        else:
            return Severity.INFO

    def _hash_text(self, text: str) -> str:
        """Create privacy-preserving hash of text.

        Uses SHA256 to create non-reversible hash.
        This allows telemetry without exposing PII.

        Args:
            text: Text to hash

        Returns:
            Hex-encoded SHA256 hash
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _validate_telemetry_event(self, payload: dict[str, object]) -> bool:
        """Validate telemetry event against schema.

        Args:
            payload: Telemetry event payload

        Returns:
            True if valid or validation disabled, False if invalid
        """
        if not self._validator:
            return True  # Validation disabled or failed to init

        try:
            is_valid, errors = self._validator.validate_scan_event(payload)

            if not is_valid:
                self._validation_errors += 1

                if self.schema_validation_mode == "log_only":
                    # Just log errors, don't block
                    logger.debug(f"Telemetry validation failed: {errors}")
                    return True  # Allow send anyway

                elif self.schema_validation_mode == "warn":
                    # Log warning but allow send
                    logger.warning(
                        f"Telemetry validation failed: {errors}. "
                        f"Sending anyway (mode=warn)"
                    )
                    return True

                elif self.schema_validation_mode == "enforce":
                    # Block invalid data
                    logger.error(
                        f"Telemetry validation failed: {errors}. "
                        f"Blocked (mode=enforce)"
                    )
                    return False

            return True

        except Exception as e:
            logger.warning(f"Schema validation error: {e}")
            return True  # Don't block on validation errors

    def _send_telemetry(
        self,
        result: ScanPipelineResult,
        customer_id: str | None,
    ) -> None:
        """Send privacy-preserving telemetry.

        Sends only:
        - Text hash (NOT the actual text)
        - Detection counts
        - Severity levels
        - Performance metrics
        - Customer ID (for analytics)

        NEVER sends:
        - Actual text content
        - Pattern matches
        - Any PII

        Args:
            result: Scan pipeline result
            customer_id: Customer ID
        """
        # Build telemetry payload (privacy-first)
        payload: dict[str, object] = {
            "event_name": "scan_performed",
            "prompt_hash": result.text_hash,
            "timestamp": result.metadata.get("scan_timestamp"),
            "max_severity": result.severity or "none",
            "detection_count": result.total_detections,
            "l1_detection_count": result.scan_result.l1_detection_count,
            "l2_prediction_count": result.scan_result.l2_prediction_count,
            "scan_duration_ms": result.duration_ms,
            "policy_action": result.policy_decision.value,
            "blocked": result.should_block,
        }

        # Add optional fields
        if customer_id:
            payload["customer_id"] = customer_id

        # Validate if enabled
        if self.enable_schema_validation:
            if not self._validate_telemetry_event(payload):
                # Validation failed in enforce mode - don't send
                logger.warning("Telemetry blocked due to schema validation failure")
                return

        # Send via telemetry hook
        try:
            self.telemetry_hook.send(payload)
        except Exception:
            # Never fail scan due to telemetry errors
            # Just log and continue (logging happens in hook)
            pass

    @property
    def average_scan_time_ms(self) -> float:
        """Average scan time across all scans.

        Returns:
            Average duration in milliseconds
        """
        if self._scan_count == 0:
            return 0.0
        return self._total_duration_ms / self._scan_count

    @property
    def scan_count(self) -> int:
        """Total number of scans performed."""
        return self._scan_count

    def get_stats(self) -> dict[str, object]:
        """Get pipeline statistics.

        Returns:
            Dictionary with performance metrics
        """
        return {
            "scan_count": self._scan_count,
            "average_scan_time_ms": self.average_scan_time_ms,
            "total_duration_ms": self._total_duration_ms,
            "enable_l2": self.enable_l2,
            "fail_fast_on_critical": self.fail_fast_on_critical,
        }

    def _track_scan_error(
        self,
        error: Exception,
        error_code: str = "SCAN_001",
        is_recoverable: bool = False,
    ) -> None:
        """Track a scan error via telemetry orchestrator.

        This is a helper method that safely tracks errors without letting
        telemetry failures break the main scan flow.

        Args:
            error: The exception that occurred
            error_code: Error code for categorization
            is_recoverable: Whether the error is recoverable
        """
        try:
            orchestrator = get_orchestrator()
            if orchestrator and orchestrator.is_enabled():
                # Determine error type based on exception type
                error_type = "internal_error"
                if isinstance(error, ValueError):
                    error_type = "validation_error"
                elif isinstance(error, TimeoutError):
                    error_type = "timeout_error"
                elif isinstance(error, PermissionError):
                    error_type = "permission_error"
                elif isinstance(error, OSError):
                    error_type = "network_error"

                orchestrator.track_error(
                    error_type=error_type,  # type: ignore[arg-type]
                    error_code=error_code,
                    component="engine",
                    error_message=str(error),
                    is_recoverable=is_recoverable,
                    operation="scan",
                )
        except Exception as e:
            # Never let telemetry errors break scanning
            logger.debug(f"Error tracking failed (non-blocking): {e}")
