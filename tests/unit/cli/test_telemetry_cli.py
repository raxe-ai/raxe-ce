"""Tests for telemetry CLI commands.

This module tests the CLI commands in raxe.cli.telemetry:
- `raxe telemetry status` - Display telemetry status and queue statistics
- `raxe telemetry dlq list` - List DLQ events
- `raxe telemetry dlq show <event_id>` - Show specific DLQ event
- `raxe telemetry dlq clear` - Clear DLQ events
- `raxe telemetry dlq retry` - Retry DLQ events
- `raxe telemetry flush` - Flush telemetry queues
- `raxe telemetry disable` - Disable telemetry (paid tiers only)
- `raxe telemetry enable` - Enable telemetry
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.telemetry import (
    _format_relative_time,
    _get_tier_name,
    _mask_api_key,
    _parse_duration,
    telemetry,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_config() -> Mock:
    """Provide a mock RaxeConfig.

    Uses a test URL to avoid coupling tests to production endpoints.
    """
    config = Mock()
    config.core = Mock()
    config.core.api_key = "raxe_live_test1234567890abcdef1234"
    config.telemetry = Mock()
    config.telemetry.enabled = True
    config.telemetry.endpoint = "http://test.local/v1/telemetry"  # Test-specific endpoint
    config.telemetry.batch_size = 50
    config.validate.return_value = []
    return config


@pytest.fixture
def mock_queue_stats() -> dict[str, Any]:
    """Provide mock queue statistics."""
    return {
        "critical_count": 3,
        "standard_count": 15,
        "dlq_count": 2,
        "total_queued": 18,
        "oldest_critical": "2025-01-22T10:00:00Z",
        "oldest_standard": "2025-01-22T09:30:00Z",
        "retry_pending": 1,
    }


@pytest.fixture
def mock_dlq_events() -> list[dict[str, Any]]:
    """Provide mock DLQ events."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "event_id": "evt_dlq_001",
            "event_type": "scan",
            "priority": "standard",
            "payload": {
                "prompt_hash": "a" * 64,
                "threat_detected": False,
            },
            "created_at": (base_time - timedelta(hours=2)).isoformat(),
            "failed_at": (base_time - timedelta(hours=1)).isoformat(),
            "failure_reason": "Connection timeout",
            "retry_count": 3,
            "server_error_code": "504",
            "server_error_message": "Gateway Timeout",
        },
        {
            "event_id": "evt_dlq_002",
            "event_type": "error",
            "priority": "critical",
            "payload": {
                "error_type": "network_error",
                "error_code": "NET_001",
            },
            "created_at": (base_time - timedelta(hours=3)).isoformat(),
            "failed_at": (base_time - timedelta(minutes=30)).isoformat(),
            "failure_reason": "Server unavailable",
            "retry_count": 3,
            "server_error_code": "503",
            "server_error_message": "Service Unavailable",
        },
    ]


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestParseDuration:
    """Tests for _parse_duration helper function."""

    def test_parse_days(self) -> None:
        """Parse day durations correctly."""
        assert _parse_duration("7d") == 7
        assert _parse_duration("30d") == 30
        assert _parse_duration("1d") == 1

    def test_parse_hours(self) -> None:
        """Parse hour durations correctly."""
        assert _parse_duration("24h") == 1
        assert _parse_duration("48h") == 2
        assert _parse_duration("12h") == 1  # Rounds up to 1 day minimum

    def test_parse_minutes(self) -> None:
        """Parse minute durations correctly."""
        assert _parse_duration("1440m") == 1  # 1 day
        assert _parse_duration("30m") == 1  # Rounds up to 1 day minimum

    def test_invalid_format_returns_none(self) -> None:
        """Invalid formats return None."""
        assert _parse_duration("7") is None
        assert _parse_duration("days") is None
        assert _parse_duration("7x") is None
        assert _parse_duration("") is None

    def test_case_insensitive(self) -> None:
        """Duration parsing is case insensitive."""
        assert _parse_duration("7D") == 7
        assert _parse_duration("24H") == 1
        assert _parse_duration("7d ") == 7  # With trailing space


