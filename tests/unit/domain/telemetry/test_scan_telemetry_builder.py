"""Tests for ScanTelemetryBuilder voting block and L1 family extraction."""

from dataclasses import dataclass

from raxe.domain.ml.protocol import L2Prediction, L2Result
from raxe.domain.telemetry.scan_telemetry_builder import ScanTelemetryBuilder


@dataclass
class MockDetection:
    """Mock Detection object for testing family extraction."""

    rule_id: str = "unknown"
    category: str | None = None
    severity: str = "medium"
    confidence: float = 0.9


class TestGetFamilyFromDetection:
    """Tests for _get_family_from_detection method."""

    def test_extracts_family_from_category_field(self):
        """Should extract and uppercase family from category field."""
        builder = ScanTelemetryBuilder()

        detection = MockDetection(rule_id="pi-001", category="pi")
        result = builder._get_family_from_detection(detection)

        assert result == "PI"

    def test_extracts_family_from_category_jailbreak(self):
        """Should extract JB from jb category."""
        builder = ScanTelemetryBuilder()

        detection = MockDetection(rule_id="jb-002", category="jb")
        result = builder._get_family_from_detection(detection)

        assert result == "JB"

    def test_extracts_family_from_category_pii(self):
        """Should extract PII from pii category."""
        builder = ScanTelemetryBuilder()

        detection = MockDetection(rule_id="pii-001", category="pii")
        result = builder._get_family_from_detection(detection)

        assert result == "PII"

    def test_extracts_family_from_category_encoding(self):
        """Should extract ENC from enc category."""
        builder = ScanTelemetryBuilder()

        detection = MockDetection(rule_id="enc-001", category="enc")
        result = builder._get_family_from_detection(detection)

        assert result == "ENC"

    def test_falls_back_to_rule_id_prefix_when_no_category(self):
        """Should derive family from rule_id prefix when category is None."""
        builder = ScanTelemetryBuilder()

        detection = MockDetection(rule_id="pi-001", category=None)
        result = builder._get_family_from_detection(detection)

        assert result == "PI"

    def test_falls_back_to_rule_id_prefix_when_category_unknown(self):
        """Should derive family from rule_id prefix when category is 'unknown'."""
        builder = ScanTelemetryBuilder()

        detection = MockDetection(rule_id="jb-003", category="unknown")
        result = builder._get_family_from_detection(detection)

        assert result == "JB"

    def test_returns_unknown_when_no_category_and_no_hyphen(self):
        """Should return UNKNOWN when no category and rule_id has no hyphen."""
        builder = ScanTelemetryBuilder()

        detection = MockDetection(rule_id="orphan_rule", category=None)
        result = builder._get_family_from_detection(detection)

        assert result == "UNKNOWN"

    def test_handles_long_form_category_names(self):
        """Should map long form category names to short family codes."""
        builder = ScanTelemetryBuilder()

        detection = MockDetection(rule_id="pi-001", category="prompt_injection")
        result = builder._get_family_from_detection(detection)

        assert result == "PI"

    def test_handles_missing_attributes(self):
        """Should handle objects with missing attributes gracefully."""
        builder = ScanTelemetryBuilder()

        # Create a bare object without category attribute
        class BareDetection:
            rule_id = "cmd-001"

        detection = BareDetection()
        result = builder._get_family_from_detection(detection)

        assert result == "CMD"


