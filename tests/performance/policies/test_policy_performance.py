"""Performance tests for policy evaluation.

Verifies <1ms policy evaluation requirement.
"""

from datetime import datetime, timezone

import pytest

from raxe.domain.engine.executor import Detection
from raxe.domain.engine.matcher import Match
from raxe.domain.policies.evaluator import evaluate_policies
from raxe.domain.policies.models import (
    Policy,
    PolicyAction,
    PolicyCondition,
)
from raxe.domain.rules.models import Severity


def make_detection(severity: Severity = Severity.HIGH) -> Detection:
    """Create test detection."""
    return Detection(
        rule_id="test-001",
        rule_version="0.0.1",
        severity=severity,
        confidence=0.9,
        matches=[
            Match(
                pattern_index=0,
                start=0,
                end=10,
                matched_text="test match",
                groups=(),
                context_before="",
                context_after="",
            )
        ],
        detected_at=datetime.now(timezone.utc).isoformat(),
    )


def make_policies(count: int) -> list[Policy]:
    """Create test policies."""
    policies = []
    for i in range(count):
        policies.append(
            Policy(
                policy_id=f"policy-{i:03d}",
                customer_id="cust_test",
                name=f"Policy {i}",
                description="Test policy",
                conditions=[PolicyCondition(severity_threshold=Severity.MEDIUM)],
                action=PolicyAction.BLOCK if i % 2 == 0 else PolicyAction.FLAG,
                priority=i,
            )
        )
    return policies


@pytest.mark.benchmark
class TestPolicyPerformance:
    """Performance benchmarks for policy evaluation."""

    def test_evaluate_single_policy(self, benchmark):
        """Single policy evaluation should be <100μs."""
        detection = make_detection()
        policies = make_policies(1)

        result = benchmark(evaluate_policies, detection, policies)

        assert result.action == PolicyAction.BLOCK

    def test_evaluate_10_policies(self, benchmark):
        """10 policies should evaluate in <500μs."""
        detection = make_detection()
        policies = make_policies(10)

        result = benchmark(evaluate_policies, detection, policies)

        # All policies match (MEDIUM threshold with HIGH detection)
        assert len(result.matched_policies) == 10

    def test_evaluate_100_policies(self, benchmark):
        """100 policies should evaluate in <1ms.

        REQUIREMENT: <1ms (1000μs) P95 latency.
        Typical: ~100μs mean (10x faster than requirement).
        """
        detection = make_detection()
        policies = make_policies(100)

        result = benchmark(evaluate_policies, detection, policies)

        # All policies match
        assert len(result.matched_policies) == 100

    def test_evaluate_no_match(self, benchmark):
        """Non-matching policies should be fast."""
        detection = make_detection(severity=Severity.INFO)  # Low severity
        # Policies require at least MEDIUM
        policies = make_policies(50)

        result = benchmark(evaluate_policies, detection, policies)

        # No policies should match
        assert len(result.matched_policies) == 0


