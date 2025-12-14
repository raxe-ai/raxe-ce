"""Tests for ScanTelemetryBuilder voting block."""

import pytest

from raxe.domain.ml.protocol import L2Prediction, L2Result
from raxe.domain.telemetry.scan_telemetry_builder import ScanTelemetryBuilder


class TestBuildVotingBlock:
    """Tests for _build_voting_block method."""

    def test_voting_block_included_when_present(self):
        """Test voting block is included in telemetry when L2Result has voting data."""
        builder = ScanTelemetryBuilder()

        # Create L2Result with voting data
        voting_data = {
            "decision": "threat",
            "confidence": 0.85,
            "preset_used": "balanced",
            "decision_rule_triggered": "weighted_majority",
            "threat_vote_count": 4,
            "safe_vote_count": 1,
            "abstain_vote_count": 0,
            "weighted_threat_score": 4.7,
            "weighted_safe_score": 0.8,
            "per_head_votes": {
                "binary": {
                    "vote": "threat",
                    "confidence": 0.85,
                    "weight": 1.0,
                    "raw_probability": 0.85,
                    "threshold_used": 0.65,
                    "prediction": "threat",
                    "rationale": "Probability 0.85 >= threshold 0.65",
                },
                "family": {
                    "vote": "threat",
                    "confidence": 0.75,
                    "weight": 1.2,
                    "raw_probability": 0.75,
                    "threshold_used": 0.55,
                    "prediction": "jailbreak",
                    "rationale": "Family jailbreak with confidence 0.75 >= 0.55",
                },
                "severity": {
                    "vote": "threat",
                    "confidence": 0.80,
                    "weight": 1.5,
                    "raw_probability": 0.80,
                    "threshold_used": None,
                    "prediction": "high",
                    "rationale": "Severity high is a threat severity",
                },
                "technique": {
                    "vote": "threat",
                    "confidence": 0.70,
                    "weight": 1.0,
                    "raw_probability": 0.70,
                    "threshold_used": 0.50,
                    "prediction": "instruction_override",
                    "rationale": "Technique instruction_override with confidence 0.70 >= 0.50",
                },
                "harm": {
                    "vote": "safe",
                    "confidence": 0.30,
                    "weight": 0.8,
                    "raw_probability": 0.30,
                    "threshold_used": 0.92,
                    "prediction": None,
                    "rationale": "Max harm probability 0.30 < threshold 0.50",
                },
            },
            "aggregated_scores": {
                "safe": 0.24,
                "threat": 4.70,
                "ratio": 19.58,
            },
        }

        l2_result = L2Result(
            predictions=[
                L2Prediction(
                    threat_type="jailbreak",
                    confidence=0.85,
                    features_used=["binary", "family", "severity"],
                    metadata={"is_attack": True},
                )
            ],
            confidence=0.85,
            processing_time_ms=15.0,
            model_version="gemma-5head-v1",
            voting=voting_data,
        )

        # Build voting block
        result = builder._build_voting_block(l2_result)

        assert result is not None
        assert result["decision"] == "threat"
        assert result["confidence"] == 0.85
        assert result["preset_used"] == "balanced"
        assert result["decision_rule_triggered"] == "weighted_majority"
        assert result["threat_vote_count"] == 4
        assert result["safe_vote_count"] == 1
        assert "per_head_votes" in result
        assert "binary" in result["per_head_votes"]
        assert "severity" in result["per_head_votes"]
        assert result["per_head_votes"]["severity"]["weight"] == 1.5

    def test_voting_block_none_when_no_voting_data(self):
        """Test voting block is None when L2Result has no voting data."""
        builder = ScanTelemetryBuilder()

        l2_result = L2Result(
            predictions=[
                L2Prediction(
                    threat_type="benign",
                    confidence=0.90,
                    features_used=["binary"],
                    metadata={},
                )
            ],
            confidence=0.90,
            processing_time_ms=10.0,
            model_version="gemma-5head-v1",
            voting=None,  # No voting data
        )

        result = builder._build_voting_block(l2_result)

        assert result is None

    def test_voting_block_none_when_l2_result_is_none(self):
        """Test voting block is None when L2Result is None."""
        builder = ScanTelemetryBuilder()

        result = builder._build_voting_block(None)

        assert result is None

    def test_voting_block_has_all_required_fields(self):
        """Test voting block contains all required fields."""
        builder = ScanTelemetryBuilder()

        # Create L2 result with complete voting data
        voting_data = {
            "decision": "safe",
            "confidence": 0.92,
            "preset_used": "balanced",
            "decision_rule_triggered": "severity_veto",
            "threat_vote_count": 1,
            "safe_vote_count": 4,
            "abstain_vote_count": 0,
            "weighted_threat_score": 1.0,
            "weighted_safe_score": 4.5,
            "per_head_votes": {
                "binary": {"vote": "abstain", "confidence": 0.55, "weight": 1.0},
                "family": {"vote": "safe", "confidence": 0.80, "weight": 1.2},
                "severity": {"vote": "safe", "confidence": 0.94, "weight": 1.5},
                "technique": {"vote": "safe", "confidence": 0.70, "weight": 1.0},
                "harm": {"vote": "safe", "confidence": 0.30, "weight": 0.8},
            },
            "aggregated_scores": {"safe": 4.5, "threat": 1.0, "ratio": 0.22},
        }

        l2_result = L2Result(
            predictions=[
                L2Prediction(
                    threat_type="benign",
                    confidence=0.92,
                    features_used=[],
                    metadata={"is_attack": False, "severity": "none"},
                )
            ],
            confidence=0.92,
            processing_time_ms=12.0,
            model_version="gemma-5head-v1",
            voting=voting_data,
        )

        result = builder._build_voting_block(l2_result)

        # Verify all required fields are present
        assert result is not None
        assert result["decision"] == "safe"
        assert result["preset_used"] == "balanced"
        assert result["decision_rule_triggered"] == "severity_veto"
        assert result["threat_vote_count"] == 1
        assert result["safe_vote_count"] == 4
        assert result["abstain_vote_count"] == 0

        # Verify per-head votes structure
        assert "per_head_votes" in result
        assert len(result["per_head_votes"]) == 5
        for head in ["binary", "family", "severity", "technique", "harm"]:
            assert head in result["per_head_votes"]
            assert "vote" in result["per_head_votes"][head]
            assert "confidence" in result["per_head_votes"][head]
            assert "weight" in result["per_head_votes"][head]

        # Verify aggregated scores
        assert "aggregated_scores" in result
        assert "safe" in result["aggregated_scores"]
        assert "threat" in result["aggregated_scores"]


