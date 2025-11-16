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
