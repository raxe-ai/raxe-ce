"""Tests for CLI export command.

Tests for:
- raxe export (default JSON)
- raxe export --format csv
- raxe export --output <file>
- raxe export --days <n>
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from raxe.cli.export import export


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_scan_data():
    """Sample scan history data."""
    return [
        {
            "timestamp": "2025-01-15T10:00:00+00:00",
            "prompt_hash": "hash_0",
            "has_threats": True,
            "detection_count": 1,
            "highest_severity": "high",
            "duration_ms": 5.2,
        },
        {
            "timestamp": "2025-01-14T10:00:00+00:00",
            "prompt_hash": "hash_1",
            "has_threats": False,
            "detection_count": 0,
            "highest_severity": "none",
            "duration_ms": 5.3,
        },
    ]


class TestExportJson:
    """Tests for export in JSON format."""

    def test_export_json_default(self, runner, tmp_path, sample_scan_data):
        """Test default JSON export creates file."""
        with (
            runner.isolated_filesystem(temp_dir=tmp_path),
            patch("raxe.cli.export._load_scan_history", return_value=sample_scan_data),
        ):
            result = runner.invoke(export, obj={"quiet": True})

        assert result.exit_code == 0
        assert "Exported" in result.output

    def test_export_json_to_file(self, runner, tmp_path, sample_scan_data):
        """Test JSON export to specified file."""
        output_file = tmp_path / "output.json"
        with patch("raxe.cli.export._load_scan_history", return_value=sample_scan_data):
            result = runner.invoke(export, ["--output", str(output_file)], obj={"quiet": True})

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "scans" in data
        assert data["record_count"] == 2

    def test_export_json_structure(self, runner, tmp_path, sample_scan_data):
        """Test exported JSON has correct structure."""
        output_file = tmp_path / "output.json"
        with patch("raxe.cli.export._load_scan_history", return_value=sample_scan_data):
            result = runner.invoke(export, ["--output", str(output_file)], obj={"quiet": True})

        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        assert "exported_at" in data
        assert "record_count" in data
        assert "scans" in data
        assert len(data["scans"]) == 2


class TestExportCsv:
    """Tests for export in CSV format."""

    def test_export_csv_format(self, runner, tmp_path, sample_scan_data):
        """Test CSV export creates valid file."""
        output_file = tmp_path / "output.csv"
        with patch("raxe.cli.export._load_scan_history", return_value=sample_scan_data):
            result = runner.invoke(
                export,
                ["--format", "csv", "--output", str(output_file)],
                obj={"quiet": True},
            )

        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        # CSV should have header row
        assert "timestamp" in content or "prompt_hash" in content

    def test_export_csv_to_file(self, runner, tmp_path, sample_scan_data):
        """Test CSV export to specified file."""
        output_file = tmp_path / "scans.csv"
        with patch("raxe.cli.export._load_scan_history", return_value=sample_scan_data):
            result = runner.invoke(
                export,
                ["--format", "csv", "--output", str(output_file)],
                obj={"quiet": True},
            )

        assert result.exit_code == 0
        assert output_file.exists()
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) >= 3  # header + 2 data rows


class TestExportDays:
    """Tests for export --days option."""

    def test_export_custom_days(self, runner, tmp_path, sample_scan_data):
        """Test export with custom days parameter."""
        output_file = tmp_path / "output.json"
        with patch(
            "raxe.cli.export._load_scan_history", return_value=sample_scan_data
        ) as mock_load:
            result = runner.invoke(
                export,
                ["--days", "7", "--output", str(output_file)],
                obj={"quiet": True},
            )

        assert result.exit_code == 0
        mock_load.assert_called_once_with(7)


class TestExportEmptyData:
    """Tests for export with empty data."""

    def test_export_empty_data(self, runner, tmp_path):
        """Test export when no scan history exists."""
        with patch("raxe.cli.export._load_scan_history", return_value=[]):
            result = runner.invoke(export, obj={"quiet": True})

        assert result.exit_code == 0
        assert "No scan history" in result.output


class TestExportErrors:
    """Tests for export error handling."""

    def test_export_handles_load_error(self, runner, tmp_path):
        """Test export handles data loading error."""
        with patch(
            "raxe.cli.export._load_scan_history",
            side_effect=Exception("DB error"),
        ):
            result = runner.invoke(export, obj={"quiet": True})

        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "Error" in result.output
