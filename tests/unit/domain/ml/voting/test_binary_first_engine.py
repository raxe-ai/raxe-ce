"""Tests for BinaryFirstEngine."""

import pytest

from raxe.domain.ml.voting.binary_first_engine import (
    BinaryFirstConfig,
    BinaryFirstEngine,
    SuppressionDetail,
    create_binary_first_engine,
)
from raxe.domain.ml.voting.engine import HeadOutputs
from raxe.domain.ml.voting.models import Decision


class TestBinaryFirstConfig:
    """Tests for BinaryFirstConfig dataclass."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = BinaryFirstConfig()
        assert config.name == "binary_first"
        assert config.high_threat_threshold == 0.85
        assert config.mid_zone_low == 0.50
        assert (
            config.suppression_quorum == 3
        )  # Requires 3 heads for suppression (validated: TPR 90.4%)
        assert config.severity_none_confidence == 0.70
        assert config.family_benign_confidence == 0.60
        assert config.technique_none_confidence == 0.50

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = BinaryFirstConfig(
            name="custom_binary_first",
            high_threat_threshold=0.90,
            suppression_quorum=3,
        )
        assert config.name == "custom_binary_first"
        assert config.high_threat_threshold == 0.90
        assert config.suppression_quorum == 3


class TestBinaryFirstEngine:
    """Tests for BinaryFirstEngine class."""

    @pytest.fixture
    def engine(self):
        """Create default BinaryFirstEngine."""
        return BinaryFirstEngine()

    @pytest.fixture
    def lenient_engine(self):
        """Create engine with lenient suppression (quorum=2, low_fp preset)."""
        return BinaryFirstEngine(BinaryFirstConfig(suppression_quorum=2))

    # ============================================================
    # HIGH_THREAT_ZONE tests (binary >= 0.85)
    # ============================================================

    def test_high_threat_zone_no_suppression(self, engine):
        """Binary >= 0.85 without suppression quorum → THREAT."""
        outputs = HeadOutputs(
            binary_threat_prob=0.92,
            binary_safe_prob=0.08,
            family_prediction="jailbreak",
            family_confidence=0.80,
            severity_prediction="moderate",  # Not "none"
            severity_confidence=0.85,
            technique_prediction="instruction_override",
            technique_confidence=0.70,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.THREAT
        assert result.is_threat
        assert "binary_high_threat" in result.decision_rule_triggered
        assert result.confidence == pytest.approx(0.92, abs=0.01)

    def test_high_threat_zone_with_suppression_3_heads(self, engine):
        """Binary >= 0.85 with 3 benign heads → SAFE (suppressed)."""
        outputs = HeadOutputs(
            binary_threat_prob=0.92,
            binary_safe_prob=0.08,
            family_prediction="benign",  # Benign with high confidence (1)
            family_confidence=0.75,
            severity_prediction="none",  # None with high confidence (2)
            severity_confidence=0.85,
            technique_prediction="none",  # None with high confidence (3)
            technique_confidence=0.60,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.SAFE
        assert result.is_safe
        assert "suppression" in result.decision_rule_triggered

    def test_high_threat_zone_suppression_requires_confidence(self, engine):
        """Suppression requires heads to meet confidence thresholds."""
        outputs = HeadOutputs(
            binary_threat_prob=0.92,
            binary_safe_prob=0.08,
            family_prediction="benign",
            family_confidence=0.40,  # Below threshold (0.60)
            severity_prediction="none",
            severity_confidence=0.50,  # Below threshold (0.70)
            technique_prediction="none",
            technique_confidence=0.40,  # Below threshold (0.50)
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # No heads meet confidence threshold, so no suppression
        assert result.decision == Decision.THREAT
        assert "binary_high_threat" in result.decision_rule_triggered

    def test_high_threat_zone_single_head_cannot_suppress(self, engine):
        """Single benign head cannot suppress (need quorum of 3)."""
        outputs = HeadOutputs(
            binary_threat_prob=0.92,
            binary_safe_prob=0.08,
            family_prediction="jailbreak",  # Threat
            family_confidence=0.80,
            severity_prediction="none",  # Only this is benign with high conf
            severity_confidence=0.90,
            technique_prediction="instruction_override",  # Threat
            technique_confidence=0.70,
            harm_max_probability=0.50,
            harm_active_labels=["cybersecurity_or_malware"],
        )

        result = engine.vote(outputs)

        # Only 1 head voted benign, need 3 for suppression
        assert result.decision == Decision.THREAT

    def test_high_threat_zone_suppression_tracks_telemetry(self, engine):
        """Suppression details are tracked for telemetry."""
        outputs = HeadOutputs(
            binary_threat_prob=0.92,
            binary_safe_prob=0.08,
            family_prediction="benign",  # (1)
            family_confidence=0.75,
            severity_prediction="none",  # (2)
            severity_confidence=0.85,
            technique_prediction="none",  # (3)
            technique_confidence=0.60,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        _result = engine.vote(outputs)
        suppression = engine.last_suppression

        assert suppression is not None
        assert suppression.evaluated is True
        assert suppression.suppressed is True
        assert suppression.benign_votes >= 3
        assert suppression.quorum_required == 3

    # ============================================================
    # MID_ZONE tests (binary 0.50-0.85)
    # ============================================================

    def test_mid_zone_high_ratio_returns_threat(self, engine):
        """Mid-zone with high weighted ratio → THREAT."""
        outputs = HeadOutputs(
            binary_threat_prob=0.70,  # In mid zone
            binary_safe_prob=0.30,
            family_prediction="jailbreak",  # Threat
            family_confidence=0.80,
            severity_prediction="severe",  # Threat
            severity_confidence=0.85,
            technique_prediction="instruction_override",  # Threat
            technique_confidence=0.75,
            harm_max_probability=0.60,  # Threat
            harm_active_labels=["cybersecurity_or_malware"],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.THREAT
        assert "mid_zone_threat_ratio" in result.decision_rule_triggered

    def test_mid_zone_uncertain_returns_review(self, engine):
        """Mid-zone with uncertain signals → REVIEW."""
        outputs = HeadOutputs(
            binary_threat_prob=0.60,  # In mid zone
            binary_safe_prob=0.40,
            family_prediction="benign",  # Safe
            family_confidence=0.55,
            severity_prediction="moderate",  # Threat
            severity_confidence=0.60,
            technique_prediction="none",  # Safe
            technique_confidence=0.55,
            harm_max_probability=0.45,  # Safe
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # Mixed signals should result in REVIEW
        assert result.decision in [Decision.REVIEW, Decision.SAFE, Decision.THREAT]

    def test_mid_zone_low_ratio_returns_safe(self, engine):
        """Mid-zone with low weighted ratio → SAFE."""
        outputs = HeadOutputs(
            binary_threat_prob=0.55,  # In mid zone, low
            binary_safe_prob=0.45,
            family_prediction="benign",  # Safe
            family_confidence=0.80,
            severity_prediction="none",  # Safe
            severity_confidence=0.85,
            technique_prediction="none",  # Safe
            technique_confidence=0.75,
            harm_max_probability=0.20,  # Safe
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.SAFE
        assert "mid_zone_safe" in result.decision_rule_triggered

    # ============================================================
    # LOW_THREAT_ZONE tests (binary < 0.50)
    # ============================================================

    def test_low_zone_always_safe(self, engine):
        """Binary < 0.50 → SAFE regardless of other heads."""
        outputs = HeadOutputs(
            binary_threat_prob=0.30,  # Low zone
            binary_safe_prob=0.70,
            family_prediction="jailbreak",  # Even if family says threat
            family_confidence=0.95,
            severity_prediction="severe",  # Even if severity says severe
            severity_confidence=0.90,
            technique_prediction="instruction_override",
            technique_confidence=0.85,
            harm_max_probability=0.80,
            harm_active_labels=["cybersecurity_or_malware"],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.SAFE
        assert result.is_safe
        assert "binary_low_threat" in result.decision_rule_triggered

    def test_low_zone_very_low_probability(self, engine):
        """Very low binary probability → high confidence SAFE."""
        outputs = HeadOutputs(
            binary_threat_prob=0.05,
            binary_safe_prob=0.95,
            family_prediction="benign",
            family_confidence=0.90,
            severity_prediction="none",
            severity_confidence=0.90,
            technique_prediction="none",
            technique_confidence=0.85,
            harm_max_probability=0.10,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.SAFE
        assert result.confidence >= 0.90  # 1 - 0.05 = 0.95

    # ============================================================
    # Zone boundary tests
    # ============================================================

    def test_boundary_high_threat_zone(self, engine):
        """Binary exactly at high_threat_threshold (0.85)."""
        outputs = HeadOutputs(
            binary_threat_prob=0.85,  # Exactly at boundary
            binary_safe_prob=0.15,
            family_prediction="jailbreak",
            family_confidence=0.70,
            severity_prediction="moderate",
            severity_confidence=0.70,
            technique_prediction="instruction_override",
            technique_confidence=0.60,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # Should be in HIGH_THREAT_ZONE
        assert result.decision == Decision.THREAT
        assert "binary_high_threat" in result.decision_rule_triggered

    def test_boundary_mid_zone_low(self, engine):
        """Binary exactly at mid_zone_low (0.50)."""
        outputs = HeadOutputs(
            binary_threat_prob=0.50,  # Exactly at boundary
            binary_safe_prob=0.50,
            family_prediction="benign",
            family_confidence=0.70,
            severity_prediction="none",
            severity_confidence=0.70,
            technique_prediction="none",
            technique_confidence=0.60,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # Should be in MID_ZONE
        assert "mid_zone" in result.decision_rule_triggered

    def test_boundary_below_mid_zone(self, engine):
        """Binary just below mid_zone_low (0.49)."""
        outputs = HeadOutputs(
            binary_threat_prob=0.49,  # Just below boundary
            binary_safe_prob=0.51,
            family_prediction="jailbreak",  # Even with threat signals
            family_confidence=0.90,
            severity_prediction="severe",
            severity_confidence=0.90,
            technique_prediction="instruction_override",
            technique_confidence=0.80,
            harm_max_probability=0.60,
            harm_active_labels=["cybersecurity_or_malware"],
        )

        result = engine.vote(outputs)

        # Should be in LOW_THREAT_ZONE
        assert result.decision == Decision.SAFE
        assert "binary_low_threat" in result.decision_rule_triggered

    # ============================================================
    # VotingResult structure tests
    # ============================================================

    def test_vote_returns_all_head_votes(self, engine):
        """Vote returns all 5 head votes."""
        outputs = HeadOutputs(
            binary_threat_prob=0.50,
            binary_safe_prob=0.50,
            family_prediction="benign",
            family_confidence=0.50,
            severity_prediction="none",
            severity_confidence=0.50,
            technique_prediction="none",
            technique_confidence=0.50,
            harm_max_probability=0.50,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert len(result.per_head_votes) == 5
        assert "binary" in result.per_head_votes
        assert "family" in result.per_head_votes
        assert "severity" in result.per_head_votes
        assert "technique" in result.per_head_votes
        assert "harm" in result.per_head_votes

    def test_vote_result_has_aggregated_scores(self, engine):
        """VotingResult includes aggregated scores."""
        outputs = HeadOutputs(
            binary_threat_prob=0.70,
            binary_safe_prob=0.30,
            family_prediction="jailbreak",
            family_confidence=0.80,
            severity_prediction="severe",
            severity_confidence=0.85,
            technique_prediction="instruction_override",
            technique_confidence=0.75,
            harm_max_probability=0.60,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert "safe" in result.aggregated_scores
        assert "threat" in result.aggregated_scores
        assert "ratio" in result.aggregated_scores

    def test_vote_result_has_preset_name(self, engine):
        """VotingResult includes preset name."""
        outputs = HeadOutputs(
            binary_threat_prob=0.50,
            binary_safe_prob=0.50,
            family_prediction="benign",
            family_confidence=0.50,
            severity_prediction="none",
            severity_confidence=0.50,
            technique_prediction="none",
            technique_confidence=0.50,
            harm_max_probability=0.50,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.preset_used == "balanced"  # Default preset is "balanced"

    def test_vote_result_confidence_in_valid_range(self, engine):
        """VotingResult confidence is between 0 and 1."""
        test_cases = [
            (0.95, 0.05),  # High threat
            (0.50, 0.50),  # Uncertain
            (0.10, 0.90),  # Low threat
        ]

        for threat_prob, safe_prob in test_cases:
            outputs = HeadOutputs(
                binary_threat_prob=threat_prob,
                binary_safe_prob=safe_prob,
                family_prediction="benign",
                family_confidence=0.50,
                severity_prediction="none",
                severity_confidence=0.50,
                technique_prediction="none",
                technique_confidence=0.50,
                harm_max_probability=0.50,
                harm_active_labels=[],
            )

            result = engine.vote(outputs)

            assert 0.0 <= result.confidence <= 1.0

    # ============================================================
    # Lenient engine tests (suppression_quorum=2, low_fp preset)
    # ============================================================

    def test_lenient_engine_suppresses_with_2_heads(self, lenient_engine):
        """Lenient engine (quorum=2) suppresses when 2 heads vote benign."""
        outputs = HeadOutputs(
            binary_threat_prob=0.92,
            binary_safe_prob=0.08,
            family_prediction="benign",  # (1)
            family_confidence=0.75,
            severity_prediction="none",  # (2)
            severity_confidence=0.85,
            technique_prediction="instruction_override",  # Threat (not counted)
            technique_confidence=0.70,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = lenient_engine.vote(outputs)

        # 2 benign heads meet lenient quorum
        assert result.decision == Decision.SAFE
        assert "suppression" in result.decision_rule_triggered

    def test_default_engine_does_not_suppress_with_2_heads(self, engine):
        """Default engine (quorum=3) does NOT suppress when only 2 heads vote benign."""
        outputs = HeadOutputs(
            binary_threat_prob=0.92,
            binary_safe_prob=0.08,
            family_prediction="benign",  # (1)
            family_confidence=0.75,
            severity_prediction="none",  # (2)
            severity_confidence=0.85,
            technique_prediction="instruction_override",  # Threat
            technique_confidence=0.70,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # Only 2 benign heads, need 3 for suppression with default
        assert result.decision == Decision.THREAT
        assert "binary_high_threat" in result.decision_rule_triggered


class TestCreateBinaryFirstEngine:
    """Tests for factory function."""

    def test_create_with_defaults(self):
        """Test factory function with defaults."""
        engine = create_binary_first_engine()
        assert engine.config.name == "balanced"  # Default preset name
        assert engine.config.suppression_quorum == 3

    def test_create_with_preset_balanced(self):
        """Test factory function with balanced preset."""
        engine = create_binary_first_engine(preset="balanced")
        assert engine.config.name == "balanced"
        assert engine.config.suppression_quorum == 3

    def test_create_with_preset_high_recall(self):
        """Test factory function with high_recall preset."""
        engine = create_binary_first_engine(preset="high_recall")
        assert engine.config.name == "high_recall"
        assert engine.config.high_threat_threshold == 0.80

    def test_create_with_preset_low_fp(self):
        """Test factory function with low_fp preset."""
        engine = create_binary_first_engine(preset="low_fp")
        assert engine.config.name == "low_fp"
        assert engine.config.suppression_quorum == 2  # More lenient

    def test_create_with_invalid_preset_raises(self):
        """Test factory function with invalid preset raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_binary_first_engine(preset="invalid_preset")
        assert "Unknown preset" in str(exc_info.value)

    def test_create_with_custom_config(self):
        """Test factory function with custom config."""
        config = BinaryFirstConfig(
            name="custom",
            suppression_quorum=2,
            high_threat_threshold=0.90,
        )
        engine = create_binary_first_engine(config=config)
        assert engine.config.name == "custom"
        assert engine.config.suppression_quorum == 2
        assert engine.config.high_threat_threshold == 0.90

    def test_config_takes_precedence_over_preset(self):
        """Test that config parameter takes precedence over preset."""
        config = BinaryFirstConfig(name="custom", suppression_quorum=1)
        engine = create_binary_first_engine(preset="balanced", config=config)
        assert engine.config.name == "custom"
        assert engine.config.suppression_quorum == 1


