"""Tests for ScanPipelineResult convenience properties.

Tests the flattened API for accessing scan results without deep nesting.
"""
import pytest

from raxe.application.scan_merger import CombinedScanResult
from raxe.application.scan_pipeline import BlockAction, ScanPipelineResult
from raxe.domain.engine.executor import Detection, ScanResult
from raxe.domain.engine.matcher import Match
from raxe.domain.ml.protocol import L2Prediction, L2Result, L2ThreatType
from raxe.domain.rules.models import Severity


def create_detection(
    rule_id: str = "pi-001",
    severity: Severity = Severity.HIGH,
    confidence: float = 0.9,
) -> Detection:
    """Helper to create a Detection object."""
    return Detection(
        rule_id=rule_id,
        rule_version="1.0.0",
        severity=severity,
        confidence=confidence,
        matches=[
            Match(
                pattern_index=0,
                start=0,
                end=10,
                matched_text="test match",
                groups=(),
                context_before="",
                context_after="",
            )
        ],
        detected_at="2024-01-01T00:00:00Z",
    )


def create_l1_result(
    detections: list[Detection] | None = None,
    scan_time_ms: float = 5.0,
) -> ScanResult:
    """Helper to create L1 scan result."""
    return ScanResult(
        detections=detections or [],
        scanned_at="2024-01-01T00:00:00Z",
        text_length=100,
        rules_checked=10,
        scan_duration_ms=scan_time_ms,
    )


def create_l2_result(
    predictions: list[L2Prediction] | None = None,
    processing_time_ms: float = 3.0,
) -> L2Result:
    """Helper to create L2 result."""
    preds = predictions or []
    max_confidence = max((p.confidence for p in preds), default=0.0)
    return L2Result(
        predictions=preds,
        confidence=max_confidence,
        processing_time_ms=processing_time_ms,
        model_version="stub-1.0.0",
    )


def create_pipeline_result(
    l1_detections: list[Detection] | None = None,
    l2_predictions: list[L2Prediction] | None = None,
    policy_decision: BlockAction = BlockAction.ALLOW,
    should_block: bool = False,
    combined_severity: Severity | None = None,
) -> ScanPipelineResult:
    """Helper to create a ScanPipelineResult for testing."""
    l1_result = create_l1_result(detections=l1_detections)
    l2_result = create_l2_result(predictions=l2_predictions) if l2_predictions else None

    combined = CombinedScanResult(
        l1_result=l1_result,
        l2_result=l2_result,
        combined_severity=combined_severity,
        total_processing_ms=8.0,
        metadata={},
    )

    return ScanPipelineResult(
        scan_result=combined,
        policy_decision=policy_decision,
        should_block=should_block,
        duration_ms=10.0,
        text_hash="abc123",
        metadata={"test": True},
    )


class TestScanPipelineResultConvenienceProperties:
    """Test convenience properties for flattened API access."""

    def test_has_threats_forwards_to_scan_result(self):
        """has_threats should forward to scan_result.has_threats."""
        # With threats
        result_with_threats = create_pipeline_result(
            l1_detections=[create_detection()],
            combined_severity=Severity.HIGH,
        )
        assert result_with_threats.has_threats is True

        # Without threats
        result_no_threats = create_pipeline_result()
        assert result_no_threats.has_threats is False

    def test_severity_forwards_to_scan_result(self):
        """severity should return combined_severity value string."""
        result = create_pipeline_result(
            l1_detections=[create_detection(severity=Severity.CRITICAL)],
            combined_severity=Severity.CRITICAL,
        )
        assert result.severity == "critical"

    def test_severity_returns_none_when_no_threats(self):
        """severity should return None when no threats detected."""
        result = create_pipeline_result()
        assert result.severity is None

    def test_detections_returns_l1_detections(self):
        """detections should return L1 detections list."""
        detection1 = create_detection(rule_id="pi-001")
        detection2 = create_detection(rule_id="pi-002")

        result = create_pipeline_result(
            l1_detections=[detection1, detection2],
            combined_severity=Severity.HIGH,
        )

        assert len(result.detections) == 2
        assert result.detections[0].rule_id == "pi-001"
        assert result.detections[1].rule_id == "pi-002"

    def test_detections_returns_empty_list_when_no_detections(self):
        """detections should return empty list when no L1 detections."""
        result = create_pipeline_result()
        assert result.detections == []

    def test_total_detections_property(self):
        """total_detections should count L1 and L2 combined."""
        detection = create_detection()
        prediction = L2Prediction(
            threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
            confidence=0.9,
        )

        result = create_pipeline_result(
            l1_detections=[detection],
            l2_predictions=[prediction],
            combined_severity=Severity.HIGH,
        )

        assert result.total_detections == 2


