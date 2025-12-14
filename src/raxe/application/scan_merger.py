"""Merge L1 and L2 scan results.

Application layer - orchestrates domain logic to combine rule-based (L1)
and ML-based (L2) threat detection results.

This is the integration point between the two detection layers:
- L1: Fast, deterministic rule-based detection
- L2: Slower, probabilistic ML-based detection

The merger preserves both L1 and L2 results while providing a unified
view for downstream processing (logging, blocking, alerting, etc.).
"""
from dataclasses import dataclass
from typing import ClassVar

from raxe.domain.engine.executor import ScanResult as L1ScanResult
from raxe.domain.ml.protocol import L2Result
from raxe.domain.rules.models import Severity


@dataclass(frozen=True)
class CombinedScanResult:
    """Combined result from L1 + L2 detection.

    Preserves both rule-based and ML-based detections for complete visibility.

    Attributes:
        l1_result: Rule-based detection results (always present)
        l2_result: ML-based prediction results (optional, may be None)
        combined_severity: Maximum severity across both L1 and L2
        total_processing_ms: Total time for L1 + L2 combined
        metadata: Additional metadata about the scan
    """
    l1_result: L1ScanResult
    l2_result: L2Result | None
    combined_severity: Severity | None
    total_processing_ms: float
    metadata: dict[str, object] = None

    def __post_init__(self) -> None:
        """Validate combined result."""
        if self.total_processing_ms < 0:
            raise ValueError(
                f"total_processing_ms must be non-negative, got {self.total_processing_ms}"
            )

    @property
    def has_threats(self) -> bool:
        """True if either L1 or L2 detected threats.

        Returns:
            True if any threats detected by L1 rules or L2 predictions
        """
        l1_threats = self.l1_result.has_detections
        l2_threats = (
            self.l2_result.has_predictions
            if self.l2_result else False
        )
        return l1_threats or l2_threats

    @property
    def l1_detection_count(self) -> int:
        """Number of L1 rule detections."""
        return self.l1_result.detection_count

    @property
    def l2_prediction_count(self) -> int:
        """Number of L2 ML predictions."""
        if not self.l2_result:
            return 0
        return self.l2_result.prediction_count

    @property
    def total_threat_count(self) -> int:
        """Total threats across both L1 and L2.

        Returns:
            Sum of L1 detections and L2 predictions
        """
        return self.l1_detection_count + self.l2_prediction_count

    @property
    def l1_processing_ms(self) -> float:
        """L1 processing time in milliseconds."""
        return self.l1_result.scan_duration_ms

    @property
    def l2_processing_ms(self) -> float:
        """L2 processing time in milliseconds."""
        if not self.l2_result:
            return 0.0
        return self.l2_result.processing_time_ms

    @property
    def l1_detections(self) -> list:
        """List of L1 detections."""
        return self.l1_result.detections

    @property
    def l2_predictions(self) -> list:
        """List of L2 predictions."""
        if not self.l2_result:
            return []
        return self.l2_result.predictions

    @property
    def plugin_detection_count(self) -> int:
        """Number of plugin detections (embedded in L1 result)."""
        return sum(1 for d in self.l1_result.detections if d.detection_layer == "PLUGIN")

    def layer_breakdown(self) -> dict[str, int]:
        """Return detection count by layer.

        Returns:
            Dictionary with keys L1, L2, PLUGIN and their respective counts
        """
        l1_count = sum(1 for d in self.l1_result.detections if d.detection_layer == "L1")
        plugin_count = self.plugin_detection_count
        l2_count = self.l2_prediction_count

        return {
            "L1": l1_count,
            "L2": l2_count,
            "PLUGIN": plugin_count,
        }

    @property
    def threat_summary(self) -> str:
        """Human-readable threat summary.

        Returns:
            Summary string like:
            "HIGH: 2 L1 detections, 1 L2 prediction (8.5ms total)"
        """
        l1_count = self.l1_detection_count
        l2_count = self.l2_prediction_count

        severity_str = (
            self.combined_severity.value.upper()
            if self.combined_severity else "NONE"
        )

        parts = []
        if l1_count > 0:
            parts.append(f"{l1_count} L1 detection{'s' if l1_count > 1 else ''}")
        if l2_count > 0:
            parts.append(f"{l2_count} L2 prediction{'s' if l2_count > 1 else ''}")

        if not parts:
            return f"No threats detected ({self.total_processing_ms:.2f}ms)"

        threats_str = ", ".join(parts)
        return (
            f"{severity_str}: {threats_str} "
            f"({self.total_processing_ms:.2f}ms total)"
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation including both L1 and L2 data
        """
        result = {
            "has_threats": self.has_threats,
            "combined_severity": self.combined_severity.value if self.combined_severity else None,
            "total_processing_ms": self.total_processing_ms,
            "l1": self.l1_result.to_dict(),
            "l2": self.l2_result.to_summary() if self.l2_result else None,
            "summary": self.threat_summary,
            "layer_breakdown": self.layer_breakdown(),
        }

        if self.metadata:
            result["metadata"] = self.metadata

        return result


class ScanMerger:
    """Merge L1 rule-based and L2 ML-based results.

    Application layer orchestration - combines domain layer results.

    This class is stateless and thread-safe.
    """

    # Confidence thresholds for mapping L2 predictions to severity
    # These are conservative - L2 must be quite confident to elevate severity
    SEVERITY_CONFIDENCE_THRESHOLDS: ClassVar[dict[Severity, float]] = {
        Severity.CRITICAL: 0.95,  # Very high confidence required for CRITICAL
        Severity.HIGH: 0.85,      # High confidence for HIGH
        Severity.MEDIUM: 0.70,    # Moderate confidence for MEDIUM
        Severity.LOW: 0.50,       # Low confidence for LOW
        Severity.INFO: 0.30,      # Very low confidence for INFO
    }

    def merge(
        self,
        l1_result: L1ScanResult,
        l2_result: L2Result | None = None,
        metadata: dict[str, object] | None = None
    ) -> CombinedScanResult:
        """Combine L1 and L2 results.

        Args:
            l1_result: Rule-based detection results (required)
            l2_result: ML-based prediction results (optional)
            metadata: Optional metadata to attach to result

        Returns:
            CombinedScanResult with merged data
        """
        # Calculate combined severity (max of L1 and L2)
        combined_severity = self._calculate_combined_severity(
            l1_result,
            l2_result
        )

        # Sum processing time
        total_time = l1_result.scan_duration_ms
        if l2_result:
            total_time += l2_result.processing_time_ms

        return CombinedScanResult(
            l1_result=l1_result,
            l2_result=l2_result,
            combined_severity=combined_severity,
            total_processing_ms=total_time,
            metadata=metadata or {}
        )

    def _calculate_combined_severity(
        self,
        l1_result: L1ScanResult,
        l2_result: L2Result | None
    ) -> Severity | None:
        """Calculate combined severity from L1 and L2.

        Takes maximum severity from:
        1. L1 detections (direct severity from rules)
        2. L2 predictions (mapped from confidence to severity)

        L2 confidence → severity mapping:
        - ≥0.95 → CRITICAL
        - ≥0.85 → HIGH
        - ≥0.70 → MEDIUM
        - ≥0.50 → LOW
        - ≥0.30 → INFO

        Args:
            l1_result: L1 scan result
            l2_result: L2 scan result (optional)

        Returns:
            Maximum severity or None if no threats
        """
        severities = []

        # Add L1 highest severity
        if l1_result.highest_severity:
            severities.append(l1_result.highest_severity)

        # Map L2 confidence to severity
        if l2_result and l2_result.has_predictions:
            l2_severity = self._map_confidence_to_severity(
                l2_result.highest_confidence
            )
            if l2_severity:
                severities.append(l2_severity)

        if not severities:
            return None

        # Return maximum severity (lower enum value = more severe)
        return self._max_severity(severities)

    def _map_confidence_to_severity(self, confidence: float) -> Severity | None:
        """Map L2 confidence score to severity level.

        Uses conservative thresholds - L2 must be quite confident
        to map to higher severity levels.

        Args:
            confidence: Confidence score (0.0-1.0)

        Returns:
            Severity level or None if below minimum threshold
        """
        if confidence >= self.SEVERITY_CONFIDENCE_THRESHOLDS[Severity.CRITICAL]:
            return Severity.CRITICAL
        elif confidence >= self.SEVERITY_CONFIDENCE_THRESHOLDS[Severity.HIGH]:
            return Severity.HIGH
        elif confidence >= self.SEVERITY_CONFIDENCE_THRESHOLDS[Severity.MEDIUM]:
            return Severity.MEDIUM
        elif confidence >= self.SEVERITY_CONFIDENCE_THRESHOLDS[Severity.LOW]:
            return Severity.LOW
        elif confidence >= self.SEVERITY_CONFIDENCE_THRESHOLDS[Severity.INFO]:
            return Severity.INFO
        else:
            return None

    def _max_severity(self, severities: list[Severity]) -> Severity:
        """Get maximum severity from list.

        Args:
            severities: List of severity levels

        Returns:
            Most severe level (CRITICAL > HIGH > MEDIUM > LOW > INFO)
        """
        # Severity order (lower number = more severe)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }

        return min(severities, key=lambda s: severity_order[s])
