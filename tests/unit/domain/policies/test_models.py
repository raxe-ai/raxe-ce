"""Tests for policy domain models.

Tests all value objects and their validation rules.
Target: >95% coverage for domain layer.
"""
import pytest

from raxe.domain.policies.models import (
    Policy,
    PolicyAction,
    PolicyCondition,
    PolicyDecision,
)
from raxe.domain.rules.models import Severity


class TestPolicyAction:
    """Test PolicyAction enum."""

    def test_action_values(self):
        """All actions have expected values."""
        assert PolicyAction.ALLOW.value == "ALLOW"
        assert PolicyAction.BLOCK.value == "BLOCK"
        assert PolicyAction.FLAG.value == "FLAG"
        assert PolicyAction.LOG.value == "LOG"

    def test_action_members(self):
        """All expected actions exist."""
        actions = {a.name for a in PolicyAction}
        assert actions == {"ALLOW", "BLOCK", "FLAG", "LOG"}


class TestPolicyCondition:
    """Test PolicyCondition value object."""

    def test_default_condition(self):
        """Default condition with all None values."""
        condition = PolicyCondition()
        assert condition.rule_ids is None
        assert condition.severity_threshold is None
        assert condition.threat_types is None
        assert condition.min_confidence is None
        assert condition.max_confidence is None
        assert condition.custom_filter is None

    def test_condition_with_values(self):
        """Condition with all fields specified."""
        condition = PolicyCondition(
            rule_ids=["pi-001", "pi-002"],
            severity_threshold=Severity.HIGH,
            threat_types=["PROMPT_INJECTION"],
            min_confidence=0.7,
            max_confidence=1.0,
            custom_filter="$.pattern",
        )
        assert condition.rule_ids == ["pi-001", "pi-002"]
        assert condition.severity_threshold == Severity.HIGH
        assert condition.threat_types == ["PROMPT_INJECTION"]
        assert condition.min_confidence == 0.7
        assert condition.max_confidence == 1.0
        assert condition.custom_filter == "$.pattern"

    def test_confidence_validation(self):
        """Confidence values must be 0-1."""
        # Valid
        PolicyCondition(min_confidence=0.0)
        PolicyCondition(min_confidence=1.0)
        PolicyCondition(max_confidence=0.5)

        # Invalid min
        with pytest.raises(ValueError, match="min_confidence must be 0-1"):
            PolicyCondition(min_confidence=-0.1)

        with pytest.raises(ValueError, match="min_confidence must be 0-1"):
            PolicyCondition(min_confidence=1.1)

        # Invalid max
        with pytest.raises(ValueError, match="max_confidence must be 0-1"):
            PolicyCondition(max_confidence=-0.1)

        with pytest.raises(ValueError, match="max_confidence must be 0-1"):
            PolicyCondition(max_confidence=1.5)

    def test_confidence_range_validation(self):
        """Min confidence cannot exceed max confidence."""
        # Valid ranges
        PolicyCondition(min_confidence=0.5, max_confidence=0.8)
        PolicyCondition(min_confidence=0.5, max_confidence=0.5)  # Equal is OK

        # Invalid range
        with pytest.raises(ValueError, match="cannot be greater than"):
            PolicyCondition(min_confidence=0.8, max_confidence=0.5)

    def test_empty_list_validation(self):
        """Empty lists not allowed (use None instead)."""
        with pytest.raises(ValueError, match="cannot be empty list"):
            PolicyCondition(rule_ids=[])

        with pytest.raises(ValueError, match="cannot be empty list"):
            PolicyCondition(threat_types=[])

    def test_immutable(self):
        """PolicyCondition is immutable (frozen)."""
        condition = PolicyCondition(min_confidence=0.7)
        with pytest.raises(Exception):  # FrozenInstanceError
            condition.min_confidence = 0.8  # type: ignore


