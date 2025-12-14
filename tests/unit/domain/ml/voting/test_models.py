"""Tests for voting models."""

import pytest

from raxe.domain.ml.voting.models import (
    Decision,
    HeadOutput,
    HeadVoteDetail,
    Vote,
    VotingResult,
)


class TestVote:
    """Tests for Vote enum."""

    def test_vote_values(self):
        """Test vote enum values."""
        assert Vote.SAFE.value == "safe"
        assert Vote.ABSTAIN.value == "abstain"
        assert Vote.THREAT.value == "threat"

    def test_vote_is_string_enum(self):
        """Test vote is string enum for JSON serialization."""
        assert str(Vote.SAFE) == "Vote.SAFE"
        assert Vote.SAFE == "safe"


class TestDecision:
    """Tests for Decision enum."""

    def test_decision_values(self):
        """Test decision enum values."""
        assert Decision.SAFE.value == "safe"
        assert Decision.REVIEW.value == "review"
        assert Decision.THREAT.value == "threat"


class TestHeadVoteDetail:
    """Tests for HeadVoteDetail dataclass."""

    def test_create_valid_head_vote(self):
        """Test creating a valid head vote detail."""
        detail = HeadVoteDetail(
            head_name="binary",
            vote=Vote.THREAT,
            confidence=0.85,
            weight=1.0,
            raw_probability=0.85,
            threshold_used=0.65,
            prediction="threat",
            rationale="threat_probability (85.00%) >= threat_threshold (65.00%)",
        )
        assert detail.head_name == "binary"
        assert detail.vote == Vote.THREAT
        assert detail.confidence == 0.85
        assert detail.weight == 1.0

    def test_head_vote_immutable(self):
        """Test that head vote is immutable (frozen)."""
        detail = HeadVoteDetail(
            head_name="binary",
            vote=Vote.SAFE,
            confidence=0.75,
            weight=1.0,
            raw_probability=0.25,
            threshold_used=0.40,
            prediction="safe",
            rationale="benign",
        )
        with pytest.raises(AttributeError):
            detail.confidence = 0.5  # type: ignore

    def test_head_vote_confidence_validation(self):
        """Test confidence validation."""
        with pytest.raises(ValueError, match="confidence must be 0-1"):
            HeadVoteDetail(
                head_name="binary",
                vote=Vote.THREAT,
                confidence=1.5,  # Invalid
                weight=1.0,
                raw_probability=0.85,
                threshold_used=0.65,
                prediction="threat",
                rationale="test",
            )

    def test_head_vote_negative_weight_validation(self):
        """Test weight validation."""
        with pytest.raises(ValueError, match="weight must be non-negative"):
            HeadVoteDetail(
                head_name="binary",
                vote=Vote.THREAT,
                confidence=0.85,
                weight=-1.0,  # Invalid
                raw_probability=0.85,
                threshold_used=0.65,
                prediction="threat",
                rationale="test",
            )

    def test_head_vote_to_dict(self):
        """Test to_dict serialization."""
        detail = HeadVoteDetail(
            head_name="binary",
            vote=Vote.THREAT,
            confidence=0.85,
            weight=1.0,
            raw_probability=0.85,
            threshold_used=0.65,
            prediction="threat",
            rationale="test",
        )
        d = detail.to_dict()
        assert d["head_name"] == "binary"
        assert d["vote"] == "threat"
        assert d["confidence"] == 0.85


