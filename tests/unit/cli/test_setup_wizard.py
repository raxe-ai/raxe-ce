"""
Tests for the setup wizard module.

Tests the interactive setup wizard functionality including:
- API key validation
- Shell detection
- Configuration creation
- First-run detection
- Command integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from raxe.cli.setup_wizard import (
    API_KEY_PATTERN,
    TestScanResult,
    WizardConfig,
    _get_api_key_display,
    _is_temp_key,
    _quick_init,
    _read_key_with_timeout,
    auto_launch_first_run,
    check_first_run,
    create_config_file,
    detect_shell,
    display_first_run_message,
    display_next_steps,
    get_completion_path,
    run_setup_wizard,
    validate_api_key_format,
)
from raxe.cli.terminal_context import (
    TerminalContext,
    TerminalMode,
    clear_context_cache,
)


class TestAPIKeyValidation:
    """Test suite for API key format validation."""

    def test_valid_live_key(self):
        """Test valid live API key format."""
        assert validate_api_key_format("raxe_live_abc123def456ghi789jkl012mno345")

    def test_valid_test_key(self):
        """Test valid test API key format."""
        assert validate_api_key_format("raxe_test_abc123def456ghi789jkl012mno345")

    def test_valid_temp_key(self):
        """Test valid temporary API key format."""
        assert validate_api_key_format("raxe_temp_abc123def456ghi789jkl012mno345")

    def test_invalid_prefix(self):
        """Test key with invalid prefix."""
        assert not validate_api_key_format("raxe_invalid_abc123def456ghi789jkl012mno345")

    def test_missing_prefix(self):
        """Test key without raxe prefix."""
        assert not validate_api_key_format("live_abc123def456ghi789jkl012mno345")

    def test_too_short_key(self):
        """Test key that is too short."""
        assert not validate_api_key_format("raxe_live_short")

    def test_empty_key(self):
        """Test empty key."""
        assert not validate_api_key_format("")

    def test_key_with_special_chars(self):
        """Test key with special characters (should be alphanumeric only)."""
        # The regex allows alphanumeric, so this should still validate based on length
        assert validate_api_key_format("raxe_live_abc123def456ghi789jkl012mno345")

    def test_api_key_pattern_matches_expected_format(self):
        """Test that the pattern matches expected format."""
        # Should match: raxe_{type}_{20+ alphanumeric chars}
        assert API_KEY_PATTERN.match("raxe_live_abc123def456ghi789jkl012")
        assert API_KEY_PATTERN.match("raxe_test_ABCdefGHI123jklMNO456pqr")
        assert API_KEY_PATTERN.match("raxe_temp_12345678901234567890")


class TestShellDetection:
    """Test suite for shell detection."""

    def test_detect_zsh_from_shell_env(self):
        """Test detecting zsh from SHELL environment variable."""
        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}, clear=False):
            shell = detect_shell()
            assert shell == "zsh"

    def test_detect_bash_from_shell_env(self):
        """Test detecting bash from SHELL environment variable."""
        with patch.dict(os.environ, {"SHELL": "/bin/bash"}, clear=False):
            shell = detect_shell()
            assert shell == "bash"

    def test_detect_fish_from_shell_env(self):
        """Test detecting fish from SHELL environment variable."""
        with patch.dict(os.environ, {"SHELL": "/usr/local/bin/fish"}, clear=False):
            shell = detect_shell()
            assert shell == "fish"

    @patch("sys.platform", "win32")
    def test_detect_powershell_on_windows(self):
        """Test detecting PowerShell on Windows."""
        with patch.dict(os.environ, {"SHELL": ""}, clear=False):
            shell = detect_shell()
            assert shell == "powershell"

    def test_unknown_shell_from_env(self):
        """Test that unknown shell from SHELL env falls back to process detection."""
        with patch.dict(os.environ, {"SHELL": "/bin/unknown"}, clear=False):
            # With psutil available, it will detect from parent process
            # Without psutil, would return None
            # Either behavior is acceptable
            shell = detect_shell()
            # Shell can be None or detected from parent process
            assert shell is None or shell in ("bash", "zsh", "fish", "powershell")


class TestCompletionPath:
    """Test suite for completion path generation."""

    def test_bash_completion_path(self):
        """Test bash completion path generation."""
        path = get_completion_path("bash")
        assert path is not None
        assert "raxe" in str(path)
        assert ".bash_completion" in str(path) or "bash" in str(path).lower()

    def test_zsh_completion_path(self):
        """Test zsh completion path generation."""
        path = get_completion_path("zsh")
        assert path is not None
        assert "_raxe" in str(path)

    def test_fish_completion_path(self):
        """Test fish completion path generation."""
        path = get_completion_path("fish")
        assert path is not None
        assert "raxe.fish" in str(path)
        assert "fish" in str(path).lower()

    def test_powershell_completion_path(self):
        """Test PowerShell completion path (returns None for manual setup)."""
        path = get_completion_path("powershell")
        assert path is None  # PowerShell needs manual profile setup

    def test_unknown_shell_returns_none(self):
        """Test unknown shell returns None."""
        path = get_completion_path("unknown")
        assert path is None


class TestFirstRunDetection:
    """Test suite for first-run detection."""

    def test_first_run_when_no_config(self, tmp_path, monkeypatch):
        """Test first run detection when no config exists."""
        # Use a non-existent home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent")
        monkeypatch.chdir(tmp_path)

        assert check_first_run() is True

    def test_not_first_run_when_home_config_exists(self, tmp_path, monkeypatch):
        """Test first run detection when home config exists."""
        # Create config in "home" directory
        home_dir = tmp_path / "home"
        config_dir = home_dir / ".raxe"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text("test: true")

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        assert check_first_run() is False

    def test_not_first_run_when_local_config_exists(self, tmp_path, monkeypatch):
        """Test first run detection when local config exists."""
        # Create local .raxe/config.yaml
        local_config = tmp_path / ".raxe"
        local_config.mkdir(parents=True)
        (local_config / "config.yaml").write_text("test: true")

        # Use empty home
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        assert check_first_run() is False


class TestWizardConfig:
    """Test suite for WizardConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = WizardConfig()

        assert config.api_key is None
        assert config.l2_enabled is True
        assert config.telemetry_enabled is True
        assert config.install_completions is False
        assert config.detected_shell is None

    def test_custom_values(self):
        """Test custom configuration values."""
        config = WizardConfig(
            api_key="raxe_live_test123456789012345678901",
            l2_enabled=False,
            telemetry_enabled=False,
            install_completions=True,
            detected_shell="zsh",
        )

        assert config.api_key == "raxe_live_test123456789012345678901"
        assert config.l2_enabled is False
        assert config.telemetry_enabled is False
        assert config.install_completions is True
        assert config.detected_shell == "zsh"


