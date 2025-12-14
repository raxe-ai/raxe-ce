"""Integration tests for hierarchical scoring configuration.

Tests that the scoring system integrates properly with the scan pipeline:
- Config loading
- Scorer creation
- Integration with folder detector
"""
import pytest

from raxe.domain.ml.scoring_models import (
    ActionType,
    ScoringMode,
    ThreatLevel,
    ThreatScore,
)
from raxe.domain.ml.threat_scorer import HierarchicalThreatScorer
from raxe.infrastructure.config.scan_config import L2ScoringConfig, ScanConfig


class TestL2ScoringConfig:
    """Test L2ScoringConfig data class."""

    def test_default_config(self):
        """Test default scoring configuration."""
        config = L2ScoringConfig()

        assert config.mode == "balanced"
        assert config.custom_thresholds is None
        assert config.weights is None
        assert config.family_adjustments is None
        assert config.enable_consistency_check is True
        assert config.enable_margin_analysis is True
        assert config.enable_entropy is False

    def test_valid_modes(self):
        """Test all valid scoring modes."""
        for mode in ["high_security", "balanced", "low_fp"]:
            config = L2ScoringConfig(mode=mode)
            assert config.mode == mode

    def test_invalid_mode(self):
        """Test invalid mode raises error."""
        with pytest.raises(ValueError, match="mode must be one of"):
            L2ScoringConfig(mode="invalid")

    def test_custom_thresholds_validation(self):
        """Test custom thresholds are validated."""
        with pytest.raises(ValueError, match="must be 0-1"):
            L2ScoringConfig(custom_thresholds={"safe": 1.5})

    def test_custom_weights_validation(self):
        """Test custom weights are validated."""
        # Invalid key
        with pytest.raises(ValueError, match="must only contain"):
            L2ScoringConfig(weights={"invalid_key": 0.5})

        # Out of range
        with pytest.raises(ValueError, match="must be 0-1"):
            L2ScoringConfig(weights={"binary": 1.5})

    def test_to_dict(self):
        """Test serialization to dict."""
        config = L2ScoringConfig(
            mode="balanced",
            enable_consistency_check=True,
            enable_margin_analysis=False,
        )

        result = config.to_dict()

        assert result["mode"] == "balanced"
        assert result["enable_consistency_check"] is True
        assert result["enable_margin_analysis"] is False


class TestScanConfigIntegration:
    """Test integration of scoring config into ScanConfig."""

    def test_scan_config_includes_scoring(self):
        """Test ScanConfig includes L2 scoring config."""
        config = ScanConfig()

        assert hasattr(config, "l2_scoring")
        assert isinstance(config.l2_scoring, L2ScoringConfig)
        assert config.l2_scoring.mode == "balanced"

    def test_scan_config_custom_scoring(self):
        """Test ScanConfig with custom scoring config."""
        scoring_config = L2ScoringConfig(
            mode="high_security",
            enable_consistency_check=False,
        )

        config = ScanConfig(l2_scoring=scoring_config)

        assert config.l2_scoring.mode == "high_security"
        assert config.l2_scoring.enable_consistency_check is False

    def test_scan_config_to_dict_includes_scoring(self):
        """Test ScanConfig serialization includes scoring."""
        config = ScanConfig()
        result = config.to_dict()

        assert "l2_scoring" in result
        assert result["l2_scoring"]["mode"] == "balanced"


class TestHierarchicalScorerIntegration:
    """Test hierarchical scorer integration."""

    def test_create_scorer_from_config(self):
        """Test creating scorer from config."""
        config = L2ScoringConfig(mode="balanced")

        # Map mode to enum
        mode_map = {
            "high_security": ScoringMode.HIGH_SECURITY,
            "balanced": ScoringMode.BALANCED,
            "low_fp": ScoringMode.LOW_FP,
        }
        mode = mode_map[config.mode]

        scorer = HierarchicalThreatScorer(mode=mode)

        assert scorer.mode == ScoringMode.BALANCED

    def test_scorer_basic_usage(self):
        """Test basic scorer usage."""
        scorer = HierarchicalThreatScorer(mode=ScoringMode.BALANCED)

        # Create a threat score
        threat_score = ThreatScore(
            binary_threat_score=0.88,
            binary_safe_score=0.12,
            family_confidence=0.70,
            subfamily_confidence=0.55,
            binary_proba=[0.12, 0.88],
            family_proba=[0.70, 0.20, 0.10],
            subfamily_proba=[0.55, 0.30, 0.15],
        )

        result = scorer.score(threat_score)

        assert result is not None
        assert hasattr(result, "classification")
        assert hasattr(result, "action")
        assert hasattr(result, "hierarchical_score")

    def test_scorer_false_positive_detection(self):
        """Test scorer detects likely false positives."""
        scorer = HierarchicalThreatScorer(mode=ScoringMode.BALANCED)

        # Business jargon: high binary, low family/subfamily
        threat_score = ThreatScore(
            binary_threat_score=0.902,
            binary_safe_score=0.098,
            family_confidence=0.518,
            subfamily_confidence=0.286,
            binary_proba=[0.098, 0.902],
            family_proba=[0.518, 0.25, 0.15, 0.08, 0.01, 0.008],
            subfamily_proba=[0.286, 0.2, 0.15, 0.1, 0.01, 0.01, 0.01],
        )

        result = scorer.score(threat_score)

        # Should be classified as FP_LIKELY or REVIEW due to weak signals
        # Note: classification is an enum value, action is ActionType enum
        assert result.classification in (ThreatLevel.FP_LIKELY, ThreatLevel.REVIEW)
        assert result.action in (ActionType.ALLOW_WITH_LOG, ActionType.MANUAL_REVIEW)

    def test_scorer_clear_threat_detection(self):
        """Test scorer detects clear threats."""
        scorer = HierarchicalThreatScorer(mode=ScoringMode.BALANCED)

        # Clear threat: all high confidence
        threat_score = ThreatScore(
            binary_threat_score=0.9835,
            binary_safe_score=0.0165,
            family_confidence=0.85,
            subfamily_confidence=0.70,
            binary_proba=[0.0165, 0.9835],
            family_proba=[0.85, 0.10, 0.05],
            subfamily_proba=[0.70, 0.20, 0.10],
        )

        result = scorer.score(threat_score)

        # Should be classified as THREAT or HIGH_THREAT
        assert result.classification in (ThreatLevel.THREAT, ThreatLevel.HIGH_THREAT)
        assert result.action in (ActionType.BLOCK, ActionType.BLOCK_ALERT)