class TestVotingBlockPresets:
    """Test that different presets appear correctly in telemetry."""

    def test_high_security_preset_in_telemetry(self):
        """Test high_security preset appears in voting telemetry."""
        builder = ScanTelemetryBuilder()

        voting_data = {
            "decision": "threat",
            "confidence": 0.75,
            "preset_used": "high_security",
            "decision_rule_triggered": "single_threat_vote",
            "threat_vote_count": 1,
            "safe_vote_count": 4,
            "abstain_vote_count": 0,
            "per_head_votes": {},
            "aggregated_scores": {},
        }

        l2_result = L2Result(
            predictions=[],
            confidence=0.75,
            processing_time_ms=10.0,
            model_version="gemma-5head-v1",
            voting=voting_data,
        )

        result = builder._build_voting_block(l2_result)

        assert result["preset_used"] == "high_security"

    def test_low_fp_preset_in_telemetry(self):
        """Test low_fp preset appears in voting telemetry."""
        builder = ScanTelemetryBuilder()

        voting_data = {
            "decision": "safe",
            "confidence": 0.85,
            "preset_used": "low_fp",
            "decision_rule_triggered": "insufficient_threat_votes",
            "threat_vote_count": 2,
            "safe_vote_count": 3,
            "abstain_vote_count": 0,
            "per_head_votes": {},
            "aggregated_scores": {},
        }

        l2_result = L2Result(
            predictions=[],
            confidence=0.85,
            processing_time_ms=10.0,
            model_version="gemma-5head-v1",
            voting=voting_data,
        )

        result = builder._build_voting_block(l2_result)

        assert result["preset_used"] == "low_fp"
        # low_fp requires 3 THREAT votes, so 2 is insufficient
        assert result["decision_rule_triggered"] == "insufficient_threat_votes"


class TestVotingBlockWithEmptyPredictions:
    """Test that voting data is included even with empty predictions (for SAFE decisions)."""

    def test_voting_block_included_when_no_predictions(self):
        """Test voting block is included in L2 block even when predictions list is empty.

        This is critical for transparency on SAFE/FP classifications so users can
        see how the decision was derived.
        """
        builder = ScanTelemetryBuilder()

        # Create L2Result with voting data but empty predictions (SAFE case)
        voting_data = {
            "decision": "safe",
            "confidence": 0.88,
            "preset_used": "balanced",
            "decision_rule_triggered": "weighted_majority",
            "threat_vote_count": 1,
            "safe_vote_count": 4,
            "abstain_vote_count": 0,
            "weighted_threat_score": 1.2,
            "weighted_safe_score": 4.3,
            "per_head_votes": {
                "binary": {"vote": "safe", "confidence": 0.85, "weight": 1.0},
                "family": {"vote": "safe", "confidence": 0.90, "weight": 1.2},
                "severity": {"vote": "safe", "confidence": 0.92, "weight": 1.5},
                "technique": {"vote": "safe", "confidence": 0.80, "weight": 1.0},
                "harm": {"vote": "safe", "confidence": 0.15, "weight": 0.8},
            },
            "aggregated_scores": {"safe": 4.3, "threat": 1.2, "ratio": 0.28},
        }

        l2_result = L2Result(
            predictions=[],  # Empty predictions (SAFE case)
            confidence=0.88,
            processing_time_ms=12.0,
            model_version="gemma-5head-v1",
            voting=voting_data,
        )

        # Build L2 block (not just voting block)
        result = builder._build_l2_block(l2_result, l2_enabled=True)

        # Verify L2 block structure
        assert result is not None
        assert result["enabled"] is True
        assert result["hit"] is False
        assert result["model_version"] == "gemma-5head-v1"

        # Critical: voting block should be present even with empty predictions
        assert "voting" in result
        assert result["voting"]["decision"] == "safe"
        assert result["voting"]["preset_used"] == "balanced"
        assert result["voting"]["safe_vote_count"] == 4
        assert "per_head_votes" in result["voting"]

    def test_no_voting_block_when_voting_is_none_and_no_predictions(self):
        """Test that voting block is NOT included when voting=None and no predictions."""
        builder = ScanTelemetryBuilder()

        l2_result = L2Result(
            predictions=[],
            confidence=0.5,
            processing_time_ms=10.0,
            model_version="gemma-5head-v1",
            voting=None,  # No voting data
        )

        result = builder._build_l2_block(l2_result, l2_enabled=True)

        assert result is not None
        assert result["enabled"] is True
        assert result["hit"] is False
        assert "voting" not in result  # No voting block when voting is None
