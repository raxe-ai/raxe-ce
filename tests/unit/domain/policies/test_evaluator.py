"""Tests for policy evaluation logic.

Tests pure domain logic - no I/O, fast execution.
Target: >95% coverage for domain layer.
"""

from datetime import datetime, timezone

from raxe.domain.engine.executor import Detection
from raxe.domain.engine.matcher import Match
from raxe.domain.policies.evaluator import (
    evaluate_policies,
    evaluate_policies_batch,
    filter_policies_by_customer,
)
from raxe.domain.policies.models import (
    Policy,
    PolicyAction,
    PolicyCondition,
)
from raxe.domain.rules.models import Severity


def make_detection(
    rule_id: str = "test-001",
    severity: Severity = Severity.HIGH,
    confidence: float = 0.9,
) -> Detection:
    """Helper to create test detection."""
    return Detection(
        rule_id=rule_id,
        rule_version="1.0.0",
        severity=severity,
        confidence=confidence,
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


def make_policy(
    policy_id: str = "test-policy",
    customer_id: str = "cust_test",
    action: PolicyAction = PolicyAction.BLOCK,
    conditions: list[PolicyCondition] | None = None,
    priority: int = 0,
    override_severity: Severity | None = None,
    webhooks: list[str] | None = None,
    enabled: bool = True,
) -> Policy:
    """Helper to create test policy."""
    if conditions is None:
        conditions = [PolicyCondition()]

    return Policy(
        policy_id=policy_id,
        customer_id=customer_id,
        name=f"Test Policy {policy_id}",
        description="Test policy",
        conditions=conditions,
        action=action,
        priority=priority,
        override_severity=override_severity,
        enabled=enabled,
    )


class TestEvaluatePolicies:
    """Test evaluate_policies function."""

    def test_no_policies_returns_default(self):
        """No policies returns default LOG decision."""
        detection = make_detection()
        decision = evaluate_policies(detection, [])

        assert decision.action == PolicyAction.LOG
        assert decision.original_severity == Severity.HIGH
        assert decision.final_severity == Severity.HIGH
        assert len(decision.matched_policies) == 0
        assert decision.severity_changed is False

    def test_no_matching_policies_returns_default(self):
        """Non-matching policies return default decision."""
        detection = make_detection(rule_id="pi-001", severity=Severity.LOW)

        # Policy only matches HIGH severity
        policy = make_policy(
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
        )

        decision = evaluate_policies(detection, [policy])

        assert decision.action == PolicyAction.LOG
        assert len(decision.matched_policies) == 0

    def test_single_matching_policy(self):
        """Single matching policy determines action."""
        detection = make_detection(severity=Severity.CRITICAL)
        policy = make_policy(
            policy_id="block-critical",
            action=PolicyAction.BLOCK,
            conditions=[PolicyCondition(severity_threshold=Severity.CRITICAL)],
        )

        decision = evaluate_policies(detection, [policy])

        assert decision.action == PolicyAction.BLOCK
        assert decision.matched_policies == ["block-critical"]

    def test_multiple_matching_policies_priority_order(self):
        """Highest priority policy wins."""
        detection = make_detection(severity=Severity.HIGH)

        # Lower priority - ALLOW
        policy1 = make_policy(
            policy_id="allow-high",
            action=PolicyAction.ALLOW,
            priority=10,
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
        )

        # Higher priority - BLOCK
        policy2 = make_policy(
            policy_id="block-high",
            action=PolicyAction.BLOCK,
            priority=100,
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
        )

        decision = evaluate_policies(detection, [policy1, policy2])

        # Highest priority wins
        assert decision.action == PolicyAction.BLOCK
        assert decision.matched_policies == ["block-high", "allow-high"]

    def test_severity_override(self):
        """Policy can override severity."""
        detection = make_detection(severity=Severity.MEDIUM)
        policy = make_policy(
            action=PolicyAction.FLAG,
            override_severity=Severity.CRITICAL,
            conditions=[PolicyCondition(severity_threshold=Severity.MEDIUM)],
        )

        decision = evaluate_policies(detection, [policy])

        assert decision.original_severity == Severity.MEDIUM
        assert decision.final_severity == Severity.CRITICAL
        assert decision.severity_changed is True

    def test_no_severity_override(self):
        """Policy without override keeps original severity."""
        detection = make_detection(severity=Severity.HIGH)
        policy = make_policy(
            action=PolicyAction.BLOCK,
            override_severity=None,
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
        )

        decision = evaluate_policies(detection, [policy])

        assert decision.original_severity == Severity.HIGH
        assert decision.final_severity == Severity.HIGH
        assert decision.severity_changed is False

    def test_disabled_policy_ignored(self):
        """Disabled policies are not evaluated."""
        detection = make_detection(severity=Severity.CRITICAL)

        policy = make_policy(
            action=PolicyAction.BLOCK,
            enabled=False,
            conditions=[PolicyCondition(severity_threshold=Severity.CRITICAL)],
        )

        decision = evaluate_policies(detection, [policy])

        # Policy disabled, so default LOG action
        assert decision.action == PolicyAction.LOG
        assert len(decision.matched_policies) == 0


class TestPolicyConditionMatching:
    """Test policy condition matching logic."""

    def test_severity_threshold_matching(self):
        """Severity threshold matches correctly."""
        # CRITICAL threshold matches CRITICAL
        detection = make_detection(severity=Severity.CRITICAL)
        policy = make_policy(
            conditions=[PolicyCondition(severity_threshold=Severity.CRITICAL)],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) > 0

        # HIGH threshold matches CRITICAL (more severe)
        detection = make_detection(severity=Severity.CRITICAL)
        policy = make_policy(
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) > 0

        # CRITICAL threshold does NOT match HIGH (less severe)
        detection = make_detection(severity=Severity.HIGH)
        policy = make_policy(
            conditions=[PolicyCondition(severity_threshold=Severity.CRITICAL)],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) == 0

    def test_rule_id_matching(self):
        """Rule ID condition matches correctly."""
        # Match
        detection = make_detection(rule_id="pi-001")
        policy = make_policy(
            conditions=[PolicyCondition(rule_ids=["pi-001", "pi-002"])],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) > 0

        # No match
        detection = make_detection(rule_id="jb-001")
        policy = make_policy(
            conditions=[PolicyCondition(rule_ids=["pi-001", "pi-002"])],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) == 0

    def test_confidence_range_matching(self):
        """Confidence range matching works correctly."""
        # Within range
        detection = make_detection(confidence=0.8)
        policy = make_policy(
            conditions=[PolicyCondition(min_confidence=0.7, max_confidence=0.9)],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) > 0

        # Below min
        detection = make_detection(confidence=0.5)
        policy = make_policy(
            conditions=[PolicyCondition(min_confidence=0.7)],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) == 0

        # Above max
        detection = make_detection(confidence=0.95)
        policy = make_policy(
            conditions=[PolicyCondition(max_confidence=0.9)],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) == 0

    def test_multiple_conditions_and_logic(self):
        """Multiple conditions in same PolicyCondition use AND logic."""
        detection = make_detection(
            rule_id="pi-001",
            severity=Severity.HIGH,
            confidence=0.8,
        )

        # All conditions match
        policy = make_policy(
            conditions=[
                PolicyCondition(
                    rule_ids=["pi-001"],
                    severity_threshold=Severity.HIGH,
                    min_confidence=0.7,
                )
            ],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) > 0

        # One condition doesn't match (wrong rule ID)
        policy = make_policy(
            conditions=[
                PolicyCondition(
                    rule_ids=["jb-001"],
                    severity_threshold=Severity.HIGH,
                    min_confidence=0.7,
                )
            ],
        )
        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) == 0

    def test_multiple_policy_conditions_or_logic(self):
        """Multiple PolicyConditions in policy use OR logic."""
        detection = make_detection(
            rule_id="pi-001",
            severity=Severity.MEDIUM,
        )

        policy = make_policy(
            conditions=[
                PolicyCondition(rule_ids=["jb-001"]),  # Doesn't match
                PolicyCondition(severity_threshold=Severity.MEDIUM),  # Matches
            ],
        )

        decision = evaluate_policies(detection, [policy])
        assert len(decision.matched_policies) > 0


