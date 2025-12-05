"""Unit tests for YAML rule loader."""
from pathlib import Path

import pytest

from raxe.domain.rules.models import Rule, RuleFamily, Severity
from raxe.infrastructure.rules.yaml_loader import YAMLLoader, YAMLLoadError


class TestYAMLLoader:
    """Test YAML rule loading."""

    def test_load_rule_from_valid_file(self, tmp_path: Path):
        """Load a valid rule YAML file."""
        # Create test YAML file
        rule_file = tmp_path / "test-rule.yaml"
        rule_file.write_text("""
version: 1.0.0
rule_id: test-001
family: PI
sub_family: test_category

name: Test Rule
description: A test rule for unit testing

severity: high
confidence: 0.9

patterns:
  - pattern: \\btest\\b
    flags: [IGNORECASE]
    timeout: 5.0

examples:
  should_match:
    - This is a test
  should_not_match:
    - This is production

metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d:
    true_positive: 0
    false_positive: 0

mitre_attack:
  - T1234.001

metadata:
  created: "2025-11-15"
  author: test

rule_hash: sha256:abc123
""")

        loader = YAMLLoader()
        rule = loader.load_rule(rule_file)

        assert isinstance(rule, Rule)
        assert rule.rule_id == "test-001"
        assert rule.version == "1.0.0"
        assert rule.family == RuleFamily.PI
        assert rule.sub_family == "test_category"
        assert rule.severity == Severity.HIGH
        assert rule.confidence == 0.9
        assert len(rule.patterns) == 1
        assert rule.patterns[0].pattern == r"\btest\b"
        assert len(rule.examples.should_match) == 1
        assert len(rule.mitre_attack) == 1

    def test_load_rule_file_not_found(self):
        """Loading non-existent file raises FileNotFoundError."""
        loader = YAMLLoader()

        with pytest.raises(FileNotFoundError):
            loader.load_rule(Path("/nonexistent/file.yaml"))

    def test_load_rule_invalid_yaml(self, tmp_path: Path):
        """Loading malformed YAML raises YAMLLoadError."""
        rule_file = tmp_path / "bad.yaml"
        rule_file.write_text("invalid: yaml: content:")

        loader = YAMLLoader()

        with pytest.raises(YAMLLoadError, match="Failed to parse YAML"):
            loader.load_rule(rule_file)

    def test_load_rule_empty_file(self, tmp_path: Path):
        """Loading empty YAML file raises YAMLLoadError."""
        rule_file = tmp_path / "empty.yaml"
        rule_file.write_text("")

        loader = YAMLLoader()

        with pytest.raises(YAMLLoadError, match="Empty YAML file"):
            loader.load_rule(rule_file)

    def test_load_rule_missing_version(self, tmp_path: Path):
        """Loading YAML without version raises YAMLLoadError."""
        rule_file = tmp_path / "no-version.yaml"
        rule_file.write_text("""
rule_id: test-001
name: Test
""")

        loader = YAMLLoader()

        with pytest.raises(YAMLLoadError, match="Missing required 'version' field"):
            loader.load_rule(rule_file)

    def test_load_rule_incompatible_version(self, tmp_path: Path):
        """Loading rule with incompatible version raises YAMLLoadError."""
        rule_file = tmp_path / "bad-version.yaml"
        rule_file.write_text("""
version: 99.0.0
rule_id: test-001
family: PI
sub_family: test
name: Test
description: Test
severity: high
confidence: 0.9
patterns:
  - pattern: test
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        loader = YAMLLoader()

        with pytest.raises(YAMLLoadError, match="Version incompatibility"):
            loader.load_rule(rule_file)

    def test_load_rule_missing_required_field(self, tmp_path: Path):
        """Loading rule with missing required field raises YAMLLoadError."""
        rule_file = tmp_path / "missing-field.yaml"
        rule_file.write_text("""
version: 1.0.0
rule_id: test-001
# Missing 'family' field
sub_family: test
name: Test
description: Test
severity: high
confidence: 0.9
patterns:
  - pattern: test
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        loader = YAMLLoader()

        with pytest.raises(YAMLLoadError, match="Validation failed"):
            loader.load_rule(rule_file)

    def test_load_rule_invalid_severity(self, tmp_path: Path):
        """Loading rule with invalid severity raises YAMLLoadError."""
        rule_file = tmp_path / "bad-severity.yaml"
        rule_file.write_text("""
version: 1.0.0
rule_id: test-001
family: PI
sub_family: test
name: Test
description: Test
severity: invalid_severity
confidence: 0.9
patterns:
  - pattern: test
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        loader = YAMLLoader()

        with pytest.raises(YAMLLoadError, match="Validation failed"):
            loader.load_rule(rule_file)

    def test_load_rules_from_directory(self, tmp_path: Path):
        """Load multiple rules from a directory."""
        # Create test rules
        (tmp_path / "rule1.yaml").write_text("""
version: 1.0.0
rule_id: test-001
family: PI
sub_family: test
name: Test 1
description: Test
severity: high
confidence: 0.9
patterns:
  - pattern: test1
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        (tmp_path / "rule2.yaml").write_text("""
version: 1.0.0
rule_id: test-002
family: JB
sub_family: test
name: Test 2
description: Test
severity: medium
confidence: 0.8
patterns:
  - pattern: test2
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        loader = YAMLLoader()
        rules = loader.load_rules_from_directory(tmp_path)

        assert len(rules) == 2
        assert {r.rule_id for r in rules} == {"test-001", "test-002"}

    def test_load_rules_from_empty_directory(self, tmp_path: Path):
        """Loading from empty directory returns empty list."""
        loader = YAMLLoader()
        rules = loader.load_rules_from_directory(tmp_path)

        assert rules == []

    def test_load_rules_from_nonexistent_directory(self):
        """Loading from non-existent directory raises NotADirectoryError."""
        loader = YAMLLoader()

        with pytest.raises(NotADirectoryError):
            loader.load_rules_from_directory(Path("/nonexistent"))

    def test_load_rules_recursive(self, tmp_path: Path):
        """Load rules recursively from subdirectories."""
        # Create nested structure
        (tmp_path / "PI").mkdir()
        (tmp_path / "JB").mkdir()

        (tmp_path / "PI" / "rule1.yaml").write_text("""
version: 1.0.0
rule_id: pi-001
family: PI
sub_family: test
name: PI Test
description: Test
severity: high
confidence: 0.9
patterns:
  - pattern: test
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        (tmp_path / "JB" / "rule2.yaml").write_text("""
version: 1.0.0
rule_id: jb-001
family: JB
sub_family: test
name: JB Test
description: Test
severity: medium
confidence: 0.8
patterns:
  - pattern: test
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        loader = YAMLLoader()
        rules = loader.load_rules_from_directory(tmp_path, recursive=True)

        assert len(rules) == 2
        assert {r.rule_id for r in rules} == {"pi-001", "jb-001"}

    def test_load_rules_non_recursive(self, tmp_path: Path):
        """Load rules without recursion skips subdirectories."""
        (tmp_path / "PI").mkdir()
        (tmp_path / "PI" / "rule1.yaml").write_text("""
version: 1.0.0
rule_id: pi-001
family: PI
sub_family: test
name: Test
description: Test
severity: high
confidence: 0.9
patterns:
  - pattern: test
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        loader = YAMLLoader()
        rules = loader.load_rules_from_directory(tmp_path, recursive=False)

        assert len(rules) == 0

    def test_load_rules_strict_mode_fails_on_error(self, tmp_path: Path):
        """Strict mode raises on first error."""
        (tmp_path / "good.yaml").write_text("""
version: 1.0.0
rule_id: good-001
family: PI
sub_family: test
name: Good
description: Test
severity: high
confidence: 0.9
patterns:
  - pattern: test
examples:
  should_match: []
  should_not_match: []
metrics:
  precision: null
  recall: null
  f1_score: null
  last_evaluated: null
  counts_30d: {}
""")

        (tmp_path / "bad.yaml").write_text("""
version: invalid
rule_id: bad-001
""")

        loader = YAMLLoader(strict=True)

        with pytest.raises(YAMLLoadError):
            loader.load_rules_from_directory(tmp_path)

    def test_validate_yaml_structure(self):
        """validate_yaml_structure checks required fields."""
        loader = YAMLLoader()

        valid_data = {
            "version": "1.0.0",
            "rule_id": "test-001",
            "family": "PI",
            "sub_family": "test",
            "name": "Test",
            "description": "Test rule",
            "severity": "high",
            "confidence": 0.9,
            "patterns": [{"pattern": "test"}],
            "examples": {"should_match": [], "should_not_match": []},
            "metrics": {
                "precision": None,
                "recall": None,
                "f1_score": None,
                "last_evaluated": None,
                "counts_30d": {},
            },
        }

        # Should not raise
        loader.validate_yaml_structure(valid_data)

    def test_validate_yaml_structure_missing_field(self):
        """validate_yaml_structure raises for missing fields."""
        loader = YAMLLoader()

        invalid_data = {
            "version": "1.0.0",
            "rule_id": "test-001",
            # Missing required fields
        }

        with pytest.raises(YAMLLoadError, match="Missing required fields"):
            loader.validate_yaml_structure(invalid_data)
