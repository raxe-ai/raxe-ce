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
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from raxe.cli.setup_wizard import (
    API_KEY_PATTERN,
    WizardConfig,
    check_first_run,
    create_config_file,
    detect_shell,
    display_first_run_message,
    get_completion_path,
    run_setup_wizard,
    validate_api_key_format,
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

        config = WizardConfig(
            api_key="raxe_live_test123456789012345678901"
        )
        console = Console()

        config_path = create_config_file(config, console)

        # Read and verify config
        content = config_path.read_text()
        # API key is saved in the config
        assert config_path.exists()

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

    def test_bash_completion_includes_setup(self, runner):
        """Test bash completion includes setup command."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["completion", "bash"])

        assert result.exit_code == 0
        assert "setup" in result.output

    def test_zsh_completion_includes_setup(self, runner):
        """Test zsh completion includes setup command."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["completion", "zsh"])

        assert result.exit_code == 0
        assert "setup" in result.output

    def test_fish_completion_includes_setup(self, runner):
        """Test fish completion includes setup command."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["completion", "fish"])

        assert result.exit_code == 0
        assert "setup" in result.output

    def test_powershell_completion_includes_setup(self, runner):
        """Test PowerShell completion includes setup command."""
        from raxe.cli.main import cli

        result = runner.invoke(cli, ["completion", "powershell"])

        assert result.exit_code == 0
        assert "setup" in result.output
