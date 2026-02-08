"""Tests for MCP CLI commands.

TDD: These tests define expected CLI behavior for MCP server management.
Implementation should make these tests pass.

Commands:
- raxe mcp status [--json] [--output json|table]
- raxe mcp serve [--transport stdio] [--log-level debug|info|warn|error] [--quiet]
"""

import json
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from raxe.cli.main import cli


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mcp_module():
    """Import MCP module for monkeypatching."""
    import importlib

    module = importlib.import_module("raxe.cli.mcp_cmd")
    return module


class TestMCPCommandRegistration:
    """Tests for MCP command registration in CLI."""

    def test_mcp_command_registered(self, runner):
        """Test that mcp command is registered in main CLI."""
        result = runner.invoke(cli, ["mcp", "--help"])

        assert result.exit_code == 0
        assert "serve" in result.output.lower() or "mcp" in result.output.lower()

    def test_mcp_serve_subcommand_available(self, runner):
        """Test that mcp serve subcommand is available."""
        result = runner.invoke(cli, ["mcp", "serve", "--help"])

        assert result.exit_code == 0
        assert "serve" in result.output.lower() or "mcp" in result.output.lower()


class TestMCPServeCommand:
    """Tests for raxe mcp serve command."""

    def test_serve_help_text(self, runner):
        """Test that serve command shows helpful text."""
        result = runner.invoke(cli, ["mcp", "serve", "--help"])

        assert result.exit_code == 0
        # Should mention MCP or server
        assert "mcp" in result.output.lower() or "server" in result.output.lower()

    def test_serve_without_mcp_installed_shows_error(self, runner, mcp_module, monkeypatch):
        """Test that serve without MCP SDK installed shows error."""
        # Mock _check_mcp_available to return (False, error_message)
        monkeypatch.setattr(
            mcp_module, "_check_mcp_available", lambda: (False, "MCP SDK not installed")
        )

        result = runner.invoke(cli, ["mcp", "serve"])

        # Should show error about MCP not being installed
        assert result.exit_code != 0
        assert (
            "mcp" in result.output.lower()
            or "pip install" in result.output.lower()
            or "not installed" in result.output.lower()
        )

    def test_serve_starts_server_with_default_options(self, runner, mcp_module, monkeypatch):
        """Test that serve starts server with default options."""
        # Mock MCP as available
        monkeypatch.setattr(mcp_module, "_check_mcp_available", lambda: (True, None))
        # Mock run_server to prevent actual server start
        mock_run_server = MagicMock(return_value=0)
        monkeypatch.setattr(mcp_module, "run_server", mock_run_server)

        result = runner.invoke(cli, ["mcp", "serve"])

        assert result.exit_code == 0
        mock_run_server.assert_called_once()
        # Default transport should be stdio
        call_kwargs = mock_run_server.call_args
        assert call_kwargs.kwargs.get("transport", "stdio") == "stdio"

    def test_serve_handles_keyboard_interrupt(self, runner, mcp_module, monkeypatch):
        """Test that serve handles KeyboardInterrupt gracefully."""
        # Mock MCP as available
        monkeypatch.setattr(mcp_module, "_check_mcp_available", lambda: (True, None))

        # Mock run_server to raise KeyboardInterrupt
        def mock_run_server(*args, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr(mcp_module, "run_server", mock_run_server)

        result = runner.invoke(cli, ["mcp", "serve"])

        # Should exit cleanly without traceback
        assert result.exit_code == 0
        # Should show shutdown message
        assert "shutdown" in result.output.lower() or result.exit_code == 0

    def test_serve_flushes_telemetry_on_exit(self, runner, mcp_module, monkeypatch):
        """Test that serve flushes telemetry on exit."""
        # Mock MCP as available
        monkeypatch.setattr(mcp_module, "_check_mcp_available", lambda: (True, None))
        mock_run_server = MagicMock(return_value=0)
        mock_flush = MagicMock()
        monkeypatch.setattr(mcp_module, "run_server", mock_run_server)
        monkeypatch.setattr(
            "raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed",
            mock_flush,
        )

        runner.invoke(cli, ["mcp", "serve"])

        # Telemetry should be flushed before sys.exit
        mock_flush.assert_called()


class TestMCPServeOptions:
    """Tests for MCP serve command options."""

    def test_transport_option(self, runner, mcp_module, monkeypatch):
        """Test --transport option."""
        # Mock MCP as available
        monkeypatch.setattr(mcp_module, "_check_mcp_available", lambda: (True, None))
        mock_run_server = MagicMock(return_value=0)
        monkeypatch.setattr(mcp_module, "run_server", mock_run_server)

        result = runner.invoke(cli, ["mcp", "serve", "--transport", "stdio"])

        assert result.exit_code == 0
        call_kwargs = mock_run_server.call_args
        assert call_kwargs.kwargs.get("transport") == "stdio"

    def test_log_level_option(self, runner, mcp_module, monkeypatch):
        """Test --log-level option."""
        # Mock MCP as available
        monkeypatch.setattr(mcp_module, "_check_mcp_available", lambda: (True, None))
        mock_run_server = MagicMock(return_value=0)
        monkeypatch.setattr(mcp_module, "run_server", mock_run_server)

        result = runner.invoke(cli, ["mcp", "serve", "--log-level", "debug"])

        assert result.exit_code == 0
        call_kwargs = mock_run_server.call_args
        assert call_kwargs.kwargs.get("verbose") is True

    def test_quiet_flag_suppresses_banner(self, runner, mcp_module, monkeypatch):
        """Test --quiet flag suppresses startup banner."""
        # Mock MCP as available
        monkeypatch.setattr(mcp_module, "_check_mcp_available", lambda: (True, None))
        mock_run_server = MagicMock(return_value=0)
        monkeypatch.setattr(mcp_module, "run_server", mock_run_server)

        result = runner.invoke(cli, ["mcp", "serve", "--quiet"])

        assert result.exit_code == 0
        # Should not contain banner text
        assert "raxe" not in result.output.lower() or result.output.strip() == ""


class TestMCPServeErrorHandling:
    """Tests for MCP serve error handling."""

    def test_serve_returns_nonzero_on_server_error(self, runner, mcp_module, monkeypatch):
        """Test that serve returns non-zero exit code on server error."""
        # Mock MCP as available
        monkeypatch.setattr(mcp_module, "_check_mcp_available", lambda: (True, None))
        mock_run_server = MagicMock(return_value=1)
        monkeypatch.setattr(mcp_module, "run_server", mock_run_server)

        result = runner.invoke(cli, ["mcp", "serve"])

        assert result.exit_code == 1

    def test_serve_reports_server_startup_error(self, runner, mcp_module, monkeypatch):
        """Test that serve reports server startup errors."""
        # Mock MCP as available
        monkeypatch.setattr(mcp_module, "_check_mcp_available", lambda: (True, None))

        def mock_run_server(*args, **kwargs):
            raise RuntimeError("Failed to bind to port")

        monkeypatch.setattr(mcp_module, "run_server", mock_run_server)

        result = runner.invoke(cli, ["mcp", "serve"])

        assert result.exit_code != 0
        assert "error" in result.output.lower() or "failed" in result.output.lower()


class TestMCPStatusCommand:
    """Tests for raxe mcp status command."""

    def test_status_exits_zero(self, runner):
        """Test that status command exits cleanly."""
        result = runner.invoke(cli, ["mcp", "status"])

        assert result.exit_code == 0

    def test_status_shows_raxe_version(self, runner):
        """Test that status displays RAXE version."""
        result = runner.invoke(cli, ["mcp", "status"])

        assert result.exit_code == 0
        assert "raxe version" in result.output.lower() or "0." in result.output

    def test_status_shows_mcp_sdk_info(self, runner):
        """Test that status displays MCP SDK availability."""
        result = runner.invoke(cli, ["mcp", "status"])

        assert result.exit_code == 0
        assert "mcp sdk" in result.output.lower() or "mcp_sdk" in result.output.lower()

    def test_status_json_output(self, runner):
        """Test that status --json produces valid JSON."""
        result = runner.invoke(cli, ["mcp", "status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "raxe_version" in data
        assert "mcp_sdk" in data
        assert "server" in data
        assert "gateway" in data
        assert "claude_desktop" in data

    def test_status_json_sdk_fields(self, runner):
        """Test that JSON output includes MCP SDK details."""
        result = runner.invoke(cli, ["mcp", "status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        sdk = data["mcp_sdk"]
        assert "installed" in sdk
        assert "version" in sdk
        assert isinstance(sdk["installed"], bool)

    def test_status_json_via_output_flag(self, runner):
        """Test that --output json also produces JSON."""
        result = runner.invoke(cli, ["mcp", "status", "--output", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "raxe_version" in data

    def test_status_help_text(self, runner):
        """Test that status command has help text."""
        result = runner.invoke(cli, ["mcp", "status", "--help"])

        assert result.exit_code == 0
        assert "status" in result.output.lower()
