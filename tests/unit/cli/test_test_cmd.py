"""Tests for test CLI command.

Tests for the `raxe test` command that verifies RAXE configuration and connectivity.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.test import test


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_raxe_client():
    """Create a mock Raxe client with standard responses."""
    mock = MagicMock()
    mock.stats = {"rules_loaded": 500, "packs_loaded": 3}
    mock.has_api_key.return_value = True

    # Mock scan result
    mock_result = MagicMock()
    mock_result.duration_ms = 4.5
    mock_result.scan_result.l1_result.detections = [MagicMock()]
    mock.scan.return_value = mock_result

    return mock


class TestTestCommand:
    """Tests for raxe test command."""

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_all_checks_pass(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test that all checks pass with proper config."""
        mock_client = MagicMock()
        mock_client.stats = {"rules_loaded": 500, "packs_loaded": 3}
        mock_client.has_api_key.return_value = True
        mock_result = MagicMock()
        mock_result.duration_ms = 4.5
        mock_result.scan_result.l1_result.detections = [MagicMock()]
        mock_client.scan.return_value = mock_result
        mock_raxe_cls.return_value = mock_client

        # Create fake config file
        config_file = tmp_path / ".raxe" / "config.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("api_key: test")

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        assert result.exit_code == 0
        assert "checks passed" in result.output.lower()

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_missing_config_file(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test behavior when config file is missing."""
        mock_client = MagicMock()
        mock_client.stats = {"rules_loaded": 500, "packs_loaded": 3}
        mock_client.has_api_key.return_value = False
        mock_result = MagicMock()
        mock_result.duration_ms = 3.0
        mock_result.scan_result.l1_result.detections = []
        mock_client.scan.return_value = mock_result
        mock_raxe_cls.return_value = mock_client

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        assert result.exit_code == 0
        assert "Not found" in result.output or "not found" in result.output.lower()

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_rules_loaded(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test that rule loading check reports count."""
        mock_client = MagicMock()
        mock_client.stats = {"rules_loaded": 515, "packs_loaded": 3}
        mock_client.has_api_key.return_value = False
        mock_result = MagicMock()
        mock_result.duration_ms = 5.0
        mock_result.scan_result.l1_result.detections = []
        mock_client.scan.return_value = mock_result
        mock_raxe_cls.return_value = mock_client

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        assert result.exit_code == 0
        assert "515" in result.output

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_no_rules_loaded(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test behavior when no rules are loaded."""
        mock_client = MagicMock()
        mock_client.stats = {"rules_loaded": 0, "packs_loaded": 0}
        mock_client.has_api_key.return_value = False
        mock_result = MagicMock()
        mock_result.duration_ms = 1.0
        mock_result.scan_result.l1_result.detections = []
        mock_client.scan.return_value = mock_result
        mock_raxe_cls.return_value = mock_client

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        assert result.exit_code == 0
        assert "No rules" in result.output or "0 rules" in result.output.lower()

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_api_key_configured(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test check passes when API key is configured."""
        mock_client = MagicMock()
        mock_client.stats = {"rules_loaded": 100, "packs_loaded": 1}
        mock_client.has_api_key.return_value = True
        mock_result = MagicMock()
        mock_result.duration_ms = 2.0
        mock_result.scan_result.l1_result.detections = []
        mock_client.scan.return_value = mock_result
        mock_raxe_cls.return_value = mock_client

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        assert result.exit_code == 0
        assert "API key configured" in result.output

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_no_api_key(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test offline mode message when no API key."""
        mock_client = MagicMock()
        mock_client.stats = {"rules_loaded": 100, "packs_loaded": 1}
        mock_client.has_api_key.return_value = False
        mock_result = MagicMock()
        mock_result.duration_ms = 2.0
        mock_result.scan_result.l1_result.detections = []
        mock_client.scan.return_value = mock_result
        mock_raxe_cls.return_value = mock_client

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        assert result.exit_code == 0
        assert "offline" in result.output.lower() or "No API key" in result.output

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_scan_completes(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test that local scan check reports duration."""
        mock_client = MagicMock()
        mock_client.stats = {"rules_loaded": 100, "packs_loaded": 1}
        mock_client.has_api_key.return_value = False
        mock_result = MagicMock()
        mock_result.duration_ms = 7.35
        mock_result.scan_result.l1_result.detections = [MagicMock(), MagicMock()]
        mock_client.scan.return_value = mock_result
        mock_raxe_cls.return_value = mock_client

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        assert result.exit_code == 0
        assert "Scan completed" in result.output
        assert "7.35" in result.output

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_scan_failure(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test behavior when scan fails."""
        mock_client = MagicMock()
        mock_client.stats = {"rules_loaded": 100, "packs_loaded": 1}
        mock_client.has_api_key.return_value = False
        mock_client.scan.side_effect = RuntimeError("scan engine broken")
        mock_raxe_cls.return_value = mock_client

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        assert result.exit_code == 0  # Command itself doesn't fail
        assert "Failed" in result.output or "failed" in result.output.lower()

    @patch("raxe.cli.branding.print_logo")
    @patch("raxe.cli.test.Raxe")
    def test_test_raxe_init_failure(self, mock_raxe_cls, mock_logo, runner, tmp_path):
        """Test behavior when Raxe client fails to initialize."""
        mock_raxe_cls.side_effect = RuntimeError("Cannot init")

        with patch("raxe.cli.test.Path.home", return_value=tmp_path):
            result = runner.invoke(test)

        # Should still report partial results, not crash
        assert "Failed" in result.output or "Cannot init" in result.output
