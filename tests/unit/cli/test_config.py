"""Tests for CLI config commands.

Tests for:
- raxe config show
- raxe config set-value <key> <value>
- raxe config reset
- raxe config validate
- raxe config edit
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.config import config


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Create a mock RaxeConfig instance."""
    cfg = MagicMock()
    cfg.core.environment = "production"
    cfg.core.version = "0.0.1"
    cfg.core.api_key = ""
    cfg.detection.l1_enabled = True
    cfg.detection.l2_enabled = True
    cfg.detection.mode = "balanced"
    cfg.detection.confidence_threshold = 0.5
    cfg.telemetry.enabled = True
    cfg.telemetry.batch_size = 50
    cfg.telemetry.flush_interval = 300
    cfg.performance.max_queue_size = 10000
    cfg.performance.scan_timeout = 30
    cfg.logging.level = "INFO"
    cfg.logging.directory = "~/.raxe/logs"
    cfg.validate.return_value = []
    return cfg


class TestConfigShow:
    """Tests for raxe config show command."""

    def test_show_displays_config(self, runner, mock_config):
        """Test that show displays configuration values."""
        with patch("raxe.cli.config.RaxeConfig.load", return_value=mock_config):
            result = runner.invoke(config, ["show"])

        assert result.exit_code == 0
        assert "Configuration" in result.output

    def test_show_displays_all_sections(self, runner, mock_config):
        """Test that show displays all config sections."""
        with patch("raxe.cli.config.RaxeConfig.load", return_value=mock_config):
            result = runner.invoke(config, ["show"])

        assert result.exit_code == 0
        # Check key sections/values appear
        assert "production" in result.output
        assert "balanced" in result.output
        assert "INFO" in result.output

    def test_show_masks_api_key_when_set(self, runner, mock_config):
        """Test that show masks the API key value."""
        mock_config.core.api_key = "raxe_live_secret123"
        with patch("raxe.cli.config.RaxeConfig.load", return_value=mock_config):
            result = runner.invoke(config, ["show"])

        assert result.exit_code == 0
        assert "***" in result.output
        # Raw key should NOT be displayed
        assert "secret123" not in result.output

    def test_show_indicates_api_key_not_set(self, runner, mock_config):
        """Test that show shows indicator when API key is empty."""
        mock_config.core.api_key = ""
        with patch("raxe.cli.config.RaxeConfig.load", return_value=mock_config):
            result = runner.invoke(config, ["show"])

        assert result.exit_code == 0
        assert "not set" in result.output

    def test_show_with_custom_path(self, runner, mock_config, tmp_path):
        """Test show with --path option."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("core:\n  environment: test\n")
        with patch("raxe.cli.config.RaxeConfig.load", return_value=mock_config):
            result = runner.invoke(config, ["show", "--path", str(config_file)])

        assert result.exit_code == 0

    def test_show_handles_load_error(self, runner):
        """Test show handles config load failure gracefully."""
        with patch(
            "raxe.cli.config.RaxeConfig.load",
            side_effect=Exception("Config file corrupt"),
        ):
            result = runner.invoke(config, ["show"])

        assert result.exit_code != 0
        assert "Error" in result.output


class TestConfigSetValue:
    """Tests for raxe config set-value command."""

    def test_set_key_value(self, runner, mock_config, tmp_path):
        """Test setting a configuration value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("core:\n  environment: production\n")

        with patch("raxe.cli.config.RaxeConfig.from_file", return_value=mock_config):
            result = runner.invoke(
                config,
                ["set-value", "detection.mode", "fast", "--path", str(config_file)],
            )

        assert result.exit_code == 0
        assert "Set" in result.output
        assert "detection.mode" in result.output

    def test_set_api_key_masks_output(self, runner, mock_config, tmp_path):
        """Test that setting API key masks value in output."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("core:\n  api_key: ''\n")

        with (
            patch("raxe.cli.config.RaxeConfig.from_file", return_value=mock_config),
            patch("raxe.cli.config._send_key_upgrade_event"),
        ):
            result = runner.invoke(
                config,
                [
                    "set-value",
                    "core.api_key",
                    "raxe_live_abcdef123456",
                    "--path",
                    str(config_file),
                ],
            )

        assert result.exit_code == 0
        # Should show masked value, not full key
        assert "****" in result.output
        assert "3456" in result.output  # last 4 chars shown
        assert "abcdef" not in result.output

    def test_set_invalid_key_fails(self, runner, mock_config, tmp_path):
        """Test that setting invalid key path fails."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("core:\n  environment: production\n")

        mock_config.update.side_effect = ValueError("Invalid key: nonexistent")
        with patch("raxe.cli.config.RaxeConfig.from_file", return_value=mock_config):
            result = runner.invoke(
                config,
                [
                    "set-value",
                    "invalid.nonexistent",
                    "value",
                    "--path",
                    str(config_file),
                ],
            )

        assert result.exit_code != 0
        assert "Invalid" in result.output or "Error" in result.output

    def test_set_creates_config_if_missing(self, runner, mock_config, tmp_path):
        """Test that set creates config file if it doesn't exist."""
        config_file = tmp_path / "new_config.yaml"

        with patch("raxe.cli.config.RaxeConfig", return_value=mock_config):
            result = runner.invoke(
                config,
                [
                    "set-value",
                    "detection.mode",
                    "fast",
                    "--path",
                    str(config_file),
                ],
            )

        assert result.exit_code == 0

    def test_set_validation_error_shows_errors(self, runner, mock_config, tmp_path):
        """Test that validation errors are shown after set."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("core:\n  environment: production\n")

        mock_config.validate.return_value = ["Invalid threshold value"]
        with patch("raxe.cli.config.RaxeConfig.from_file", return_value=mock_config):
            result = runner.invoke(
                config,
                [
                    "set-value",
                    "detection.confidence_threshold",
                    "2.0",
                    "--path",
                    str(config_file),
                ],
            )

        assert result.exit_code != 0
        assert "Validation" in result.output


class TestConfigReset:
    """Tests for raxe config reset command."""

    def test_reset_with_confirmation(self, runner, tmp_path):
        """Test reset with --yes flag (click's confirmation_option)."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("core:\n  environment: test\n")

        with patch("raxe.cli.config.create_default_config") as mock_create:
            result = runner.invoke(config, ["reset", "--path", str(config_file), "--yes"])

        assert result.exit_code == 0
        assert "reset" in result.output.lower() or "defaults" in result.output.lower()
        mock_create.assert_called_once()

    def test_reset_aborts_without_confirmation(self, runner):
        """Test reset aborts when user declines."""
        result = runner.invoke(config, ["reset"], input="n\n")

        assert result.exit_code != 0 or "Abort" in result.output

    def test_reset_handles_error(self, runner):
        """Test reset handles errors gracefully."""
        with patch(
            "raxe.cli.config.create_default_config",
            side_effect=PermissionError("Cannot write"),
        ):
            result = runner.invoke(config, ["reset", "--yes"])

        assert result.exit_code != 0
        assert "Error" in result.output


class TestConfigValidate:
    """Tests for raxe config validate command."""

    def test_validate_valid_config(self, runner, mock_config):
        """Test validate reports valid config."""
        mock_config.validate.return_value = []
        with patch("raxe.cli.config.RaxeConfig.load", return_value=mock_config):
            result = runner.invoke(config, ["validate"])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_invalid_config(self, runner, mock_config):
        """Test validate reports invalid config."""
        mock_config.validate.return_value = ["detection.confidence_threshold must be 0-1, got 5.0"]
        with patch("raxe.cli.config.RaxeConfig.load", return_value=mock_config):
            result = runner.invoke(config, ["validate"])

        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "Validation" in result.output

    def test_validate_with_custom_path(self, runner, mock_config, tmp_path):
        """Test validate with --path option."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("core:\n  environment: production\n")
        mock_config.validate.return_value = []

        with patch("raxe.cli.config.RaxeConfig.load", return_value=mock_config):
            result = runner.invoke(config, ["validate", "--path", str(config_file)])

        assert result.exit_code == 0

    def test_validate_handles_load_error(self, runner):
        """Test validate handles config load failure."""
        with patch(
            "raxe.cli.config.RaxeConfig.load",
            side_effect=Exception("File not found"),
        ):
            result = runner.invoke(config, ["validate"])

        assert result.exit_code != 0
        assert "Error" in result.output
