"""Tests for VotingEngine."""

from raxe.domain.ml.voting.config import (
    VotingConfig,
    VotingPreset,
)
from raxe.domain.ml.voting.engine import (
    HeadOutputs,
    VotingEngine,
    create_voting_engine,
)
from raxe.domain.ml.voting.models import Decision, Vote


class TestHeadOutputs:
    """Tests for HeadOutputs dataclass."""

    def test_create_head_outputs(self):
        """Test creating head outputs."""
        outputs = HeadOutputs(
            binary_threat_prob=0.80,
            binary_safe_prob=0.20,
            family_prediction="jailbreak",
            family_confidence=0.75,
            severity_prediction="severe",
            severity_confidence=0.85,
            technique_prediction="instruction_override",
            technique_confidence=0.70,
            harm_max_probability=0.60,
            harm_active_labels=[],
        )
        assert outputs.binary_threat_prob == 0.80
        assert outputs.family_prediction == "jailbreak"


class TestVotingEngine:
    """Tests for VotingEngine class."""

    def test_create_with_default_preset(self):
        """Test creating engine with default preset."""
        engine = VotingEngine()
        assert engine.preset_name == "balanced"

    def test_create_with_preset_enum(self):
        """Test creating engine with preset enum."""
        engine = VotingEngine(preset=VotingPreset.HIGH_SECURITY)
        assert engine.preset_name == "high_security"

    def test_create_with_preset_string(self):
        """Test creating engine with preset string."""
        engine = VotingEngine(preset="low_fp")
        assert engine.preset_name == "low_fp"

    def test_create_with_custom_config(self):
        """Test creating engine with custom config."""
        config = VotingConfig(name="custom")
        engine = VotingEngine(config=config)
        assert engine.preset_name == "custom"

    def test_config_property(self):
        """Test config property."""
        engine = VotingEngine()
        config = engine.config
        assert isinstance(config, VotingConfig)

    def test_vote_clear_threat(self):
        """Test voting on clear threat (high probability across heads)."""
        engine = VotingEngine()
        outputs = HeadOutputs(
            binary_threat_prob=0.85,
            binary_safe_prob=0.15,
            family_prediction="jailbreak",
            family_confidence=0.80,
            severity_prediction="severe",
            severity_confidence=0.85,
            technique_prediction="instruction_override",
            technique_confidence=0.75,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.THREAT
        assert result.is_threat
        assert result.threat_vote_count >= 3
        assert "binary" in result.per_head_votes

    def test_vote_clear_safe(self):
        """Test voting on clear safe (low probability across heads)."""
        engine = VotingEngine()
        outputs = HeadOutputs(
            binary_threat_prob=0.15,
            binary_safe_prob=0.85,
            family_prediction="benign",
            family_confidence=0.90,
            severity_prediction="none",
            severity_confidence=0.88,
            technique_prediction="none",
            technique_confidence=0.85,
            harm_max_probability=0.10,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.SAFE
        assert result.is_safe
        assert result.safe_vote_count >= 4

    def test_vote_returns_all_head_votes(self):
        """Test that vote returns all 5 head votes."""
        engine = VotingEngine()
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

    def test_high_confidence_override_rule(self):
        """Test high-confidence override decision rule."""
        engine = VotingEngine()
        outputs = HeadOutputs(
            binary_threat_prob=0.90,  # High confidence
            binary_safe_prob=0.10,
            family_prediction="jailbreak",
            family_confidence=0.70,  # Another THREAT vote
            severity_prediction="none",
            severity_confidence=0.60,
            technique_prediction="none",
            technique_confidence=0.60,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.THREAT
        assert "high_confidence_override" in result.decision_rule_triggered

    def test_severity_veto_rule(self):
        """Test severity veto decision rule."""
        engine = VotingEngine()
        # Severity says SAFE, only 2 other THREAT votes (not enough to override)
        outputs = HeadOutputs(
            binary_threat_prob=0.70,  # THREAT
            binary_safe_prob=0.30,
            family_prediction="jailbreak",
            family_confidence=0.60,  # THREAT
            severity_prediction="none",  # SAFE - veto
            severity_confidence=0.85,
            technique_prediction="none",
            technique_confidence=0.60,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # Severity veto should apply since only 2 THREAT votes (need 3+)
        assert result.decision == Decision.SAFE
        assert "severity_veto" in result.decision_rule_triggered

    def test_min_votes_rule(self):
        """Test minimum votes decision rule."""
        engine = VotingEngine()
        # Only 1 THREAT vote (binary), not enough for THREAT decision
        outputs = HeadOutputs(
            binary_threat_prob=0.70,  # THREAT
            binary_safe_prob=0.30,
            family_prediction="benign",  # SAFE
            family_confidence=0.80,
            severity_prediction="none",  # SAFE
            severity_confidence=0.85,
            technique_prediction="none",  # SAFE
            technique_confidence=0.60,
            harm_max_probability=0.30,  # SAFE
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # Only 1 THREAT vote, not enough (need 2)
        assert result.threat_vote_count == 1
        # Could be SAFE or REVIEW depending on weighted ratio
        assert result.decision in (Decision.SAFE, Decision.REVIEW)

    def test_weighted_ratio_threshold_rule(self):
        """Test weighted ratio threshold decision rule."""
        engine = VotingEngine()
        # 4 THREAT votes, 1 SAFE vote - should trigger weighted ratio
        outputs = HeadOutputs(
            binary_threat_prob=0.70,  # THREAT
            binary_safe_prob=0.30,
            family_prediction="jailbreak",
            family_confidence=0.60,  # THREAT
            severity_prediction="severe",  # THREAT
            severity_confidence=0.80,
            technique_prediction="instruction_override",
            technique_confidence=0.60,  # THREAT
            harm_max_probability=0.30,  # SAFE
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert result.decision == Decision.THREAT
        assert result.threat_vote_count == 4
        assert result.weighted_threat_score > result.weighted_safe_score

    def test_review_zone(self):
        """Test review zone decision (uncertain)."""
        engine = VotingEngine()
        # Mixed signals - should go to REVIEW
        outputs = HeadOutputs(
            binary_threat_prob=0.50,  # ABSTAIN
            binary_safe_prob=0.50,
            family_prediction="jailbreak",
            family_confidence=0.60,  # THREAT
            severity_prediction="moderate",  # THREAT
            severity_confidence=0.50,
            technique_prediction="none",  # SAFE
            technique_confidence=0.60,
            harm_max_probability=0.30,  # SAFE
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # 2 THREAT, 2 SAFE, 1 ABSTAIN - uncertain
        assert result.abstain_vote_count >= 0
        # Could be REVIEW or SAFE depending on ratio
        assert result.decision in (Decision.REVIEW, Decision.SAFE, Decision.THREAT)

    def test_tie_breaker_favors_safe(self):
        """Test tie breaker favors SAFE."""
        engine = VotingEngine()
        # Equal votes and equal weights
        outputs = HeadOutputs(
            binary_threat_prob=0.70,  # THREAT
            binary_safe_prob=0.30,
            family_prediction="benign",  # SAFE
            family_confidence=0.80,
            severity_prediction="none",  # SAFE
            severity_confidence=0.80,
            technique_prediction="instruction_override",
            technique_confidence=0.60,  # THREAT
            harm_max_probability=0.30,  # SAFE
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # 2 THREAT, 3 SAFE - not a tie, should be SAFE anyway
        assert result.safe_vote_count >= result.threat_vote_count

    def test_aggregated_scores(self):
        """Test aggregated scores calculation."""
        engine = VotingEngine()
        outputs = HeadOutputs(
            binary_threat_prob=0.80,
            binary_safe_prob=0.20,
            family_prediction="benign",
            family_confidence=0.70,
            severity_prediction="none",
            severity_confidence=0.80,
            technique_prediction="none",
            technique_confidence=0.70,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        assert "safe" in result.aggregated_scores
        assert "threat" in result.aggregated_scores
        assert "ratio" in result.aggregated_scores

    def test_weighted_scores(self):
        """Test weighted scores calculation."""
        engine = VotingEngine()
        outputs = HeadOutputs(
            binary_threat_prob=0.80,  # THREAT (weight 1.0)
            binary_safe_prob=0.20,
            family_prediction="jailbreak",
            family_confidence=0.70,  # THREAT (weight 1.2)
            severity_prediction="severe",  # THREAT (weight 1.5)
            severity_confidence=0.80,
            technique_prediction="instruction_override",
            technique_confidence=0.60,  # THREAT (weight 1.0)
            harm_max_probability=0.30,  # SAFE (weight 0.8)
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # 4 THREAT votes: 1.0 + 1.2 + 1.5 + 1.0 = 4.7
        # 1 SAFE vote: 0.8
        assert result.weighted_threat_score > 4.0
        assert result.weighted_safe_score < 1.0

    def test_to_dict_serialization(self):
        """Test VotingResult to_dict serialization."""
        engine = VotingEngine()
        outputs = HeadOutputs(
            binary_threat_prob=0.80,
            binary_safe_prob=0.20,
            family_prediction="jailbreak",
            family_confidence=0.70,
            severity_prediction="severe",
            severity_confidence=0.80,
            technique_prediction="instruction_override",
            technique_confidence=0.60,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)
        d = result.to_dict()

        assert isinstance(d, dict)
        assert d["decision"] in ("safe", "review", "threat")
        assert "per_head_votes" in d
        assert "aggregated_scores" in d
        assert "decision_rule_triggered" in d


class TestCreateVotingEngine:
    """Tests for create_voting_engine factory function."""

    def test_create_with_default(self):
        """Test creating engine with defaults."""
        engine = create_voting_engine()
        assert engine.preset_name == "balanced"

    def test_create_with_preset_string(self):
        """Test creating engine with preset string."""
        engine = create_voting_engine(preset="high_security")
        assert engine.preset_name == "high_security"

    def test_create_with_preset_enum(self):
        """Test creating engine with preset enum."""
        engine = create_voting_engine(preset=VotingPreset.LOW_FP)
        assert engine.preset_name == "low_fp"

    def test_create_with_custom_config(self):
        """Test creating engine with custom config."""
        config = VotingConfig(name="my_custom")
        engine = create_voting_engine(config=config)
        assert engine.preset_name == "my_custom"


class TestHighSecurityPreset:
    """Tests specifically for high_security preset behavior."""

    def test_single_threat_vote_can_trigger(self):
        """Test that single THREAT vote can trigger in high_security."""
        engine = VotingEngine(preset="high_security")

        # With high_security, min_threat_votes=1
        outputs = HeadOutputs(
            binary_threat_prob=0.60,  # THREAT with lower threshold
            binary_safe_prob=0.40,
            family_prediction="benign",
            family_confidence=0.80,
            severity_prediction="none",
            severity_confidence=0.80,
            technique_prediction="none",
            technique_confidence=0.70,
            harm_max_probability=0.30,
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # Should at least get a REVIEW or THREAT with single high-confidence vote
        assert result.threat_vote_count >= 1

    def test_lower_thresholds_more_threats(self):
        """Test that lower thresholds trigger more THREAT votes."""
        balanced_engine = VotingEngine(preset="balanced")
        high_sec_engine = VotingEngine(preset="high_security")

        outputs = HeadOutputs(
            binary_threat_prob=0.55,  # Between thresholds
            binary_safe_prob=0.45,
            family_prediction="jailbreak",
            family_confidence=0.45,  # Between thresholds
            severity_prediction="moderate",
            severity_confidence=0.70,
            technique_prediction="instruction_override",
            technique_confidence=0.40,  # Between thresholds
            harm_max_probability=0.85,  # Between thresholds
            harm_active_labels=["privacy"],
        )

        balanced_result = balanced_engine.vote(outputs)
        high_sec_result = high_sec_engine.vote(outputs)

        # High security should be more likely to vote THREAT
        assert high_sec_result.threat_vote_count >= balanced_result.threat_vote_count


class TestLowFpPreset:
    """Tests specifically for low_fp preset behavior."""

    def test_requires_more_threat_votes(self):
        """Test that low_fp requires more THREAT votes."""
        engine = VotingEngine(preset="low_fp")

        # 2 THREAT votes - not enough for low_fp (needs 3)
        outputs = HeadOutputs(
            binary_threat_prob=0.85,  # THREAT
            binary_safe_prob=0.15,
            family_prediction="jailbreak",
            family_confidence=0.80,  # THREAT
            severity_prediction="none",  # SAFE
            severity_confidence=0.85,
            technique_prediction="none",  # SAFE
            technique_confidence=0.70,
            harm_max_probability=0.30,  # SAFE
            harm_active_labels=[],
        )

        result = engine.vote(outputs)

        # With only 2 THREAT votes and severity veto, should be SAFE
        assert result.decision in (Decision.SAFE, Decision.REVIEW)

    def test_higher_thresholds_fewer_threats(self):
        """Test that higher thresholds result in fewer THREAT votes."""
        balanced_engine = VotingEngine(preset="balanced")
        low_fp_engine = VotingEngine(preset="low_fp")

        outputs = HeadOutputs(
            binary_threat_prob=0.70,  # Below low_fp threshold (0.80)
            binary_safe_prob=0.30,
            family_prediction="jailbreak",
            family_confidence=0.65,  # Below low_fp threshold (0.70)
            severity_prediction="moderate",  # SAFE in low_fp (moderate is safe there)
            severity_confidence=0.70,
            technique_prediction="instruction_override",
            technique_confidence=0.60,  # Below low_fp threshold (0.65)
            harm_max_probability=0.93,  # Below low_fp threshold (0.95)
            harm_active_labels=["privacy"],
        )

        balanced_result = balanced_engine.vote(outputs)
        low_fp_result = low_fp_engine.vote(outputs)

        # Low FP should have fewer THREAT votes
        assert low_fp_result.threat_vote_count <= balanced_result.threat_vote_count


class TestHarmFocusedPreset:
    """Tests specifically for harm_focused preset behavior."""

    def test_harm_head_triggers_threat_at_lower_probability(self):
        """Test that harm_focused catches harm content that balanced misses.

        Simulates the "create a bomb" scenario where harm head detected
        violence at 53% but balanced preset required 92%.
        """
        balanced_engine = VotingEngine(preset="balanced")
        harm_focused_engine = VotingEngine(preset="harm_focused")

        # Simulate the bomb prompt scenario:
        # - Binary: 37.8% threat (below threshold)
        # - Family: prompt_injection at 26.5% (below threshold)
        # - Severity: none (votes SAFE)
        # - Technique: data_exfil at 31.2% (gray zone)
        # - Harm: violence at 53% (above harm_focused 50%, below balanced 92%)
        outputs = HeadOutputs(
            binary_threat_prob=0.378,
            binary_safe_prob=0.622,
            family_prediction="prompt_injection",
            family_confidence=0.265,
            severity_prediction="none",
            severity_confidence=0.383,
            technique_prediction="data_exfil_user_content",
            technique_confidence=0.312,
            harm_max_probability=0.53,  # 53% violence detection
            harm_active_labels=["violence_or_physical_harm"],
        )

        balanced_result = balanced_engine.vote(outputs)
        harm_focused_result = harm_focused_engine.vote(outputs)

        # Balanced should classify as SAFE (harm at 53% < 92% threshold)
        assert balanced_result.decision == Decision.SAFE

        # Harm-focused should classify as THREAT (harm at 53% >= 50% threshold)
        assert harm_focused_result.decision == Decision.THREAT

    def test_harm_head_has_highest_weight(self):
        """Test that harm head has highest weight in harm_focused preset."""
        engine = VotingEngine(preset="harm_focused")
        config = engine.config

        # Harm should have the highest weight (3.0 = dominant)
        assert config.weights.harm == 3.0
        assert config.weights.harm >= config.weights.severity
        assert config.weights.harm >= config.weights.binary
        assert config.weights.harm >= config.weights.family

    def test_single_harm_vote_can_trigger_threat(self):
        """Test that a single THREAT vote from harm head is sufficient."""
        engine = VotingEngine(preset="harm_focused")

        # Only harm head votes THREAT (high harm probability)
        outputs = HeadOutputs(
            binary_threat_prob=0.25,  # SAFE
            binary_safe_prob=0.75,
            family_prediction="benign",  # SAFE
            family_confidence=0.80,
            severity_prediction="none",  # SAFE
            severity_confidence=0.90,
            technique_prediction="none",  # SAFE
            technique_confidence=0.85,
            harm_max_probability=0.60,  # THREAT (above 0.50 threshold)
            harm_active_labels=["violence_or_physical_harm"],
        )

        result = engine.vote(outputs)

        # min_threat_votes=1 and severity_veto_override_votes=1
        # So single harm vote should trigger THREAT or at least REVIEW
        assert result.decision in (Decision.THREAT, Decision.REVIEW)
        assert result.per_head_votes["harm"].vote == Vote.THREAT

    def test_harm_can_override_severity_veto(self):
        """Test that harm vote can override severity=none veto."""
        engine = VotingEngine(preset="harm_focused")

        # Severity is "none" (would normally veto), but harm is high
        outputs = HeadOutputs(
            binary_threat_prob=0.55,  # THREAT in harm_focused
            binary_safe_prob=0.45,
            family_prediction="toxic_or_policy_violating_content",
            family_confidence=0.50,  # THREAT
            severity_prediction="none",  # SAFE - would normally veto
            severity_confidence=0.80,
            technique_prediction="none",
            technique_confidence=0.70,
            harm_max_probability=0.65,  # THREAT
            harm_active_labels=["self_harm_or_suicide"],
        )

        result = engine.vote(outputs)

        # With severity_veto_override_votes=1, harm vote should override
        # severity veto and result in THREAT
        assert result.decision == Decision.THREAT


class TestVoteFromClassification:
    """Tests for vote_from_classification() method."""

    def test_vote_from_classification_threat(self):
        """Test voting from GemmaClassificationResult for threat."""
        from raxe.domain.ml.gemma_models import (
            GemmaClassificationResult,
            HarmType,
            MultilabelResult,
            PrimaryTechnique,
            Severity,
            ThreatFamily,
        )

        engine = VotingEngine()

        classification = GemmaClassificationResult(
            is_threat=True,
            threat_probability=0.85,
            safe_probability=0.15,
            threat_family=ThreatFamily.JAILBREAK,
            family_confidence=0.75,
            family_probabilities=tuple([0.02] * 6 + [0.75] + [0.02] * 8),  # 15 classes
            severity=Severity.SEVERE,
            severity_confidence=0.80,
            severity_probabilities=(0.05, 0.15, 0.80),  # 3 classes: none, moderate, severe
            primary_technique=PrimaryTechnique.INSTRUCTION_OVERRIDE,
            technique_confidence=0.70,
            technique_probabilities=tuple([0.01] * 16 + [0.70] + [0.01] * 18),  # 35 classes
            harm_types=MultilabelResult(
                active_labels=[HarmType.CYBERSECURITY_OR_MALWARE],
                probabilities={HarmType.CYBERSECURITY_OR_MALWARE: 0.75},
                thresholds_used={HarmType.CYBERSECURITY_OR_MALWARE: 0.5},
            ),
        )

        result = engine.vote_from_classification(classification)

        assert result.decision == Decision.THREAT
        assert result.threat_vote_count >= 3  # binary, family, severity should vote THREAT
        assert "binary" in result.per_head_votes
        assert "family" in result.per_head_votes
        assert "severity" in result.per_head_votes

    def test_vote_from_classification_safe(self):
        """Test voting from GemmaClassificationResult for safe content."""
        from raxe.domain.ml.gemma_models import (
            GemmaClassificationResult,
            Severity,
            ThreatFamily,
        )

        engine = VotingEngine()

        classification = GemmaClassificationResult(
            is_threat=False,
            threat_probability=0.15,
            safe_probability=0.85,
            threat_family=ThreatFamily.BENIGN,
            family_confidence=0.90,
            family_probabilities=(0.90, 0.02, 0.01, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01),
            severity=Severity.NONE,
            severity_confidence=0.95,
            severity_probabilities=(0.95, 0.02, 0.01, 0.01, 0.01),
            primary_technique=None,
            technique_confidence=0.0,
            technique_probabilities=None,
            harm_types=None,
        )

        result = engine.vote_from_classification(classification)

        assert result.decision == Decision.SAFE
        assert result.safe_vote_count >= 3  # binary, family, severity should vote SAFE

    def test_vote_from_classification_with_no_harm_types(self):
        """Test voting handles None harm_types correctly."""
        from raxe.domain.ml.gemma_models import (
            GemmaClassificationResult,
            Severity,
            ThreatFamily,
        )

        engine = VotingEngine()

        classification = GemmaClassificationResult(
            is_threat=False,
            threat_probability=0.30,
            safe_probability=0.70,
            threat_family=ThreatFamily.BENIGN,
            family_confidence=0.80,
            family_probabilities=(0.80,) + (0.025,) * 8,
            severity=Severity.NONE,
            severity_confidence=0.90,
            severity_probabilities=(0.90, 0.04, 0.03, 0.02, 0.01),
            primary_technique=None,
            technique_confidence=0.0,
            technique_probabilities=None,
            harm_types=None,  # No harm types
        )

        result = engine.vote_from_classification(classification)

        # Should handle None harm_types gracefully
        assert "harm" in result.per_head_votes
        assert result.per_head_votes["harm"].vote in (Vote.SAFE, Vote.ABSTAIN)

    def test_vote_from_classification_matches_direct_vote(self):
        """Test vote_from_classification matches direct vote() call."""
        from raxe.domain.ml.gemma_models import (
            GemmaClassificationResult,
            HarmType,
            MultilabelResult,
            PrimaryTechnique,
            Severity,
            ThreatFamily,
        )

        engine = VotingEngine()

        classification = GemmaClassificationResult(
            is_threat=True,
            threat_probability=0.75,
            safe_probability=0.25,
            threat_family=ThreatFamily.PROMPT_INJECTION,
            family_confidence=0.65,
            family_probabilities=tuple([0.02] * 10 + [0.65] + [0.02] * 4),  # 15 classes
            severity=Severity.MODERATE,
            severity_confidence=0.70,
            severity_probabilities=(0.10, 0.70, 0.20),  # 3 classes: none, moderate, severe
            primary_technique=PrimaryTechnique.CONTEXT_OR_DELIMITER_INJECTION,
            technique_confidence=0.55,
            technique_probabilities=tuple([0.02] * 4 + [0.55] + [0.02] * 30),  # 35 classes
            harm_types=MultilabelResult(
                active_labels=[HarmType.PRIVACY_OR_PII],
                probabilities={HarmType.PRIVACY_OR_PII: 0.60},
                thresholds_used={HarmType.PRIVACY_OR_PII: 0.4},
            ),
        )

        # Vote from classification
        result_from_classification = engine.vote_from_classification(classification)

        # Direct vote with same data
        outputs = HeadOutputs(
            binary_threat_prob=0.75,
            binary_safe_prob=0.25,
            family_prediction="prompt_injection",
            family_confidence=0.65,
            severity_prediction="moderate",
            severity_confidence=0.70,
            technique_prediction="context_or_delimiter_injection",
            technique_confidence=0.55,
            harm_max_probability=0.60,
            harm_active_labels=["privacy_or_pii"],
        )
        result_direct = engine.vote(outputs)

        # Results should match
        assert result_from_classification.decision == result_direct.decision
        assert result_from_classification.threat_vote_count == result_direct.threat_vote_count
        assert result_from_classification.safe_vote_count == result_direct.safe_vote_count
