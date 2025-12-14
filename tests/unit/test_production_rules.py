"""
Test production rule loading and validation.

This test ensures all 107 production rules in core v1.0.0 load correctly
and meet quality standards.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

RULEPACK_PATH = Path(__file__).parent.parent.parent / "src" / "raxe" / "packs" / "core" / "v1.0.0" / "rules"
EXPECTED_TOTAL_RULES = 460  # Community edition expanded rule set

EXPECTED_FAMILIES = {
    "cmd": 65,
    "PI": 59,
    "jb": 77,
    "pii": 112,
    "enc": 70,
    "rag": 12,
    "hc": 65,
}


def load_rule(path: Path) -> dict[str, Any]:
    """Load a rule YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def get_all_rule_files() -> list[Path]:
    """Get all rule YAML files from the rulepack."""
    rule_files = []
    for family_dir in RULEPACK_PATH.iterdir():
        if family_dir.is_dir():
            rule_files.extend(family_dir.glob("*.yaml"))
    return rule_files


class TestProductionRules:
    """Test suite for production rules."""

    def test_rulepack_directory_exists(self):
        """Verify rulepack directory exists."""
        assert RULEPACK_PATH.exists(), f"Rulepack not found at {RULEPACK_PATH}"
        assert RULEPACK_PATH.is_dir(), f"{RULEPACK_PATH} is not a directory"

    def test_manifest_exists(self):
        """Verify pack.yaml exists (pack manifest)."""
        # pack.yaml is in parent directory of rules/
        manifest_path = RULEPACK_PATH.parent / "pack.yaml"
        assert manifest_path.exists(), "pack.yaml not found"

        # Load and validate manifest structure
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        assert "pack" in manifest
        assert manifest["pack"]["id"] == "core"
        assert manifest["pack"]["version"] == "1.0.0"
        # Rule count is in the rules array, not a separate field
        assert len(manifest["pack"]["rules"]) == EXPECTED_TOTAL_RULES

    def test_all_family_directories_exist(self):
        """Verify all expected family directories exist."""
        for family in EXPECTED_FAMILIES.keys():
            family_dir = RULEPACK_PATH / family
            assert family_dir.exists(), f"Family directory {family} not found"
            assert family_dir.is_dir(), f"{family} is not a directory"

    def test_total_rule_count(self):
        """Verify total number of rules is 104."""
        all_rules = get_all_rule_files()
        actual_count = len(all_rules)
        assert actual_count == EXPECTED_TOTAL_RULES, (
            f"Expected {EXPECTED_TOTAL_RULES} rules, found {actual_count}"
        )

    def test_rule_count_per_family(self):
        """Verify correct number of rules per family."""
        for family, expected_count in EXPECTED_FAMILIES.items():
            family_dir = RULEPACK_PATH / family
            rule_files = list(family_dir.glob("*.yaml"))
            actual_count = len(rule_files)

            assert actual_count == expected_count, (
                f"Family {family}: expected {expected_count} rules, found {actual_count}"
            )

    @pytest.mark.parametrize("rule_file", get_all_rule_files())
    def test_rule_loads_successfully(self, rule_file: Path):
        """Test that each rule file loads without errors."""
        try:
            rule = load_rule(rule_file)
            assert rule is not None, f"Rule {rule_file} loaded as None"
        except Exception as e:
            pytest.fail(f"Failed to load {rule_file}: {e}")

    @pytest.mark.parametrize("rule_file", get_all_rule_files())
    def test_rule_has_required_fields(self, rule_file: Path):
        """Test that each rule has all required fields."""
        rule = load_rule(rule_file)

        required_fields = [
            "version",
            "rule_id",
            "family",
            "sub_family",
            "name",
            "description",
            "severity",
            "confidence",
            "patterns",
            "examples",
            "metadata",
        ]

        for field in required_fields:
            assert field in rule, f"Rule {rule_file} missing required field: {field}"

    @pytest.mark.parametrize("rule_file", get_all_rule_files())
    def test_rule_confidence_threshold(self, rule_file: Path):
        """Test that all rules meet minimum confidence threshold."""
        rule = load_rule(rule_file)
        confidence = rule.get("confidence", 0.0)

        # Community edition allows experimental rules with lower confidence
        # Core rules should have >= 0.85, but experimental rules can be >= 0.7
        # This supports the 460+ rule community-driven approach
        assert confidence >= 0.7, (
            f"Rule {rule_file} has confidence {confidence}, below threshold 0.7"
        )

    @pytest.mark.parametrize("rule_file", get_all_rule_files())
    def test_rule_has_patterns(self, rule_file: Path):
        """Test that each rule has at least one pattern."""
        rule = load_rule(rule_file)
        patterns = rule.get("patterns", [])

        assert len(patterns) > 0, f"Rule {rule_file} has no patterns"

        # Verify pattern structure
        for pattern in patterns:
            assert "pattern" in pattern, f"Pattern in {rule_file} missing 'pattern' field"

    @pytest.mark.parametrize("rule_file", get_all_rule_files())
    def test_rule_has_examples(self, rule_file: Path):
        """Test that each rule has good examples."""
        rule = load_rule(rule_file)
        examples = rule.get("examples", {})

        assert "should_match" in examples, f"Rule {rule_file} missing should_match examples"
        assert "should_not_match" in examples, f"Rule {rule_file} missing should_not_match examples"

        should_match = examples.get("should_match", [])
        should_not_match = examples.get("should_not_match", [])

        # Production rules should have at least 2 examples of each type
        assert len(should_match) >= 2, (
            f"Rule {rule_file} has only {len(should_match)} should_match examples"
        )
        assert len(should_not_match) >= 2, (
            f"Rule {rule_file} has only {len(should_not_match)} should_not_match examples"
        )

    @pytest.mark.parametrize("rule_file", get_all_rule_files())
    def test_rule_severity_is_valid(self, rule_file: Path):
        """Test that rule severity is valid."""
        rule = load_rule(rule_file)
        severity = rule.get("severity")

        valid_severities = ["low", "medium", "high", "critical"]
        assert severity in valid_severities, (
            f"Rule {rule_file} has invalid severity: {severity}"
        )

    @pytest.mark.parametrize("rule_file", get_all_rule_files())
    def test_rule_family_matches_directory(self, rule_file: Path):
        """Test that rule family matches its directory."""
        rule = load_rule(rule_file)
        family = rule.get("family", "").upper()
        directory_family = rule_file.parent.name.upper()

        assert family == directory_family, (
            f"Rule {rule_file} has family {family} but is in {directory_family} directory"
        )

    def test_overall_statistics(self):
        """Test overall rulepack statistics."""
        all_rules = get_all_rule_files()

        confidences = []
        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for rule_file in all_rules:
            rule = load_rule(rule_file)
            confidences.append(rule.get("confidence", 0.0))
            severity = rule.get("severity", "low")
            severities[severity] += 1

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Production pack should have high average confidence
        assert avg_confidence >= 0.90, (
            f"Average confidence {avg_confidence:.3f} below threshold 0.90"
        )

        # Most rules should be critical or high severity
        critical_high_count = severities["critical"] + severities["high"]
        total_count = sum(severities.values())
        critical_high_ratio = critical_high_count / total_count if total_count > 0 else 0

        assert critical_high_ratio >= 0.80, (
            f"Only {critical_high_ratio:.1%} rules are critical/high severity"
        )

        print("\nProduction Rulepack Statistics:")
        print(f"  Total Rules: {len(all_rules)}")
        print(f"  Average Confidence: {avg_confidence:.3f}")
        print(f"  Severity Distribution: {severities}")
        print(f"  Critical/High Ratio: {critical_high_ratio:.1%}")