class TestScanPipelineResultBooleanEvaluation:
    """Test __bool__ method for intuitive conditional checks."""

    def test_bool_true_when_no_threats(self):
        """Result should be truthy when no threats detected (safe)."""
        result = create_pipeline_result()
        assert bool(result) is True
        assert result  # Direct truthiness test

    def test_bool_false_when_threats_detected(self):
        """Result should be falsy when threats detected."""
        result = create_pipeline_result(
            l1_detections=[create_detection()],
            combined_severity=Severity.HIGH,
        )
        assert bool(result) is False
        assert not result  # Direct falsiness test

    def test_bool_enables_intuitive_conditionals(self):
        """Should enable intuitive if/else patterns."""
        safe_result = create_pipeline_result()
        threat_result = create_pipeline_result(
            l1_detections=[create_detection()],
            combined_severity=Severity.HIGH,
        )

        # Pattern: if result: (safe to proceed)
        if safe_result:
            safe_path = True
        else:
            safe_path = False
        assert safe_path is True

        # Pattern: if not result: (threats detected)
        if not threat_result:
            blocked_path = True
        else:
            blocked_path = False
        assert blocked_path is True

    def test_bool_with_l2_only_threats(self):
        """Should be falsy when only L2 predictions exist."""
        prediction = L2Prediction(
            threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
            confidence=0.95,
        )

        result = create_pipeline_result(
            l2_predictions=[prediction],
            combined_severity=Severity.HIGH,
        )

        assert not result  # L2 predictions make it falsy


class TestScanPipelineResultBackwardsCompatibility:
    """Ensure existing properties still work correctly."""

    def test_scan_result_still_accessible(self):
        """scan_result should still be accessible for deep access."""
        detection = create_detection()
        result = create_pipeline_result(
            l1_detections=[detection],
            combined_severity=Severity.HIGH,
        )

        # Old nested access pattern should still work
        assert result.scan_result.has_threats is True
        assert result.scan_result.l1_detections[0].rule_id == "pi-001"
        assert result.scan_result.combined_severity == Severity.HIGH

    def test_policy_decision_accessible(self):
        """policy_decision should remain accessible."""
        result = create_pipeline_result(
            policy_decision=BlockAction.BLOCK,
            should_block=True,
        )
        assert result.policy_decision == BlockAction.BLOCK

    def test_should_block_accessible(self):
        """should_block should remain accessible."""
        result = create_pipeline_result(should_block=True)
        assert result.should_block is True

    def test_duration_ms_accessible(self):
        """duration_ms should remain accessible."""
        result = create_pipeline_result()
        assert result.duration_ms == 10.0

    def test_metadata_accessible(self):
        """metadata should remain accessible."""
        result = create_pipeline_result()
        assert result.metadata == {"test": True}

    def test_layer_breakdown_still_works(self):
        """layer_breakdown() method should still work."""
        result = create_pipeline_result()
        breakdown = result.layer_breakdown()
        assert "L1" in breakdown
        assert "L2" in breakdown
        assert "PLUGIN" in breakdown

    def test_to_dict_still_works(self):
        """to_dict() method should still work."""
        result = create_pipeline_result(
            l1_detections=[create_detection()],
            combined_severity=Severity.HIGH,
        )
        result_dict = result.to_dict()

        assert "has_threats" in result_dict
        assert "severity" in result_dict
        assert "total_detections" in result_dict
        assert result_dict["has_threats"] is True


class TestScanPipelineResultValidation:
    """Test validation in ScanPipelineResult."""

    def test_negative_duration_raises_error(self):
        """Should raise ValueError for negative duration_ms."""
        l1_result = create_l1_result()
        combined = CombinedScanResult(
            l1_result=l1_result,
            l2_result=None,
            combined_severity=None,
            total_processing_ms=5.0,
        )

        with pytest.raises(ValueError, match="duration_ms cannot be negative"):
            ScanPipelineResult(
                scan_result=combined,
                policy_decision=BlockAction.ALLOW,
                should_block=False,
                duration_ms=-1.0,
                text_hash="abc123",
                metadata={},
            )
