"""Tests for L2 ML predictions to virtual rule detection mapping.

Tests the L2 virtual rule mapping added in Phase 3:
- L2 prediction → virtual rule ID mapping (e.g., "l2-jailbreak")
- L2 confidence → severity level mapping
- Virtual detection object creation
- Metadata preservation

Target: >80% coverage for application layer.
"""
import pytest

from raxe.application.scan_pipeline import ScanPipeline
from raxe.domain.engine.executor import Detection
from raxe.domain.ml.protocol import L2Prediction, L2Result, L2ThreatType
from raxe.domain.rules.models import Severity


class TestL2VirtualRuleMapping:
    """Test L2 prediction to virtual rule ID mapping."""

    def test_rag_context_attack_virtual_rule_id(self):
        """L2 RAG/context attack maps to 'l2-rag-or-context-attack'."""
        prediction = L2Prediction(
            threat_type=L2ThreatType.RAG_OR_CONTEXT_ATTACK,
            confidence=0.95,
        )
        l2_result = L2Result(
            predictions=[prediction],
            confidence=0.95,
            processing_time_ms=5.0,
            model_version="1.0.0",
        )

        # Create minimal pipeline for testing (only need the mapping method)
        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        assert len(detections) == 1
        assert detections[0].rule_id == "l2-rag-or-context-attack"
        assert detections[0].category == "rag_or_context_attack"
        assert detections[0].detection_layer == "L2"

    def test_jailbreak_virtual_rule_id(self):
        """L2 jailbreak maps to 'l2-jailbreak'."""
        prediction = L2Prediction(
            threat_type=L2ThreatType.JAILBREAK,
            confidence=0.85,
        )
        l2_result = L2Result(
            predictions=[prediction],
            confidence=0.85,
            processing_time_ms=5.0,
            model_version="1.0.0",
        )

        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        assert len(detections) == 1
        assert detections[0].rule_id == "l2-jailbreak"
        assert detections[0].category == "jailbreak"

    def test_data_exfiltration_virtual_rule_id(self):
        """Data exfiltration threat type converted to rule ID."""
        prediction = L2Prediction(
            threat_type=L2ThreatType.DATA_EXFILTRATION,
            confidence=0.80,
        )
        l2_result = L2Result(
            predictions=[prediction],
            confidence=0.80,
            processing_time_ms=5.0,
            model_version="1.0.0",
        )

        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        assert len(detections) == 1
        assert detections[0].rule_id == "l2-data-exfiltration"
        assert detections[0].category == "data_exfiltration"

    def test_prompt_injection_virtual_rule_id(self):
        """Prompt injection threat type maps to 'l2-prompt-injection'."""
        prediction = L2Prediction(
            threat_type=L2ThreatType.PROMPT_INJECTION,
            confidence=0.90,
        )
        l2_result = L2Result(
            predictions=[prediction],
            confidence=0.90,
            processing_time_ms=5.0,
            model_version="1.0.0",
        )

        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        assert len(detections) == 1
        assert detections[0].rule_id == "l2-prompt-injection"

    def test_multiple_predictions_create_multiple_detections(self):
        """Multiple L2 predictions create multiple virtual detections."""
        predictions = [
            L2Prediction(
                threat_type=L2ThreatType.RAG_OR_CONTEXT_ATTACK,
                confidence=0.95,
            ),
            L2Prediction(
                threat_type=L2ThreatType.JAILBREAK,
                confidence=0.85,
            ),
            L2Prediction(
                threat_type=L2ThreatType.ENCODING_OR_OBFUSCATION,
                confidence=0.75,
            ),
        ]
        l2_result = L2Result(
            predictions=predictions,
            confidence=0.95,
            processing_time_ms=10.0,
            model_version="1.0.0",
        )

        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        assert len(detections) == 3
        rule_ids = {d.rule_id for d in detections}
        assert rule_ids == {"l2-rag-or-context-attack", "l2-jailbreak", "l2-encoding-or-obfuscation-attack"}

    def test_empty_predictions_create_no_detections(self):
        """L2 result with no predictions creates no detections."""
        l2_result = L2Result(
            predictions=[],
            confidence=0.0,
            processing_time_ms=1.0,
            model_version="1.0.0",
        )

        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        assert len(detections) == 0

    def _create_test_pipeline(self) -> ScanPipeline:
        """Create minimal ScanPipeline for testing mapping methods."""
        from unittest.mock import Mock

        return ScanPipeline(
            pack_registry=Mock(),
            rule_executor=Mock(),
            l2_detector=Mock(),
            scan_merger=Mock(),
        )


