"""Tests for layer control API in ScanPipeline.

Tests the new layer control parameters (l1_enabled, l2_enabled, mode, etc.)
"""

from unittest.mock import Mock

import pytest

from raxe.application.scan_merger import ScanMerger
from raxe.application.scan_pipeline import ScanPipeline
from raxe.domain.engine.executor import Detection, RuleExecutor, ScanResult
from raxe.domain.engine.matcher import Match
from raxe.domain.ml.protocol import L2Detector
from raxe.domain.rules.models import Pattern, Rule, RuleExamples, RuleFamily, RuleMetrics, Severity
from raxe.infrastructure.packs.registry import PackRegistry


@pytest.fixture
def mock_registry():
    """Mock pack registry with test rules."""
    registry = Mock(spec=PackRegistry)

    # Create test rules
    test_rules = [
        Rule(
            rule_id="test-001",
            version="1.0.0",
            family=RuleFamily.PI,
            sub_family="test",
            name="Test Rule 1",
            description="Test description",
            severity=Severity.HIGH,
            confidence=0.9,
            patterns=[Pattern(pattern=r"test", flags=[], timeout=5.0)],
            examples=RuleExamples(),
            metrics=RuleMetrics(),
        )
    ]

    registry.get_all_rules.return_value = test_rules
    return registry


@pytest.fixture
def mock_executor():
    """Mock rule executor."""
    executor = Mock(spec=RuleExecutor)

    # Return empty result by default
    executor.execute_rules.return_value = ScanResult(
        detections=[],
        scanned_at="2025-01-01T00:00:00Z",
        text_length=10,
        rules_checked=1,
        scan_duration_ms=1.0,
    )

    return executor


@pytest.fixture
def mock_l2_detector():
    """Mock L2 detector."""
    detector = Mock(spec=L2Detector)
    detector.analyze.return_value = None
    return detector


@pytest.fixture
def scan_pipeline(mock_registry, mock_executor, mock_l2_detector):
    """Create scan pipeline with mocks."""
    merger = ScanMerger()

    return ScanPipeline(
        pack_registry=mock_registry,
        rule_executor=mock_executor,
        l2_detector=mock_l2_detector,
        scan_merger=merger,
    )


def test_scan_with_l1_disabled(scan_pipeline, mock_executor):
    """Test scanning with L1 disabled."""
    result = scan_pipeline.scan("test text", l1_enabled=False, l2_enabled=False)

    # L1 should not be called
    mock_executor.execute_rules.assert_not_called()

    # Result should have no detections
    assert result.l1_detections == 0
    assert result.total_detections == 0


def test_scan_with_l2_disabled(scan_pipeline, mock_l2_detector):
    """Test scanning with L2 disabled."""
    result = scan_pipeline.scan("test text", l1_enabled=True, l2_enabled=False)

    # L2 should not be called
    mock_l2_detector.analyze.assert_not_called()

    # Result should indicate L2 was disabled
    assert result.l2_duration_ms == 0.0


def test_scan_mode_fast(scan_pipeline, mock_l2_detector):
    """Test fast mode (L1 only, no L2)."""
    result = scan_pipeline.scan("test text", mode="fast")

    # L2 should not be called in fast mode
    mock_l2_detector.analyze.assert_not_called()

    # Metadata should indicate fast mode
    assert result.metadata["mode"] == "fast"
    assert result.metadata["l1_enabled"] is True
    assert result.metadata["l2_enabled"] is False


def test_scan_mode_balanced(scan_pipeline, mock_executor, mock_l2_detector):
    """Test balanced mode (L1 + L2)."""
    result = scan_pipeline.scan("test text", mode="balanced")

    # Both L1 and L2 should be enabled
    mock_executor.execute_rules.assert_called_once()
    # L2 may or may not be called depending on L1 results

    # Metadata should indicate balanced mode
    assert result.metadata["mode"] == "balanced"


def test_scan_mode_thorough(scan_pipeline, mock_executor):
    """Test thorough mode (all layers)."""
    result = scan_pipeline.scan("test text", mode="thorough")

    # L1 should be called
    mock_executor.execute_rules.assert_called_once()

    # Metadata should indicate thorough mode
    assert result.metadata["mode"] == "thorough"
    assert result.metadata["l1_enabled"] is True
    assert result.metadata["l2_enabled"] is True


