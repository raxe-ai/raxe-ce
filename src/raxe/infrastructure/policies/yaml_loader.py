"""YAML policy file loader.

Loads policies from local .raxe/policies.yaml files.
Validates schema and converts to domain models.
"""
from pathlib import Path

import yaml

from raxe.domain.policies.models import (
    Policy,
    PolicyAction,
    PolicyCondition,
)
from raxe.domain.rules.models import Severity


class PolicyLoadError(Exception):
    """Error loading or parsing policy file."""
    pass


class YAMLPolicyLoader:
    """Load policies from YAML files.

    Expected YAML format:
    ```yaml
    version: 1.0.0
    policies:
      - id: block-critical
        customer_id: cust_abc123
        name: "Block all critical threats"
        description: "Zero tolerance for critical threats"
        priority: 100
        enabled: true
        conditions:
          - severity: critical
        action: BLOCK
        metadata:
          created_by: admin
    ```
    """

    def load_from_file(self, file_path: Path) -> list[Policy]:
        """Load policies from YAML file.

        Args:
            file_path: Path to YAML policy file

        Returns:
            List of Policy objects

        Raises:
            PolicyLoadError: If file doesn't exist, invalid YAML, or schema error
        """
        if not file_path.exists():
            raise PolicyLoadError(f"Policy file not found: {file_path}")

        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise PolicyLoadError(f"Invalid YAML in {file_path}: {e}") from e
        except OSError as e:
            raise PolicyLoadError(f"Cannot read {file_path}: {e}") from e

        if not data:
            raise PolicyLoadError(f"Empty policy file: {file_path}")

        return self._parse_yaml_data(data, str(file_path))

    def load_from_string(self, yaml_content: str) -> list[Policy]:
        """Load policies from YAML string.

        Useful for testing and programmatic policy creation.

        Args:
            yaml_content: YAML content as string

        Returns:
            List of Policy objects

        Raises:
            PolicyLoadError: If invalid YAML or schema error
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise PolicyLoadError(f"Invalid YAML: {e}") from e

        if not data:
            raise PolicyLoadError("Empty YAML content")

        return self._parse_yaml_data(data, "<string>")

    def _parse_yaml_data(
        self,
        data: dict,
        source: str,
    ) -> list[Policy]:
        """Parse YAML data into Policy objects.

        Args:
            data: Parsed YAML data
            source: Source description for error messages

        Returns:
            List of Policy objects

        Raises:
            PolicyLoadError: If schema validation fails
        """
        # Validate root structure
        if not isinstance(data, dict):
            raise PolicyLoadError(f"Policy file must be a YAML object, got {type(data)}")

        # Check version
        version = data.get("version")
        if not version:
            raise PolicyLoadError(f"Missing 'version' field in {source}")

        if not isinstance(version, str):
            raise PolicyLoadError(f"'version' must be string, got {type(version)}")

        # Currently only support v1.0.0
        if not version.startswith("1."):
            raise PolicyLoadError(
                f"Unsupported policy version {version} (expected 1.x.x)"
            )

        # Parse policies
        policies_data = data.get("policies")
        if not policies_data:
            raise PolicyLoadError(f"Missing 'policies' field in {source}")

        if not isinstance(policies_data, list):
            raise PolicyLoadError(
                f"'policies' must be a list, got {type(policies_data)}"
            )

        policies: list[Policy] = []
        for idx, policy_data in enumerate(policies_data):
            try:
                policy = self._parse_policy(policy_data)
                policies.append(policy)
            except (ValueError, KeyError) as e:
                raise PolicyLoadError(
                    f"Invalid policy at index {idx} in {source}: {e}"
                ) from e

        # Validate policy count using PolicySet (enforces max 100 policies)
        from raxe.domain.policies.models import PolicySet
        try:
            PolicySet(policies=policies)  # Validates count in __post_init__
        except ValueError as e:
            raise PolicyLoadError(f"Policy validation failed in {source}: {e}") from e

        return policies

    def _parse_policy(self, data: dict) -> Policy:
        """Parse single policy from YAML data.

        Args:
            data: Policy data dictionary

        Returns:
            Policy object

        Raises:
            ValueError: If required fields missing or invalid
            KeyError: If required fields missing
        """
        # Parse conditions
        conditions_data = data["conditions"]
        if not isinstance(conditions_data, list) or not conditions_data:
            raise ValueError("'conditions' must be non-empty list")

        conditions = [
            self._parse_condition(cond_data)
            for cond_data in conditions_data
        ]

        # Parse action
        action_str = data["action"].upper()
        try:
            action = PolicyAction[action_str]
        except KeyError:
            raise ValueError(
                f"Invalid action '{action_str}'. "
                f"Must be one of: {', '.join(a.name for a in PolicyAction)}"
            ) from None

        # Parse optional severity override
        override_severity = None
        if "override_severity" in data:
            severity_str = data["override_severity"].lower()
            try:
                override_severity = Severity[severity_str.upper()]
            except KeyError:
                raise ValueError(
                    f"Invalid override_severity '{severity_str}'. "
                    f"Must be one of: {', '.join(s.name.lower() for s in Severity)}"
                ) from None

        # Build Policy
        return Policy(
            policy_id=data["id"],
            customer_id=data["customer_id"],
            name=data["name"],
            description=data.get("description", ""),
            conditions=conditions,
            action=action,
            override_severity=override_severity,
            priority=data.get("priority", 0),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
        )

    def _parse_condition(self, data: dict) -> PolicyCondition:
        """Parse single condition from YAML data.

        Args:
            data: Condition data dictionary

        Returns:
            PolicyCondition object

        Raises:
            ValueError: If condition data invalid
        """
        # Parse optional severity threshold
        severity_threshold = None
        if "severity" in data:
            severity_str = data["severity"].lower()
            try:
                severity_threshold = Severity[severity_str.upper()]
            except KeyError:
                raise ValueError(
                    f"Invalid severity '{severity_str}'. "
                    f"Must be one of: {', '.join(s.name.lower() for s in Severity)}"
                ) from None

        return PolicyCondition(
            rule_ids=data.get("rule_ids"),
            severity_threshold=severity_threshold,
            threat_types=data.get("threat_types"),
            min_confidence=data.get("min_confidence"),
            max_confidence=data.get("max_confidence"),
            custom_filter=data.get("custom_filter"),
        )
