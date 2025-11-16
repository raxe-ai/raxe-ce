"""Tests for YAML policy loader.

Tests infrastructure layer - file I/O and parsing.
"""
from pathlib import Path
from textwrap import dedent

import pytest

from raxe.domain.policies.models import PolicyAction
from raxe.domain.rules.models import Severity
from raxe.infrastructure.policies.yaml_loader import (
    PolicyLoadError,
    YAMLPolicyLoader,
)


class TestYAMLPolicyLoader:
    """Test YAML policy loading."""

    def test_load_from_string_minimal(self):
        """Load minimal valid policy YAML."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_abc123
                name: Test Policy
                description: Test description
                conditions:
                  - severity: high
                action: BLOCK
        """)

        loader = YAMLPolicyLoader()
        policies = loader.load_from_string(yaml_content)

        assert len(policies) == 1
        policy = policies[0]
        assert policy.policy_id == "test-001"
        assert policy.customer_id == "cust_abc123"
        assert policy.name == "Test Policy"
        assert policy.action == PolicyAction.BLOCK
        assert len(policy.conditions) == 1
        assert policy.conditions[0].severity_threshold == Severity.HIGH

    def test_load_from_string_full(self):
        """Load policy with all optional fields."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_abc123
                name: Test Policy
                description: Full test policy
                priority: 100
                enabled: true
                conditions:
                  - severity: critical
                    rule_ids:
                      - pi-001
                      - pi-002
                    min_confidence: 0.7
                    max_confidence: 1.0
                action: BLOCK
                override_severity: critical
                notify_webhooks:
                  - https://example.com/webhook1
                  - https://example.com/webhook2
                metadata:
                  created_by: admin
                  environment: production
        """)

        loader = YAMLPolicyLoader()
        policies = loader.load_from_string(yaml_content)

        policy = policies[0]
        assert policy.priority == 100
        assert policy.enabled is True
        assert policy.override_severity == Severity.CRITICAL
        assert len(policy.notify_webhooks) == 2
        assert policy.metadata == {"created_by": "admin", "environment": "production"}

        condition = policy.conditions[0]
        assert condition.severity_threshold == Severity.CRITICAL
        assert condition.rule_ids == ["pi-001", "pi-002"]
        assert condition.min_confidence == 0.7
        assert condition.max_confidence == 1.0

    def test_load_multiple_policies(self):
        """Load multiple policies from one file."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: policy-001
                customer_id: cust_abc123
                name: Policy 1
                description: First
                conditions:
                  - severity: high
                action: BLOCK

              - id: policy-002
                customer_id: cust_abc123
                name: Policy 2
                description: Second
                conditions:
                  - severity: medium
                action: FLAG
        """)

        loader = YAMLPolicyLoader()
        policies = loader.load_from_string(yaml_content)

        assert len(policies) == 2
        assert policies[0].policy_id == "policy-001"
        assert policies[1].policy_id == "policy-002"

    def test_load_from_file(self, tmp_path: Path):
        """Load policies from file."""
        policy_file = tmp_path / "policies.yaml"
        policy_file.write_text(dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_test
                name: File Policy
                description: From file
                conditions:
                  - severity: high
                action: BLOCK
        """))

        loader = YAMLPolicyLoader()
        policies = loader.load_from_file(policy_file)

        assert len(policies) == 1
        assert policies[0].name == "File Policy"

    def test_file_not_found(self, tmp_path: Path):
        """Error if file doesn't exist."""
        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="not found"):
            loader.load_from_file(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_syntax(self):
        """Error on invalid YAML syntax."""
        yaml_content = """
            version: 1.0.0
            policies:
              - id: test
                invalid yaml here: [
        """

        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="Invalid YAML"):
            loader.load_from_string(yaml_content)

    def test_empty_yaml(self):
        """Error on empty YAML."""
        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="Empty"):
            loader.load_from_string("")

    def test_missing_version(self):
        """Error if version field missing."""
        yaml_content = dedent("""
            policies:
              - id: test-001
                customer_id: cust_test
                name: Test
                description: Test
                conditions:
                  - severity: high
                action: BLOCK
        """)

        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="Missing 'version'"):
            loader.load_from_string(yaml_content)

    def test_unsupported_version(self):
        """Error on unsupported version."""
        yaml_content = dedent("""
            version: 2.0.0
            policies: []
        """)

        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="Unsupported policy version"):
            loader.load_from_string(yaml_content)

    def test_missing_policies_field(self):
        """Error if policies field missing."""
        yaml_content = "version: 1.0.0"

        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="Missing 'policies'"):
            loader.load_from_string(yaml_content)

    def test_invalid_action(self):
        """Error on invalid action value."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_test
                name: Test
                description: Test
                conditions:
                  - severity: high
                action: INVALID_ACTION
        """)

        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="Invalid action"):
            loader.load_from_string(yaml_content)

    def test_invalid_severity(self):
        """Error on invalid severity value."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_test
                name: Test
                description: Test
                conditions:
                  - severity: invalid_severity
                action: BLOCK
        """)

        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="Invalid severity"):
            loader.load_from_string(yaml_content)

    def test_case_insensitive_action(self):
        """Action parsing is case-insensitive."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_test
                name: Test
                description: Test
                conditions:
                  - severity: high
                action: block
        """)

        loader = YAMLPolicyLoader()
        policies = loader.load_from_string(yaml_content)

        assert policies[0].action == PolicyAction.BLOCK

    def test_case_insensitive_severity(self):
        """Severity parsing is case-insensitive."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_test
                name: Test
                description: Test
                conditions:
                  - severity: CRITICAL
                action: BLOCK
        """)

        loader = YAMLPolicyLoader()
        policies = loader.load_from_string(yaml_content)

        assert policies[0].conditions[0].severity_threshold == Severity.CRITICAL

    def test_multiple_conditions_per_policy(self):
        """Policy can have multiple conditions (OR logic)."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_test
                name: Test
                description: Test
                conditions:
                  - severity: critical
                  - rule_ids:
                      - pi-001
                      - pi-002
                  - min_confidence: 0.9
                action: BLOCK
        """)

        loader = YAMLPolicyLoader()
        policies = loader.load_from_string(yaml_content)

        assert len(policies[0].conditions) == 3

    def test_empty_conditions_list_error(self):
        """Error if conditions list is empty."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_test
                name: Test
                description: Test
                conditions: []
                action: BLOCK
        """)

        loader = YAMLPolicyLoader()

        with pytest.raises(PolicyLoadError, match="non-empty list"):
            loader.load_from_string(yaml_content)

    def test_disabled_policy(self):
        """Can load disabled policy."""
        yaml_content = dedent("""
            version: 1.0.0
            policies:
              - id: test-001
                customer_id: cust_test
                name: Test
                description: Test
                enabled: false
                conditions:
                  - severity: high
                action: BLOCK
        """)

        loader = YAMLPolicyLoader()
        policies = loader.load_from_string(yaml_content)

        assert policies[0].enabled is False
