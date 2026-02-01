"""Tests for raxe serve CLI command.

Tests the JSON-RPC server command for integration with AI platforms like OpenClaw.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from raxe.cli.main import cli

if TYPE_CHECKING:
    pass


class TestServeCommandRegistration:
    """Test that serve command is properly registered."""

    def test_serve_command_registered(self):
        """Test serve command is registered with CLI."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help-all"])

        assert result.exit_code == 0
        # serve command should appear in help output
        assert "serve" in result.output

    def test_serve_help_text(self):
        """Test serve command has proper help text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])

        assert result.exit_code == 0
        assert "JSON-RPC" in result.output
        assert "server" in result.output.lower()


class TestServeCommand:
    """Test serve command behavior."""

    def test_serve_default_mode_is_jsonrpc(self):
        """Test default mode is jsonrpc."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])

        assert result.exit_code == 0
        # Help should show default mode is jsonrpc
        assert "jsonrpc" in result.output.lower()

    @patch("raxe.infrastructure.jsonrpc.server.JsonRpcServer")
    @patch("raxe.infrastructure.jsonrpc.transports.stdio.StdioTransport")
    @patch("raxe.application.jsonrpc.dispatcher.JsonRpcDispatcher")
    @patch("raxe.application.jsonrpc.handlers.register_handlers")
    @patch("raxe.sdk.client.Raxe")
    def test_serve_starts_server(
        self,
        mock_raxe_cls: MagicMock,
        mock_register_handlers: MagicMock,
        mock_dispatcher_cls: MagicMock,
        mock_transport_cls: MagicMock,
        mock_server_cls: MagicMock,
    ):
        """Test serve command starts the JSON-RPC server."""
        # Setup mocks
        mock_raxe = MagicMock()
        mock_raxe.stats = {"rules_loaded": 100}
        mock_raxe_cls.return_value = mock_raxe

        mock_dispatcher = MagicMock()
        mock_dispatcher_cls.return_value = mock_dispatcher

        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport

        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        runner = CliRunner()
        runner.invoke(cli, ["serve", "--quiet"], input="")

        # Verify Raxe client was created
        mock_raxe_cls.assert_called_once()

        # Verify handlers were registered
        mock_register_handlers.assert_called_once_with(mock_raxe)

        # Verify transport was created
        mock_transport_cls.assert_called_once()

        # Verify dispatcher was created
        mock_dispatcher_cls.assert_called_once()

        # Verify server was created with transport and dispatcher
        mock_server_cls.assert_called_once()

        # Verify server.start() was called
        mock_server.start.assert_called_once()

    @patch("raxe.infrastructure.jsonrpc.server.JsonRpcServer")
    @patch("raxe.infrastructure.jsonrpc.transports.stdio.StdioTransport")
    @patch("raxe.application.jsonrpc.dispatcher.JsonRpcDispatcher")
    @patch("raxe.application.jsonrpc.handlers.register_handlers")
    @patch("raxe.sdk.client.Raxe")
    def test_serve_handles_keyboard_interrupt(
        self,
        mock_raxe_cls: MagicMock,
        mock_register_handlers: MagicMock,
        mock_dispatcher_cls: MagicMock,
        mock_transport_cls: MagicMock,
        mock_server_cls: MagicMock,
    ):
        """Test serve command handles KeyboardInterrupt gracefully."""
        mock_raxe = MagicMock()
        mock_raxe.stats = {"rules_loaded": 100}
        mock_raxe_cls.return_value = mock_raxe

        mock_server = MagicMock()
        mock_server.start.side_effect = KeyboardInterrupt()
        mock_server_cls.return_value = mock_server

        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--quiet"])

        # Should exit cleanly (not with error)
        assert result.exit_code == 0

    @patch("raxe.infrastructure.jsonrpc.server.JsonRpcServer")
    @patch("raxe.infrastructure.jsonrpc.transports.stdio.StdioTransport")
    @patch("raxe.application.jsonrpc.dispatcher.JsonRpcDispatcher")
    @patch("raxe.application.jsonrpc.handlers.register_handlers")
    @patch("raxe.sdk.client.Raxe")
    def test_serve_shows_version_on_start(
        self,
        mock_raxe_cls: MagicMock,
        mock_register_handlers: MagicMock,
        mock_dispatcher_cls: MagicMock,
        mock_transport_cls: MagicMock,
        mock_server_cls: MagicMock,
    ):
        """Test serve command shows version on startup."""
        mock_raxe = MagicMock()
        mock_raxe.stats = {"rules_loaded": 100}
        mock_raxe_cls.return_value = mock_raxe

        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        runner = CliRunner()
        result = runner.invoke(cli, ["serve"])

        # Should show version information
        # Note: The banner goes to stderr, which is mixed in by CliRunner
        assert "RAXE" in result.output
        assert "JSON-RPC" in result.output


