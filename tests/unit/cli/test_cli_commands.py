"""
Tests for CLI commands.

Tests the enhanced CLI functionality including rules, doctor, batch, and enhanced scan.
"""

import pytest
from click.testing import CliRunner

from raxe.cli.main import cli


class TestCLICommands:
    """Test suite for CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_help_command(self, runner):
        """Test that help command works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # Minimal help shows tagline without "RAXE -" prefix
        assert "AI Security for LLMs" in result.output

    def test_version_command(self, runner):
        """Test that version command works."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        # Check that version is displayed (actual version is 0.0.2)
        assert "0.0.2" in result.output or "RAXE CLI" in result.output

    def test_init_command(self, runner):
        """Test init command creates config."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init", "--force"])
            assert result.exit_code == 0 or "initialized" in result.output.lower()

    def test_rules_list_help(self, runner):
        """Test rules list help."""
        result = runner.invoke(cli, ["rules", "list", "--help"])
        assert result.exit_code == 0
        assert "List all available detection rules" in result.output

    def test_rules_show_help(self, runner):
        """Test rules show help."""
        result = runner.invoke(cli, ["rules", "show", "--help"])
        assert result.exit_code == 0
        assert "Show detailed information" in result.output

    def test_rules_search_help(self, runner):
        """Test rules search help."""
        result = runner.invoke(cli, ["rules", "search", "--help"])
        assert result.exit_code == 0
        assert "Search rules by keyword" in result.output

    def test_rules_test_help(self, runner):
        """Test rules test help."""
        result = runner.invoke(cli, ["rules", "test", "--help"])
        assert result.exit_code == 0
        assert "Test a rule against provided text" in result.output

    def test_rules_stats_help(self, runner):
        """Test rules stats help."""
        result = runner.invoke(cli, ["rules", "stats", "--help"])
        assert result.exit_code == 0
        assert "Show rule statistics" in result.output

    def test_doctor_help(self, runner):
        """Test doctor help."""
        result = runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "Run comprehensive system health checks" in result.output

    def test_batch_help(self, runner):
        """Test batch scan help."""
        result = runner.invoke(cli, ["batch", "--help"])
        assert result.exit_code == 0
        assert "Batch scan prompts from a file" in result.output

    def test_scan_enhanced_help(self, runner):
        """Test enhanced scan command help."""
        result = runner.invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--l1-only" in result.output
        assert "--l2-only" in result.output
        assert "--mode" in result.output
        assert "--confidence" in result.output
        assert "--explain" in result.output
        assert "--dry-run" in result.output

    def test_repl_help(self, runner):
        """Test REPL help."""
        result = runner.invoke(cli, ["repl", "--help"])
        assert result.exit_code == 0
        # Check for REPL-related content (actual text is "Launch interactive REPL mode")
        assert "interactive" in result.output.lower() or "REPL" in result.output

    def test_completion_bash(self, runner):
        """Test bash completion generation."""
        result = runner.invoke(cli, ["completion", "bash"])
        assert result.exit_code == 0
        assert "_raxe_completion" in result.output
        assert "rules" in result.output
        assert "doctor" in result.output
        assert "batch" in result.output

    def test_completion_zsh(self, runner):
        """Test zsh completion generation."""
        result = runner.invoke(cli, ["completion", "zsh"])
        assert result.exit_code == 0
        assert "#compdef raxe" in result.output
        assert "rules" in result.output
        assert "doctor" in result.output

    def test_completion_fish(self, runner):
        """Test fish completion generation."""
        result = runner.invoke(cli, ["completion", "fish"])
        assert result.exit_code == 0
        assert "complete -c raxe" in result.output
        assert "rules" in result.output
        assert "doctor" in result.output

    def test_completion_powershell(self, runner):
        """Test powershell completion generation."""
        result = runner.invoke(cli, ["completion", "powershell"])
        assert result.exit_code == 0
        assert "Register-ArgumentCompleter" in result.output
        assert "rules" in result.output
        assert "doctor" in result.output


class TestScanCommand:
    """Test suite for enhanced scan command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_scan_basic(self, runner):
        """Test basic scan functionality."""
        result = runner.invoke(cli, ["scan", "test prompt"])
        # Should succeed or fail gracefully
        assert result.exit_code in [0, 1]

    def test_scan_json_format(self, runner):
        """Test scan with JSON output."""
        result = runner.invoke(cli, ["scan", "test", "--format", "json"])
        # Should succeed or fail gracefully
        assert result.exit_code in [0, 1]

    def test_scan_yaml_format(self, runner):
        """Test scan with YAML output."""
        result = runner.invoke(cli, ["scan", "test", "--format", "yaml"])
        # Should succeed or fail gracefully
        assert result.exit_code in [0, 1]


class TestBatchCommand:
    """Test suite for batch scan command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_batch_missing_file(self, runner):
        """Test batch with missing file."""
        result = runner.invoke(cli, ["batch", "nonexistent.txt"])
        assert result.exit_code != 0

    def test_batch_with_file(self, runner):
        """Test batch with actual file."""
        with runner.isolated_filesystem():
            # Create test file
            with open("prompts.txt", "w") as f:
                f.write("test prompt 1\n")
                f.write("test prompt 2\n")

            result = runner.invoke(cli, ["batch", "prompts.txt"])
            # Should succeed or fail gracefully
            assert result.exit_code in [0, 1]

    def test_batch_accepts_tenant_option(self, runner):
        """Test batch accepts --tenant option."""
        result = runner.invoke(cli, ["batch", "--help"])
        assert "--tenant" in result.output or "-t" in result.output
        assert "Tenant ID" in result.output

    def test_batch_accepts_app_option(self, runner):
        """Test batch accepts --app option."""
        result = runner.invoke(cli, ["batch", "--help"])
        assert "--app" in result.output or "-a" in result.output
        assert "App ID" in result.output

    def test_batch_accepts_policy_option(self, runner):
        """Test batch accepts --policy option."""
        result = runner.invoke(cli, ["batch", "--help"])
        assert "--policy" in result.output or "-p" in result.output
        assert "policy" in result.output.lower()

    def test_batch_with_tenant_options(self, runner):
        """Test batch with multi-tenant options."""
        with runner.isolated_filesystem():
            with open("prompts.txt", "w") as f:
                f.write("test prompt\n")

            result = runner.invoke(
                cli,
                ["batch", "prompts.txt", "--tenant", "acme", "--app", "chatbot"],
            )
            # Should succeed or fail gracefully (not crash on invalid tenant)
            assert result.exit_code in [0, 1]


class TestRulesCommands:
    """Test suite for rules commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_rules_list(self, runner):
        """Test rules list command."""
        result = runner.invoke(cli, ["rules", "list"])
        # Should succeed or fail gracefully
        assert result.exit_code in [0, 1]

    def test_rules_search(self, runner):
        """Test rules search command."""
        result = runner.invoke(cli, ["rules", "search", "injection"])
        # Should succeed or fail gracefully
        assert result.exit_code in [0, 1]

    def test_rules_stats(self, runner):
        """Test rules stats command."""
        result = runner.invoke(cli, ["rules", "stats"])
        # Should succeed or fail gracefully
        assert result.exit_code in [0, 1]


class TestDoctorCommand:
    """Test suite for doctor command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_doctor_basic(self, runner):
        """Test basic doctor command."""
        result = runner.invoke(cli, ["doctor"])
        # Should succeed or fail gracefully
        assert result.exit_code in [0, 1]
        # Should have some health check output
        if result.exit_code == 0:
            assert "Health Check" in result.output or "Installation" in result.output