def test_scan_invalid_mode_raises_error(scan_pipeline):
    """Test that invalid mode raises ValueError."""
    with pytest.raises(ValueError, match="mode must be"):
        scan_pipeline.scan("test text", mode="invalid")


def test_confidence_threshold_filtering(scan_pipeline, mock_executor):
    """Test confidence threshold filtering."""
    # Create detections with different confidence levels
    from datetime import datetime, timezone

    detections = [
        Detection(
            rule_id="test-001",
            rule_version="1.0.0",
            severity=Severity.HIGH,
            confidence=0.9,
            matches=[
                Match(
                    pattern_index=0,
                    start=0,
                    end=4,
                    matched_text="test",
                    groups=(),
                    context_before="",
                    context_after="",
                )
            ],
            detected_at=datetime.now(timezone.utc).isoformat(),
            detection_layer="L1",
            layer_latency_ms=1.0,
            category="pi",
            message="Test detection",
        ),
        Detection(
            rule_id="test-002",
            rule_version="1.0.0",
            severity=Severity.MEDIUM,
            confidence=0.4,  # Below threshold
            matches=[
                Match(
                    pattern_index=0,
                    start=0,
                    end=4,
                    matched_text="test",
                    groups=(),
                    context_before="",
                    context_after="",
                )
            ],
            detected_at=datetime.now(timezone.utc).isoformat(),
            detection_layer="L1",
            layer_latency_ms=1.0,
            category="pi",
            message="Low confidence detection",
        ),
    ]

    mock_executor.execute_rules.return_value = ScanResult(
        detections=detections,
        scanned_at=datetime.now(timezone.utc).isoformat(),
        text_length=10,
        rules_checked=2,
        scan_duration_ms=2.0,
    )

    # Scan with threshold of 0.5
    result = scan_pipeline.scan("test text", confidence_threshold=0.5)

    # Should only have 1 detection (confidence 0.9)
    assert result.l1_detections == 1


def test_layer_attribution_in_result(scan_pipeline, mock_executor):
    """Test that layer attribution is included in result."""
    from datetime import datetime, timezone

    detection = Detection(
        rule_id="test-001",
        rule_version="1.0.0",
        severity=Severity.HIGH,
        confidence=0.9,
        matches=[
            Match(
                pattern_index=0,
                start=0,
                end=4,
                matched_text="test",
                groups=(),
                context_before="",
                context_after="",
            )
        ],
        detected_at=datetime.now(timezone.utc).isoformat(),
        detection_layer="L1",
        layer_latency_ms=1.5,
        category="pi",
        message="Prompt injection detected",
    )

    mock_executor.execute_rules.return_value = ScanResult(
        detections=[detection],
        scanned_at=datetime.now(timezone.utc).isoformat(),
        text_length=10,
        rules_checked=1,
        scan_duration_ms=1.5,
    )

    result = scan_pipeline.scan("test text")

    # Check layer breakdown
    assert result.l1_detections == 1
    assert result.l2_detections == 0
    assert result.plugin_detections == 0

    # Check layer breakdown method
    breakdown = result.layer_breakdown()
    assert breakdown["L1"] == 1
    assert breakdown["L2"] == 0
    assert breakdown["PLUGIN"] == 0


def test_explain_parameter_in_metadata(scan_pipeline):
    """Test that explain parameter is stored in metadata."""
    result = scan_pipeline.scan("test text", explain=True)

    assert result.metadata["explain"] is True


def test_layer_durations_tracked(scan_pipeline, mock_executor, mock_l2_detector):
    """Test that L1 and L2 durations are tracked separately."""
    result = scan_pipeline.scan("test text", l1_enabled=True, l2_enabled=True)

    # Both durations should be >= 0
    assert result.l1_duration_ms >= 0
    assert result.l2_duration_ms >= 0

    # Should be in result dict
    result_dict = result.to_dict()
    assert "l1_duration_ms" in result_dict
    assert "l2_duration_ms" in result_dict


def test_empty_text_raises_error(scan_pipeline):
    """Test that empty text raises ValueError."""
    with pytest.raises(ValueError, match="Text cannot be empty"):
        scan_pipeline.scan("")


def test_scan_with_custom_threshold_and_mode(scan_pipeline):
    """Test combining custom threshold with performance mode."""
    result = scan_pipeline.scan(
        "test text",
        mode="fast",
        confidence_threshold=0.7,
    )

    assert result.metadata["mode"] == "fast"
    assert result.metadata["confidence_threshold"] == 0.7
