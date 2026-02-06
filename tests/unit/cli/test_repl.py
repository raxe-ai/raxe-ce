"""Tests for REPL CLI command.

Tests for the `raxe repl` command that launches interactive shell mode.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.repl import repl


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_prompt_toolkit_unavailable():
    """Mock prompt_toolkit as unavailable."""
    with patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", False):
        yield


@pytest.fixture
def mock_interactive_context():
    """Mock an interactive terminal context."""
    ctx = MagicMock()
    ctx.is_interactive = True
    ctx.is_ci = False
    with patch("raxe.cli.repl.get_terminal_context", return_value=ctx):
        yield ctx


@pytest.fixture
def mock_non_interactive_context():
    """Mock a non-interactive terminal context."""
    ctx = MagicMock()
    ctx.is_interactive = False
    ctx.is_ci = False
    with patch("raxe.cli.repl.get_terminal_context", return_value=ctx):
        yield ctx


@pytest.fixture
def mock_ci_context():
    """Mock a CI environment context."""
    ctx = MagicMock()
    ctx.is_interactive = False
    ctx.is_ci = True
    ctx.detected_ci = "GitHub Actions"
    with patch("raxe.cli.repl.get_terminal_context", return_value=ctx):
        yield ctx


class TestReplPromptToolkit:
    """Tests for REPL prompt_toolkit dependency check."""

    def test_repl_requires_prompt_toolkit(self, runner, mock_prompt_toolkit_unavailable):
        """Test that REPL shows error when prompt_toolkit not installed."""
        result = runner.invoke(repl)
        assert result.exit_code != 0
        assert "prompt-toolkit" in result.output or "prompt_toolkit" in result.output


class TestReplNonInteractive:
    """Tests for REPL in non-interactive environments."""

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    def test_repl_rejects_non_interactive(self, runner, mock_non_interactive_context):
        """Test that REPL refuses to start in non-interactive mode."""
        result = runner.invoke(repl)
        assert result.exit_code != 0
        assert "interactive" in result.output.lower()

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    def test_repl_shows_alternatives_in_non_interactive(self, runner, mock_non_interactive_context):
        """Test that non-interactive error shows alternative commands."""
        result = runner.invoke(repl)
        assert "raxe scan" in result.output

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    def test_repl_detects_ci_environment(self, runner, mock_ci_context):
        """Test that REPL detects CI environment and names it."""
        result = runner.invoke(repl)
        assert result.exit_code != 0
        assert "GitHub Actions" in result.output


class TestReplInteractive:
    """Tests for REPL in interactive mode."""

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed")
    def test_repl_exits_on_exit_command(
        self, mock_flush, mock_logo, runner, mock_interactive_context
    ):
        """Test that typing 'exit' exits the REPL."""
        mock_session = MagicMock()
        mock_session.prompt = MagicMock(side_effect=["exit"])

        with patch("raxe.cli.repl.PromptSession", return_value=mock_session):
            with patch("raxe.cli.repl.FileHistory"):
                with patch("raxe.cli.repl.Raxe"):
                    result = runner.invoke(repl)

        assert result.exit_code == 0
        assert "Goodbye" in result.output

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed")
    def test_repl_exits_on_quit_command(
        self, mock_flush, mock_logo, runner, mock_interactive_context
    ):
        """Test that typing 'quit' exits the REPL."""
        mock_session = MagicMock()
        mock_session.prompt = MagicMock(side_effect=["quit"])

        with patch("raxe.cli.repl.PromptSession", return_value=mock_session):
            with patch("raxe.cli.repl.FileHistory"):
                with patch("raxe.cli.repl.Raxe"):
                    result = runner.invoke(repl)

        assert result.exit_code == 0
        assert "Goodbye" in result.output

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed")
    def test_repl_handles_empty_input(
        self, mock_flush, mock_logo, runner, mock_interactive_context
    ):
        """Test that empty input is skipped without error."""
        mock_session = MagicMock()
        mock_session.prompt = MagicMock(side_effect=["", "   ", "exit"])

        with patch("raxe.cli.repl.PromptSession", return_value=mock_session):
            with patch("raxe.cli.repl.FileHistory"):
                with patch("raxe.cli.repl.Raxe"):
                    result = runner.invoke(repl)

        assert result.exit_code == 0
        assert "Goodbye" in result.output

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed")
    def test_repl_scans_input(self, mock_flush, mock_logo, runner, mock_interactive_context):
        """Test that 'scan <text>' invokes the scanner."""
        mock_session = MagicMock()
        mock_session.prompt = MagicMock(side_effect=["scan test prompt", "exit"])

        mock_raxe = MagicMock()
        mock_result = MagicMock()
        mock_result.scan_result.has_threats = False
        mock_raxe.scan.return_value = mock_result

        with patch("raxe.cli.repl.PromptSession", return_value=mock_session):
            with patch("raxe.cli.repl.FileHistory"):
                with patch("raxe.cli.repl.Raxe", return_value=mock_raxe):
                    with patch("raxe.cli.repl.display_scan_result"):
                        result = runner.invoke(repl)

        assert result.exit_code == 0
        mock_raxe.scan.assert_called_once_with("test prompt", entry_point="cli")

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed")
    def test_repl_exits_on_eof(self, mock_flush, mock_logo, runner, mock_interactive_context):
        """Test that EOF (Ctrl+D) exits the REPL."""
        mock_session = MagicMock()
        mock_session.prompt = MagicMock(side_effect=EOFError)

        with patch("raxe.cli.repl.PromptSession", return_value=mock_session):
            with patch("raxe.cli.repl.FileHistory"):
                with patch("raxe.cli.repl.Raxe"):
                    result = runner.invoke(repl)

        assert result.exit_code == 0
        assert "Goodbye" in result.output

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed")
    def test_repl_shows_help(self, mock_flush, mock_logo, runner, mock_interactive_context):
        """Test that 'help' command displays help text."""
        mock_session = MagicMock()
        mock_session.prompt = MagicMock(side_effect=["help", "exit"])

        with patch("raxe.cli.repl.PromptSession", return_value=mock_session):
            with patch("raxe.cli.repl.FileHistory"):
                with patch("raxe.cli.repl.Raxe"):
                    result = runner.invoke(repl)

        assert result.exit_code == 0
        assert "Available Commands" in result.output

    @patch("raxe.cli.repl.PROMPT_TOOLKIT_AVAILABLE", True)
    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.infrastructure.telemetry.flush_helper.ensure_telemetry_flushed")
    def test_repl_unknown_command(self, mock_flush, mock_logo, runner, mock_interactive_context):
        """Test that unknown commands show error message."""
        mock_session = MagicMock()
        mock_session.prompt = MagicMock(side_effect=["foobar", "exit"])

        with patch("raxe.cli.repl.PromptSession", return_value=mock_session):
            with patch("raxe.cli.repl.FileHistory"):
                with patch("raxe.cli.repl.Raxe"):
                    result = runner.invoke(repl)

        assert result.exit_code == 0
        assert "Unknown command" in result.output