class TestL2ConfidenceToSeverityMapping:
    """Test L2 confidence score to severity level mapping."""

    def test_confidence_095_maps_to_critical(self):
        """Confidence >= 0.95 maps to CRITICAL severity."""
        pipeline = self._create_test_pipeline()

        severity = pipeline._map_l2_severity(0.95)
        assert severity == Severity.CRITICAL

        severity = pipeline._map_l2_severity(0.99)
        assert severity == Severity.CRITICAL

        severity = pipeline._map_l2_severity(1.0)
        assert severity == Severity.CRITICAL

    def test_confidence_085_maps_to_high(self):
        """Confidence >= 0.85 (< 0.95) maps to HIGH severity."""
        pipeline = self._create_test_pipeline()

        severity = pipeline._map_l2_severity(0.85)
        assert severity == Severity.HIGH

        severity = pipeline._map_l2_severity(0.90)
        assert severity == Severity.HIGH

        severity = pipeline._map_l2_severity(0.94)
        assert severity == Severity.HIGH

    def test_confidence_070_maps_to_medium(self):
        """Confidence >= 0.70 (< 0.85) maps to MEDIUM severity."""
        pipeline = self._create_test_pipeline()

        severity = pipeline._map_l2_severity(0.70)
        assert severity == Severity.MEDIUM

        severity = pipeline._map_l2_severity(0.75)
        assert severity == Severity.MEDIUM

        severity = pipeline._map_l2_severity(0.84)
        assert severity == Severity.MEDIUM

    def test_confidence_050_maps_to_low(self):
        """Confidence >= 0.50 (< 0.70) maps to LOW severity."""
        pipeline = self._create_test_pipeline()

        severity = pipeline._map_l2_severity(0.50)
        assert severity == Severity.LOW

        severity = pipeline._map_l2_severity(0.60)
        assert severity == Severity.LOW

        severity = pipeline._map_l2_severity(0.69)
        assert severity == Severity.LOW

    def test_confidence_below_050_maps_to_info(self):
        """Confidence < 0.50 maps to INFO severity."""
        pipeline = self._create_test_pipeline()

        severity = pipeline._map_l2_severity(0.49)
        assert severity == Severity.INFO

        severity = pipeline._map_l2_severity(0.30)
        assert severity == Severity.INFO

        severity = pipeline._map_l2_severity(0.0)
        assert severity == Severity.INFO

    def test_boundary_conditions(self):
        """Test exact boundary values for severity mapping."""
        pipeline = self._create_test_pipeline()

        # Boundary tests
        assert pipeline._map_l2_severity(0.949999) == Severity.HIGH
        assert pipeline._map_l2_severity(0.950000) == Severity.CRITICAL

        assert pipeline._map_l2_severity(0.849999) == Severity.MEDIUM
        assert pipeline._map_l2_severity(0.850000) == Severity.HIGH

        assert pipeline._map_l2_severity(0.699999) == Severity.LOW
        assert pipeline._map_l2_severity(0.700000) == Severity.MEDIUM

        assert pipeline._map_l2_severity(0.499999) == Severity.INFO
        assert pipeline._map_l2_severity(0.500000) == Severity.LOW

    def _create_test_pipeline(self) -> ScanPipeline:
        """Create minimal ScanPipeline for testing mapping methods."""
        from unittest.mock import Mock

        return ScanPipeline(
            pack_registry=Mock(),
            rule_executor=Mock(),
            l2_detector=Mock(),
            scan_merger=Mock(),
        )


