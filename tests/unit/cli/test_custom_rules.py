"""Tests for custom rules CLI commands.

Tests for `raxe rules custom` subcommands: create, validate, list, install, uninstall, package.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from raxe.cli.custom_rules import custom_rules


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def custom_rules_dir(tmp_path):
    """Create a temporary custom rules directory."""
    rules_dir = tmp_path / "custom_rules"
    rules_dir.mkdir()
    return rules_dir


@pytest.fixture
def sample_rule_yaml():
    """Return valid custom rule YAML content."""
    return {
        "id": "custom-001",
        "name": "Test Custom Rule",
        "description": "A test rule for unit testing",
        "version": "1.0.0",
        "author": "tester",
        "detection": {
            "layer": "L1",
            "pattern": "test pattern",
            "severity": "medium",
            "confidence": 0.9,
            "category": "CUSTOM",
        },
        "examples": {
            "positive": ["test pattern here"],
            "negative": ["safe text"],
        },
        "metadata": {
            "tags": ["test"],
            "references": [],
        },
    }


@pytest.fixture
def sample_rule_file(custom_rules_dir, sample_rule_yaml):
    """Create a sample rule YAML file on disk."""
    rule_file = custom_rules_dir / "custom-001.yaml"
    rule_file.write_text(yaml.dump(sample_rule_yaml, default_flow_style=False))
    return rule_file


class TestCustomRulesList:
    """Tests for raxe rules custom list."""

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_list_empty(self, mock_loader_cls, runner):
        """Test listing when no custom rules installed."""
        mock_loader = MagicMock()
        mock_loader.list_custom_rules.return_value = []
        mock_loader.custom_rules_dir = Path("/fake/custom_rules")
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["list"])

        assert result.exit_code == 0
        assert "No custom rules" in result.output

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_list_with_rules(self, mock_loader_cls, runner):
        """Test listing installed custom rules."""
        mock_loader = MagicMock()
        mock_loader.list_custom_rules.return_value = [
            {
                "id": "custom-001",
                "name": "Test Rule",
                "version": "1.0.0",
                "file_path": "/fake/custom_rules/custom-001.yaml",
            },
            {
                "id": "custom-002",
                "name": "Another Rule",
                "version": "0.1.0",
                "file_path": "/fake/custom_rules/custom-002.yaml",
            },
        ]
        mock_loader.custom_rules_dir = Path("/fake/custom_rules")
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["list"])

        assert result.exit_code == 0
        assert "custom-001" in result.output
        assert "custom-002" in result.output
        assert "2 installed" in result.output

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_list_verbose(self, mock_loader_cls, runner):
        """Test verbose listing shows file paths."""
        mock_loader = MagicMock()
        mock_loader.list_custom_rules.return_value = [
            {
                "id": "custom-001",
                "name": "Test Rule",
                "version": "1.0.0",
                "file_path": "/fake/custom_rules/custom-001.yaml",
            },
        ]
        mock_loader.custom_rules_dir = Path("/fake/custom_rules")
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["list", "--verbose"])

        assert result.exit_code == 0
        assert "custom-001" in result.output


class TestCustomRulesCreate:
    """Tests for raxe rules custom create."""

    def test_create_non_interactive_prints_template(self, runner):
        """Test non-interactive mode prints YAML template."""
        result = runner.invoke(custom_rules, ["create", "--no-interactive"])

        assert result.exit_code == 0
        assert "custom-001" in result.output
        assert "severity" in result.output.lower()

    def test_create_non_interactive_to_file(self, runner, tmp_path):
        """Test non-interactive mode writes template to file."""
        output_file = tmp_path / "my_rule.yaml"

        result = runner.invoke(
            custom_rules, ["create", "--no-interactive", "--output", str(output_file)]
        )

        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "custom-001" in content


class TestCustomRulesValidate:
    """Tests for raxe rules custom validate."""

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_validate_valid_rule(self, mock_loader_cls, runner, sample_rule_file):
        """Test validating a valid rule file."""
        mock_loader = MagicMock()
        mock_loader.validate_file.return_value = (True, [])
        mock_rule = MagicMock()
        mock_rule.name = "Test Rule"
        mock_rule.versioned_id = "custom-001@1.0.0"
        mock_rule.severity.value = "medium"
        mock_rule.confidence = 0.9
        mock_rule.patterns = ["test"]
        mock_rule.examples.should_match = ["a"]
        mock_rule.examples.should_not_match = ["b"]
        mock_loader.load_rule_from_file.return_value = mock_rule
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["validate", str(sample_rule_file)])

        assert result.exit_code == 0
        assert "passed" in result.output.lower()

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_validate_invalid_rule(self, mock_loader_cls, runner, sample_rule_file):
        """Test validating an invalid rule file."""
        mock_loader = MagicMock()
        mock_loader.validate_file.return_value = (
            False,
            ["Missing required field: detection", "Invalid severity"],
        )
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["validate", str(sample_rule_file)])

        assert result.exit_code == 0  # Command itself succeeds
        assert "failed" in result.output.lower()

    def test_validate_nonexistent_file(self, runner):
        """Test validating a file that doesn't exist."""
        result = runner.invoke(custom_rules, ["validate", "/nonexistent/rule.yaml"])

        # Click's Path(exists=True) will reject the file
        assert result.exit_code != 0


