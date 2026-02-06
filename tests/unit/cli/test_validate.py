"""Tests for CLI validate-rule command.

Tests for:
- raxe validate-rule <path>
- raxe validate-rule <path> --strict
- raxe validate-rule <path> --json
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.validate import validate_rule_command


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


def _make_validation_result(
    valid=True, rule_id="pi-001", issues=None, errors_count=0, warnings_count=0
):
    """Create a mock ValidationResult."""
    result = MagicMock()
    result.valid = valid
    result.rule_id = rule_id
    result.issues = issues or []
    result.errors_count = errors_count
    result.warnings_count = warnings_count
    result.has_errors = errors_count > 0
    return result


def _make_validation_issue(
    severity="error",
    field="patterns[0]",
    message="Issue found",
    suggestion="Fix it",
):
    """Create a mock ValidationIssue."""
    issue = MagicMock()
    issue.severity = severity
    issue.field = field
    issue.message = message
    issue.suggestion = suggestion
    return issue


class TestValidateRuleValid:
    """Tests for validate-rule with valid rules."""

    def test_validate_valid_rule_file(self, runner, tmp_path):
        """Test validating a valid rule file."""
        rule_file = tmp_path / "valid_rule.yaml"
        rule_file.write_text("rule_id: pi-001\nname: Test Rule\n")

        mock_result = _make_validation_result(valid=True, rule_id="pi-001")
        with patch("raxe.cli.validate.RuleValidator") as mock_validator:
            mock_validator.return_value.validate_file.return_value = mock_result
            result = runner.invoke(validate_rule_command, [str(rule_file)])

        # Exit code 0 = passed
        assert result.exit_code == 0
        assert "PASSED" in result.output or "valid" in result.output.lower()

    def test_validate_valid_rule_json_output(self, runner, tmp_path):
        """Test validating a valid rule with JSON output."""
        rule_file = tmp_path / "valid_rule.yaml"
        rule_file.write_text("rule_id: pi-001\nname: Test Rule\n")

        mock_result = _make_validation_result(valid=True, rule_id="pi-001")
        with patch("raxe.cli.validate.RuleValidator") as mock_validator:
            mock_validator.return_value.validate_file.return_value = mock_result
            result = runner.invoke(validate_rule_command, [str(rule_file), "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is True
        assert data["rule_id"] == "pi-001"


class TestValidateRuleInvalid:
    """Tests for validate-rule with invalid rules."""

    def test_validate_invalid_rule_file(self, runner, tmp_path):
        """Test validating an invalid rule file."""
        rule_file = tmp_path / "invalid_rule.yaml"
        rule_file.write_text("name: incomplete\n")

        issues = [
            _make_validation_issue(
                severity="error",
                field="rule_id",
                message="Missing required field",
            ),
        ]
        mock_result = _make_validation_result(
            valid=False, rule_id=None, issues=issues, errors_count=1
        )
        with patch("raxe.cli.validate.RuleValidator") as mock_validator:
            mock_validator.return_value.validate_file.return_value = mock_result
            result = runner.invoke(validate_rule_command, [str(rule_file)])

        assert result.exit_code == 1
        assert "FAILED" in result.output or "error" in result.output.lower()

    def test_validate_invalid_rule_json_output(self, runner, tmp_path):
        """Test validating an invalid rule with JSON output."""
        rule_file = tmp_path / "invalid_rule.yaml"
        rule_file.write_text("name: incomplete\n")

        issues = [
            _make_validation_issue(
                severity="error",
                field="rule_id",
                message="Missing required field",
            ),
        ]
        mock_result = _make_validation_result(
            valid=False, rule_id=None, issues=issues, errors_count=1
        )
        with patch("raxe.cli.validate.RuleValidator") as mock_validator:
            mock_validator.return_value.validate_file.return_value = mock_result
            result = runner.invoke(validate_rule_command, [str(rule_file), "--json"])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["valid"] is False
        assert data["summary"]["errors"] == 1


class TestValidateRuleMissing:
    """Tests for validate-rule with missing files."""

    def test_validate_missing_file(self, runner):
        """Test validating a file that doesn't exist."""
        result = runner.invoke(validate_rule_command, ["/nonexistent/rule.yaml"])

        # Click should report the missing file before our command runs
        assert result.exit_code != 0


class TestValidateRuleStrict:
    """Tests for validate-rule --strict mode."""

    def test_strict_mode_fails_on_warnings(self, runner, tmp_path):
        """Test that --strict mode fails on warnings."""
        rule_file = tmp_path / "rule_with_warnings.yaml"
        rule_file.write_text("rule_id: pi-001\n")

        issues = [
            _make_validation_issue(
                severity="warning",
                field="description",
                message="Description is very short",
            ),
        ]
        mock_result = _make_validation_result(
            valid=True,
            rule_id="pi-001",
            issues=issues,
            errors_count=0,
            warnings_count=1,
        )
        with patch("raxe.cli.validate.RuleValidator") as mock_validator:
            mock_validator.return_value.validate_file.return_value = mock_result
            result = runner.invoke(validate_rule_command, [str(rule_file), "--strict"])

        # Exit code 2 = warnings in strict mode
        assert result.exit_code == 2

    def test_strict_mode_passes_without_warnings(self, runner, tmp_path):
        """Test that --strict mode passes with no warnings."""
        rule_file = tmp_path / "clean_rule.yaml"
        rule_file.write_text("rule_id: pi-001\n")

        mock_result = _make_validation_result(valid=True, rule_id="pi-001", warnings_count=0)
        with patch("raxe.cli.validate.RuleValidator") as mock_validator:
            mock_validator.return_value.validate_file.return_value = mock_result
            result = runner.invoke(validate_rule_command, [str(rule_file), "--strict"])

        assert result.exit_code == 0


class TestValidateRuleYamlError:
    """Tests for validate-rule with YAML syntax errors."""

    def test_validate_yaml_syntax_error(self, runner, tmp_path):
        """Test validating a file with YAML syntax errors."""
        rule_file = tmp_path / "bad_yaml.yaml"
        rule_file.write_text("invalid: yaml: content: [unclosed\n")

        issues = [
            _make_validation_issue(
                severity="error",
                field="yaml",
                message="Invalid YAML syntax",
            ),
        ]
        mock_result = _make_validation_result(valid=False, issues=issues, errors_count=1)
        with patch("raxe.cli.validate.RuleValidator") as mock_validator:
            mock_validator.return_value.validate_file.return_value = mock_result
            result = runner.invoke(validate_rule_command, [str(rule_file)])

        assert result.exit_code == 1


class TestValidateRuleFieldsMissing:
    """Tests for validate-rule with missing required fields."""

    def test_validate_rule_missing_fields(self, runner, tmp_path):
        """Test validating a rule missing required fields."""
        rule_file = tmp_path / "incomplete.yaml"
        rule_file.write_text("rule_id: pi-test\n")

        issues = [
            _make_validation_issue(
                severity="error",
                field="patterns",
                message="patterns is required",
            ),
            _make_validation_issue(
                severity="error",
                field="name",
                message="name is required",
            ),
        ]
        mock_result = _make_validation_result(valid=False, issues=issues, errors_count=2)
        with patch("raxe.cli.validate.RuleValidator") as mock_validator:
            mock_validator.return_value.validate_file.return_value = mock_result
            result = runner.invoke(validate_rule_command, [str(rule_file)])

        assert result.exit_code == 1
        assert "2 error" in result.output