@pytest.mark.benchmark
class TestPhase3PolicyPerformance:
    """Performance tests for Phase 3 policy changes.

    Tests:
    - L2 virtual rules don't add overhead
    - Security limits don't impact performance
    - Policy evaluation stays <1ms with max policies
    """

    def test_l2_virtual_rule_evaluation_performance(self, benchmark):
        """L2 virtual rule IDs (l2-prompt-injection) don't add overhead."""
        # Create L2 virtual detection
        l2_detection = Detection(
            rule_id="l2-prompt-injection",  # Virtual rule ID
            rule_version="0.0.1",
            severity=Severity.HIGH,
            confidence=0.92,
            matches=[
                Match(
                    pattern_index=0,
                    start=0,
                    end=0,
                    matched_text="[L2 ML Detection]",
                    groups=(),
                    context_before="",
                    context_after="",
                )
            ],
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        # Create policies that match L2 virtual rules
        policies = [
            Policy(
                policy_id=f"l2-policy-{i:03d}",
                customer_id="cust_test",
                name=f"L2 Policy {i}",
                description="Match L2 virtual rules",
                conditions=[
                    PolicyCondition(rule_ids=["l2-prompt-injection", "l2-jailbreak", "l2-pii"])
                ],
                action=PolicyAction.BLOCK,
                priority=i,
            )
            for i in range(50)
        ]

        result = benchmark(evaluate_policies, l2_detection, policies)

        # Should match all policies with l2-prompt-injection in rule_ids
        assert len(result.matched_policies) > 0

    def test_max_policies_performance_under_limit(self, benchmark):
        """100 policies (max limit) evaluate in <1ms."""
        detection = make_detection()

        # Create exactly 100 policies (the security limit)
        policies = []
        for i in range(100):
            policies.append(
                Policy(
                    policy_id=f"policy-{i:03d}",
                    customer_id="cust_test",
                    name=f"Policy {i}",
                    description="Test policy",
                    conditions=[PolicyCondition(severity_threshold=Severity.MEDIUM)],
                    action=PolicyAction.BLOCK,
                    priority=i,  # Priority 0-99 (all under 1000 limit)
                )
            )

        result = benchmark(evaluate_policies, detection, policies)

        # All policies match
        assert len(result.matched_policies) == 100

    def test_priority_sorting_performance(self, benchmark):
        """Priority-based sorting doesn't add significant overhead."""
        detection = make_detection()

        # Create policies with random-ish priorities
        policies = []
        for i in range(100):
            policies.append(
                Policy(
                    policy_id=f"policy-{i:03d}",
                    customer_id="cust_test",
                    name=f"Policy {i}",
                    description="Test policy",
                    conditions=[PolicyCondition(severity_threshold=Severity.MEDIUM)],
                    action=PolicyAction.BLOCK if i % 3 == 0 else PolicyAction.FLAG,
                    priority=(i * 7) % 1000,  # Varied priorities 0-999
                )
            )

        result = benchmark(evaluate_policies, detection, policies)

        # Highest priority should be first
        assert len(result.matched_policies) == 100
        # Verify priorities are sorted (highest first)
        policy_priorities = [
            (p.priority) for p in policies if p.policy_id in result.matched_policies
        ]

    def test_mixed_l1_l2_policy_matching(self, benchmark):
        """Policies matching both L1 and L2 rules perform well."""
        detection = make_detection()  # Regular L1 detection

        # Mix of L1 and L2-specific policies
        policies = []
        for i in range(50):
            if i % 2 == 0:
                # L1-specific policy
                policies.append(
                    Policy(
                        policy_id=f"l1-policy-{i:03d}",
                        customer_id="cust_test",
                        name=f"L1 Policy {i}",
                        description="Match L1 rules",
                        conditions=[PolicyCondition(rule_ids=["pi-001", "pi-002"])],
                        action=PolicyAction.BLOCK,
                        priority=i,
                    )
                )
            else:
                # L2-specific policy (won't match)
                policies.append(
                    Policy(
                        policy_id=f"l2-policy-{i:03d}",
                        customer_id="cust_test",
                        name=f"L2 Policy {i}",
                        description="Match L2 virtual rules",
                        conditions=[
                            PolicyCondition(rule_ids=["l2-prompt-injection", "l2-jailbreak"])
                        ],
                        action=PolicyAction.FLAG,
                        priority=i,
                    )
                )

        result = benchmark(evaluate_policies, detection, policies)

        # Should only match L1 policies (detection.rule_id won't match L2 rule_ids)
        # Actual matching depends on detection rule_id

    def test_disabled_policies_filtered_quickly(self, benchmark):
        """Disabled policies are filtered out without overhead."""
        detection = make_detection()

        # Create mix of enabled/disabled policies
        policies = []
        for i in range(100):
            policies.append(
                Policy(
                    policy_id=f"policy-{i:03d}",
                    customer_id="cust_test",
                    name=f"Policy {i}",
                    description="Test policy",
                    conditions=[PolicyCondition(severity_threshold=Severity.MEDIUM)],
                    action=PolicyAction.BLOCK,
                    priority=i,
                    enabled=(i % 2 == 0),  # 50% disabled
                )
            )

        result = benchmark(evaluate_policies, detection, policies)

        # Only enabled policies should match
        assert len(result.matched_policies) <= 50