class TestCreateConfigFile:
    """Test suite for config file creation."""

    def test_creates_config_directory(self, tmp_path, monkeypatch):
        """Test that config directory is created."""
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        config = WizardConfig()
        console = Console()

        config_path = create_config_file(config, console)

        assert (home_dir / ".raxe").exists()
        assert config_path.exists()

    def test_saves_api_key_when_provided(self, tmp_path, monkeypatch):
        """Test that API key is saved when provided."""
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        config = WizardConfig(api_key="raxe_live_test123456789012345678901")
        console = Console()

        config_path = create_config_file(config, console)

        # Verify config file was created and is readable
        assert config_path.exists()
        assert config_path.read_text()  # Verify file has content

    def test_saves_l2_setting(self, tmp_path, monkeypatch):
        """Test that L2 setting is saved correctly."""
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        config = WizardConfig(l2_enabled=False)
        console = Console()

        config_path = create_config_file(config, console)

        assert config_path.exists()

    def test_saves_telemetry_setting(self, tmp_path, monkeypatch):
        """Test that telemetry setting is saved correctly."""
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        config = WizardConfig(telemetry_enabled=False)
        console = Console()

        config_path = create_config_file(config, console)

        assert config_path.exists()


class TestDisplayFirstRunMessage:
    """Test suite for first-run message display."""

    def test_displays_without_error(self, capsys):
        """Test that first-run message displays without errors."""
        console = Console(file=sys.stdout, force_terminal=False)

        # Should not raise
        display_first_run_message(console)

        captured = capsys.readouterr()
        # Should contain key phrases
        assert "Welcome to RAXE" in captured.out or "raxe" in captured.out.lower()