class TestVotingResult:
    """Tests for VotingResult dataclass."""

    def test_create_valid_voting_result(self):
        """Test creating a valid voting result."""
        votes = {
            "binary": HeadVoteDetail(
                head_name="binary",
                vote=Vote.THREAT,
                confidence=0.85,
                weight=1.0,
                raw_probability=0.85,
                threshold_used=0.65,
                prediction="threat",
                rationale="test",
            ),
        }
        result = VotingResult(
            decision=Decision.THREAT,
            confidence=0.85,
            preset_used="balanced",
            per_head_votes=votes,
            aggregated_scores={"safe": 0.0, "threat": 1.0, "ratio": 999.0},
            decision_rule_triggered="high_confidence_override:binary",
            threat_vote_count=1,
            safe_vote_count=0,
            abstain_vote_count=0,
            weighted_threat_score=1.0,
            weighted_safe_score=0.0,
        )
        assert result.decision == Decision.THREAT
        assert result.is_threat
        assert not result.is_safe
        assert not result.is_review

    def test_voting_result_immutable(self):
        """Test that voting result is immutable (frozen)."""
        result = VotingResult(
            decision=Decision.SAFE,
            confidence=0.75,
            preset_used="balanced",
            per_head_votes={},
            aggregated_scores={"safe": 1.0, "threat": 0.0},
            decision_rule_triggered="safe_majority",
            threat_vote_count=0,
            safe_vote_count=1,
            abstain_vote_count=0,
        )
        with pytest.raises(AttributeError):
            result.decision = Decision.THREAT  # type: ignore

    def test_voting_result_properties(self):
        """Test voting result properties."""
        result = VotingResult(
            decision=Decision.REVIEW,
            confidence=0.60,
            preset_used="balanced",
            per_head_votes={},
            aggregated_scores={"safe": 1.0, "threat": 1.2},
            decision_rule_triggered="weighted_ratio_review_zone",
            threat_vote_count=2,
            safe_vote_count=2,
            abstain_vote_count=1,
            weighted_threat_score=2.4,
            weighted_safe_score=2.0,
        )
        assert result.is_review
        assert not result.is_threat
        assert not result.is_safe
        assert result.total_votes == 4
        assert result.threat_ratio == 0.5
        assert result.weighted_ratio == 1.2

    def test_voting_result_to_dict(self):
        """Test to_dict serialization."""
        result = VotingResult(
            decision=Decision.THREAT,
            confidence=0.85,
            preset_used="balanced",
            per_head_votes={},
            aggregated_scores={"safe": 0.0, "threat": 1.0},
            decision_rule_triggered="test",
            threat_vote_count=1,
            safe_vote_count=0,
            abstain_vote_count=0,
            weighted_threat_score=1.0,
            weighted_safe_score=0.0,
        )
        d = result.to_dict()
        assert d["decision"] == "threat"
        assert d["confidence"] == 0.85
        assert d["preset_used"] == "balanced"

    def test_voting_result_to_dict_infinity_is_json_serializable(self):
        """Test that to_dict handles infinity ratio for JSON serialization.

        When weighted_safe_score is 0, weighted_ratio becomes infinity.
        JSON doesn't support Infinity, so to_dict must convert it to a finite value.
        Regression test for telemetry 400 Bad Request bug.
        """
        import json

        result = VotingResult(
            decision=Decision.THREAT,
            confidence=0.95,
            preset_used="balanced",
            per_head_votes={},
            aggregated_scores={"safe": 0.0, "threat": 5.5},
            decision_rule_triggered="high_confidence_override",
            threat_vote_count=5,
            safe_vote_count=0,  # All threats, no safe votes
            abstain_vote_count=0,
            weighted_threat_score=5.5,
            weighted_safe_score=0.0,  # This causes weighted_ratio = infinity
        )

        # Verify raw property returns infinity
        assert result.weighted_ratio == float("inf")

        # Verify to_dict returns a JSON-serializable value
        d = result.to_dict()
        assert d["weighted_ratio"] == 999.0  # Sentinel value for infinity

        # Verify the entire dict is JSON serializable (no ValueError)
        json_str = json.dumps(d)
        assert "999.0" in json_str
        assert "Infinity" not in json_str


class TestHeadOutput:
    """Tests for HeadOutput dataclass."""

    def test_create_valid_head_output(self):
        """Test creating a valid head output."""
        output = HeadOutput(
            head_name="binary",
            prediction="threat",
            confidence=0.85,
            is_threat_indicator=True,
        )
        assert output.head_name == "binary"
        assert output.prediction == "threat"
        assert output.confidence == 0.85
        assert output.is_threat_indicator

    def test_head_output_confidence_validation(self):
        """Test confidence validation."""
        with pytest.raises(ValueError, match="confidence must be 0-1"):
            HeadOutput(
                head_name="binary",
                prediction="threat",
                confidence=1.5,  # Invalid
            )