class TestCustomRulesInstall:
    """Tests for raxe rules custom install."""

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_install_valid_rule(self, mock_loader_cls, runner, sample_rule_file):
        """Test installing a valid custom rule."""
        mock_loader = MagicMock()
        mock_loader.validate_file.return_value = (True, [])
        mock_rule = MagicMock()
        mock_rule.rule_id = "custom-001"
        mock_rule.name = "Test Rule"
        mock_rule.versioned_id = "custom-001@1.0.0"
        mock_rule.severity.value = "medium"
        mock_loader.load_rule_from_file.return_value = mock_rule
        # Use MagicMock for custom_rules_dir so / operator works
        mock_dir = MagicMock()
        mock_dest = MagicMock()
        mock_dest.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_dest)
        mock_loader.custom_rules_dir = mock_dir
        mock_loader.save_rule_to_file.return_value = sample_rule_file
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["install", str(sample_rule_file)])

        assert result.exit_code == 0
        assert "installed" in result.output.lower()

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_install_invalid_rule_fails(self, mock_loader_cls, runner, sample_rule_file):
        """Test that installing an invalid rule shows errors."""
        mock_loader = MagicMock()
        mock_loader.validate_file.return_value = (
            False,
            ["Missing field: id"],
        )
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["install", str(sample_rule_file)])

        assert result.exit_code == 0  # Command doesn't crash
        assert "failed" in result.output.lower() or "Missing" in result.output

    def test_install_nonexistent_file(self, runner):
        """Test installing from a nonexistent file."""
        result = runner.invoke(custom_rules, ["install", "/nonexistent/rule.yaml"])
        assert result.exit_code != 0


class TestCustomRulesUninstall:
    """Tests for raxe rules custom uninstall."""

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_uninstall_existing_rule(self, mock_loader_cls, runner, custom_rules_dir):
        """Test uninstalling an existing rule with --yes."""
        mock_loader = MagicMock()
        # Create the rule file on disk so it exists
        rule_file = custom_rules_dir / "custom-001.yaml"
        rule_file.write_text("id: custom-001")
        # Use MagicMock for custom_rules_dir so / operator works
        mock_dir = MagicMock()
        mock_dir.__truediv__ = MagicMock(return_value=rule_file)
        mock_loader.custom_rules_dir = mock_dir
        mock_loader.delete_rule.return_value = True
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["uninstall", "custom-001", "--yes"])

        assert result.exit_code == 0
        assert "uninstalled" in result.output.lower()

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_uninstall_nonexistent_rule(self, mock_loader_cls, runner, tmp_path):
        """Test uninstalling a rule that doesn't exist."""
        mock_loader = MagicMock()
        nonexistent = tmp_path / "custom_rules" / "nonexistent.yaml"
        mock_dir = MagicMock()
        mock_dir.__truediv__ = MagicMock(return_value=nonexistent)
        mock_loader.custom_rules_dir = mock_dir
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["uninstall", "nonexistent", "--yes"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_uninstall_cancelled_by_user(self, mock_loader_cls, runner, custom_rules_dir):
        """Test that uninstall can be cancelled without --yes."""
        mock_loader = MagicMock()
        rule_file = custom_rules_dir / "custom-001.yaml"
        rule_file.write_text("id: custom-001")
        mock_dir = MagicMock()
        mock_dir.__truediv__ = MagicMock(return_value=rule_file)
        mock_loader.custom_rules_dir = mock_dir
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["uninstall", "custom-001"], input="n\n")

        assert result.exit_code == 0 or result.exit_code == 1
        assert "Cancelled" in result.output or "Aborted" in result.output


class TestCustomRulesPackage:
    """Tests for raxe rules custom package."""

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_package_no_rules(self, mock_loader_cls, runner):
        """Test packaging when no rules exist."""
        mock_loader = MagicMock()
        mock_loader.list_custom_rules.return_value = []
        mock_loader_cls.return_value = mock_loader

        result = runner.invoke(custom_rules, ["package"])

        assert result.exit_code == 0
        assert "No custom rules" in result.output

    @patch("raxe.cli.custom_rules.CustomRuleLoader")
    def test_package_with_rules(self, mock_loader_cls, runner, sample_rule_file, tmp_path):
        """Test packaging rules into tar.gz."""
        mock_loader = MagicMock()
        mock_loader.list_custom_rules.return_value = [
            {
                "id": "custom-001",
                "name": "Test Rule",
                "version": "1.0.0",
                "file_path": str(sample_rule_file),
            },
        ]
        mock_loader_cls.return_value = mock_loader

        output_file = tmp_path / "output.tar.gz"
        result = runner.invoke(custom_rules, ["package", "--output", str(output_file)])

        assert result.exit_code == 0
        assert "Packaged" in result.output or "packaged" in result.output.lower()
        assert output_file.exists()