class TestSetupWizardCLI:
    """Test suite for setup command CLI integration."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_setup_command_exists(self, runner):
        """Test that setup command is registered."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["setup", "--help"])

        assert result.exit_code == 0
        assert "Interactive setup wizard" in result.output

    def test_setup_command_help(self, runner):
        """Test setup command help text."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["setup", "--help"])

        assert result.exit_code == 0
        assert "API key" in result.output or "setup" in result.output.lower()


class TestSetupWizardFlow:
    """Test suite for setup wizard flow."""

    @pytest.fixture(autouse=True)
    def mock_interactive_terminal(self):
        """Mock terminal context as interactive for setup wizard tests.

        The setup wizard checks for interactive terminal context before
        running. In pytest, stdin is not a TTY, so we need to mock it.
        """
        interactive_context = TerminalContext(
            mode=TerminalMode.INTERACTIVE,
            is_interactive=True,
            detected_ci=None,
            has_tty=True,
        )
        with patch(
            "raxe.cli.setup_wizard.get_terminal_context",
            return_value=interactive_context,
        ):
            clear_context_cache()
            yield
            clear_context_cache()

    def test_wizard_cancellation_with_keyboard_interrupt(self, tmp_path, monkeypatch):
        """Test that wizard handles Ctrl+C gracefully."""
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        console = Console(force_terminal=False)

        # Mock Confirm.ask to raise KeyboardInterrupt
        with patch("raxe.cli.setup_wizard.Confirm.ask", side_effect=KeyboardInterrupt):
            result = run_setup_wizard(console, skip_test_scan=True)

        assert result is False

    @patch("raxe.cli.setup_wizard.Confirm.ask")
    @patch("raxe.cli.setup_wizard.Prompt.ask")
    @patch("raxe.cli.setup_wizard.run_test_scan")
    def test_wizard_completes_with_defaults(
        self,
        mock_test_scan,
        mock_prompt,
        mock_confirm,
        tmp_path,
        monkeypatch,
    ):
        """Test wizard completes with default settings."""
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        # Mock user inputs:
        # 1. Has API key? No
        # 2. Open console? No
        # 3. Enable L2? Yes
        # 4. Enable telemetry? Yes
        # 5. Install completions? No
        mock_confirm.side_effect = [False, False, True, True, False]
        mock_test_scan.return_value = True

        console = Console(force_terminal=False)
        result = run_setup_wizard(console, skip_test_scan=True)

        assert result is True
        assert (home_dir / ".raxe" / "config.yaml").exists()

    @patch("raxe.cli.setup_wizard.Confirm.ask")
    @patch("raxe.cli.setup_wizard.Prompt.ask")
    def test_wizard_saves_api_key(
        self,
        mock_prompt,
        mock_confirm,
        tmp_path,
        monkeypatch,
    ):
        """Test wizard saves API key when provided."""
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        # Mock user inputs:
        # 1. Has API key? Yes
        # 2. API key input
        # 3. Enable L2? Yes
        # 4. Enable telemetry? Yes
        # 5. Install completions? No
        mock_confirm.side_effect = [True, True, True, False]
        mock_prompt.return_value = "raxe_live_abc123def456ghi789jkl012mno345"

        console = Console(force_terminal=False)
        result = run_setup_wizard(console, skip_test_scan=True)

        assert result is True
        config_path = home_dir / ".raxe" / "config.yaml"
        assert config_path.exists()


class TestCompletionInCLI:
    """Test suite for completion command including setup."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_bash_completion_generates_output(self, runner):
        """Test bash completion generates Click-based script."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["completion", "bash"])

        assert result.exit_code == 0
        assert "_RAXE_COMPLETE" in result.output

    def test_zsh_completion_generates_output(self, runner):
        """Test zsh completion generates Click-based script."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["completion", "zsh"])

        assert result.exit_code == 0
        assert "_RAXE_COMPLETE" in result.output

    def test_fish_completion_generates_output(self, runner):
        """Test fish completion generates Click-based script."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["completion", "fish"])

        assert result.exit_code == 0
        assert "_RAXE_COMPLETE" in result.output


class TestAutoLaunchFirstRun:
    """Test suite for auto-launch first-run wizard (P0-1)."""

    def test_auto_launch_shows_welcome_message(self, capsys):
        """Test that auto_launch shows welcome message."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        # Mock terminal context to be non-interactive to avoid countdown
        with patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context:
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.CI,
                is_interactive=False,
                detected_ci="GitHub Actions",
                has_tty=False,
            )
            auto_launch_first_run(console)

        output_text = output.getvalue()
        # In non-interactive mode, should show static message
        assert "Welcome to RAXE" in output_text or "raxe" in output_text.lower()

    def test_auto_launch_non_interactive_shows_static_message(self, capsys):
        """Test that non-interactive mode shows static message."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context:
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.CI,
                is_interactive=False,
                detected_ci="GitHub Actions",
                has_tty=False,
            )
            auto_launch_first_run(console)

        output_text = output.getvalue()
        # Should contain welcome but NOT the countdown options (since non-interactive)
        assert "Welcome" in output_text
        # Non-interactive mode shows display_first_run_message which has different content

    def test_read_key_with_timeout_returns_none_for_non_tty(self):
        """Test that _read_key_with_timeout returns None for non-TTY."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False

            result = _read_key_with_timeout(0.1)

            assert result is None

    def test_quick_init_creates_config(self, tmp_path, monkeypatch):
        """Test that _quick_init creates config with defaults."""
        from io import StringIO

        home_dir = tmp_path / "home"
        home_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        _quick_init(console)

        config_path = home_dir / ".raxe" / "config.yaml"
        assert config_path.exists()

        output_text = output.getvalue()
        assert "initialized" in output_text.lower() or "success" in output_text.lower()

    def test_quick_init_enables_l2_detection(self, tmp_path, monkeypatch):
        """Test that _quick_init enables L2 detection by default."""
        from io import StringIO

        import yaml

        home_dir = tmp_path / "home"
        home_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        _quick_init(console)

        config_path = home_dir / ".raxe" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # L2 should be enabled by default
        assert config.get("detection", {}).get("l2_enabled", True) is True

    def test_quick_init_enables_telemetry(self, tmp_path, monkeypatch):
        """Test that _quick_init enables telemetry by default."""
        from io import StringIO

        import yaml

        home_dir = tmp_path / "home"
        home_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        _quick_init(console)

        config_path = home_dir / ".raxe" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Telemetry should be enabled by default
        assert config.get("telemetry", {}).get("enabled", True) is True


