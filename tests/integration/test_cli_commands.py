"""
Integration tests for CLI commands.

Tests the new CLI enhancements: test, stats, export, and repl commands.
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from raxe.cli.export import export
from raxe.cli.main import cli
from raxe.cli.stats import stats
from raxe.cli.test import test


@pytest.fixture
def cli_runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_config(tmp_path):
    """Create temporary config directory."""
    config_dir = tmp_path / ".raxe"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "config.yaml"
    config_file.write_text(
        """
version: 1.0.0
telemetry:
  enabled: false
"""
    )

    return config_dir


class TestCliMainCommands:
    """Test main CLI command integration."""

    def test_cli_help(self, cli_runner):
        """Test CLI help output."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "RAXE - AI Security for LLMs" in result.output

    def test_cli_version(self, cli_runner):
        """Test CLI version output."""
        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.0.2" in result.output
        assert "RAXE CLI" in result.output

    def test_scan_with_no_color(self, cli_runner):
        """Test scan command with --no-color flag."""
        result = cli_runner.invoke(cli, ["--no-color", "scan", "test prompt"])
        # Should complete without error (may or may not detect threats)
        assert result.exit_code == 0


class TestTestCommand:
    """Test the 'raxe test' command."""

    def test_test_command_basic(self, cli_runner):
        """Test basic execution of test command."""
        result = cli_runner.invoke(test, [])

        # Command should complete
        assert result.exit_code == 0
        assert "Testing RAXE configuration" in result.output

    def test_test_command_checks(self, cli_runner):
        """Test that test command performs all checks."""
        result = cli_runner.invoke(test, [])

        # Should include all check messages
        assert "Checking configuration file" in result.output
        assert "Loading detection rules" in result.output
        assert "Testing cloud connection" in result.output
        assert "Testing local scan" in result.output


class TestStatsCommand:
    """Test the 'raxe stats' command."""

    def test_stats_text_format(self, cli_runner):
        """Test stats command with text format."""
        result = cli_runner.invoke(stats, ["--format", "text"])

        # Should complete successfully
        assert result.exit_code == 0

    def test_stats_json_format(self, cli_runner):
        """Test stats command with JSON format."""
        result = cli_runner.invoke(stats, ["--format", "json"])

        # Should complete successfully
        assert result.exit_code == 0

        # Should be valid JSON
        try:
            json.loads(result.output)
        except json.JSONDecodeError:
            pytest.fail("Stats JSON output is not valid JSON")


class TestExportCommand:
    """Test the 'raxe export' command."""

    def test_export_json_default(self, cli_runner, tmp_path):
        """Test export command with default JSON format."""
        output_file = tmp_path / "export.json"

        result = cli_runner.invoke(export, ["--output", str(output_file)])

        # Should complete successfully
        assert result.exit_code == 0

        # Output file should exist (if there was data to export)
        # Note: May not exist if no scan history

    def test_export_csv_format(self, cli_runner, tmp_path):
        """Test export command with CSV format."""
        output_file = tmp_path / "export.csv"

        result = cli_runner.invoke(export, ["--format", "csv", "--output", str(output_file)])

        # Should complete successfully
        assert result.exit_code == 0

    def test_export_days_parameter(self, cli_runner, tmp_path):
        """Test export command with custom days parameter."""
        output_file = tmp_path / "export.json"

        result = cli_runner.invoke(
            export, ["--days", "7", "--output", str(output_file), "--format", "json"]
        )

        # Should complete successfully
        assert result.exit_code == 0


class TestReplCommand:
    """Test the 'raxe repl' command."""

    def test_repl_exit_command(self, cli_runner):
        """Test REPL with immediate exit."""
        # Simulate user typing 'exit'
        result = cli_runner.invoke(cli, ["repl"], input="exit\n")

        # Should exit cleanly
        assert result.exit_code == 0
        assert "RAXE Interactive Shell" in result.output

    def test_repl_help_command(self, cli_runner):
        """Test REPL help command."""
        # Simulate user typing 'help' then 'exit'
        result = cli_runner.invoke(cli, ["repl"], input="help\nexit\n")

        assert result.exit_code == 0
        assert "Available Commands" in result.output

    def test_repl_scan_command(self, cli_runner):
        """Test REPL scan command."""
        # Simulate user typing 'scan test' then 'exit'
        result = cli_runner.invoke(cli, ["repl"], input="scan test prompt\nexit\n")

        # Should complete without error
        assert result.exit_code == 0


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    def test_init_test_stats_workflow(self, cli_runner, tmp_path):
        """Test typical user workflow: init -> test -> stats."""
        # Step 1: Initialize
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = cli_runner.invoke(cli, ["init", "--no-telemetry"])
            assert result.exit_code == 0

        # Step 2: Test configuration
        result = cli_runner.invoke(test, [])
        assert result.exit_code == 0

        # Step 3: View stats
        result = cli_runner.invoke(stats, [])
        assert result.exit_code == 0

    def test_scan_export_workflow(self, cli_runner, tmp_path):
        """Test scan and export workflow."""
        # Step 1: Perform a scan
        result = cli_runner.invoke(cli, ["scan", "test prompt"])
        assert result.exit_code == 0

        # Step 2: Export results
        output_file = tmp_path / "scans.json"
        result = cli_runner.invoke(export, ["--output", str(output_file)])
        assert result.exit_code == 0


class TestErrorHandling:
    """Test error handling in CLI commands."""

    def test_scan_no_input(self, cli_runner):
        """Test scan command with no input."""
        result = cli_runner.invoke(cli, ["scan"])

        # Should fail with helpful error
        assert result.exit_code != 0

    def test_export_invalid_format(self, cli_runner):
        """Test export with invalid format."""
        result = cli_runner.invoke(export, ["--format", "invalid"])

        # Should fail
        assert result.exit_code != 0