class TestServeOptions:
    """Test serve command options."""

    def test_serve_mode_option(self):
        """Test --mode option is available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])

        assert result.exit_code == 0
        assert "--mode" in result.output

    def test_serve_log_level_option(self):
        """Test --log-level option is available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])

        assert result.exit_code == 0
        assert "--log-level" in result.output

    def test_serve_quiet_option(self):
        """Test --quiet option is available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])

        assert result.exit_code == 0
        assert "--quiet" in result.output

    @patch("raxe.infrastructure.jsonrpc.server.JsonRpcServer")
    @patch("raxe.infrastructure.jsonrpc.transports.stdio.StdioTransport")
    @patch("raxe.application.jsonrpc.dispatcher.JsonRpcDispatcher")
    @patch("raxe.application.jsonrpc.handlers.register_handlers")
    @patch("raxe.sdk.client.Raxe")
    def test_serve_quiet_suppresses_banner(
        self,
        mock_raxe_cls: MagicMock,
        mock_register_handlers: MagicMock,
        mock_dispatcher_cls: MagicMock,
        mock_transport_cls: MagicMock,
        mock_server_cls: MagicMock,
    ):
        """Test --quiet option suppresses startup banner."""
        mock_raxe = MagicMock()
        mock_raxe.stats = {"rules_loaded": 100}
        mock_raxe_cls.return_value = mock_raxe

        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--quiet"])

        # With --quiet, should not show banner
        assert "Ready to accept requests" not in result.output


class TestServeIntegration:
    """Integration tests for serve command (no mocks)."""

    def test_serve_with_single_request_via_stdin(self):
        """Test serve processes a single JSON-RPC request from stdin."""
        # Create a version request
        request = json.dumps({"jsonrpc": "2.0", "id": "test-1", "method": "version", "params": {}})

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["serve", "--quiet"],
            input=request + "\n",
        )

        # Command should complete (EOF after single request)
        assert result.exit_code == 0

        # Output should contain JSON-RPC response
        # Extract just the JSON line (skip any other output)
        lines = result.output.strip().split("\n")
        json_lines = [line for line in lines if line.strip().startswith("{")]

        assert len(json_lines) >= 1, f"No JSON response found. Output: {result.output}"

        response = json.loads(json_lines[0])
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-1"
        assert "result" in response
        assert "version" in response["result"]

    def test_serve_handles_invalid_json(self):
        """Test serve handles invalid JSON gracefully."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["serve", "--quiet"],
            input="not valid json\n",
        )

        # Should complete without crashing
        assert result.exit_code == 0

        # Output should contain error response
        lines = result.output.strip().split("\n")
        json_lines = [line for line in lines if line.strip().startswith("{")]

        if json_lines:
            response = json.loads(json_lines[0])
            assert response["jsonrpc"] == "2.0"
            assert "error" in response

    def test_serve_handles_method_not_found(self):
        """Test serve handles unknown method."""
        request = json.dumps(
            {"jsonrpc": "2.0", "id": "test-2", "method": "unknown_method", "params": {}}
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["serve", "--quiet"],
            input=request + "\n",
        )

        # Should complete without crashing
        assert result.exit_code == 0

        # Output should contain error response
        lines = result.output.strip().split("\n")
        json_lines = [line for line in lines if line.strip().startswith("{")]

        assert len(json_lines) >= 1, f"No JSON response found. Output: {result.output}"

        response = json.loads(json_lines[0])
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-2"
        assert "error" in response
        assert response["error"]["code"] == -32601  # Method not found

    def test_serve_scan_method(self):
        """Test serve can process a scan request."""
        request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "scan-1",
                "method": "scan",
                "params": {"prompt": "Hello world"},
            }
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["serve", "--quiet"],
            input=request + "\n",
        )

        # Should complete without crashing
        assert result.exit_code == 0

        # Output should contain response
        lines = result.output.strip().split("\n")
        json_lines = [line for line in lines if line.strip().startswith("{")]

        assert len(json_lines) >= 1, f"No JSON response found. Output: {result.output}"

        response = json.loads(json_lines[0])
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "scan-1"
        assert "result" in response
        # Result should have scan data
        assert "has_threats" in response["result"]