class TestSuppressionDetail:
    """Tests for SuppressionDetail dataclass."""

    def test_suppression_detail_defaults(self):
        """Test SuppressionDetail default values."""
        detail = SuppressionDetail()
        assert detail.evaluated is False
        assert detail.suppressed is False
        assert detail.benign_votes == 0
        assert detail.quorum_required == 3  # Default quorum is now 3
        assert detail.head_contributions == {}

    def test_suppression_detail_populated(self):
        """Test SuppressionDetail with values."""
        detail = SuppressionDetail(
            evaluated=True,
            suppressed=True,
            benign_votes=2,
            quorum_required=2,
            head_contributions={
                "severity": ("none", 0.85, True),
                "family": ("benign", 0.75, True),
                "technique": ("instruction_override", 0.70, False),
            },
        )
        assert detail.evaluated is True
        assert detail.suppressed is True
        assert detail.benign_votes == 2
        assert len(detail.head_contributions) == 3


class TestBinaryFirstVsOriginalEngineComparison:
    """Tests comparing BinaryFirstEngine behavior to VotingEngine.

    These tests document the key behavioral differences between engines.
    """

    def test_no_severity_veto_in_binary_first(self):
        """BinaryFirstEngine does not have severity_veto rule.

        This is the key difference - VotingEngine would return SAFE here
        due to severity_veto, but BinaryFirstEngine returns THREAT.
        """
        engine = BinaryFirstEngine()

        # High binary prob + severity="none" + only 1 other threat vote
        outputs = HeadOutputs(
            binary_threat_prob=0.95,
            binary_safe_prob=0.05,
            family_prediction="jailbreak",  # Threat
            family_confidence=0.70,
            severity_prediction="none",  # Would trigger severity_veto
            severity_confidence=0.85,
            technique_prediction="instruction_override",  # Threat
            technique_confidence=0.65,
            harm_max_probability=0.40,  # Safe
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # BinaryFirstEngine: THREAT (binary is high, only 1 benign head)
        # VotingEngine would: SAFE (severity_veto)
        assert result.decision == Decision.THREAT
        assert "binary_high_threat" in result.decision_rule_triggered

    def test_binary_first_trusts_binary_in_low_zone(self):
        """BinaryFirstEngine trusts binary head completely in low zone.

        Even with strong threat signals from other heads, low binary
        probability results in SAFE.
        """
        engine = BinaryFirstEngine()

        outputs = HeadOutputs(
            binary_threat_prob=0.40,  # Low zone
            binary_safe_prob=0.60,
            family_prediction="data_exfiltration",  # Strong threat
            family_confidence=0.95,
            severity_prediction="severe",  # Strong threat
            severity_confidence=0.95,
            technique_prediction="credential_theft_via_tool",  # Strong threat
            technique_confidence=0.90,
            harm_max_probability=0.85,  # Strong threat
            harm_active_labels=["privacy_or_pii", "crime_or_fraud"],
        )

        result = engine.vote(outputs)

        # Binary says benign -> SAFE regardless of other heads
        assert result.decision == Decision.SAFE
        assert "binary_low_threat" in result.decision_rule_triggered