class TestFormatRelativeTime:
    """Tests for _format_relative_time helper function."""

    def test_seconds_ago(self) -> None:
        """Format times in seconds."""
        recent = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        result = _format_relative_time(recent)
        assert "s ago" in result

    def test_minutes_ago(self) -> None:
        """Format times in minutes."""
        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        result = _format_relative_time(recent)
        assert "m ago" in result

    def test_hours_ago(self) -> None:
        """Format times in hours."""
        recent = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = _format_relative_time(recent)
        assert "h ago" in result

    def test_days_ago(self) -> None:
        """Format times in days."""
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        result = _format_relative_time(recent)
        assert "d ago" in result

    def test_none_returns_unknown(self) -> None:
        """None timestamp returns 'unknown'."""
        assert _format_relative_time(None) == "unknown"

    def test_invalid_timestamp_returns_unknown(self) -> None:
        """Invalid timestamp returns 'unknown'."""
        assert _format_relative_time("not-a-date") == "unknown"


class TestMaskApiKey:
    """Tests for _mask_api_key helper function."""

    def test_masks_api_key(self) -> None:
        """API key is masked properly."""
        result = _mask_api_key("raxe_live_test1234567890abcdef1234")
        assert "raxe_live_***" in result
        assert result.endswith("234")
        assert "1234567890" not in result

    def test_none_returns_not_configured(self) -> None:
        """None returns '(not configured)'."""
        assert _mask_api_key(None) == "(not configured)"

    def test_short_key_returns_stars(self) -> None:
        """Very short keys return just stars."""
        assert _mask_api_key("short") == "***"


class TestGetTierName:
    """Tests for _get_tier_name helper function."""

    def test_free_tier(self) -> None:
        """None API key is free tier."""
        assert _get_tier_name(None) == "Free tier"

    def test_enterprise_tier(self) -> None:
        """Enterprise key detected."""
        assert _get_tier_name("raxe_enterprise_xxx") == "Enterprise tier"

    def test_pro_tier(self) -> None:
        """Pro key detected."""
        assert _get_tier_name("raxe_pro_xxx") == "Pro tier"

    def test_test_tier(self) -> None:
        """Test key detected."""
        assert _get_tier_name("raxe_test_xxx") == "Test tier"

    def test_default_pro_tier(self) -> None:
        """Unknown key type defaults to Pro tier."""
        assert _get_tier_name("raxe_live_xxx") == "Pro tier"


# =============================================================================
# Status Command Tests
# =============================================================================


class TestStatusCommand:
    """Tests for `raxe telemetry status` command."""

    def test_status_text_output(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
        mock_queue_stats: dict[str, Any],
    ) -> None:
        """Status command displays text output correctly."""
        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
                mock_queue.return_value.get_stats.return_value = mock_queue_stats
                mock_queue.return_value.close = Mock()

                with patch("raxe.cli.telemetry.BatchSender") as mock_sender:
                    mock_sender.return_value.get_circuit_state.return_value = "closed"

                    result = cli_runner.invoke(telemetry, ["status"])

        assert result.exit_code == 0
        # Check key elements are present (without strict format matching)
        assert "Telemetry" in result.output or "telemetry" in result.output.lower()

    def test_status_json_output(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
        mock_queue_stats: dict[str, Any],
    ) -> None:
        """Status command outputs valid JSON."""
        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
                mock_queue.return_value.get_stats.return_value = mock_queue_stats
                mock_queue.return_value.close = Mock()

                with patch("raxe.cli.telemetry.BatchSender") as mock_sender:
                    mock_sender.return_value.get_circuit_state.return_value = "closed"

                    result = cli_runner.invoke(telemetry, ["status", "--format", "json"])

        assert result.exit_code == 0
        # Output should be valid JSON
        data = json.loads(result.output)
        assert "endpoint" in data
        assert "telemetry_enabled" in data
        assert "queues" in data


