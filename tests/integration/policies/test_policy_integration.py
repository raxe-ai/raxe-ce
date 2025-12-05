"""Integration tests for policy pipeline.

Tests end-to-end flow: load → validate → evaluate.
"""
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

import pytest

from raxe.application.apply_policy import (
    ApplyPolicyUseCase,
    PolicySource,
)
from raxe.domain.engine.executor import Detection
from raxe.domain.engine.matcher import Match
from raxe.domain.policies.models import PolicyAction
from raxe.domain.rules.models import Severity
from raxe.infrastructure.security.auth import APIKey


def make_detection(severity: Severity = Severity.HIGH) -> Detection:
    """Create test detection."""
    return Detection(
        rule_id="pi-001",
        rule_version="0.0.1",
        severity=severity,
        confidence=0.9,
        matches=[Match(
            pattern_index=0,
            start=0,
            end=10,
            matched_text="test match",
            groups=(),
            context_before="",
            context_after="",
        )],
        detected_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.mark.integration
class TestPolicyPipelineIntegration:
    """Integration tests for complete policy pipeline."""

    def test_local_file_policy_loading(self, tmp_path: Path):
        """Test loading policies from local YAML file."""
        # Create policy file
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: block-critical
                customer_id: cust_test123
                name: Block Critical
                description: Block all critical threats
                conditions:
                  - severity: critical
                action: BLOCK
                priority: 100
        """))

        # Apply policy
        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.CRITICAL)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        # Should be blocked
        assert decision.should_block is True
        assert decision.action == PolicyAction.BLOCK
        assert "block-critical" in decision.matched_policies

    def test_inline_policy_evaluation(self):
        """Test inline policy programmatic creation."""
        from raxe.domain.policies.models import Policy, PolicyCondition

        # Create policies programmatically
        inline_policies = [
            Policy(
                policy_id="inline-001",
                customer_id="cust_test",
                name="Inline Policy",
                description="Created in code",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.FLAG,
                priority=50,
            )
        ]

        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.HIGH)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.INLINE,
            inline_policies=inline_policies,
        )

        assert decision.should_flag is True
        assert decision.action == PolicyAction.FLAG
        assert "inline-001" in decision.matched_policies

    def test_no_policy_file_returns_default(self, tmp_path: Path):
        """If policy file doesn't exist, return default LOG action."""
        use_case = ApplyPolicyUseCase()
        detection = make_detection()

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=tmp_path / "nonexistent.yaml",
        )

        # Default action
        assert decision.action == PolicyAction.LOG
        assert len(decision.matched_policies) == 0

    def test_multiple_policies_priority_order(self, tmp_path: Path):
        """Highest priority policy wins."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: low-priority
                customer_id: cust_test
                name: Low Priority
                description: Lower priority
                priority: 10
                conditions:
                  - severity: high
                action: ALLOW

              - id: high-priority
                customer_id: cust_test
                name: High Priority
                description: Higher priority
                priority: 100
                conditions:
                  - severity: high
                action: BLOCK
        """))

        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.HIGH)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        # Highest priority wins
        assert decision.action == PolicyAction.BLOCK
        assert decision.matched_policies[0] == "high-priority"
        assert decision.matched_policies[1] == "low-priority"

    def test_customer_filtering_with_api_key(self, tmp_path: Path):
        """Policies filtered by customer ID from API key."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: customer-a-policy
                customer_id: cust_customer_a
                name: Customer A Policy
                description: For customer A only
                conditions:
                  - severity: high
                action: BLOCK

              - id: customer-b-policy
                customer_id: cust_customer_b
                name: Customer B Policy
                description: For customer B only
                conditions:
                  - severity: high
                action: ALLOW
        """))

        # Customer A should only see their policy
        api_key = APIKey.parse("raxe_test_cust_customer_a_abc123def456")
        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.HIGH)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
            api_key=api_key,
        )

        # Only customer A policy matched
        assert decision.action == PolicyAction.BLOCK
        assert decision.matched_policies == ["customer-a-policy"]

    def test_severity_override(self, tmp_path: Path):
        """Policy can override detection severity."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: upgrade-severity
                customer_id: cust_test
                name: Upgrade Severity
                description: Upgrade medium to critical
                conditions:
                  - severity: medium
                action: FLAG
                override_severity: critical
        """))

        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.MEDIUM)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        assert decision.original_severity == Severity.MEDIUM
        assert decision.final_severity == Severity.CRITICAL
        assert decision.severity_changed is True


