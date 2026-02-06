"""Tests for CLI history commands.

Tests for:
- raxe history list-scans
- raxe history show <scan_id>
- raxe history stats
- raxe history export <scan_id>
- raxe history clean
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raxe.cli.history import history


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


def _make_scan_record(
    scan_id=1,
    threats_found=0,
    highest_severity=None,
    total_duration_ms=5.2,
    l1_duration_ms=2.0,
    l2_duration_ms=3.0,
):
    """Create a mock ScanRecord."""
    record = MagicMock()
    record.id = scan_id
    record.timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    record.prompt_hash = f"sha256:hash_{scan_id}"
    record.threats_found = threats_found
    record.highest_severity = highest_severity
    record.total_duration_ms = total_duration_ms
    record.l1_duration_ms = l1_duration_ms
    record.l2_duration_ms = l2_duration_ms
    return record


def _make_detection_record(rule_id="pi-001", severity="HIGH", confidence=0.95):
    """Create a mock DetectionRecord."""
    record = MagicMock()
    record.rule_id = rule_id
    record.severity = severity
    record.confidence = confidence
    record.detection_layer = "L1"
    record.category = "injection"
    return record


@pytest.fixture
def mock_db():
    """Create a mock ScanHistoryDB."""
    db = MagicMock()
    return db


class TestHistoryListScans:
    """Tests for raxe history list-scans command."""

    def test_list_empty(self, runner, mock_db):
        """Test listing scans when history is empty."""
        mock_db.list_scans.return_value = []
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["list-scans"])

        assert result.exit_code == 0
        assert "No scans" in result.output

    def test_list_with_entries(self, runner, mock_db):
        """Test listing scans with entries."""
        mock_db.list_scans.return_value = [
            _make_scan_record(scan_id=1, threats_found=0),
            _make_scan_record(scan_id=2, threats_found=1, highest_severity="HIGH"),
        ]
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["list-scans"])

        assert result.exit_code == 0
        assert "2025-01-15" in result.output

    def test_list_with_limit(self, runner, mock_db):
        """Test listing scans with --limit option."""
        mock_db.list_scans.return_value = [_make_scan_record(scan_id=1)]
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["list-scans", "--limit", "5"])

        assert result.exit_code == 0
        mock_db.list_scans.assert_called_once_with(limit=5, severity_filter=None)

    def test_list_with_severity_filter(self, runner, mock_db):
        """Test listing scans filtered by severity."""
        mock_db.list_scans.return_value = [
            _make_scan_record(scan_id=1, threats_found=1, highest_severity="CRITICAL"),
        ]
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["list-scans", "--severity", "CRITICAL"])

        assert result.exit_code == 0
        mock_db.list_scans.assert_called_once_with(limit=20, severity_filter="CRITICAL")

    def test_list_handles_db_error(self, runner, mock_db):
        """Test list handles database error gracefully."""
        mock_db.list_scans.side_effect = Exception("DB connection failed")
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["list-scans"])

        assert result.exit_code != 0
        assert "Error" in result.output


class TestHistoryShow:
    """Tests for raxe history show command."""

    def test_show_entry(self, runner, mock_db):
        """Test showing a specific scan entry."""
        mock_db.get_scan.return_value = _make_scan_record(
            scan_id=42, threats_found=1, highest_severity="HIGH"
        )
        mock_db.get_detections.return_value = [
            _make_detection_record(rule_id="pi-001"),
        ]
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["show", "42"])

        assert result.exit_code == 0
        assert "42" in result.output
        assert "pi-001" in result.output

    def test_show_nonexistent(self, runner, mock_db):
        """Test showing a nonexistent scan entry."""
        mock_db.get_scan.return_value = None
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["show", "999"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_show_entry_no_detections(self, runner, mock_db):
        """Test showing a scan with no detections."""
        mock_db.get_scan.return_value = _make_scan_record(scan_id=1, threats_found=0)
        mock_db.get_detections.return_value = []
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["show", "1"])

        assert result.exit_code == 0
        assert "Threats Found: 0" in result.output

    def test_show_displays_performance_metrics(self, runner, mock_db):
        """Test show displays L1/L2 duration metrics."""
        mock_db.get_scan.return_value = _make_scan_record(
            scan_id=1, l1_duration_ms=2.5, l2_duration_ms=8.3, total_duration_ms=11.0
        )
        mock_db.get_detections.return_value = []
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["show", "1"])

        assert result.exit_code == 0
        assert "2.50" in result.output
        assert "8.30" in result.output


class TestHistoryStats:
    """Tests for raxe history stats command."""

    def test_stats_displays_summary(self, runner, mock_db):
        """Test stats displays summary statistics."""
        mock_db.get_statistics.return_value = {
            "total_scans": 100,
            "scans_with_threats": 15,
            "threat_rate": 0.15,
            "severity_counts": {"HIGH": 10, "MEDIUM": 5},
            "avg_l1_duration_ms": 3.5,
            "avg_l2_duration_ms": 8.2,
            "avg_total_duration_ms": 12.0,
        }
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["stats"])

        assert result.exit_code == 0
        assert "100" in result.output
        assert "15" in result.output

    def test_stats_with_custom_days(self, runner, mock_db):
        """Test stats with --days option."""
        mock_db.get_statistics.return_value = {
            "total_scans": 10,
            "scans_with_threats": 2,
            "threat_rate": 0.2,
            "severity_counts": {},
            "avg_l1_duration_ms": None,
            "avg_l2_duration_ms": None,
            "avg_total_duration_ms": None,
        }
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["stats", "--days", "7"])

        assert result.exit_code == 0
        assert "7 days" in result.output
        mock_db.get_statistics.assert_called_once_with(days=7)


class TestHistoryExport:
    """Tests for raxe history export command."""

    def test_export_json_to_stdout(self, runner, mock_db):
        """Test exporting scan as JSON to stdout."""
        mock_db.export_to_json.return_value = {
            "scan_id": 1,
            "threats": 0,
        }
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["export", "1"])

        assert result.exit_code == 0
        assert "scan_id" in result.output

    def test_export_json_to_file(self, runner, mock_db, tmp_path):
        """Test exporting scan as JSON to a file."""
        output_file = tmp_path / "out.json"
        mock_db.export_to_json.return_value = {"scan_id": 1}
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["export", "1", "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["scan_id"] == 1

    def test_export_csv_format(self, runner, mock_db):
        """Test exporting scan as CSV."""
        mock_db.get_scan.return_value = _make_scan_record(scan_id=1)
        mock_db.get_detections.return_value = [
            _make_detection_record(rule_id="pi-001"),
        ]
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["export", "1", "--format", "csv"])

        assert result.exit_code == 0
        assert "scan_id" in result.output
        assert "pi-001" in result.output

    def test_export_csv_to_file(self, runner, mock_db, tmp_path):
        """Test exporting scan as CSV to a file."""
        output_file = tmp_path / "out.csv"
        mock_db.get_scan.return_value = _make_scan_record(scan_id=1)
        mock_db.get_detections.return_value = []
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(
                history,
                ["export", "1", "--format", "csv", "--output", str(output_file)],
            )

        assert result.exit_code == 0
        assert output_file.exists()


class TestHistoryClean:
    """Tests for raxe history clean command."""

    def test_clean_with_confirmation(self, runner, mock_db):
        """Test clean deletes old scans with --yes."""
        mock_db.cleanup_old_scans.return_value = 42
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["clean", "--yes"])

        assert result.exit_code == 0
        assert "42" in result.output
        mock_db.cleanup_old_scans.assert_called_once_with(retention_days=90)

    def test_clean_with_custom_days(self, runner, mock_db):
        """Test clean with --days option."""
        mock_db.cleanup_old_scans.return_value = 10
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["clean", "--days", "30", "--yes"])

        assert result.exit_code == 0
        mock_db.cleanup_old_scans.assert_called_once_with(retention_days=30)

    def test_clean_aborts_without_confirmation(self, runner, mock_db):
        """Test clean aborts when user declines."""
        with patch("raxe.cli.history.ScanHistoryDB", return_value=mock_db):
            result = runner.invoke(history, ["clean"], input="n\n")

        assert result.exit_code != 0 or "Abort" in result.output
        mock_db.cleanup_old_scans.assert_not_called()
