"""Tests for help command."""

import pytest
from click.testing import CliRunner

from raxe.cli.main import cli


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestHelpCommand:
    """Test suite for raxe help command."""

    def test_help_no_args_shows_topics(self, runner):
        """No args shows help topics overview."""
        result = runner.invoke(cli, ["help"])
        assert result.exit_code == 0
        assert "Help Topics" in result.output

    def test_help_list_flag_shows_categories(self, runner):
        """--list shows all error code categories."""
        result = runner.invoke(cli, ["help", "--list"])
        assert result.exit_code == 0
        assert "CFG" in result.output
        assert "RULE" in result.output
        assert "SEC" in result.output
        assert "DB" in result.output
        assert "VAL" in result.output
        assert "INFRA" in result.output

    def test_help_error_code_shows_details(self, runner):
        """Error code shows detailed help."""
        result = runner.invoke(cli, ["help", "CFG-001"])
        assert result.exit_code == 0
        assert "CFG-001" in result.output
        assert "Configuration Not Found" in result.output
        assert "raxe init" in result.output

    def test_help_error_code_case_insensitive(self, runner):
        """Error codes work case-insensitively."""
        result = runner.invoke(cli, ["help", "cfg-001"])
        assert result.exit_code == 0
        assert "CFG-001" in result.output

    def test_help_unknown_error_code_suggests(self, runner):
        """Unknown error code suggests similar codes."""
        result = runner.invoke(cli, ["help", "CFG-999"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_help_category_flag(self, runner):
        """--category filters to category."""
        result = runner.invoke(cli, ["help", "--category", "CFG"])
        assert result.exit_code == 0
        assert "CFG-001" in result.output
        assert "CFG-002" in result.output
        # Should not show other categories
        assert "RULE-100" not in result.output

    def test_help_category_unknown(self, runner):
        """Unknown category shows error."""
        result = runner.invoke(cli, ["help", "--category", "UNKNOWN"])
        assert result.exit_code == 0
        assert "Unknown category" in result.output

    def test_help_shows_description(self, runner):
        """Help shows error description."""
        result = runner.invoke(cli, ["help", "CFG-001"])
        assert result.exit_code == 0
        assert "Description" in result.output
        assert "configuration file" in result.output.lower()

    def test_help_shows_causes(self, runner):
        """Help shows common causes."""
        result = runner.invoke(cli, ["help", "CFG-001"])
        assert result.exit_code == 0
        assert "Common Causes" in result.output
        assert "First time running RAXE" in result.output

    def test_help_shows_fix(self, runner):
        """Help shows fix command."""
        result = runner.invoke(cli, ["help", "CFG-001"])
        assert result.exit_code == 0
        assert "Fix" in result.output
        assert "raxe init" in result.output

    def test_help_shows_examples(self, runner):
        """Help shows examples."""
        result = runner.invoke(cli, ["help", "CFG-001"])
        assert result.exit_code == 0
        assert "Examples" in result.output

    def test_help_shows_see_also(self, runner):
        """Help shows related errors."""
        result = runner.invoke(cli, ["help", "CFG-001"])
        assert result.exit_code == 0
        assert "See Also" in result.output
        assert "CFG-002" in result.output

    def test_help_shows_doc_url(self, runner):
        """Help shows documentation URL."""
        result = runner.invoke(cli, ["help", "CFG-001"])
        assert result.exit_code == 0
        assert "Documentation" in result.output
        assert "docs.raxe.ai" in result.output


class TestHelpTopicDelegation:
    """Test help command delegates to subcommand help."""

    def test_help_scan_shows_scan_help(self, runner):
        """Help for command shows command's help."""
        result = runner.invoke(cli, ["help", "scan"])
        assert result.exit_code == 0
        # Should show scan command's help
        assert "scan" in result.output.lower()

    def test_help_unknown_topic(self, runner):
        """Unknown topic shows error."""
        result = runner.invoke(cli, ["help", "notacommand"])
        assert result.exit_code == 0
        assert "Unknown topic" in result.output