class TestBuildL1BlockFamilies:
    """Tests for L1 block family extraction."""

    def test_l1_block_includes_families_from_category(self):
        """Should include families extracted from Detection.category field."""
        builder = ScanTelemetryBuilder()

        # Create a mock L1Result with detections that have category field
        class MockL1Result:
            scan_duration_ms = 5.0
            detections = [
                MockDetection(rule_id="pi-001", category="pi", severity="high"),
                MockDetection(rule_id="jb-001", category="jb", severity="high"),
            ]

        l1_result = MockL1Result()
        result = builder._build_l1_block(l1_result)

        assert result is not None
        assert "families" in result
        assert "PI" in result["families"]
        assert "JB" in result["families"]
        assert len(result["families"]) == 2

    def test_l1_detection_details_include_family(self):
        """Should include family in per-detection details."""
        builder = ScanTelemetryBuilder()

        class MockL1Result:
            scan_duration_ms = 5.0
            detections = [
                MockDetection(rule_id="pi-001", category="pi", severity="high"),
            ]

        l1_result = MockL1Result()
        result = builder._build_l1_block(l1_result)

        assert result is not None
        assert "detections" in result
        assert len(result["detections"]) == 1
        assert result["detections"][0]["family"] == "PI"

    def test_l1_families_deduplicates(self):
        """Should deduplicate families when multiple detections have same family."""
        builder = ScanTelemetryBuilder()

        class MockL1Result:
            scan_duration_ms = 5.0
            detections = [
                MockDetection(rule_id="pi-001", category="pi", severity="high"),
                MockDetection(rule_id="pi-002", category="pi", severity="medium"),
                MockDetection(rule_id="pi-003", category="pi", severity="low"),
            ]

        l1_result = MockL1Result()
        result = builder._build_l1_block(l1_result)

        assert result is not None
        assert len(result["families"]) == 1
        assert result["families"] == ["PI"]


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


class TestMultiTenantTelemetry:
    """Tests for multi-tenant fields in telemetry (tenant_id, policy_id)."""

    def test_tenant_id_included_in_payload(self):
        """Test tenant_id is included in telemetry payload when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            tenant_id="acme",
        )

        assert "tenant_id" in result
        assert result["tenant_id"] == "acme"

    def test_policy_id_included_in_payload(self):
        """Test policy_id is included in telemetry payload when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            policy_id="strict",
        )

        assert "policy_id" in result
        assert result["policy_id"] == "strict"

    def test_both_tenant_and_policy_included(self):
        """Test both tenant_id and policy_id are included when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            tenant_id="bunny-tenant-123",
            policy_id="balanced",
        )

        assert result["tenant_id"] == "bunny-tenant-123"
        assert result["policy_id"] == "balanced"

    def test_tenant_fields_not_included_when_not_provided(self):
        """Test tenant_id and policy_id are NOT in payload when not provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
        )

        assert "tenant_id" not in result
        assert "policy_id" not in result

    def test_app_id_included_in_payload(self):
        """Test app_id is included in telemetry payload when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            tenant_id="acme",
            app_id="chatbot",
        )

        assert "app_id" in result
        assert result["app_id"] == "chatbot"

    def test_full_multi_tenant_context(self):
        """Test complete multi-tenant context (tenant_id, app_id, policy_id)."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            tenant_id="enterprise-bank",
            app_id="fraud-detection",
            policy_id="strict",
        )

        assert result["tenant_id"] == "enterprise-bank"
        assert result["app_id"] == "fraud-detection"
        assert result["policy_id"] == "strict"

    def test_tenant_fields_are_not_pii(self):
        """Test that tenant_id, app_id, policy_id are configuration identifiers (not PII).

        These fields are safe to include in telemetry because they are:
        - Configuration identifiers, not user identifiers
        - Set by the application operator, not end users
        - Used for billing/audit, not tracking individuals
        """
        builder = ScanTelemetryBuilder()

        # Use realistic tenant/app/policy IDs
        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="user query that should not appear in telemetry",
            tenant_id="tenant_bunny_abc123",
            app_id="app_chatbot_xyz789",
            policy_id="pol_strict_v1",
        )

        # These are safe configuration identifiers
        assert result["tenant_id"] == "tenant_bunny_abc123"
        assert result["app_id"] == "app_chatbot_xyz789"
        assert result["policy_id"] == "pol_strict_v1"

        # Prompt should be hashed, not raw
        assert "prompt" not in result  # Raw prompt not in payload
        assert result["prompt_hash"].startswith("sha256:")  # Only hash present
