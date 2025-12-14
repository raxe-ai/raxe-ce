"""Custom rule framework for user-defined threat detection.

This module provides functionality for loading, validating, and managing
custom threat detection rules defined in YAML format.

Pure domain layer - NO I/O operations (loading done in infrastructure layer).
"""
import hashlib
from dataclasses import dataclass
from typing import Any

from raxe.domain.rules.models import Pattern, Rule, RuleExamples, RuleFamily, RuleMetrics, Severity


@dataclass(frozen=True)
class CustomRuleMetadata:
    """Metadata for a custom rule.

    Attributes:
        author: Rule author (username or org)
        created_at: ISO timestamp when rule was created
        updated_at: ISO timestamp when rule was last updated
        tags: List of tags for categorization
        references: List of reference URLs or documents
        enabled: Whether the rule is active
    """
    author: str
    created_at: str
    updated_at: str | None = None
    tags: list[str] | None = None
    references: list[str] | None = None
    enabled: bool = True


class CustomRuleValidator:
    """Validate custom rules.

    Pure domain logic for validating rule structure and correctness.
    """

    @staticmethod
    def validate_rule_dict(rule_dict: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a rule dictionary.

        Args:
            rule_dict: Dictionary representation of a rule

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Required fields
        required_fields = ["id", "name", "description", "version", "detection"]
        for field in required_fields:
            if field not in rule_dict:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # Validate detection section
        detection = rule_dict.get("detection", {})
        if not isinstance(detection, dict):
            errors.append("detection must be a dictionary")
            return False, errors

        # Required detection fields
        detection_required = ["layer", "severity", "category"]
        for field in detection_required:
            if field not in detection:
                errors.append(f"Missing required detection field: {field}")

        # Validate layer
        layer = detection.get("layer", "")
        if layer not in ("L1", "L2"):
            errors.append(f"detection.layer must be 'L1' or 'L2', got '{layer}'")

        # For L1, pattern is required
        if layer == "L1":
            if "pattern" not in detection:
                errors.append("L1 rules require 'pattern' in detection")
            else:
                # Try to compile pattern
                pattern_str = detection.get("pattern", "")
                try:
                    import re
                    re.compile(pattern_str)
                except re.error as e:
                    errors.append(f"Invalid regex pattern: {e}")

        # Validate severity
        severity = detection.get("severity", "").lower()
        if severity not in ("critical", "high", "medium", "low", "info"):
            errors.append(
                f"detection.severity must be one of: critical, high, medium, low, info. Got '{severity}'"
            )

        # Validate confidence (if present)
        confidence = detection.get("confidence")
        if confidence is not None:
            if not isinstance(confidence, (int, float)):
                errors.append(f"detection.confidence must be a number, got {type(confidence)}")
            elif not (0.0 <= float(confidence) <= 1.0):
                errors.append(f"detection.confidence must be between 0 and 1, got {confidence}")

        # Validate examples (if present)
        examples = rule_dict.get("examples", {})
        if examples:
            if not isinstance(examples, dict):
                errors.append("examples must be a dictionary")
            else:
                if "positive" in examples and not isinstance(examples["positive"], list):
                    errors.append("examples.positive must be a list")
                if "negative" in examples and not isinstance(examples["negative"], list):
                    errors.append("examples.negative must be a list")

        return len(errors) == 0, errors

    @staticmethod
    def test_rule_examples(rule: Rule) -> tuple[bool, list[str]]:
        """Test a rule against its examples.

        Args:
            rule: Rule to test

        Returns:
            Tuple of (all_passed, list of failures)
        """
        failures = []

        # Test positive examples (should match)
        failed_should_match, failed_should_not_match = rule.matches_examples()

        for example in failed_should_match:
            failures.append(f"Expected to match but didn't: {example[:50]}...")

        for example in failed_should_not_match:
            failures.append(f"Expected NOT to match but did: {example[:50]}...")

        return len(failures) == 0, failures


class CustomRuleBuilder:
    """Build Rule objects from custom YAML definitions.

    Pure domain logic - converts validated dictionaries to Rule objects.
    """

    @staticmethod
    def from_dict(rule_dict: dict[str, Any]) -> Rule:
        """Build a Rule from a validated dictionary.

        Args:
            rule_dict: Validated rule dictionary

        Returns:
            Rule object

        Raises:
            ValueError: If rule_dict is invalid
        """
        # Validate first
        is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)
        if not is_valid:
            raise ValueError(f"Invalid rule: {', '.join(errors)}")

        detection = rule_dict["detection"]

        # Map YAML fields to Rule fields
        rule_id = rule_dict["id"]
        version = rule_dict["version"]
        name = rule_dict["name"]
        description = rule_dict["description"]

        # Map severity
        severity_str = detection["severity"].lower()
        severity = Severity(severity_str)

        # Map category to family
        category = detection.get("category", "CUSTOM").upper()
        try:
            family = RuleFamily(category)
        except ValueError:
            family = RuleFamily.CUSTOM

        sub_family = detection.get("sub_family", category.lower())

        # Build patterns (L1 only)
        patterns = []
        if detection.get("layer") == "L1":
            pattern_str = detection["pattern"]
            flags = detection.get("flags", [])
            timeout = detection.get("timeout", 5.0)

            patterns.append(Pattern(
                pattern=pattern_str,
                flags=flags,
                timeout=timeout,
            ))

        # Build examples
        examples_dict = rule_dict.get("examples", {})
        examples = RuleExamples(
            should_match=examples_dict.get("positive", []),
            should_not_match=examples_dict.get("negative", []),
        )

        # Build metrics (initially empty)
        metrics = RuleMetrics()

        # Get confidence
        confidence = detection.get("confidence", 0.9)

        # Get MITRE ATT&CK techniques
        mitre_attack = rule_dict.get("mitre_attack", [])

        # Build metadata
        metadata_dict = rule_dict.get("metadata", {})
        # Check for author at top level (legacy) or in metadata
        author = rule_dict.get("author") or metadata_dict.get("author", "unknown")
        metadata = {
            "author": author,
            "created_at": metadata_dict.get("created_at", ""),
            "tags": metadata_dict.get("tags", []),
            "references": metadata_dict.get("references", []),
            "custom": True,  # Mark as custom rule
        }

        # Calculate rule hash
        rule_content = f"{rule_id}{version}{name}{description}{''.join(p.pattern for p in patterns)}"
        rule_hash = hashlib.sha256(rule_content.encode()).hexdigest()

        return Rule(
            rule_id=rule_id,
            version=version,
            family=family,
            sub_family=sub_family,
            name=name,
            description=description,
            severity=severity,
            confidence=confidence,
            patterns=patterns,
            examples=examples,
            metrics=metrics,
            mitre_attack=mitre_attack,
            metadata=metadata,
            rule_hash=rule_hash,
        )

    @staticmethod
    def to_dict(rule: Rule) -> dict[str, Any]:
        """Convert a Rule to YAML-compatible dictionary.

        Args:
            rule: Rule to convert

        Returns:
            Dictionary representation suitable for YAML serialization
        """
        return {
            "id": rule.rule_id,
            "version": rule.version,
            "name": rule.name,
            "description": rule.description,
            "author": rule.metadata.get("author", "unknown"),
            "detection": {
                "layer": "L1" if rule.patterns else "L2",
                "pattern": rule.patterns[0].pattern if rule.patterns else "",
                "flags": rule.patterns[0].flags if rule.patterns else [],
                "timeout": rule.patterns[0].timeout if rule.patterns else 5.0,
                "severity": rule.severity.value,
                "confidence": rule.confidence,
                "category": rule.family.value,
                "sub_family": rule.sub_family,
            },
            "examples": {
                "positive": rule.examples.should_match,
                "negative": rule.examples.should_not_match,
            },
            "metadata": {
                "tags": rule.metadata.get("tags", []),
                "references": rule.metadata.get("references", []),
            },
            "mitre_attack": rule.mitre_attack,
        }