@pytest.mark.integration
class TestPhase3PolicyIntegration:
    """Integration tests for Phase 3 policy changes.

    Tests:
    - L2 virtual rules can be matched by policies
    - Security limits enforced (max 100 policies, priority 0-1000)
    - End-to-end: load policies.yaml → scan → policy applied
    - ALLOW/FLAG/BLOCK actions work correctly
    """

    def test_l2_virtual_rule_matches_policy(self, tmp_path: Path):
        """L2 virtual rule (l2-prompt-injection) matches policy."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: block-l2-pi
                customer_id: cust_test
                name: Block L2 Prompt Injection
                description: Block ML-detected prompt injection
                conditions:
                  - rule_ids: ["l2-prompt-injection"]
                action: BLOCK
                priority: 100
        """))

        # Create L2 virtual detection
        l2_detection = Detection(
            rule_id="l2-prompt-injection",
            rule_version="0.0.1",
            severity=Severity.HIGH,
            confidence=0.92,
            matches=[Match(
                pattern_index=0,
                start=0,
                end=0,
                matched_text="[L2 ML Detection]",
                groups=(),
                context_before="",
                context_after="",
            )],
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        use_case = ApplyPolicyUseCase()
        decision = use_case.apply_to_detection(
            l2_detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        assert decision.should_block is True
        assert decision.action == PolicyAction.BLOCK
        assert "block-l2-pi" in decision.matched_policies

    def test_l2_jailbreak_virtual_rule_matches_policy(self, tmp_path: Path):
        """L2 jailbreak virtual rule (l2-jailbreak) matches policy."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: flag-l2-jb
                customer_id: cust_test
                name: Flag L2 Jailbreak
                description: Flag ML-detected jailbreak attempts
                conditions:
                  - rule_ids: ["l2-jailbreak"]
                action: FLAG
                priority: 50
        """))

        l2_detection = Detection(
            rule_id="l2-jailbreak",
            rule_version="0.0.1",
            severity=Severity.HIGH,
            confidence=0.88,
            matches=[Match(
                pattern_index=0,
                start=0,
                end=0,
                matched_text="[L2 ML Detection]",
                groups=(),
                context_before="",
                context_after="",
            )],
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        use_case = ApplyPolicyUseCase()
        decision = use_case.apply_to_detection(
            l2_detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        assert decision.should_flag is True
        assert decision.action == PolicyAction.FLAG
        assert "flag-l2-jb" in decision.matched_policies

    def test_wildcard_matches_l2_virtual_rules(self, tmp_path: Path):
        """Policy with wildcard pattern matches L2 virtual rules."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: block-all-l2
                customer_id: cust_test
                name: Block All L2 Detections
                description: Block any ML detection
                conditions:
                  - rule_ids: ["l2-prompt-injection", "l2-jailbreak", "l2-pii"]
                action: BLOCK
                priority: 100
        """))

        use_case = ApplyPolicyUseCase()

        # Test multiple L2 virtual rule IDs
        for rule_id in ["l2-prompt-injection", "l2-jailbreak", "l2-pii"]:
            detection = Detection(
                rule_id=rule_id,
                rule_version="0.0.1",
                severity=Severity.HIGH,
                confidence=0.90,
                matches=[Match(
                    pattern_index=0,
                    start=0,
                    end=0,
                    matched_text="[L2 ML Detection]",
                    groups=(),
                    context_before="",
                    context_after="",
                )],
                detected_at=datetime.now(timezone.utc).isoformat(),
            )

            decision = use_case.apply_to_detection(
                detection,
                policy_source=PolicySource.LOCAL_FILE,
                policy_file=policy_file,
            )

            assert decision.should_block is True, f"Failed for {rule_id}"
            assert decision.action == PolicyAction.BLOCK

    def test_policy_max_count_limit_enforced(self, tmp_path: Path):
        """Cannot load more than 100 policies (security limit)."""
        # Create policy file with 101 policies
        policies_yaml = "version: 1.0.0\npolicies:\n"
        for i in range(101):
            policies_yaml += dedent(f"""
              - id: policy-{i:03d}
                customer_id: cust_test
                name: Policy {i}
                description: Test policy {i}
                conditions:
                  - severity: high
                action: BLOCK
                priority: {i}
            """)

        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(policies_yaml)

        use_case = ApplyPolicyUseCase()
        detection = make_detection()

        # Should raise error when trying to load too many policies
        # Infrastructure wraps domain ValueError in PolicyLoadError
        from raxe.infrastructure.policies.yaml_loader import PolicyLoadError
        with pytest.raises(PolicyLoadError, match="exceeds maximum"):
            use_case.apply_to_detection(
                detection,
                policy_source=PolicySource.LOCAL_FILE,
                policy_file=policy_file,
            )

    def test_policy_priority_cap_enforced(self, tmp_path: Path):
        """Policy priority cannot exceed 1000 (security limit)."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: invalid-priority
                customer_id: cust_test
                name: Invalid Priority
                description: Priority too high
                conditions:
                  - severity: high
                action: BLOCK
                priority: 9999
        """))

        use_case = ApplyPolicyUseCase()
        detection = make_detection()

        # Should raise error for priority > 1000
        # Infrastructure wraps domain ValueError in PolicyLoadError
        from raxe.infrastructure.policies.yaml_loader import PolicyLoadError
        with pytest.raises(PolicyLoadError, match="priority cannot exceed 1000"):
            use_case.apply_to_detection(
                detection,
                policy_source=PolicySource.LOCAL_FILE,
                policy_file=policy_file,
            )

    def test_allow_action_works_correctly(self, tmp_path: Path):
        """ALLOW action allows threat through despite detection."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: allow-known-fp
                customer_id: cust_test
                name: Allow Known False Positive
                description: Allow specific rule false positives
                conditions:
                  - rule_ids: ["pi-001"]
                action: ALLOW
                priority: 100
        """))

        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.HIGH)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        assert decision.should_allow is True
        assert decision.action == PolicyAction.ALLOW
        assert not decision.should_block

    def test_flag_action_allows_but_flags(self, tmp_path: Path):
        """FLAG action allows request but marks for review."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: flag-medium
                customer_id: cust_test
                name: Flag Medium Threats
                description: Flag medium severity for review
                conditions:
                  - severity: medium
                action: FLAG
                priority: 50
        """))

        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.MEDIUM)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        assert decision.should_flag is True
        assert decision.action == PolicyAction.FLAG
        assert not decision.should_block
        assert not decision.should_allow

    def test_block_action_blocks_request(self, tmp_path: Path):
        """BLOCK action blocks the request."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: block-high
                customer_id: cust_test
                name: Block High Threats
                description: Block all high severity
                conditions:
                  - severity: high
                action: BLOCK
                priority: 100
        """))

        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.HIGH)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        assert decision.should_block is True
        assert decision.action == PolicyAction.BLOCK
        assert not decision.should_allow
        assert not decision.should_flag

    def test_disabled_policy_not_applied(self, tmp_path: Path):
        """Disabled policies are not evaluated."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: disabled-policy
                customer_id: cust_test
                name: Disabled Policy
                description: This policy is disabled
                conditions:
                  - severity: high
                action: BLOCK
                priority: 100
                enabled: false
        """))

        use_case = ApplyPolicyUseCase()
        detection = make_detection(severity=Severity.HIGH)

        decision = use_case.apply_to_detection(
            detection,
            policy_source=PolicySource.LOCAL_FILE,
            policy_file=policy_file,
        )

        # Should use default action since policy is disabled
        assert decision.action == PolicyAction.LOG
        assert len(decision.matched_policies) == 0
