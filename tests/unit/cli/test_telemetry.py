"""
Tests for CLI telemetry commands.

Tests the telemetry management CLI functionality including:
- Status command
- DLQ operations (list, show, clear, retry)
- Flush command
- Enable/disable commands
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.main import cli
from raxe.cli.telemetry import (
    _format_relative_time,
    _get_tier_name,
    _mask_api_key,
    _parse_duration,
)


class TestHelperFunctions:
    """Test suite for telemetry helper functions."""

    def test_parse_duration_days(self) -> None:
        """Test parsing day duration strings."""
        assert _parse_duration("7d") == 7
        assert _parse_duration("30d") == 30
        assert _parse_duration("1d") == 1

    def test_parse_duration_hours(self) -> None:
        """Test parsing hour duration strings."""
        assert _parse_duration("24h") == 1
        assert _parse_duration("48h") == 2
        assert _parse_duration("1h") == 1  # Rounds up to 1 day minimum

    def test_parse_duration_minutes(self) -> None:
        """Test parsing minute duration strings."""
        assert _parse_duration("1440m") == 1  # 1 day
        assert _parse_duration("60m") == 1  # Rounds up to 1 day minimum

    def test_parse_duration_invalid(self) -> None:
        """Test parsing invalid duration strings returns None."""
        assert _parse_duration("invalid") is None
        assert _parse_duration("7") is None
        assert _parse_duration("d7") is None
        assert _parse_duration("") is None
        assert _parse_duration("7x") is None

    def test_mask_api_key_none(self) -> None:
        """Test masking None API key."""
        assert _mask_api_key(None) == "(not configured)"
        assert _mask_api_key("") == "(not configured)"

    def test_mask_api_key_short(self) -> None:
        """Test masking short API key."""
        assert _mask_api_key("abc") == "***"
        assert _mask_api_key("123456") == "***"

    def test_mask_api_key_with_prefix(self) -> None:
        """Test masking API key with raxe_ prefix."""
        result = _mask_api_key("raxe_live_customer123_abcdef")
        assert result.startswith("raxe_live_")
        assert result.endswith("def")
        assert "***" in result

    def test_mask_api_key_without_prefix(self) -> None:
        """Test masking API key without prefix."""
        result = _mask_api_key("someapikey12345")
        assert result.startswith("***")
        assert result.endswith("345")

    def test_get_tier_name_free(self) -> None:
        """Test tier detection for free tier."""
        assert _get_tier_name(None) == "Free tier"
        assert _get_tier_name("") == "Free tier"

    def test_get_tier_name_pro(self) -> None:
        """Test tier detection for Pro tier."""
        assert _get_tier_name("raxe_pro_abc123") == "Pro tier"
        assert _get_tier_name("raxe_live_abc123") == "Pro tier"

    def test_get_tier_name_enterprise(self) -> None:
        """Test tier detection for Enterprise tier."""
        assert _get_tier_name("raxe_enterprise_abc123") == "Enterprise tier"

    def test_get_tier_name_test(self) -> None:
        """Test tier detection for test tier."""
        assert _get_tier_name("raxe_test_abc123") == "Test tier"

    def test_format_relative_time_none(self) -> None:
        """Test formatting None timestamp."""
        assert _format_relative_time(None) == "unknown"

    def test_format_relative_time_invalid(self) -> None:
        """Test formatting invalid timestamp."""
        assert _format_relative_time("invalid") == "unknown"

    def test_format_relative_time_seconds(self) -> None:
        """Test formatting recent timestamp (seconds ago)."""
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        result = _format_relative_time(timestamp)
        # Should be "0s ago" or close to it
        assert "ago" in result


class TestTelemetryStatusCommand:
    """Test suite for telemetry status command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    def test_status_help(self, runner: CliRunner) -> None:
        """Test status command help."""
        result = runner.invoke(cli, ["telemetry", "status", "--help"])
        assert result.exit_code == 0
        assert "Display telemetry status" in result.output

    @patch("raxe.cli.telemetry._get_config")
    @patch("raxe.cli.telemetry._get_queue_instance")
    @patch("raxe.cli.telemetry.BatchSender")
    def test_status_text_output(
        self,
        mock_sender_class: MagicMock,
        mock_queue: MagicMock,
        mock_config: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test status command with text output."""
        # Setup mocks
        mock_config.return_value.telemetry.endpoint = "http://test.local/v1/telemetry"
        mock_config.return_value.telemetry.enabled = True
        mock_config.return_value.core.api_key = None

        mock_queue_instance = MagicMock()
        mock_queue_instance.get_stats.return_value = {
            "critical_count": 5,
            "standard_count": 100,
            "dlq_count": 0,
            "oldest_critical": None,
            "oldest_standard": None,
        }
        mock_queue.return_value = mock_queue_instance

        mock_sender = MagicMock()
        mock_sender.get_circuit_state.return_value = "closed"
        mock_sender_class.return_value = mock_sender

        result = runner.invoke(cli, ["telemetry", "status"])

        assert result.exit_code == 0
        assert "Telemetry Status" in result.output
        assert "Circuit Breaker" in result.output

    @patch("raxe.cli.telemetry._get_config")
    @patch("raxe.cli.telemetry._get_queue_instance")
    @patch("raxe.cli.telemetry.BatchSender")
    def test_status_json_output(
        self,
        mock_sender_class: MagicMock,
        mock_queue: MagicMock,
        mock_config: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test status command with JSON output."""
        # Setup mocks
        mock_config.return_value.telemetry.endpoint = "http://test.local/v1/telemetry"
        mock_config.return_value.telemetry.enabled = True
        mock_config.return_value.core.api_key = None

        mock_queue_instance = MagicMock()
        mock_queue_instance.get_stats.return_value = {
            "critical_count": 5,
            "standard_count": 100,
            "dlq_count": 0,
            "oldest_critical": None,
            "oldest_standard": None,
        }
        mock_queue.return_value = mock_queue_instance

        mock_sender = MagicMock()
        mock_sender.get_circuit_state.return_value = "closed"
        mock_sender_class.return_value = mock_sender

        result = runner.invoke(cli, ["telemetry", "status", "--format", "json"])

        assert result.exit_code == 0
        # Should contain JSON structure
        assert '"endpoint"' in result.output
        assert '"telemetry_enabled"' in result.output


class TestTelemetryDLQCommands:
    """Test suite for telemetry DLQ commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    def test_dlq_help(self, runner: CliRunner) -> None:
        """Test DLQ command group help."""
        result = runner.invoke(cli, ["telemetry", "dlq", "--help"])
        assert result.exit_code == 0
        assert "Manage the Dead Letter Queue" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "clear" in result.output
        assert "retry" in result.output

    def test_dlq_list_help(self, runner: CliRunner) -> None:
        """Test DLQ list command help."""
        result = runner.invoke(cli, ["telemetry", "dlq", "list", "--help"])
        assert result.exit_code == 0
        assert "List events in the Dead Letter Queue" in result.output

    @patch("raxe.cli.telemetry._get_queue_instance")
    def test_dlq_list_empty(self, mock_queue: MagicMock, runner: CliRunner) -> None:
        """Test DLQ list with empty queue."""
        mock_queue_instance = MagicMock()
        mock_queue_instance.get_dlq_events.return_value = []
        mock_queue.return_value = mock_queue_instance

        result = runner.invoke(cli, ["telemetry", "dlq", "list"])

        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    @patch("raxe.cli.telemetry._get_queue_instance")
    def test_dlq_list_with_events(self, mock_queue: MagicMock, runner: CliRunner) -> None:
        """Test DLQ list with events."""
        mock_queue_instance = MagicMock()
        mock_queue_instance.get_dlq_events.return_value = [
            {
                "event_id": "evt_abc123",
                "event_type": "scan",
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "failure_reason": "Connection timeout",
                "retry_count": 3,
            }
        ]
        mock_queue.return_value = mock_queue_instance

        result = runner.invoke(cli, ["telemetry", "dlq", "list"])

        assert result.exit_code == 0
        assert "evt_abc123" in result.output

    def test_dlq_show_help(self, runner: CliRunner) -> None:
        """Test DLQ show command help."""
        result = runner.invoke(cli, ["telemetry", "dlq", "show", "--help"])
        assert result.exit_code == 0
        assert "Show details of a specific DLQ event" in result.output

    @patch("raxe.cli.telemetry._get_queue_instance")
    def test_dlq_show_not_found(self, mock_queue: MagicMock, runner: CliRunner) -> None:
        """Test DLQ show with nonexistent event."""
        mock_queue_instance = MagicMock()
        mock_queue_instance.get_dlq_events.return_value = []
        mock_queue.return_value = mock_queue_instance

        result = runner.invoke(cli, ["telemetry", "dlq", "show", "nonexistent"])

        # Should show error
        assert "not found" in result.output.lower()

    def test_dlq_clear_help(self, runner: CliRunner) -> None:
        """Test DLQ clear command help."""
        result = runner.invoke(cli, ["telemetry", "dlq", "clear", "--help"])
        assert result.exit_code == 0
        assert "Clear events from the Dead Letter Queue" in result.output
        assert "--older-than" in result.output
        assert "--force" in result.output

    @patch("raxe.cli.telemetry._get_queue_instance")
    def test_dlq_clear_empty(self, mock_queue: MagicMock, runner: CliRunner) -> None:
        """Test DLQ clear with empty queue."""
        mock_queue_instance = MagicMock()
        mock_queue_instance.get_stats.return_value = {"dlq_count": 0}
        mock_queue.return_value = mock_queue_instance

        result = runner.invoke(cli, ["telemetry", "dlq", "clear", "--force"])

        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    @patch("raxe.cli.telemetry._get_queue_instance")
    def test_dlq_clear_with_force(self, mock_queue: MagicMock, runner: CliRunner) -> None:
        """Test DLQ clear with --force flag."""
        mock_queue_instance = MagicMock()
        mock_queue_instance.get_stats.return_value = {"dlq_count": 5}
        mock_queue_instance.clear_dlq.return_value = 5
        mock_queue.return_value = mock_queue_instance

        result = runner.invoke(cli, ["telemetry", "dlq", "clear", "--force"])

        assert result.exit_code == 0
        mock_queue_instance.clear_dlq.assert_called_once()

    def test_dlq_retry_help(self, runner: CliRunner) -> None:
        """Test DLQ retry command help."""
        result = runner.invoke(cli, ["telemetry", "dlq", "retry", "--help"])
        assert result.exit_code == 0
        assert "Retry failed events" in result.output

    @patch("raxe.cli.telemetry._get_queue_instance")
    def test_dlq_retry_all(self, mock_queue: MagicMock, runner: CliRunner) -> None:
        """Test DLQ retry all events."""
        mock_queue_instance = MagicMock()
        mock_queue_instance.retry_dlq_events.return_value = 3
        mock_queue.return_value = mock_queue_instance

        result = runner.invoke(cli, ["telemetry", "dlq", "retry", "--all"])

        assert result.exit_code == 0
        mock_queue_instance.retry_dlq_events.assert_called_once()


class TestTelemetryFlushCommand:
    """Test suite for telemetry flush command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    def test_flush_help(self, runner: CliRunner) -> None:
        """Test flush command help."""
        result = runner.invoke(cli, ["telemetry", "flush", "--help"])
        assert result.exit_code == 0
        assert "Flush telemetry queues" in result.output

    @patch("raxe.cli.telemetry._get_queue_instance")
    def test_flush_empty_queues(self, mock_queue: MagicMock, runner: CliRunner) -> None:
        """Test flush with empty queues."""
        mock_queue_instance = MagicMock()
        mock_queue_instance.get_stats.return_value = {
            "critical_count": 0,
            "standard_count": 0,
        }
        mock_queue.return_value = mock_queue_instance

        result = runner.invoke(cli, ["telemetry", "flush"])

        assert result.exit_code == 0
        assert "empty" in result.output.lower() or "No events" in result.output


class TestTelemetryEnableDisableCommands:
    """Test suite for telemetry enable/disable commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    def test_enable_help(self, runner: CliRunner) -> None:
        """Test enable command help."""
        result = runner.invoke(cli, ["telemetry", "enable", "--help"])
        assert result.exit_code == 0
        assert "Enable telemetry collection" in result.output

    def test_disable_help(self, runner: CliRunner) -> None:
        """Test disable command help."""
        result = runner.invoke(cli, ["telemetry", "disable", "--help"])
        assert result.exit_code == 0
        assert "Disable telemetry collection" in result.output

    @patch("raxe.cli.telemetry._get_config")
    @patch("raxe.cli.telemetry._check_telemetry_disable_permission")
    @patch("raxe.cli.telemetry._get_cached_tier")
    def test_disable_free_tier(
        self,
        mock_get_tier: MagicMock,
        mock_check_permission: MagicMock,
        mock_config: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test disable command on free tier shows error."""
        mock_config.return_value.core.api_key = None
        mock_check_permission.return_value = False  # Free tier cannot disable
        mock_get_tier.return_value = "Community"

        result = runner.invoke(cli, ["telemetry", "disable"])

        assert result.exit_code == 0
        # Check for tier display and upgrade message
        output_lower = result.output.lower()
        assert "tier" in output_lower
        assert "upgrade" in output_lower
        assert "cannot be disabled" in output_lower

    @patch("raxe.cli.telemetry._get_config")
    @patch("raxe.cli.telemetry.Path")
    def test_disable_pro_tier(
        self, mock_path: MagicMock, mock_config: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test disable command on Pro tier succeeds."""
        mock_config_obj = MagicMock()
        mock_config_obj.core.api_key = "raxe_pro_customer123"
        mock_config_obj.telemetry.enabled = True
        mock_config.return_value = mock_config_obj

        mock_path.home.return_value = tmp_path

        result = runner.invoke(cli, ["telemetry", "disable"])

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()


class TestTelemetryConfigCommand:
    """Test suite for telemetry config command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    def test_config_help(self, runner: CliRunner) -> None:
        """Test config command help."""
        result = runner.invoke(cli, ["telemetry", "config", "--help"])
        assert result.exit_code == 0
        assert "Set telemetry configuration" in result.output

    @patch("raxe.cli.telemetry._get_config")
    def test_config_invalid_key(self, mock_config: MagicMock, runner: CliRunner) -> None:
        """Test config command with invalid key."""
        mock_config.return_value = MagicMock()

        result = runner.invoke(cli, ["telemetry", "config", "invalid_key", "100"])

        assert "Unknown key" in result.output


class TestTelemetryCommandGroup:
    """Test suite for telemetry command group registration."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    def test_telemetry_group_help(self, runner: CliRunner) -> None:
        """Test telemetry command group help."""
        result = runner.invoke(cli, ["telemetry", "--help"])
        assert result.exit_code == 0
        assert "Manage telemetry settings" in result.output
        assert "status" in result.output
        assert "dlq" in result.output
        assert "flush" in result.output
        assert "enable" in result.output
        assert "disable" in result.output
        assert "config" in result.output

    def test_telemetry_in_main_help(self, runner: CliRunner) -> None:
        """Test that telemetry appears in full CLI help (--help-all).

        Note: telemetry is an 'advanced' command and only appears in
        the full help output, not minimal help.
        """
        result = runner.invoke(cli, ["--help-all"])
        assert result.exit_code == 0
        assert "telemetry" in result.output
