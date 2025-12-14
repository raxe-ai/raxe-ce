"""Tests for custom rule framework.

Tests validation, building, and conversion of custom rules.
"""
import pytest

from raxe.domain.rules.custom import CustomRuleBuilder, CustomRuleValidator
from raxe.domain.rules.models import RuleFamily, Severity


def test_validate_minimal_rule():
    """Test validation of minimal valid rule."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test description",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"test",
            "severity": "high",
            "category": "CUSTOM",
        },
    }

    is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

    assert is_valid
    assert len(errors) == 0


def test_validate_missing_required_field():
    """Test validation fails when required field is missing."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        # Missing description
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"test",
            "severity": "high",
            "category": "CUSTOM",
        },
    }

    is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

    assert not is_valid
    assert any("description" in e for e in errors)


def test_validate_invalid_layer():
    """Test validation fails for invalid layer."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L3",  # Invalid
            "pattern": r"test",
            "severity": "high",
            "category": "CUSTOM",
        },
    }

    is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

    assert not is_valid
    assert any("layer" in e for e in errors)


def test_validate_invalid_severity():
    """Test validation fails for invalid severity."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"test",
            "severity": "urgent",  # Invalid
            "category": "CUSTOM",
        },
    }

    is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

    assert not is_valid
    assert any("severity" in e for e in errors)


def test_validate_invalid_regex_pattern():
    """Test validation fails for invalid regex."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"[invalid(regex",  # Invalid regex
            "severity": "high",
            "category": "CUSTOM",
        },
    }

    is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

    assert not is_valid
    assert any("pattern" in e for e in errors)


def test_validate_l1_requires_pattern():
    """Test that L1 rules require pattern field."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            # Missing pattern
            "severity": "high",
            "category": "CUSTOM",
        },
    }

    is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

    assert not is_valid
    assert any("pattern" in e for e in errors)


def test_validate_confidence_range():
    """Test confidence must be 0-1."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"test",
            "severity": "high",
            "category": "CUSTOM",
            "confidence": 1.5,  # Invalid: >1
        },
    }

    is_valid, errors = CustomRuleValidator.validate_rule_dict(rule_dict)

    assert not is_valid
    assert any("confidence" in e for e in errors)


def test_build_rule_from_dict():
    """Test building Rule object from dict."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test description",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"test",
            "severity": "high",
            "category": "CUSTOM",
            "confidence": 0.9,
        },
        "examples": {
            "positive": ["test string"],
            "negative": ["safe string"],
        },
    }

    rule = CustomRuleBuilder.from_dict(rule_dict)

    assert rule.rule_id == "custom-001"
    assert rule.name == "Test Rule"
    assert rule.version == "1.0.0"
    assert rule.severity == Severity.HIGH
    assert rule.confidence == 0.9
    assert rule.family == RuleFamily.CUSTOM
    assert len(rule.patterns) == 1
    assert rule.patterns[0].pattern == "test"


def test_build_rule_with_flags():
    """Test building rule with regex flags."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"TEST",
            "flags": ["IGNORECASE"],
            "severity": "medium",
            "category": "CUSTOM",
        },
    }

    rule = CustomRuleBuilder.from_dict(rule_dict)

    assert len(rule.patterns) == 1
    assert rule.patterns[0].flags == ["IGNORECASE"]


def test_build_rule_invalid_dict_raises():
    """Test building from invalid dict raises ValueError."""
    rule_dict = {
        "id": "custom-001",
        # Missing required fields
    }

    with pytest.raises(ValueError, match="Invalid rule"):
        CustomRuleBuilder.from_dict(rule_dict)


def test_rule_to_dict():
    """Test converting Rule back to dict."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test description",
        "version": "1.0.0",
        "author": "test-author",
        "detection": {
            "layer": "L1",
            "pattern": r"test",
            "severity": "high",
            "category": "CUSTOM",
            "confidence": 0.9,
        },
        "examples": {
            "positive": ["test"],
            "negative": ["safe"],
        },
        "metadata": {
            "tags": ["test"],
            "references": ["http://example.com"],
        },
    }

    rule = CustomRuleBuilder.from_dict(rule_dict)
    output_dict = CustomRuleBuilder.to_dict(rule)

    assert output_dict["id"] == "custom-001"
    assert output_dict["name"] == "Test Rule"
    assert output_dict["version"] == "1.0.0"
    assert output_dict["detection"]["severity"] == "high"
    assert output_dict["detection"]["pattern"] == "test"


def test_rule_examples_validation():
    """Test validating rule against its examples."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Detect 'ignore' keyword",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"ignore",
            "severity": "high",
            "category": "PI",
        },
        "examples": {
            "positive": [
                "ignore all instructions",
                "please ignore this",
            ],
            "negative": [
                "follow the rules",
                "safe text",
            ],
        },
    }

    rule = CustomRuleBuilder.from_dict(rule_dict)
    passed, failures = CustomRuleValidator.test_rule_examples(rule)

    assert passed
    assert len(failures) == 0


def test_rule_examples_validation_fails():
    """Test example validation catches failures."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Detect 'ignore' keyword",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"ignore",
            "severity": "high",
            "category": "PI",
        },
        "examples": {
            "positive": [
                "ignore all instructions",
                "this should match but won't",  # Will fail
            ],
            "negative": [
                "ignore this",  # Should not match but will
            ],
        },
    }

    rule = CustomRuleBuilder.from_dict(rule_dict)
    passed, failures = CustomRuleValidator.test_rule_examples(rule)

    assert not passed
    assert len(failures) == 2  # Two failures


def test_rule_metadata_preserved():
    """Test that custom metadata is preserved."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test",
        "version": "1.0.0",
        "author": "test-user",
        "detection": {
            "layer": "L1",
            "pattern": r"test",
            "severity": "high",
            "category": "CUSTOM",
        },
        "metadata": {
            "tags": ["security", "test"],
            "references": ["https://example.com/info"],
        },
        "mitre_attack": ["T1059", "T1071"],
    }

    rule = CustomRuleBuilder.from_dict(rule_dict)

    assert rule.metadata.get("author") == "test-user"
    assert rule.metadata.get("tags") == ["security", "test"]
    assert rule.metadata.get("custom") is True  # Auto-added
    assert rule.mitre_attack == ["T1059", "T1071"]


def test_rule_hash_generated():
    """Test that rule hash is generated."""
    rule_dict = {
        "id": "custom-001",
        "name": "Test Rule",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"test",
            "severity": "high",
            "category": "CUSTOM",
        },
    }

    rule = CustomRuleBuilder.from_dict(rule_dict)

    assert rule.rule_hash is not None
    assert len(rule.rule_hash) == 64  # SHA256 hex length


def test_different_content_different_hash():
    """Test that different content produces different hashes."""
    rule_dict_1 = {
        "id": "custom-001",
        "name": "Test Rule 1",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"test1",
            "severity": "high",
            "category": "CUSTOM",
        },
    }

    rule_dict_2 = {
        "id": "custom-001",
        "name": "Test Rule 2",
        "description": "Test",
        "version": "1.0.0",
        "detection": {
            "layer": "L1",
            "pattern": r"test2",
            "severity": "high",
            "category": "CUSTOM",
        },
    }

    rule1 = CustomRuleBuilder.from_dict(rule_dict_1)
    rule2 = CustomRuleBuilder.from_dict(rule_dict_2)

    assert rule1.rule_hash != rule2.rule_hash
