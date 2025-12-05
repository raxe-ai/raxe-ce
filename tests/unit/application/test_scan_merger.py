"""Tests for scan merger.

Tests merging L1 and L2 scan results in the application layer.
"""
import pytest

from raxe.application.scan_merger import CombinedScanResult, ScanMerger
from raxe.domain.engine.executor import Detection, ScanResult
from raxe.domain.engine.matcher import Match
from raxe.domain.ml.protocol import L2Prediction, L2Result, L2ThreatType
from raxe.domain.rules.models import Severity


def create_l1_result(
    detection_count: int = 0,
    severity: Severity = Severity.HIGH,
    scan_time_ms: float = 5.0
) -> ScanResult:
    """Helper to create L1 scan result."""
    detections = []
    for i in range(detection_count):
        detections.append(Detection(
            rule_id=f"rule-{i:03d}",
            rule_version="1.0.0",
            severity=severity,
            confidence=0.9,
            matches=[Match(
                pattern_index=0,
                start=0,
                end=4,
                matched_text="test",
                groups=(),
                context_before="",
                context_after=""
            )],
            detected_at="2024-01-01T00:00:00Z"
        ))

    return ScanResult(
        detections=detections,
        scanned_at="2024-01-01T00:00:00Z",
        text_length=100,
        rules_checked=10,
        scan_duration_ms=scan_time_ms
    )


def create_l2_result(
    prediction_count: int = 0,
    confidence: float = 0.8,
    processing_time_ms: float = 3.0
) -> L2Result:
    """Helper to create L2 result."""
    predictions = []
    for _i in range(prediction_count):
        predictions.append(L2Prediction(
            threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
            confidence=confidence
        ))

    return L2Result(
        predictions=predictions,
        confidence=confidence if prediction_count > 0 else 0.0,
        processing_time_ms=processing_time_ms,
        model_version="stub-1.0.0"
    )


class TestCombinedScanResult:
    """Test CombinedScanResult value object."""

    def test_create_combined_result(self):
        """Should create combined result successfully."""
        l1 = create_l1_result(detection_count=1)
        l2 = create_l2_result(prediction_count=1)

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=Severity.HIGH,
            total_processing_ms=8.0
        )

        assert combined.l1_result == l1
        assert combined.l2_result == l2
        assert combined.combined_severity == Severity.HIGH
        assert combined.total_processing_ms == 8.0

    def test_has_threats_from_l1_only(self):
        """Should detect threats from L1 only."""
        l1 = create_l1_result(detection_count=2)
        l2 = None

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=Severity.HIGH,
            total_processing_ms=5.0
        )

        assert combined.has_threats is True
        assert combined.l1_detection_count == 2
        assert combined.l2_prediction_count == 0

    def test_has_threats_from_l2_only(self):
        """Should detect threats from L2 only."""
        l1 = create_l1_result(detection_count=0)
        l2 = create_l2_result(prediction_count=1)

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=Severity.MEDIUM,
            total_processing_ms=8.0
        )

        assert combined.has_threats is True
        assert combined.l1_detection_count == 0
        assert combined.l2_prediction_count == 1

    def test_has_threats_from_both(self):
        """Should detect threats from both L1 and L2."""
        l1 = create_l1_result(detection_count=2)
        l2 = create_l2_result(prediction_count=3)

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=Severity.HIGH,
            total_processing_ms=8.0
        )

        assert combined.has_threats is True
        assert combined.total_threat_count == 5

    def test_no_threats(self):
        """Should handle no threats from either layer."""
        l1 = create_l1_result(detection_count=0)
        l2 = create_l2_result(prediction_count=0)

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=None,
            total_processing_ms=8.0
        )

        assert combined.has_threats is False
        assert combined.combined_severity is None

    def test_processing_time_properties(self):
        """Should expose processing times for both layers."""
        l1 = create_l1_result(scan_time_ms=5.5)
        l2 = create_l2_result(processing_time_ms=2.3)

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=None,
            total_processing_ms=7.8
        )

        assert combined.l1_processing_ms == 5.5
        assert combined.l2_processing_ms == 2.3
        assert combined.total_processing_ms == 7.8

    def test_processing_time_without_l2(self):
        """Should handle missing L2 result."""
        l1 = create_l1_result(scan_time_ms=5.0)

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=None,
            combined_severity=None,
            total_processing_ms=5.0
        )

        assert combined.l1_processing_ms == 5.0
        assert combined.l2_processing_ms == 0.0

    def test_threat_summary_no_threats(self):
        """Should generate summary with no threats."""
        l1 = create_l1_result(detection_count=0)
        l2 = None

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=None,
            total_processing_ms=5.0
        )

        summary = combined.threat_summary
        assert "No threats detected" in summary
        assert "5.00ms" in summary

    def test_threat_summary_with_threats(self):
        """Should generate summary with threats."""
        l1 = create_l1_result(detection_count=2, severity=Severity.CRITICAL)
        l2 = create_l2_result(prediction_count=1)

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=Severity.CRITICAL,
            total_processing_ms=8.5
        )

        summary = combined.threat_summary
        assert "CRITICAL" in summary
        assert "2 L1 detections" in summary
        assert "1 L2 prediction" in summary
        assert "8.50ms" in summary

    def test_to_dict(self):
        """Should serialize to dictionary."""
        l1 = create_l1_result(detection_count=1)
        l2 = create_l2_result(prediction_count=1)

        combined = CombinedScanResult(
            l1_result=l1,
            l2_result=l2,
            combined_severity=Severity.HIGH,
            total_processing_ms=8.0,
            metadata={"key": "value"}
        )

        result_dict = combined.to_dict()

        assert result_dict["has_threats"] is True
        assert result_dict["combined_severity"] == "high"
        assert result_dict["total_processing_ms"] == 8.0
        assert "l1" in result_dict
        assert "l2" in result_dict
        assert result_dict["metadata"]["key"] == "value"

    def test_validation_negative_processing_time(self):
        """Should reject negative processing time."""
        l1 = create_l1_result()

        with pytest.raises(ValueError, match="total_processing_ms must be non-negative"):
            CombinedScanResult(
                l1_result=l1,
                l2_result=None,
                combined_severity=None,
                total_processing_ms=-1.0
            )


