"""Tests for policy security limits and validation.

Tests the security boundaries added in Phase 3:
- Priority cap (0-1000)
- Policy count limit (max 100)
- PolicySet validation

Target: >95% coverage for domain layer.
"""
import pytest

from raxe.domain.policies.models import (
    Policy,
    PolicyAction,
    PolicyCondition,
    PolicySet,
)
from raxe.domain.rules.models import Severity


class TestPolicyPriorityLimits:
    """Test priority value constraints."""

    def test_priority_minimum_valid(self):
        """Priority can be 0 (minimum)."""
        policy = Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test Policy",
            description="Test description",
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
            action=PolicyAction.BLOCK,
            priority=0,
        )
        assert policy.priority == 0

    def test_priority_maximum_valid(self):
        """Priority can be 1000 (maximum)."""
        policy = Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test Policy",
            description="Test description",
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
            action=PolicyAction.BLOCK,
            priority=1000,
        )
        assert policy.priority == 1000

    def test_priority_negative_invalid(self):
        """Priority cannot be negative."""
        with pytest.raises(ValueError, match="priority must be non-negative"):
            Policy(
                policy_id="test-001",
                customer_id="cust_abc123",
                name="Test Policy",
                description="Test description",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
                priority=-1,
            )

    def test_priority_exceeds_maximum_invalid(self):
        """Priority cannot exceed 1000 (security limit)."""
        with pytest.raises(ValueError, match="priority cannot exceed 1000"):
            Policy(
                policy_id="test-001",
                customer_id="cust_abc123",
                name="Test Policy",
                description="Test description",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
                priority=1001,
            )

    def test_priority_high_value_invalid(self):
        """Priority cannot be arbitrarily high (prevents resource exhaustion)."""
        with pytest.raises(ValueError, match="priority cannot exceed 1000"):
            Policy(
                policy_id="test-001",
                customer_id="cust_abc123",
                name="Test Policy",
                description="Test description",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
                priority=999999,
            )

    def test_priority_mid_range_valid(self):
        """Priority in mid-range is valid."""
        policy = Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test Policy",
            description="Test description",
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
            action=PolicyAction.BLOCK,
            priority=500,
        )
        assert policy.priority == 500


