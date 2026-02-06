"""Tests for RAXE profile CLI command.

Tests cover:
- Profile with text input
- Profile with rule filter (--no-l2)
- JSON output
- Table output
- Tree output (default)
- Error handling
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.profiler import profile_command


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_profile_result():
    """Create a mock ProfileResult object."""
    # Build mock L1 profile
    rule_profile = MagicMock()
    rule_profile.rule_id = "pi-001"
    rule_profile.execution_time_ms = 0.5
    rule_profile.matched = True
    rule_profile.cache_hit = False

    l1_profile = MagicMock()
    l1_profile.total_time_ms = 3.0
    l1_profile.cache_hits = 10
    l1_profile.cache_misses = 5
    l1_profile.cache_hit_rate = 0.67
    l1_profile.slowest_rules = [rule_profile]
    l1_profile.rule_profiles = [rule_profile]

    # Build mock profile result
    profile = MagicMock()
    profile.total_time_ms = 5.0
    profile.text_length = 20
    profile.timestamp = "2025-06-01T00:00:00Z"
    profile.l1_profile = l1_profile
    profile.l2_profile = None
    profile.overhead_ms = 2.0
    profile.l1_percentage = 60.0
    profile.l2_percentage = 0.0
    profile.overhead_percentage = 40.0
    profile.identify_bottlenecks.return_value = []
    profile.get_recommendations.return_value = []

    return profile


@pytest.fixture
def mock_raxe_profiler(mock_profile_result):
    """Patch Raxe and ScanProfiler for profiling tests."""
    with (
        patch("raxe.cli.profiler.Raxe") as mock_raxe_cls,
        patch("raxe.cli.profiler.ScanProfiler") as mock_profiler_cls,
    ):
        raxe = mock_raxe_cls.return_value
        raxe.get_profiling_components.return_value = {
            "executor": MagicMock(),
            "l2_detector": MagicMock(),
            "rules": [MagicMock()],
        }

        profiler = mock_profiler_cls.return_value
        profiler.profile_scan.return_value = mock_profile_result

        yield {
            "raxe": raxe,
            "profiler": profiler,
            "profile_result": mock_profile_result,
        }


class TestProfileTreeOutput:
    """Tests for default tree output."""

    def test_profile_default_tree_output(self, runner, mock_raxe_profiler):
        """Test profile command with default tree output."""
        result = runner.invoke(profile_command, ["test prompt"], obj={})

        assert result.exit_code == 0
        assert "profile" in result.output.lower() or "time" in result.output.lower()

    def test_profile_calls_profiler(self, runner, mock_raxe_profiler):
        """Test that profile command calls ScanProfiler."""
        runner.invoke(profile_command, ["test prompt"], obj={})

        mock_raxe_profiler["profiler"].profile_scan.assert_called_once()


class TestProfileTableOutput:
    """Tests for table output format."""

    def test_profile_table_output(self, runner, mock_raxe_profiler):
        """Test profile command with table format."""
        result = runner.invoke(profile_command, ["test prompt", "--format", "table"], obj={})

        assert result.exit_code == 0
        assert "profile" in result.output.lower() or "metric" in result.output.lower()


class TestProfileJsonOutput:
    """Tests for JSON output format."""

    def test_profile_json_output(self, runner, mock_raxe_profiler):
        """Test profile command with JSON format."""
        result = runner.invoke(profile_command, ["test prompt", "--format", "json"], obj={})

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_time_ms" in data
        assert "layers" in data
        assert "l1" in data["layers"]

    def test_profile_json_contains_overhead(self, runner, mock_raxe_profiler):
        """Test JSON output includes overhead metrics."""
        result = runner.invoke(profile_command, ["test prompt", "--format", "json"], obj={})

        data = json.loads(result.output)
        assert "overhead_ms" in data
        assert "overhead_percentage" in data


class TestProfileNoL2:
    """Tests for --no-l2 flag."""

    def test_profile_no_l2(self, runner, mock_raxe_profiler):
        """Test profile command with L2 disabled."""
        result = runner.invoke(profile_command, ["test prompt", "--no-l2"], obj={})

        assert result.exit_code == 0
        # Verify L2 detector was not passed
        call_kwargs = mock_raxe_profiler["profiler"].profile_scan.call_args
        assert call_kwargs[1]["include_l2"] is False


class TestProfileErrors:
    """Tests for error handling."""

    def test_profile_raxe_init_failure(self, runner):
        """Test profile command when Raxe fails to initialize."""
        with patch("raxe.cli.profiler.Raxe", side_effect=Exception("No config")):
            result = runner.invoke(profile_command, ["test prompt"], obj={})

            assert result.exit_code != 0

    def test_profile_profiler_failure(self, runner):
        """Test profile command when profiling fails."""
        with (
            patch("raxe.cli.profiler.Raxe") as mock_raxe_cls,
            patch("raxe.cli.profiler.ScanProfiler") as mock_profiler_cls,
        ):
            raxe = mock_raxe_cls.return_value
            raxe.get_profiling_components.return_value = {
                "executor": MagicMock(),
                "l2_detector": MagicMock(),
                "rules": [MagicMock()],
            }
            profiler = mock_profiler_cls.return_value
            profiler.profile_scan.side_effect = Exception("Profiling error")

            result = runner.invoke(profile_command, ["test prompt"], obj={})

            assert result.exit_code != 0


class TestProfileQuietMode:
    """Tests for quiet mode."""

    def test_profile_quiet_mode_tree(self, runner, mock_raxe_profiler):
        """Test quiet mode suppresses logo for tree output."""
        with patch("raxe.cli.branding.print_logo") as mock_logo:
            result = runner.invoke(profile_command, ["test prompt"], obj={"quiet": True})

            assert result.exit_code == 0
            mock_logo.assert_not_called()

    def test_profile_json_skips_logo(self, runner, mock_raxe_profiler):
        """Test JSON format skips logo even without quiet mode."""
        result = runner.invoke(profile_command, ["test prompt", "--format", "json"], obj={})

        assert result.exit_code == 0
        # JSON output should be parseable (no logo garbage)
        data = json.loads(result.output)
        assert isinstance(data, dict)