class TestL2VirtualDetectionCreation:
    """Test creation of Detection objects from L2 predictions."""

    def test_virtual_detection_has_correct_structure(self):
        """Virtual detection has all required fields."""
        prediction = L2Prediction(
            threat_type=L2ThreatType.RAG_OR_CONTEXT_ATTACK,
            confidence=0.95,
        )
        l2_result = L2Result(
            predictions=[prediction],
            confidence=0.95,
            processing_time_ms=5.0,
            model_version="1.0.0",
        )

        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        detection = detections[0]
        assert isinstance(detection, Detection)
        assert detection.rule_id == "l2-rag-or-context-attack"
        assert detection.rule_version == "0.0.1"  # L2 virtual rules use 0.0.1
        assert detection.category == "rag_or_context_attack"
        assert detection.detection_layer == "L2"
        assert detection.severity == Severity.CRITICAL
        assert detection.confidence == 0.95
        assert len(detection.matches) == 1
        assert detection.matches[0].matched_text == "[L2 ML Detection]"
        assert detection.matches[0].start == 0
        assert detection.matches[0].end == 0

    def test_virtual_detection_metadata_includes_threat_type(self):
        """Virtual detection metadata includes L2 threat type information."""
        prediction = L2Prediction(
            threat_type=L2ThreatType.JAILBREAK,
            confidence=0.88,
        )
        l2_result = L2Result(
            predictions=[prediction],
            confidence=0.88,
            processing_time_ms=7.5,
            model_version="2.1.0",
        )

        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        detection = detections[0]
        # Detection uses category field for threat type
        assert detection.category == "jailbreak"
        assert detection.detection_layer == "L2"

    def test_virtual_detection_preserves_confidence(self):
        """Virtual detection preserves exact L2 confidence score."""
        test_confidences = [0.95, 0.85, 0.75, 0.65, 0.55, 0.45]

        for conf in test_confidences:
            prediction = L2Prediction(
                threat_type=L2ThreatType.OTHER_SECURITY,
                confidence=conf,
            )
            l2_result = L2Result(
                predictions=[prediction],
                confidence=conf,
                processing_time_ms=1.0,
                model_version="1.0.0",
            )

            pipeline = self._create_test_pipeline()
            detections = pipeline._map_l2_to_virtual_rules(l2_result)

            assert detections[0].confidence == conf

    def test_virtual_detection_hides_matched_text(self):
        """Virtual detection does not expose actual matched text (privacy)."""
        prediction = L2Prediction(
            threat_type=L2ThreatType.DATA_EXFILTRATION,
            confidence=0.90,
        )
        l2_result = L2Result(
            predictions=[prediction],
            confidence=0.90,
            processing_time_ms=5.0,
            model_version="1.0.0",
        )

        pipeline = self._create_test_pipeline()
        detections = pipeline._map_l2_to_virtual_rules(l2_result)

        # Should use placeholder, not actual text
        assert detections[0].matches[0].matched_text == "[L2 ML Detection]"
        # Position is zeroed out (no actual match location)
        assert detections[0].matches[0].start == 0
        assert detections[0].matches[0].end == 0

    def test_virtual_detection_severity_follows_mapping(self):
        """Virtual detection severity correctly uses confidence mapping."""
        test_cases = [
            (0.97, Severity.CRITICAL),
            (0.88, Severity.HIGH),
            (0.72, Severity.MEDIUM),
            (0.55, Severity.LOW),
            (0.30, Severity.INFO),
        ]

        pipeline = self._create_test_pipeline()

        for confidence, expected_severity in test_cases:
            prediction = L2Prediction(
                threat_type=L2ThreatType.OTHER_SECURITY,
                confidence=confidence,
            )
            l2_result = L2Result(
                predictions=[prediction],
                confidence=confidence,
                processing_time_ms=1.0,
                model_version="1.0.0",
            )

            detections = pipeline._map_l2_to_virtual_rules(l2_result)
            assert detections[0].severity == expected_severity

    def _create_test_pipeline(self) -> ScanPipeline:
        """Create minimal ScanPipeline for testing mapping methods."""
        from unittest.mock import Mock

        return ScanPipeline(
            pack_registry=Mock(),
            rule_executor=Mock(),
            l2_detector=Mock(),
            scan_merger=Mock(),
        )


class TestL2VirtualRulesInPolicyMatching:
    """Test that L2 virtual rules can be matched by policies."""

    def test_virtual_rule_id_format_matches_policy_pattern(self):
        """Virtual rule IDs follow expected format for policy matching."""
        threat_types = [
            L2ThreatType.RAG_OR_CONTEXT_ATTACK,
            L2ThreatType.JAILBREAK,
            L2ThreatType.ENCODING_OR_OBFUSCATION,
            L2ThreatType.DATA_EXFILTRATION,
            L2ThreatType.PROMPT_INJECTION,
        ]

        pipeline = self._create_test_pipeline()

        for threat_type in threat_types:
            prediction = L2Prediction(
                threat_type=threat_type,
                confidence=0.90,
            )
            l2_result = L2Result(
                predictions=[prediction],
                confidence=0.90,
                processing_time_ms=1.0,
                model_version="1.0.0",
            )

            detections = pipeline._map_l2_to_virtual_rules(l2_result)
            rule_id = detections[0].rule_id

            # Should follow "l2-{threat-type}" format
            assert rule_id.startswith("l2-")
            assert rule_id.islower()
            # Underscores in values are converted to hyphens
            assert "_" not in rule_id

    def test_virtual_rule_ids_are_stable(self):
        """Same threat type always produces same virtual rule ID."""
        pipeline = self._create_test_pipeline()

        # Create same prediction multiple times
        for _ in range(5):
            prediction = L2Prediction(
                threat_type=L2ThreatType.RAG_OR_CONTEXT_ATTACK,
                confidence=0.90,
            )
            l2_result = L2Result(
                predictions=[prediction],
                confidence=0.90,
                processing_time_ms=1.0,
                model_version="1.0.0",
            )

            detections = pipeline._map_l2_to_virtual_rules(l2_result)
            assert detections[0].rule_id == "l2-rag-or-context-attack"

    def _create_test_pipeline(self) -> ScanPipeline:
        """Create minimal ScanPipeline for testing mapping methods."""
        from unittest.mock import Mock

        return ScanPipeline(
            pack_registry=Mock(),
            rule_executor=Mock(),
            l2_detector=Mock(),
            scan_merger=Mock(),
        )
