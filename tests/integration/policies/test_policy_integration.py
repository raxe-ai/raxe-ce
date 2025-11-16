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
        rule_version="1.0.0",
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