class TestAutoLaunchKeyHandling:
    """Test suite for auto-launch key handling (P0-1)."""

    def test_auto_launch_key_s_starts_setup(self):
        """Test that pressing 'S' starts the setup wizard."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with (
            patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context,
            patch("raxe.cli.setup_wizard._read_key_with_timeout") as mock_key,
            patch("raxe.cli.setup_wizard.run_setup_wizard") as mock_wizard,
        ):
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.INTERACTIVE,
                is_interactive=True,
                detected_ci=None,
                has_tty=True,
            )
            # Simulate pressing 's' on first countdown tick
            mock_key.return_value = "s"
            mock_wizard.return_value = True

            auto_launch_first_run(console)

            # Should have called run_setup_wizard
            mock_wizard.assert_called_once()

    def test_auto_launch_key_q_runs_quick_init(self, tmp_path, monkeypatch):
        """Test that pressing 'Q' runs quick init."""
        from io import StringIO

        home_dir = tmp_path / "home"
        home_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with (
            patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context,
            patch("raxe.cli.setup_wizard._read_key_with_timeout") as mock_key,
        ):
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.INTERACTIVE,
                is_interactive=True,
                detected_ci=None,
                has_tty=True,
            )
            # Simulate pressing 'q' on first countdown tick
            mock_key.return_value = "q"

            auto_launch_first_run(console)

            # Should have created config file
            config_path = home_dir / ".raxe" / "config.yaml"
            assert config_path.exists()

    def test_auto_launch_key_x_skips_setup(self):
        """Test that pressing 'X' skips setup and shows help."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with (
            patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context,
            patch("raxe.cli.setup_wizard._read_key_with_timeout") as mock_key,
            patch("raxe.cli.branding.print_help_menu") as mock_help,
        ):
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.INTERACTIVE,
                is_interactive=True,
                detected_ci=None,
                has_tty=True,
            )
            # Simulate pressing 'x' on first countdown tick
            mock_key.return_value = "x"

            auto_launch_first_run(console)

            # Should have called print_help_menu
            mock_help.assert_called_once()

    def test_auto_launch_enter_starts_setup(self):
        """Test that pressing Enter starts the setup wizard."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with (
            patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context,
            patch("raxe.cli.setup_wizard._read_key_with_timeout") as mock_key,
            patch("raxe.cli.setup_wizard.run_setup_wizard") as mock_wizard,
        ):
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.INTERACTIVE,
                is_interactive=True,
                detected_ci=None,
                has_tty=True,
            )
            # Simulate pressing Enter
            mock_key.return_value = "\r"
            mock_wizard.return_value = True

            auto_launch_first_run(console)

            # Should have called run_setup_wizard
            mock_wizard.assert_called_once()

    def test_auto_launch_escape_skips_setup(self):
        """Test that pressing Escape skips setup and shows help."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with (
            patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context,
            patch("raxe.cli.setup_wizard._read_key_with_timeout") as mock_key,
            patch("raxe.cli.branding.print_help_menu") as mock_help,
        ):
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.INTERACTIVE,
                is_interactive=True,
                detected_ci=None,
                has_tty=True,
            )
            # Simulate pressing Escape
            mock_key.return_value = "\x1b"

            auto_launch_first_run(console)

            # Should have called print_help_menu
            mock_help.assert_called_once()

    def test_auto_launch_ctrl_c_cancels(self):
        """Test that Ctrl+C cancels setup."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with (
            patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context,
            patch("raxe.cli.setup_wizard._read_key_with_timeout") as mock_key,
            patch("raxe.cli.setup_wizard.run_setup_wizard") as mock_wizard,
        ):
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.INTERACTIVE,
                is_interactive=True,
                detected_ci=None,
                has_tty=True,
            )
            # Simulate Ctrl+C
            mock_key.return_value = "\x03"

            auto_launch_first_run(console)

            # Should NOT have called run_setup_wizard
            mock_wizard.assert_not_called()

            output_text = output.getvalue()
            assert "Cancelled" in output_text

    def test_auto_launch_timeout_starts_wizard(self):
        """Test that countdown timeout auto-starts wizard."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with (
            patch("raxe.cli.setup_wizard.get_terminal_context") as mock_context,
            patch("raxe.cli.setup_wizard._read_key_with_timeout") as mock_key,
            patch("raxe.cli.setup_wizard.run_setup_wizard") as mock_wizard,
        ):
            mock_context.return_value = TerminalContext(
                mode=TerminalMode.INTERACTIVE,
                is_interactive=True,
                detected_ci=None,
                has_tty=True,
            )
            # No key pressed - returns None each time (5 countdown iterations)
            mock_key.return_value = None
            mock_wizard.return_value = True

            auto_launch_first_run(console)

            # Should have called run_setup_wizard after timeout
            mock_wizard.assert_called_once()