class TestPolicySetLimits:
    """Test PolicySet count limits."""

    def test_empty_policy_set(self):
        """PolicySet can be empty."""
        policy_set = PolicySet(policies=[])
        assert policy_set.policy_count == 0
        assert len(policy_set.enabled_policies) == 0

    def test_single_policy(self):
        """PolicySet with single policy."""
        policy = Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test Policy",
            description="Test description",
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
            action=PolicyAction.BLOCK,
        )
        policy_set = PolicySet(policies=[policy])
        assert policy_set.policy_count == 1
        assert len(policy_set.enabled_policies) == 1

    def test_maximum_policies_valid(self):
        """PolicySet can have exactly 100 policies (default max)."""
        policies = [
            Policy(
                policy_id=f"test-{i:03d}",
                customer_id="cust_abc123",
                name=f"Test Policy {i}",
                description=f"Test description {i}",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
            )
            for i in range(100)
        ]
        policy_set = PolicySet(policies=policies)
        assert policy_set.policy_count == 100

    def test_exceeds_maximum_policies_invalid(self):
        """PolicySet cannot have more than 100 policies (security limit)."""
        policies = [
            Policy(
                policy_id=f"test-{i:03d}",
                customer_id="cust_abc123",
                name=f"Test Policy {i}",
                description=f"Test description {i}",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
            )
            for i in range(101)
        ]

        with pytest.raises(ValueError, match="Policy count.*exceeds maximum"):
            PolicySet(policies=policies)

    def test_exceeds_maximum_policies_error_message(self):
        """Error message includes security context for limit."""
        policies = [
            Policy(
                policy_id=f"test-{i:03d}",
                customer_id="cust_abc123",
                name=f"Test Policy {i}",
                description=f"Test description {i}",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
            )
            for i in range(150)
        ]

        with pytest.raises(ValueError, match="resource exhaustion"):
            PolicySet(policies=policies)

    def test_custom_maximum_limit(self):
        """PolicySet can have custom max_policies limit."""
        policies = [
            Policy(
                policy_id=f"test-{i:03d}",
                customer_id="cust_abc123",
                name=f"Test Policy {i}",
                description=f"Test description {i}",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
            )
            for i in range(50)
        ]

        # Custom limit of 50 - should pass
        policy_set = PolicySet(policies=policies, max_policies=50)
        assert policy_set.policy_count == 50
        assert policy_set.max_policies == 50

    def test_exceeds_custom_maximum_limit(self):
        """PolicySet respects custom max_policies limit."""
        policies = [
            Policy(
                policy_id=f"test-{i:03d}",
                customer_id="cust_abc123",
                name=f"Test Policy {i}",
                description=f"Test description {i}",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
            )
            for i in range(51)
        ]

        # Custom limit of 50 - should fail
        with pytest.raises(ValueError, match="exceeds maximum"):
            PolicySet(policies=policies, max_policies=50)

    def test_policy_set_enabled_policies_filter(self):
        """PolicySet.enabled_policies filters out disabled policies."""
        policies = [
            Policy(
                policy_id="test-001",
                customer_id="cust_abc123",
                name="Enabled Policy 1",
                description="Test",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
                enabled=True,
            ),
            Policy(
                policy_id="test-002",
                customer_id="cust_abc123",
                name="Disabled Policy",
                description="Test",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
                enabled=False,
            ),
            Policy(
                policy_id="test-003",
                customer_id="cust_abc123",
                name="Enabled Policy 2",
                description="Test",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
                enabled=True,
            ),
        ]

        policy_set = PolicySet(policies=policies)
        assert policy_set.policy_count == 3
        assert len(policy_set.enabled_policies) == 2

        # Verify only enabled policies returned
        enabled_ids = {p.policy_id for p in policy_set.enabled_policies}
        assert enabled_ids == {"test-001", "test-003"}

    def test_policy_set_all_disabled(self):
        """PolicySet with all disabled policies returns empty enabled list."""
        policies = [
            Policy(
                policy_id=f"test-{i:03d}",
                customer_id="cust_abc123",
                name=f"Disabled Policy {i}",
                description="Test",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
                enabled=False,
            )
            for i in range(5)
        ]

        policy_set = PolicySet(policies=policies)
        assert policy_set.policy_count == 5
        assert len(policy_set.enabled_policies) == 0


class TestPolicySetImmutability:
    """Test PolicySet immutability (frozen dataclass)."""

    def test_policy_set_is_frozen(self):
        """PolicySet is immutable (frozen)."""
        policy = Policy(
            policy_id="test-001",
            customer_id="cust_abc123",
            name="Test Policy",
            description="Test description",
            conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
            action=PolicyAction.BLOCK,
        )
        policy_set = PolicySet(policies=[policy])

        with pytest.raises(Exception):  # FrozenInstanceError
            policy_set.policies = []  # type: ignore

    def test_policy_set_property_access(self):
        """PolicySet properties are read-only."""
        policies = [
            Policy(
                policy_id=f"test-{i:03d}",
                customer_id="cust_abc123",
                name=f"Test Policy {i}",
                description="Test",
                conditions=[PolicyCondition(severity_threshold=Severity.HIGH)],
                action=PolicyAction.BLOCK,
            )
            for i in range(3)
        ]

        policy_set = PolicySet(policies=policies)

        # Properties work correctly
        assert policy_set.policy_count == 3
        assert len(policy_set.enabled_policies) == 3

        # But can't modify
        with pytest.raises(Exception):  # FrozenInstanceError
            policy_set.max_policies = 200  # type: ignore