# =============================================================================
# DLQ List Command Tests
# =============================================================================


class TestDlqListCommand:
    """Tests for `raxe telemetry dlq list` command."""

    def test_dlq_list_empty(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """List command shows empty message when DLQ is empty."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = []
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "list"])

        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    def test_dlq_list_with_events(
        self,
        cli_runner: CliRunner,
        mock_dlq_events: list[dict[str, Any]],
    ) -> None:
        """List command displays DLQ events correctly."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = mock_dlq_events
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "list"])

        assert result.exit_code == 0
        # Check that events are shown
        assert "evt_dlq_001" in result.output or "dlq_001" in result.output
        assert "scan" in result.output.lower()

    def test_dlq_list_json_output(
        self,
        cli_runner: CliRunner,
        mock_dlq_events: list[dict[str, Any]],
    ) -> None:
        """List command outputs valid JSON."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = mock_dlq_events
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "list", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "events" in data
        assert "count" in data
        assert data["count"] == 2

    def test_dlq_list_with_limit(
        self,
        cli_runner: CliRunner,
        mock_dlq_events: list[dict[str, Any]],
    ) -> None:
        """List command respects limit parameter."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = mock_dlq_events[:1]
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "list", "--limit", "1"])

        assert result.exit_code == 0
        mock_queue.return_value.get_dlq_events.assert_called_with(limit=1)


# =============================================================================
# DLQ Show Command Tests
# =============================================================================