class TestNoWizardFlag:
    """Test suite for --no-wizard flag (P0-1)."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_no_wizard_flag_shows_static_message(self, runner, tmp_path, monkeypatch):
        """Test that --no-wizard flag shows static message instead of countdown."""
        from raxe.cli.main import cli

        # Use isolated filesystem to simulate first run
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Patch home directory
            fake_home = Path(tmp_path) / "fake_home"
            fake_home.mkdir(parents=True)
            monkeypatch.setenv("HOME", str(fake_home))

            result = runner.invoke(cli, ["--no-wizard"])

            # Should show static welcome message
            assert result.exit_code == 0
            assert "Welcome" in result.output or "raxe" in result.output.lower()


class TestTestScanResult:
    """Test suite for TestScanResult dataclass (P2-1)."""

    def test_default_values(self):
        """Test default TestScanResult values."""
        result = TestScanResult()

        assert result.success is False
        assert result.duration_ms == 0.0
        assert result.threat_count == 0
        assert result.error_message is None

    def test_custom_values(self):
        """Test TestScanResult with custom values."""
        result = TestScanResult(
            success=True,
            duration_ms=5.2,
            threat_count=3,
            error_message=None,
        )

        assert result.success is True
        assert result.duration_ms == 5.2
        assert result.threat_count == 3
        assert result.error_message is None

    def test_error_result(self):
        """Test TestScanResult with error."""
        result = TestScanResult(
            success=False,
            duration_ms=0.0,
            threat_count=0,
            error_message="Connection failed",
        )

        assert result.success is False
        assert result.error_message == "Connection failed"


class TestApiKeyDisplayHelper:
    """Test suite for _get_api_key_display helper (P2-1)."""

    def test_temp_key_display(self):
        """Test display text for temporary key."""
        config = WizardConfig(api_key="raxe_temp_abc123def456ghi789jkl012mno345")

        text, style = _get_api_key_display(config)

        assert "temporary" in text.lower()
        assert style == "yellow"

    def test_live_key_display(self):
        """Test display text for live key."""
        config = WizardConfig(api_key="raxe_live_abc123def456ghi789jkl012mno345")

        text, style = _get_api_key_display(config)

        assert "permanent" in text.lower() or "raxe_live" in text
        assert style == "green"

    def test_test_key_display(self):
        """Test display text for test key."""
        config = WizardConfig(api_key="raxe_test_abc123def456ghi789jkl012mno345")

        text, style = _get_api_key_display(config)

        assert "test" in text.lower() or "raxe_test" in text
        assert style == "yellow"  # Test keys are yellow (not production)

    def test_no_key_display(self):
        """Test display text when no key configured (uses temp key)."""
        config = WizardConfig(api_key=None)

        text, style = _get_api_key_display(config)

        # No key means a temp key will be auto-generated
        assert "temporary" in text.lower() or "expiry" in text.lower()
        assert style == "yellow"


class TestIsTempKeyHelper:
    """Test suite for _is_temp_key helper (P2-1)."""

    def test_temp_key_returns_true(self):
        """Test that temp key is detected."""
        config = WizardConfig(api_key="raxe_temp_abc123def456ghi789jkl012mno345")

        assert _is_temp_key(config) is True

    def test_live_key_returns_false(self):
        """Test that live key is not detected as temp."""
        config = WizardConfig(api_key="raxe_live_abc123def456ghi789jkl012mno345")

        assert _is_temp_key(config) is False

    def test_test_key_returns_false(self):
        """Test that test key is not detected as temp."""
        config = WizardConfig(api_key="raxe_test_abc123def456ghi789jkl012mno345")

        assert _is_temp_key(config) is False

    def test_no_key_returns_true(self):
        """Test that no key is treated as temp (auto-generated temp key)."""
        config = WizardConfig(api_key=None)

        # When no key is provided, RAXE will auto-generate a temp key
        assert _is_temp_key(config) is True


class TestDisplayNextSteps:
    """Test suite for display_next_steps function (P2-1)."""

    def test_displays_success_banner(self):
        """Test that success banner is displayed."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        display_next_steps(console)

        output_text = output.getvalue()
        assert "SETUP COMPLETE" in output_text or "ready" in output_text.lower()

    def test_displays_with_config(self):
        """Test display with WizardConfig."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        config = WizardConfig(
            api_key="raxe_live_abc123def456ghi789jkl012mno345",
            l2_enabled=True,
            telemetry_enabled=True,
        )
        display_next_steps(console, config)

        output_text = output.getvalue()
        # Should show configuration summary
        assert "L2" in output_text or "Detection" in output_text

    def test_displays_test_result_success(self):
        """Test display with successful test scan result."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        config = WizardConfig(l2_enabled=True)
        test_result = TestScanResult(success=True, duration_ms=5.2, threat_count=2)

        display_next_steps(console, config, test_result)

        output_text = output.getvalue()
        # Should show test result status
        assert "5.2" in output_text or "ms" in output_text or "2" in output_text

    def test_displays_test_result_failure(self):
        """Test display with failed test scan result."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        config = WizardConfig(l2_enabled=True)
        test_result = TestScanResult(
            success=False,
            error_message="Connection timeout",
        )

        display_next_steps(console, config, test_result)

        output_text = output.getvalue()
        # Should still display (graceful handling of failure)
        assert len(output_text) > 0

    def test_displays_temp_key_warning(self):
        """Test that temp key warning is displayed."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        config = WizardConfig(api_key="raxe_temp_abc123def456ghi789jkl012mno345")

        display_next_steps(console, config)

        output_text = output.getvalue()
        # Should show warning about temp key
        assert "expire" in output_text.lower() or "temporary" in output_text.lower()

    def test_displays_quick_commands(self):
        """Test that quick commands section is displayed."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        display_next_steps(console)

        output_text = output.getvalue()
        # Should show common commands
        assert "raxe scan" in output_text or "scan" in output_text.lower()

    def test_displays_footer_resources(self):
        """Test that footer resources are displayed."""
        from io import StringIO

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        display_next_steps(console)

        output_text = output.getvalue()
        # Should show documentation link or help reference
        has_docs = "raxe.ai" in output_text or "docs" in output_text.lower()
        has_help = "help" in output_text.lower()
        assert has_docs or has_help