class TestPolicy:
    """Test Policy value object."""

    def test_minimal_policy(self):
        """Policy with minimal required fields."""
        policy = Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test Policy",
            description="Test description",
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
            action=PolicyAction.BLOCK,
        )
        assert policy.policy_id == "test-001"
        assert policy.customer_id == "cust_abc123"
        assert policy.name == "Test Policy"
        assert policy.action == PolicyAction.BLOCK
        assert policy.priority == 0
        assert policy.enabled is True
        assert policy.override_severity is None

    def test_full_policy(self):
        """Policy with all fields specified."""
        policy = Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test Policy",
            description="Test description",
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
            action=PolicyAction.BLOCK,
            override_severity=Severity.CRITICAL,
            priority=100,
            enabled=False,
            metadata={"created_by": "admin"},
        )
        assert policy.override_severity == Severity.CRITICAL
        assert policy.priority == 100
        assert policy.enabled is False
        assert policy.metadata == {"created_by": "admin"}

    def test_required_fields(self):
        """Policy requires certain fields."""
        # Missing policy_id
        with pytest.raises(TypeError):
            Policy(  # type: ignore
                customer_id="cust_abc123",
                name="Test",
                description="Test",
                conditions=[PolicyCondition()],
                action=PolicyAction.BLOCK,
            )

        # Empty policy_id
        with pytest.raises(ValueError, match="policy_id cannot be empty"):
            Policy(
                policy_id="",
                customer_id="cust_abc123",
                name="Test",
                description="Test",
                conditions=[PolicyCondition()],
                action=PolicyAction.BLOCK,
            )

    def test_conditions_required(self):
        """Policy must have at least one condition."""
        with pytest.raises(ValueError, match="at least one condition"):
            Policy(
                policy_id="test-001",
                customer_id="cust_abc123",
                name="Test",
                description="Test",
                conditions=[],
                action=PolicyAction.BLOCK,
            )

    def test_priority_validation(self):
        """Priority must be non-negative."""
        # Valid
        Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test",
            description="Test",
            conditions=[PolicyCondition()],
            action=PolicyAction.BLOCK,
            priority=0,
        )

        # Invalid
        with pytest.raises(ValueError, match="priority must be non-negative"):
            Policy(
                policy_id="test-001",
                customer_id="cust_abc123",
                name="Test",
                description="Test",
                conditions=[PolicyCondition()],
                action=PolicyAction.BLOCK,
                priority=-1,
            )


    def test_immutable(self):
        """Policy is immutable (frozen)."""
        policy = Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test",
            description="Test",
            conditions=[PolicyCondition()],
            action=PolicyAction.BLOCK,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            policy.priority = 100  # type: ignore


class TestPolicyDecision:
    """Test PolicyDecision value object."""

    def test_minimal_decision(self):
        """Decision with minimal fields."""
        decision = PolicyDecision(
            action=PolicyAction.ALLOW,
            original_severity=Severity.HIGH,
            final_severity=Severity.HIGH,
        )
        assert decision.action == PolicyAction.ALLOW
        assert decision.original_severity == Severity.HIGH
        assert decision.final_severity == Severity.HIGH
        assert len(decision.matched_policies) == 0
        assert len(decision.metadata) == 0

    def test_full_decision(self):
        """Decision with all fields."""
        decision = PolicyDecision(
            action=PolicyAction.BLOCK,
            original_severity=Severity.MEDIUM,
            final_severity=Severity.CRITICAL,
            matched_policies=["policy-001", "policy-002"],
            metadata={"reason": "test"},
        )
        assert decision.matched_policies == ["policy-001", "policy-002"]
        assert decision.metadata == {"reason": "test"}

    def test_should_block(self):
        """should_block property."""
        assert PolicyDecision(
            action=PolicyAction.BLOCK,
            original_severity=Severity.HIGH,
            final_severity=Severity.HIGH,
        ).should_block is True

        assert PolicyDecision(
            action=PolicyAction.ALLOW,
            original_severity=Severity.HIGH,
            final_severity=Severity.HIGH,
        ).should_block is False

    def test_should_allow(self):
        """should_allow property."""
        assert PolicyDecision(
            action=PolicyAction.ALLOW,
            original_severity=Severity.HIGH,
            final_severity=Severity.HIGH,
        ).should_allow is True

        assert PolicyDecision(
            action=PolicyAction.BLOCK,
            original_severity=Severity.HIGH,
            final_severity=Severity.HIGH,
        ).should_allow is False

    def test_should_flag(self):
        """should_flag property."""
        assert PolicyDecision(
            action=PolicyAction.FLAG,
            original_severity=Severity.HIGH,
            final_severity=Severity.HIGH,
        ).should_flag is True

        assert PolicyDecision(
            action=PolicyAction.ALLOW,
            original_severity=Severity.HIGH,
            final_severity=Severity.HIGH,
        ).should_flag is False

    def test_severity_changed(self):
        """severity_changed property."""
        # Changed
        assert PolicyDecision(
            action=PolicyAction.BLOCK,
            original_severity=Severity.MEDIUM,
            final_severity=Severity.CRITICAL,
        ).severity_changed is True

        # Not changed
        assert PolicyDecision(
            action=PolicyAction.BLOCK,
            original_severity=Severity.HIGH,
            final_severity=Severity.HIGH,
        ).severity_changed is False


    def test_to_dict(self):
        """to_dict serialization."""
        decision = PolicyDecision(
            action=PolicyAction.BLOCK,
            original_severity=Severity.MEDIUM,
            final_severity=Severity.CRITICAL,
            matched_policies=["policy-001"],
            metadata={"reason": "test"},
        )
        data = decision.to_dict()

        assert data["action"] == "BLOCK"
        assert data["original_severity"] == "medium"
        assert data["final_severity"] == "critical"
        assert data["severity_changed"] is True
        assert data["should_block"] is True
        assert data["should_allow"] is False
        assert data["should_flag"] is False
        assert data["matched_policies"] == ["policy-001"]
        assert data["metadata"] == {"reason": "test"}
