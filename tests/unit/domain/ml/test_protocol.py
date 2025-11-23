"""Tests for L2 ML protocol models.

Tests the pure domain models (value objects) for L2 ML detection.
No I/O, no mocks needed - just pure function testing.
"""
import pytest

from raxe.domain.ml.protocol import (
    L2Prediction,
    L2Result,
    L2ThreatType,
)


class TestL2Prediction:
    """Test L2Prediction value object."""

    def test_create_valid_prediction(self):
        """Should create prediction with valid data."""
        pred = L2Prediction(
            threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
            confidence=0.85,
            explanation="Test explanation",
            features_used=["feature1", "feature2"],
            metadata={"key": "value"}
        )

        assert pred.threat_type == L2ThreatType.SEMANTIC_JAILBREAK
        assert pred.confidence == 0.85
        assert pred.explanation == "Test explanation"
        assert pred.features_used == ["feature1", "feature2"]
        assert pred.metadata == {"key": "value"}

    def test_prediction_confidence_validation(self):
        """Should reject confidence outside 0-1 range."""
        # Too high
        with pytest.raises(ValueError, match="Confidence must be 0-1"):
            L2Prediction(
                threat_type=L2ThreatType.ENCODED_INJECTION,
                confidence=1.5
            )

        # Too low
        with pytest.raises(ValueError, match="Confidence must be 0-1"):
            L2Prediction(
                threat_type=L2ThreatType.ENCODED_INJECTION,
                confidence=-0.1
            )

    def test_prediction_edge_cases(self):
        """Should handle edge case confidence values."""
        # Exactly 0.0
        pred_zero = L2Prediction(
            threat_type=L2ThreatType.UNKNOWN,
            confidence=0.0
        )
        assert pred_zero.confidence == 0.0

        # Exactly 1.0
        pred_one = L2Prediction(
            threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
            confidence=1.0
        )
        assert pred_one.confidence == 1.0

    def test_prediction_immutable(self):
        """Should be immutable (frozen dataclass)."""
        pred = L2Prediction(
            threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
            confidence=0.85
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            pred.confidence = 0.9


class TestL2Result:
    """Test L2Result value object."""

    def test_create_empty_result(self):
        """Should create result with no predictions."""
        result = L2Result(
            predictions=[],
            confidence=0.0,
            processing_time_ms=2.5,
            model_version="stub-1.0.0"
        )

        assert result.predictions == []
        assert result.confidence == 0.0
        assert result.processing_time_ms == 2.5
        assert result.model_version == "stub-1.0.0"
        assert not result.has_predictions
        assert result.prediction_count == 0
        assert result.highest_confidence == 0.0

    def test_create_result_with_predictions(self):
        """Should create result with multiple predictions."""
        predictions = [
            L2Prediction(
                threat_type=L2ThreatType.ENCODED_INJECTION,
                confidence=0.7
            ),
            L2Prediction(
                threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
                confidence=0.9
            ),
        ]

        result = L2Result(
            predictions=predictions,
            confidence=0.9,
            processing_time_ms=3.2,
            model_version="stub-1.0.0"
        )

        assert result.has_predictions
        assert result.prediction_count == 2
        assert result.highest_confidence == 0.9

    def test_result_confidence_validation(self):
        """Should validate confidence is 0-1."""
        with pytest.raises(ValueError, match="Confidence must be 0-1"):
            L2Result(
                predictions=[],
                confidence=1.5,
                processing_time_ms=1.0,
                model_version="test"
            )

    def test_result_processing_time_validation(self):
        """Should validate processing_time_ms is non-negative."""
        with pytest.raises(ValueError, match="processing_time_ms must be non-negative"):
            L2Result(
                predictions=[],
                confidence=0.5,
                processing_time_ms=-1.0,
                model_version="test"
            )

    def test_get_predictions_by_type(self):
        """Should filter predictions by threat type."""
        predictions = [
            L2Prediction(
                threat_type=L2ThreatType.ENCODED_INJECTION,
                confidence=0.7
            ),
            L2Prediction(
                threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
                confidence=0.8
            ),
            L2Prediction(
                threat_type=L2ThreatType.ENCODED_INJECTION,
                confidence=0.9
            ),
        ]

        result = L2Result(
            predictions=predictions,
            confidence=0.9,
            processing_time_ms=1.0,
            model_version="test"
        )

        encoded = result.get_predictions_by_type(L2ThreatType.ENCODED_INJECTION)
        assert len(encoded) == 2
        assert all(p.threat_type == L2ThreatType.ENCODED_INJECTION for p in encoded)

        jailbreak = result.get_predictions_by_type(L2ThreatType.SEMANTIC_JAILBREAK)
        assert len(jailbreak) == 1

    def test_to_summary_no_predictions(self):
        """Should generate summary for empty result."""
        result = L2Result(
            predictions=[],
            confidence=0.0,
            processing_time_ms=1.5,
            model_version="test"
        )

        summary = result.to_summary()
        assert "No ML predictions" in summary
        assert "1.50ms" in summary

    def test_to_summary_with_predictions(self):
        """Should generate summary with predictions."""
        predictions = [
            L2Prediction(
                threat_type=L2ThreatType.ENCODED_INJECTION,
                confidence=0.7
            ),
            L2Prediction(
                threat_type=L2ThreatType.SEMANTIC_JAILBREAK,
                confidence=0.85
            ),
        ]

        result = L2Result(
            predictions=predictions,
            confidence=0.85,
            processing_time_ms=2.3,
            model_version="test"
        )

        summary = result.to_summary()
        assert "2 ML predictions" in summary
        assert "0.85" in summary  # Max confidence
        assert "2.30ms" in summary

    def test_features_and_metadata(self):
        """Should store features and metadata."""
        result = L2Result(
            predictions=[],
            confidence=0.0,
            processing_time_ms=1.0,
            model_version="test",
            features_extracted={"text_length": 100, "has_code": True},
            metadata={"model_type": "stub"}
        )

        assert result.features_extracted["text_length"] == 100
        assert result.features_extracted["has_code"] is True
        assert result.metadata["model_type"] == "stub"


class TestL2ThreatType:
    """Test L2ThreatType enum."""

    def test_all_threat_types_exist(self):
        """Should have all expected threat types."""
        expected_types = {
            "SEMANTIC_JAILBREAK",
            "ENCODED_INJECTION",
            "CONTEXT_MANIPULATION",
            "PRIVILEGE_ESCALATION",
            "DATA_EXFIL_PATTERN",
            "OBFUSCATED_COMMAND",
            "UNKNOWN",
        }

        actual_types = {t.name for t in L2ThreatType}
        assert actual_types == expected_types

    def test_threat_type_values(self):
        """Should have snake_case values."""
        assert L2ThreatType.SEMANTIC_JAILBREAK.value == "semantic_jailbreak"
        assert L2ThreatType.ENCODED_INJECTION.value == "encoded_injection"
        assert L2ThreatType.UNKNOWN.value == "unknown"
