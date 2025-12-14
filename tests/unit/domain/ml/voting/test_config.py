"""Tests for voting configuration."""

import pytest

from raxe.domain.ml.voting.config import (
    BinaryHeadThresholds,
    DecisionThresholds,
    FamilyHeadThresholds,
    HarmHeadThresholds,
    HeadWeights,
    SeverityHeadThresholds,
    TechniqueHeadThresholds,
    VotingConfig,
    VotingPreset,
    get_voting_config,
)


class TestBinaryHeadThresholds:
    """Tests for BinaryHeadThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        t = BinaryHeadThresholds()
        assert t.threat_threshold == 0.65
        assert t.safe_threshold == 0.40

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        t = BinaryHeadThresholds(threat_threshold=0.70, safe_threshold=0.35)
        assert t.threat_threshold == 0.70
        assert t.safe_threshold == 0.35

    def test_invalid_range_validation(self):
        """Test that safe < threat threshold validation."""
        with pytest.raises(ValueError, match="safe_threshold.*must be < threat_threshold"):
            BinaryHeadThresholds(threat_threshold=0.50, safe_threshold=0.60)

    def test_equal_thresholds_invalid(self):
        """Test that equal thresholds are invalid."""
        with pytest.raises(ValueError):
            BinaryHeadThresholds(threat_threshold=0.50, safe_threshold=0.50)


class TestFamilyHeadThresholds:
    """Tests for FamilyHeadThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        t = FamilyHeadThresholds()
        assert t.threat_confidence == 0.55
        assert t.safe_confidence == 0.35


class TestSeverityHeadThresholds:
    """Tests for SeverityHeadThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        t = SeverityHeadThresholds()
        assert "high" in t.threat_severities
        assert "critical" in t.threat_severities
        assert "none" in t.safe_severities

    def test_custom_severities(self):
        """Test custom severity configuration."""
        t = SeverityHeadThresholds(
            threat_severities=("medium", "high", "critical"),
            safe_severities=("none", "low"),
        )
        assert "low" not in t.threat_severities
        assert "low" in t.safe_severities


class TestTechniqueHeadThresholds:
    """Tests for TechniqueHeadThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        t = TechniqueHeadThresholds()
        assert t.threat_confidence == 0.50
        assert t.safe_confidence == 0.30
        assert "none" in t.safe_techniques


class TestHarmHeadThresholds:
    """Tests for HarmHeadThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        t = HarmHeadThresholds()
        assert t.threat_threshold == 0.92
        assert t.safe_threshold == 0.50


class TestHeadWeights:
    """Tests for HeadWeights."""

    def test_default_weights(self):
        """Test default weight values."""
        w = HeadWeights()
        assert w.binary == 1.0
        assert w.family == 1.2
        assert w.severity == 1.5  # Highest
        assert w.technique == 1.0
        assert w.harm == 0.8  # Lowest

    def test_get_weight(self):
        """Test get_weight method."""
        w = HeadWeights()
        assert w.get_weight("binary") == 1.0
        assert w.get_weight("severity") == 1.5

    def test_get_weight_unknown_head(self):
        """Test get_weight with unknown head."""
        w = HeadWeights()
        with pytest.raises(ValueError, match="Unknown head"):
            w.get_weight("unknown")

    def test_total_weight(self):
        """Test total_weight property."""
        w = HeadWeights()
        expected = 1.0 + 1.2 + 1.5 + 1.0 + 0.8
        assert w.total_weight == expected

    def test_negative_weight_validation(self):
        """Test negative weight validation."""
        with pytest.raises(ValueError, match="weight must be non-negative"):
            HeadWeights(binary=-1.0)


class TestDecisionThresholds:
    """Tests for DecisionThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        d = DecisionThresholds()
        assert d.high_confidence_threshold == 0.85
        assert d.min_threat_votes == 2
        assert d.severity_veto_override_votes == 3
        assert d.threat_ratio == 1.3
        assert d.review_ratio_min == 1.0

    def test_review_ratio_validation(self):
        """Test review_ratio_min < threat_ratio validation."""
        with pytest.raises(ValueError, match="review_ratio_min.*must be < threat_ratio"):
            DecisionThresholds(threat_ratio=1.0, review_ratio_min=1.5)


class TestVotingConfig:
    """Tests for VotingConfig."""

    def test_default_config(self):
        """Test default config creation."""
        config = VotingConfig()
        assert config.name == "balanced"
        assert isinstance(config.binary, BinaryHeadThresholds)
        assert isinstance(config.weights, HeadWeights)
        assert isinstance(config.decision, DecisionThresholds)

    def test_config_to_dict(self):
        """Test config serialization."""
        config = VotingConfig()
        d = config.to_dict()
        assert d["name"] == "balanced"
        assert "binary" in d
        assert "weights" in d
        assert "decision" in d


class TestVotingPreset:
    """Tests for VotingPreset enum."""

    def test_preset_values(self):
        """Test preset enum values."""
        assert VotingPreset.BALANCED.value == "balanced"
        assert VotingPreset.HIGH_SECURITY.value == "high_security"
        assert VotingPreset.LOW_FP.value == "low_fp"


class TestGetVotingConfig:
    """Tests for get_voting_config factory function."""

    def test_get_balanced_config(self):
        """Test getting balanced config."""
        config = get_voting_config(VotingPreset.BALANCED)
        assert config.name == "balanced"
        assert config.binary.threat_threshold == 0.65

    def test_get_balanced_config_by_string(self):
        """Test getting balanced config by string."""
        config = get_voting_config("balanced")
        assert config.name == "balanced"

    def test_get_high_security_config(self):
        """Test getting high_security config."""
        config = get_voting_config("high_security")
        assert config.name == "high_security"
        # Lower thresholds
        assert config.binary.threat_threshold == 0.50
        assert config.decision.min_threat_votes == 1

    def test_get_low_fp_config(self):
        """Test getting low_fp config."""
        config = get_voting_config("low_fp")
        assert config.name == "low_fp"
        # Higher thresholds
        assert config.binary.threat_threshold == 0.80
        assert config.decision.min_threat_votes == 3

    def test_get_harm_focused_config(self):
        """Test getting harm_focused config."""
        config = get_voting_config("harm_focused")
        assert config.name == "harm_focused"
        # Low harm thresholds (key feature)
        assert config.harm.threat_threshold == 0.50  # Was 0.92 in balanced
        assert config.harm.safe_threshold == 0.40    # Was 0.50 in balanced
        # Harm has DOMINANT weight (3.0)
        assert config.weights.harm == 3.0
        # Single vote can trigger threat
        assert config.decision.min_threat_votes == 1
        # Harm can override severity veto
        assert config.decision.severity_veto_override_votes == 1
        # Very low threat ratio so harm alone can win
        assert config.decision.threat_ratio == 0.25

    def test_get_harm_focused_config_by_enum(self):
        """Test getting harm_focused config by enum."""
        config = get_voting_config(VotingPreset.HARM_FOCUSED)
        assert config.name == "harm_focused"

    def test_unknown_preset_raises(self):
        """Test that unknown preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            get_voting_config("unknown")

    def test_case_insensitive(self):
        """Test that preset lookup is case insensitive."""
        config1 = get_voting_config("BALANCED")
        config2 = get_voting_config("Balanced")
        config3 = get_voting_config("balanced")
        assert config1.name == config2.name == config3.name