class TestEvaluatePoliciesBatch:
    """Test batch policy evaluation."""

    def test_batch_evaluation(self):
        """Batch evaluation returns dict of decisions."""
        detections = [
            make_detection(rule_id="pi-001", severity=Severity.HIGH),
            make_detection(rule_id="jb-001", severity=Severity.CRITICAL),
        ]

        policy = make_policy(
            action=PolicyAction.BLOCK,
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
        )

        results = evaluate_policies_batch(detections, [policy])

        assert len(results) == 2
        assert "pi-001@1.0.0" in results
        assert "jb-001@1.0.0" in results

        # Both should match policy
        assert results["pi-001@1.0.0"].action == PolicyAction.BLOCK
        assert results["jb-001@1.0.0"].action == PolicyAction.BLOCK

    def test_empty_batch(self):
        """Empty detection list returns empty dict."""
        results = evaluate_policies_batch([], [make_policy()])
        assert len(results) == 0


class TestFilterPoliciesByCustomer:
    """Test customer filtering helper."""

    def test_filter_by_customer(self):
        """Only customer's policies returned."""
        policies = [
            make_policy(policy_id="p1", customer_id="cust_abc"),
            make_policy(policy_id="p2", customer_id="cust_xyz"),
            make_policy(policy_id="p3", customer_id="cust_abc"),
        ]

        filtered = filter_policies_by_customer(policies, "cust_abc")

        assert len(filtered) == 2
        assert {p.policy_id for p in filtered} == {"p1", "p3"}

    def test_no_matching_customer(self):
        """No policies for customer returns empty list."""
        policies = [
            make_policy(policy_id="p1", customer_id="cust_abc"),
        ]

        filtered = filter_policies_by_customer(policies, "cust_other")

        assert len(filtered) == 0


class TestPolicyDecisionProperties:
    """Test PolicyDecision properties through evaluation."""

    def test_decision_properties(self):
        """All decision properties work correctly."""
        detection = make_detection(severity=Severity.MEDIUM)

        policy = make_policy(
            policy_id="test-policy",
            action=PolicyAction.FLAG,
            override_severity=Severity.HIGH,
            conditions=[PolicyCondition()],
        )

        decision = evaluate_policies(detection, [policy])

        assert decision.should_flag is True
        assert decision.should_block is False
        assert decision.should_allow is False
        assert decision.severity_changed is True
        assert decision.matched_policies == ["test-policy"]