class TestScanMerger:
    """Test ScanMerger logic."""

    def test_merge_l1_only(self):
        """Should merge L1 result without L2."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=2, severity=Severity.HIGH)

        combined = merger.merge(l1)

        assert combined.l1_result == l1
        assert combined.l2_result is None
        assert combined.combined_severity == Severity.HIGH
        assert combined.total_processing_ms == 5.0

    def test_merge_l1_and_l2(self):
        """Should merge L1 and L2 results."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=1, scan_time_ms=5.0)
        l2 = create_l2_result(prediction_count=1, processing_time_ms=3.0)

        combined = merger.merge(l1, l2)

        assert combined.l1_result == l1
        assert combined.l2_result == l2
        assert combined.total_processing_ms == 8.0

    def test_severity_from_l1_only(self):
        """Should use L1 severity when no L2."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=1, severity=Severity.CRITICAL)

        combined = merger.merge(l1)

        assert combined.combined_severity == Severity.CRITICAL

    def test_severity_from_l2_high_confidence(self):
        """Should map high L2 confidence to severity."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=0)  # No L1 detections
        l2 = create_l2_result(prediction_count=1, confidence=0.96)  # Very high

        combined = merger.merge(l1, l2)

        # 0.96 confidence should map to CRITICAL
        assert combined.combined_severity == Severity.CRITICAL

    def test_severity_from_l2_medium_confidence(self):
        """Should map medium L2 confidence to severity."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=0)
        l2 = create_l2_result(prediction_count=1, confidence=0.75)  # Medium

        combined = merger.merge(l1, l2)

        # 0.75 confidence should map to MEDIUM
        assert combined.combined_severity == Severity.MEDIUM

    def test_severity_from_l2_low_confidence(self):
        """Should map low L2 confidence to severity."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=0)
        l2 = create_l2_result(prediction_count=1, confidence=0.55)

        combined = merger.merge(l1, l2)

        # 0.55 confidence should map to LOW
        assert combined.combined_severity == Severity.LOW

    def test_severity_from_l2_very_low_confidence(self):
        """Should map very low L2 confidence to INFO or None."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=0)
        l2 = create_l2_result(prediction_count=1, confidence=0.35)

        combined = merger.merge(l1, l2)

        # 0.35 confidence should map to INFO
        assert combined.combined_severity == Severity.INFO

    def test_severity_below_threshold(self):
        """Should return None for confidence below threshold."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=0)
        l2 = create_l2_result(prediction_count=1, confidence=0.25)

        combined = merger.merge(l1, l2)

        # 0.25 is below INFO threshold (0.30)
        assert combined.combined_severity is None

    def test_severity_max_from_both_layers(self):
        """Should take maximum severity from L1 and L2."""
        merger = ScanMerger()
        # L1 has MEDIUM
        l1 = create_l1_result(detection_count=1, severity=Severity.MEDIUM)
        # L2 has high confidence → CRITICAL
        l2 = create_l2_result(prediction_count=1, confidence=0.97)

        combined = merger.merge(l1, l2)

        # Should choose CRITICAL (more severe)
        assert combined.combined_severity == Severity.CRITICAL

    def test_severity_l1_higher_than_l2(self):
        """Should choose L1 severity if higher than L2."""
        merger = ScanMerger()
        # L1 has HIGH
        l1 = create_l1_result(detection_count=1, severity=Severity.HIGH)
        # L2 has low confidence → LOW
        l2 = create_l2_result(prediction_count=1, confidence=0.55)

        combined = merger.merge(l1, l2)

        # Should choose HIGH from L1
        assert combined.combined_severity == Severity.HIGH

    def test_confidence_threshold_boundaries(self):
        """Should correctly map confidence at threshold boundaries."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=0)

        # Test each threshold boundary
        test_cases = [
            (0.95, Severity.CRITICAL),
            (0.85, Severity.HIGH),
            (0.70, Severity.MEDIUM),
            (0.50, Severity.LOW),
            (0.30, Severity.INFO),
        ]

        for confidence, expected_severity in test_cases:
            l2 = create_l2_result(prediction_count=1, confidence=confidence)
            combined = merger.merge(l1, l2)
            assert combined.combined_severity == expected_severity, (
                f"Confidence {confidence} should map to {expected_severity.value}"
            )

    def test_merge_with_metadata(self):
        """Should attach metadata to result."""
        merger = ScanMerger()
        l1 = create_l1_result()
        metadata = {"scan_id": "12345", "user": "test"}

        combined = merger.merge(l1, metadata=metadata)

        assert combined.metadata["scan_id"] == "12345"
        assert combined.metadata["user"] == "test"

    def test_merge_empty_results(self):
        """Should handle empty results from both layers."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=0)
        l2 = create_l2_result(prediction_count=0)

        combined = merger.merge(l1, l2)

        assert not combined.has_threats
        assert combined.combined_severity is None

    def test_merge_l1_empty_l2_with_predictions(self):
        """Should handle L1 empty but L2 with predictions."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=0)
        l2 = create_l2_result(prediction_count=2, confidence=0.88)

        combined = merger.merge(l1, l2)

        assert combined.has_threats
        assert combined.l1_detection_count == 0
        assert combined.l2_prediction_count == 2
        assert combined.combined_severity == Severity.HIGH

    def test_performance_tracking(self):
        """Should accurately track processing time."""
        merger = ScanMerger()
        l1 = create_l1_result(scan_time_ms=4.5)
        l2 = create_l2_result(processing_time_ms=2.8)

        combined = merger.merge(l1, l2)

        assert combined.l1_processing_ms == 4.5
        assert combined.l2_processing_ms == 2.8
        assert combined.total_processing_ms == 7.3


class TestScanMergerEdgeCases:
    """Test edge cases and error handling."""

    def test_l2_none_handled_gracefully(self):
        """Should handle L2 being None."""
        merger = ScanMerger()
        l1 = create_l1_result(detection_count=1)

        combined = merger.merge(l1, l2_result=None)

        assert combined.l2_result is None
        assert combined.l2_prediction_count == 0
        assert combined.l2_processing_ms == 0.0

    def test_l2_empty_predictions(self):
        """Should handle L2 with no predictions."""
        merger = ScanMerger()
        l1 = create_l1_result()
        l2 = create_l2_result(prediction_count=0)

        combined = merger.merge(l1, l2)

        assert not l2.has_predictions
        assert combined.l2_prediction_count == 0

    def test_multiple_severities_in_l1(self):
        """Should take highest severity from multiple L1 detections."""
        # Create L1 with mixed severities
        detections = [
            Detection(
                rule_id="rule-001",
                rule_version="1.0.0",
                severity=Severity.LOW,
                confidence=0.8,
                matches=[Match(0, 0, 4, "test", (), "", "")],
                detected_at="2024-01-01T00:00:00Z"
            ),
            Detection(
                rule_id="rule-002",
                rule_version="1.0.0",
                severity=Severity.CRITICAL,
                confidence=0.9,
                matches=[Match(0, 0, 4, "test", (), "", "")],
                detected_at="2024-01-01T00:00:00Z"
            ),
        ]

        l1 = ScanResult(
            detections=detections,
            scanned_at="2024-01-01T00:00:00Z",
            text_length=100,
            rules_checked=2,
            scan_duration_ms=5.0
        )

        merger = ScanMerger()
        combined = merger.merge(l1)

        # Should pick CRITICAL
        assert combined.combined_severity == Severity.CRITICAL
