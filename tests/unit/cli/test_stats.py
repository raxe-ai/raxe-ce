"""Tests for RAXE stats CLI command.

Tests cover:
- Default text output
- JSON format output
- Global stats flag
- Retention display
- Empty data handling
- Export to file
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.stats import stats


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_user_stats():
    """Create mock UserStats object."""
    user_stats = MagicMock()
    user_stats.installation_id = "abc123"
    user_stats.installation_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    user_stats.time_to_first_scan_seconds = 10.0
    user_stats.total_scans = 100
    user_stats.threats_detected = 5
    user_stats.detection_rate = 5.0
    user_stats.last_scan = datetime(2025, 6, 1, tzinfo=timezone.utc)
    user_stats.avg_scan_time_ms = 4.2
    user_stats.l1_detections = 4
    user_stats.l2_detections = 1
    return user_stats


@pytest.fixture
def mock_analytics(mock_user_stats):
    """Patch all analytics dependencies."""
    with (
        patch("raxe.cli.stats.AnalyticsEngine") as mock_engine_cls,
        patch("raxe.cli.stats.DataAggregator") as mock_agg_cls,
        patch("raxe.cli.stats.StreakTracker") as mock_streak_cls,
        patch("raxe.cli.stats._get_installation_id", return_value="abc123"),
    ):
        engine = mock_engine_cls.return_value
        engine.get_user_stats.return_value = mock_user_stats
        engine.get_global_stats.return_value = {
            "community": {"total_users": 500, "active_this_week": 50, "total_scans": 10000},
            "threats": {
                "total_detected": 200,
                "detection_rate": 2.0,
                "critical_threats": 10,
                "by_severity": {"critical": 10, "high": 40, "medium": 100, "low": 50},
            },
            "performance": {"avg_scan_time_ms": 5.0, "p95_latency_ms": 12.0},
        }
        engine.calculate_retention.return_value = {
            "cohort_date": "2025-01-01",
            "cohort_size": 100,
            "day_1": 80.0,
            "day_7": 60.0,
            "day_30": 40.0,
        }

        streak = mock_streak_cls.return_value
        streak.get_streak_info.return_value = {"current_streak": 5, "longest_streak": 10}
        streak.get_progress_summary.return_value = {
            "unlocked": 3,
            "total_achievements": 10,
            "completion_percentage": 30.0,
            "total_points": 150,
        }
        streak.get_unlocked_achievements.return_value = []

        yield {
            "engine": engine,
            "aggregator": mock_agg_cls.return_value,
            "streak": streak,
        }


class TestStatsDefault:
    """Tests for default stats output."""

    def test_stats_default_output(self, runner, mock_analytics):
        """Test default text output displays user stats."""
        result = runner.invoke(stats, [], obj={})

        assert result.exit_code == 0
        assert "Statistics" in result.output or "scans" in result.output.lower()

    def test_stats_calls_analytics_engine(self, runner, mock_analytics):
        """Test that stats command initializes and uses analytics engine."""
        runner.invoke(stats, [], obj={})

        mock_analytics["engine"].get_user_stats.assert_called_once_with("abc123")
        mock_analytics["engine"].close.assert_called_once()


class TestStatsJsonFormat:
    """Tests for JSON format output."""

    def test_stats_json_format(self, runner, mock_analytics):
        """Test JSON output is valid JSON."""
        result = runner.invoke(stats, ["--format", "json"], obj={})

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "user" in data
        assert "streaks" in data
        assert "achievements" in data

    def test_stats_json_contains_user_data(self, runner, mock_analytics):
        """Test JSON output contains user statistics."""
        result = runner.invoke(stats, ["--format", "json"], obj={})

        data = json.loads(result.output)
        assert data["user"]["installation_id"] == "abc123"
        assert data["user"]["total_scans"] == 100
        assert data["user"]["threats_detected"] == 5


class TestStatsGlobal:
    """Tests for global stats flag."""

    def test_stats_global_flag(self, runner, mock_analytics):
        """Test --global shows global statistics."""
        result = runner.invoke(stats, ["--global"], obj={})

        assert result.exit_code == 0
        mock_analytics["engine"].get_global_stats.assert_called_once()

    def test_stats_global_json(self, runner, mock_analytics):
        """Test --global with JSON format."""
        result = runner.invoke(stats, ["--global", "--format", "json"], obj={})

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "community" in data
        assert "threats" in data


class TestStatsRetention:
    """Tests for retention display."""

    def test_stats_retention_flag(self, runner, mock_analytics):
        """Test --retention shows retention analysis."""
        result = runner.invoke(stats, ["--retention"], obj={})

        assert result.exit_code == 0
        mock_analytics["engine"].calculate_retention.assert_called_once()

    def test_stats_retention_json(self, runner, mock_analytics):
        """Test --retention with JSON format."""
        result = runner.invoke(stats, ["--retention", "--format", "json"], obj={})

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "cohort_size" in data
        assert "day_1" in data


class TestStatsExport:
    """Tests for export functionality."""

    def test_stats_export_to_file(self, runner, mock_analytics, tmp_path):
        """Test exporting stats to a JSON file."""
        export_file = str(tmp_path / "stats.json")
        result = runner.invoke(stats, ["--export", export_file], obj={})

        assert result.exit_code == 0
        assert "exported" in result.output.lower()

        # Verify file was created with valid JSON
        with open(export_file) as f:
            data = json.load(f)
        assert "user" in data


class TestStatsQuietMode:
    """Tests for quiet mode."""

    def test_stats_quiet_mode_skips_logo(self, runner, mock_analytics):
        """Test quiet mode suppresses logo output."""
        with patch("raxe.cli.branding.print_logo") as mock_logo:
            result = runner.invoke(stats, [], obj={"quiet": True})

            assert result.exit_code == 0
            mock_logo.assert_not_called()


class TestStatsError:
    """Tests for error handling."""

    def test_stats_handles_engine_error(self, runner):
        """Test stats command handles analytics engine errors gracefully."""
        with (
            patch("raxe.cli.stats.AnalyticsEngine", side_effect=Exception("DB error")),
            patch("raxe.cli.stats.DataAggregator"),
            patch("raxe.cli.stats.StreakTracker"),
        ):
            result = runner.invoke(stats, [], obj={})

            # Should abort due to exception
            assert result.exit_code != 0
