"""Tests for privacy CLI command.

Tests for the `raxe privacy` command that displays RAXE privacy guarantees.
"""

from click.testing import CliRunner

from raxe.cli.privacy import privacy_command


class TestPrivacyCommand:
    """Tests for raxe privacy command."""

    def test_privacy_exit_code_zero(self):
        """Test that privacy command exits successfully."""
        runner = CliRunner()
        result = runner.invoke(privacy_command)
        assert result.exit_code == 0

    def test_privacy_shows_data_handling(self):
        """Test that output contains data handling information."""
        runner = CliRunner()
        result = runner.invoke(privacy_command)
        assert "Data Handling" in result.output

    def test_privacy_shows_sha256_mention(self):
        """Test that output mentions SHA-256 hashing."""
        runner = CliRunner()
        result = runner.invoke(privacy_command)
        assert "SHA-256" in result.output

    def test_privacy_shows_never_collects(self):
        """Test that output lists what RAXE never collects."""
        runner = CliRunner()
        result = runner.invoke(privacy_command)
        assert "Never Collects" in result.output

    def test_privacy_mentions_telemetry_disable(self):
        """Test that output mentions how to disable telemetry."""
        runner = CliRunner()
        result = runner.invoke(privacy_command)
        assert "telemetry" in result.output.lower()

    def test_privacy_shows_local_storage_info(self):
        """Test that output contains local storage paths."""
        runner = CliRunner()
        result = runner.invoke(privacy_command)
        assert "Local Storage" in result.output
        assert ".raxe" in result.output
