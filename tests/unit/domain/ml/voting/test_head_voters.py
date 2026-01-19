"""Tests for head voters."""

from raxe.domain.ml.voting.config import (
    BinaryHeadThresholds,
    FamilyHeadThresholds,
    HarmHeadThresholds,
    SeverityHeadThresholds,
    TechniqueHeadThresholds,
)
from raxe.domain.ml.voting.head_voters import (
    vote_binary,
    vote_family,
    vote_harm,
    vote_severity,
    vote_technique,
)
from raxe.domain.ml.voting.models import Vote


class TestVoteBinary:
    """Tests for vote_binary function."""

    def test_vote_threat_high_probability(self):
        """Test voting THREAT with high probability."""
        detail = vote_binary(
            threat_probability=0.80,
            safe_probability=0.20,
            thresholds=BinaryHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.THREAT
        assert detail.head_name == "binary"
        assert detail.confidence == 0.80
        assert "threat_probability" in detail.rationale

    def test_vote_safe_low_probability(self):
        """Test voting SAFE with low probability."""
        detail = vote_binary(
            threat_probability=0.20,
            safe_probability=0.80,
            thresholds=BinaryHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.SAFE
        assert detail.confidence == 0.80

    def test_vote_abstain_gray_zone(self):
        """Test voting ABSTAIN in gray zone."""
        detail = vote_binary(
            threat_probability=0.50,
            safe_probability=0.50,
            thresholds=BinaryHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.ABSTAIN
        assert "gray zone" in detail.rationale

    def test_vote_at_threat_threshold(self):
        """Test voting at exact threat threshold."""
        detail = vote_binary(
            threat_probability=0.65,  # Exact threshold
            safe_probability=0.35,
            thresholds=BinaryHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.THREAT

    def test_vote_just_below_safe_threshold(self):
        """Test voting just below safe threshold."""
        detail = vote_binary(
            threat_probability=0.39,  # Just below 0.40
            safe_probability=0.61,
            thresholds=BinaryHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.SAFE


class TestVoteFamily:
    """Tests for vote_family function."""

    def test_vote_safe_benign_family(self):
        """Test voting SAFE for benign family."""
        detail = vote_family(
            family_prediction="benign",
            family_confidence=0.90,
            thresholds=FamilyHeadThresholds(),
            weight=1.2,
        )
        assert detail.vote == Vote.SAFE
        assert "benign" in detail.rationale

    def test_vote_threat_high_confidence_jailbreak(self):
        """Test voting THREAT for high-confidence non-benign."""
        detail = vote_family(
            family_prediction="jailbreak",
            family_confidence=0.75,
            thresholds=FamilyHeadThresholds(),
            weight=1.2,
        )
        assert detail.vote == Vote.THREAT
        assert detail.prediction == "jailbreak"

    def test_vote_safe_low_confidence_non_benign(self):
        """Test voting SAFE for low-confidence non-benign."""
        detail = vote_family(
            family_prediction="jailbreak",
            family_confidence=0.25,  # Below safe_confidence (0.35)
            thresholds=FamilyHeadThresholds(),
            weight=1.2,
        )
        assert detail.vote == Vote.SAFE

    def test_vote_abstain_uncertain_non_benign(self):
        """Test voting ABSTAIN for uncertain non-benign."""
        detail = vote_family(
            family_prediction="jailbreak",
            family_confidence=0.45,  # Between 0.35 and 0.55
            thresholds=FamilyHeadThresholds(),
            weight=1.2,
        )
        assert detail.vote == Vote.ABSTAIN


class TestVoteSeverity:
    """Tests for vote_severity function."""

    def test_vote_safe_severity_none(self):
        """Test voting SAFE for severity=none."""
        detail = vote_severity(
            severity_prediction="none",
            severity_confidence=0.85,
            thresholds=SeverityHeadThresholds(),
            weight=1.5,
        )
        assert detail.vote == Vote.SAFE
        assert detail.weight == 1.5
        assert "safe_severities" in detail.rationale

    def test_vote_threat_severity_severe(self):
        """Test voting THREAT for severity=severe."""
        detail = vote_severity(
            severity_prediction="severe",
            severity_confidence=0.80,
            thresholds=SeverityHeadThresholds(),
            weight=1.5,
        )
        assert detail.vote == Vote.THREAT

    def test_vote_threat_severity_moderate(self):
        """Test voting THREAT for severity=moderate."""
        detail = vote_severity(
            severity_prediction="moderate",
            severity_confidence=0.70,
            thresholds=SeverityHeadThresholds(),
            weight=1.5,
        )
        assert detail.vote == Vote.THREAT

    def test_vote_severity_unknown(self):
        """Test voting for unknown severity."""
        detail = vote_severity(
            severity_prediction="unknown",
            severity_confidence=0.50,
            thresholds=SeverityHeadThresholds(),
            weight=1.5,
        )
        assert detail.vote == Vote.ABSTAIN


class TestVoteTechnique:
    """Tests for vote_technique function."""

    def test_vote_safe_technique_none(self):
        """Test voting SAFE for technique=none."""
        detail = vote_technique(
            technique_prediction="none",
            technique_confidence=0.85,
            thresholds=TechniqueHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.SAFE

    def test_vote_threat_high_confidence_attack(self):
        """Test voting THREAT for high-confidence attack technique."""
        detail = vote_technique(
            technique_prediction="instruction_override",
            technique_confidence=0.70,
            thresholds=TechniqueHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.THREAT

    def test_vote_safe_low_confidence_attack(self):
        """Test voting SAFE for low-confidence attack technique."""
        detail = vote_technique(
            technique_prediction="instruction_override",
            technique_confidence=0.20,  # Below safe_confidence
            thresholds=TechniqueHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.SAFE

    def test_vote_abstain_uncertain_attack(self):
        """Test voting ABSTAIN for uncertain attack technique."""
        detail = vote_technique(
            technique_prediction="instruction_override",
            technique_confidence=0.40,  # Between 0.30 and 0.50
            thresholds=TechniqueHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.ABSTAIN

    def test_vote_none_technique_prediction(self):
        """Test voting with None technique prediction."""
        detail = vote_technique(
            technique_prediction=None,
            technique_confidence=0.85,
            thresholds=TechniqueHeadThresholds(),
            weight=1.0,
        )
        assert detail.vote == Vote.SAFE
        assert detail.prediction == "none"


class TestVoteHarm:
    """Tests for vote_harm function."""

    def test_vote_threat_high_probability(self):
        """Test voting THREAT with high max probability."""
        detail = vote_harm(
            max_probability=0.95,
            active_labels=["violence_or_physical_harm"],
            thresholds=HarmHeadThresholds(),
            weight=0.8,
        )
        assert detail.vote == Vote.THREAT
        assert detail.weight == 0.8

    def test_vote_safe_low_probability(self):
        """Test voting SAFE with low max probability."""
        detail = vote_harm(
            max_probability=0.30,
            active_labels=[],
            thresholds=HarmHeadThresholds(),
            weight=0.8,
        )
        assert detail.vote == Vote.SAFE
        assert detail.prediction == "none"

    def test_vote_abstain_uncertain(self):
        """Test voting ABSTAIN in uncertain zone."""
        detail = vote_harm(
            max_probability=0.70,  # Between 0.50 and 0.92
            active_labels=["privacy_or_pii"],
            thresholds=HarmHeadThresholds(),
            weight=0.8,
        )
        assert detail.vote == Vote.ABSTAIN

    def test_prediction_with_multiple_labels(self):
        """Test prediction string with multiple labels."""
        detail = vote_harm(
            max_probability=0.95,
            active_labels=["violence", "hate", "crime", "other"],
            thresholds=HarmHeadThresholds(),
            weight=0.8,
        )
        assert "violence" in detail.prediction
        assert "+1" in detail.prediction  # 4 labels, only 3 shown

    def test_just_below_threat_threshold(self):
        """Test voting just below threat threshold."""
        detail = vote_harm(
            max_probability=0.91,  # Just below 0.92
            active_labels=["violence"],
            thresholds=HarmHeadThresholds(),
            weight=0.8,
        )
        assert detail.vote == Vote.ABSTAIN

    def test_at_threat_threshold(self):
        """Test voting at exact threat threshold."""
        detail = vote_harm(
            max_probability=0.92,  # Exact threshold
            active_labels=["violence"],
            thresholds=HarmHeadThresholds(),
            weight=0.8,
        )
        assert detail.vote == Vote.THREAT