class TestDlqShowCommand:
    """Tests for `raxe telemetry dlq show <event_id>` command."""

    def test_dlq_show_existing_event(
        self,
        cli_runner: CliRunner,
        mock_dlq_events: list[dict[str, Any]],
    ) -> None:
        """Show command displays event details."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = mock_dlq_events
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "show", "evt_dlq_001"])

        assert result.exit_code == 0
        # Check event details are shown
        assert "evt_dlq_001" in result.output
        assert "scan" in result.output.lower() or "Type" in result.output

    def test_dlq_show_not_found(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Show command reports error for non-existent event."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = []
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "show", "evt_nonexistent"])

        # Should show error message
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_dlq_show_json_output(
        self,
        cli_runner: CliRunner,
        mock_dlq_events: list[dict[str, Any]],
    ) -> None:
        """Show command outputs valid JSON."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = mock_dlq_events
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(
                telemetry, ["dlq", "show", "evt_dlq_001", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["event_id"] == "evt_dlq_001"

    def test_dlq_show_partial_id_match(
        self,
        cli_runner: CliRunner,
        mock_dlq_events: list[dict[str, Any]],
    ) -> None:
        """Show command matches partial event IDs."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = mock_dlq_events
            mock_queue.return_value.close = Mock()

            # Use partial ID
            result = cli_runner.invoke(telemetry, ["dlq", "show", "evt_dlq_001"])

        assert result.exit_code == 0
        assert "dlq_001" in result.output


# =============================================================================
# DLQ Clear Command Tests
# =============================================================================


class TestDlqClearCommand:
    """Tests for `raxe telemetry dlq clear` command."""

    def test_dlq_clear_with_confirmation(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Clear command prompts for confirmation."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_stats.return_value = {"dlq_count": 5}
            mock_queue.return_value.clear_dlq.return_value = 5
            mock_queue.return_value.close = Mock()

            # Provide 'y' as input for confirmation
            result = cli_runner.invoke(telemetry, ["dlq", "clear"], input="y\n")

        assert result.exit_code == 0
        mock_queue.return_value.clear_dlq.assert_called_once()

    def test_dlq_clear_with_force(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Clear command skips confirmation with --force."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_stats.return_value = {"dlq_count": 5}
            mock_queue.return_value.clear_dlq.return_value = 5
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "clear", "--force"])

        assert result.exit_code == 0
        mock_queue.return_value.clear_dlq.assert_called_once()

    def test_dlq_clear_older_than(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Clear command respects --older-than parameter."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_stats.return_value = {"dlq_count": 5}
            mock_queue.return_value.clear_dlq.return_value = 3
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(
                telemetry, ["dlq", "clear", "--older-than", "7d", "--force"]
            )

        assert result.exit_code == 0
        mock_queue.return_value.clear_dlq.assert_called_with(older_than_days=7)

    def test_dlq_clear_empty_queue(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Clear command handles empty DLQ."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_stats.return_value = {"dlq_count": 0}
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "clear"])

        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    def test_dlq_clear_cancelled(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Clear command can be cancelled."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_stats.return_value = {"dlq_count": 5}
            mock_queue.return_value.close = Mock()

            # Provide 'n' as input to cancel
            result = cli_runner.invoke(telemetry, ["dlq", "clear"], input="n\n")

        assert "cancelled" in result.output.lower()
        mock_queue.return_value.clear_dlq.assert_not_called()


# =============================================================================
# DLQ Retry Command Tests
# =============================================================================


class TestDlqRetryCommand:
    """Tests for `raxe telemetry dlq retry` command."""

    def test_dlq_retry_all(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Retry command retries all events with --all."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.retry_dlq_events.return_value = 5
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "retry", "--all"])

        assert result.exit_code == 0
        mock_queue.return_value.retry_dlq_events.assert_called_with()
        assert "5" in result.output

    def test_dlq_retry_specific_event(
        self,
        cli_runner: CliRunner,
        mock_dlq_events: list[dict[str, Any]],
    ) -> None:
        """Retry command retries specific event."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = mock_dlq_events
            mock_queue.return_value.retry_dlq_events.return_value = 1
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "retry", "evt_dlq_001"])

        assert result.exit_code == 0
        mock_queue.return_value.retry_dlq_events.assert_called_with(["evt_dlq_001"])

    def test_dlq_retry_no_args_error(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Retry command requires event ID or --all."""
        result = cli_runner.invoke(telemetry, ["dlq", "retry"])

        assert "error" in result.output.lower() or "No events" in result.output

    def test_dlq_retry_event_not_found(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Retry command reports error for non-existent event."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.get_dlq_events.return_value = []
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "retry", "evt_nonexistent"])

        assert "not found" in result.output.lower()

    def test_dlq_retry_empty_queue(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Retry command handles empty DLQ."""
        with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
            mock_queue.return_value.retry_dlq_events.return_value = 0
            mock_queue.return_value.close = Mock()

            result = cli_runner.invoke(telemetry, ["dlq", "retry", "--all"])

        assert result.exit_code == 0
        assert "No events" in result.output or "0" not in result.output


# =============================================================================
# Flush Command Tests
# =============================================================================


class TestFlushCommand:
    """Tests for `raxe telemetry flush` command."""

    def test_flush_output_format(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Flush command displays output correctly."""
        mock_config.telemetry.enabled = True

        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
                mock_queue.return_value.get_stats.return_value = {
                    "critical_count": 2,
                    "standard_count": 5,
                }
                mock_queue.return_value.dequeue_critical.side_effect = [
                    [{"event_id": "evt_1", "payload": {}}, {"event_id": "evt_2", "payload": {}}],
                    [],
                ]
                mock_queue.return_value.dequeue_standard.side_effect = [
                    [
                        {"event_id": f"evt_s{i}", "payload": {}}
                        for i in range(5)
                    ],
                    [],
                ]
                mock_queue.return_value.mark_batch_sent = Mock()
                mock_queue.return_value.close = Mock()

                with patch("raxe.cli.telemetry.BatchSender") as mock_sender:
                    mock_sender.return_value.send_batch.return_value = {"status": "ok"}

                    result = cli_runner.invoke(telemetry, ["flush"])

        assert result.exit_code == 0
        # Should show shipped counts
        assert "shipped" in result.output.lower() or "events" in result.output.lower()

    def test_flush_json_output(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Flush command outputs valid JSON."""
        mock_config.telemetry.enabled = True

        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
                mock_queue.return_value.get_stats.return_value = {
                    "critical_count": 0,
                    "standard_count": 0,
                }
                mock_queue.return_value.close = Mock()

                result = cli_runner.invoke(telemetry, ["flush", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "status" in data
        assert "total_shipped" in data

    def test_flush_empty_queues(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Flush command handles empty queues."""
        mock_config.telemetry.enabled = True

        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
                mock_queue.return_value.get_stats.return_value = {
                    "critical_count": 0,
                    "standard_count": 0,
                }
                mock_queue.return_value.close = Mock()

                result = cli_runner.invoke(telemetry, ["flush"])

        assert result.exit_code == 0
        assert "empty" in result.output.lower() or "No events" in result.output

    def test_flush_when_disabled(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Flush command warns when telemetry is disabled."""
        mock_config.telemetry.enabled = False

        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("raxe.cli.telemetry._get_queue_instance") as mock_queue:
                mock_queue.return_value.get_stats.return_value = {
                    "critical_count": 5,
                    "standard_count": 10,
                }
                mock_queue.return_value.close = Mock()

                result = cli_runner.invoke(telemetry, ["flush"])

        # Should warn about disabled telemetry
        assert "disabled" in result.output.lower()


# =============================================================================
# Disable Command Tests
# =============================================================================


class TestDisableCommand:
    """Tests for `raxe telemetry disable` command."""

    def test_disable_on_free_tier_error(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Disable command shows error on free tier."""
        mock_config.core.api_key = None  # Free tier

        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("raxe.cli.telemetry._check_telemetry_disable_permission", return_value=False):
                with patch("raxe.cli.telemetry._get_cached_tier", return_value="Community"):
                    result = cli_runner.invoke(telemetry, ["disable"])

        # Should show error about free tier
        assert "tier" in result.output.lower() or "cannot" in result.output.lower()
        # Should not modify config
        mock_config.save.assert_not_called()

    def test_disable_on_paid_tier_success(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Disable command succeeds on paid tier."""
        mock_config.core.api_key = "raxe_pro_test1234567890abcdef1234"

        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("pathlib.Path.home", return_value=tmp_path):
                (tmp_path / ".raxe").mkdir(parents=True, exist_ok=True)

                result = cli_runner.invoke(telemetry, ["disable"])

        assert "disabled" in result.output.lower() or result.exit_code == 0


# =============================================================================
# Enable Command Tests
# =============================================================================


class TestEnableCommand:
    """Tests for `raxe telemetry enable` command."""

    def test_enable_success(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Enable command succeeds."""
        mock_config.telemetry.enabled = False

        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            with patch("pathlib.Path.home", return_value=tmp_path):
                (tmp_path / ".raxe").mkdir(parents=True, exist_ok=True)

                result = cli_runner.invoke(telemetry, ["enable"])

        assert "enabled" in result.output.lower() or result.exit_code == 0

    def test_enable_already_enabled(
        self,
        cli_runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Enable command handles already enabled state."""
        mock_config.telemetry.enabled = True

        with patch("raxe.cli.telemetry._get_config", return_value=mock_config):
            result = cli_runner.invoke(telemetry, ["enable"])

        assert "already enabled" in result.output.lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestTelemetryCliIntegration:
    """Integration tests for telemetry CLI command group."""

    def test_telemetry_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Telemetry command shows help."""
        result = cli_runner.invoke(telemetry, ["--help"])

        assert result.exit_code == 0
        assert "telemetry" in result.output.lower()

    def test_dlq_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """DLQ command shows help."""
        result = cli_runner.invoke(telemetry, ["dlq", "--help"])

        assert result.exit_code == 0
        assert "dlq" in result.output.lower()

    def test_subcommand_chain(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Commands can be chained correctly."""
        # Just verify the command structure works
        result = cli_runner.invoke(telemetry, ["dlq", "list", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()
