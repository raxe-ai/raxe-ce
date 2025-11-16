"""Tests for installation and usage tracking."""
import json
from pathlib import Path

import pytest

from raxe.infrastructure.tracking.usage import (
    InstallationInfo,
    UsageStats,
    UsageTracker,
    get_tracker,
)


class TestInstallationInfo:
    """Test InstallationInfo dataclass."""

    def test_create_installation_info(self):
        """Test creating installation info."""
        info = InstallationInfo(
            installation_id="test-123",
            installed_at="2025-01-01T00:00:00Z",
            python_version="3.11.0",
            os="darwin",
        )

        assert info.installation_id == "test-123"
        assert info.python_version == "3.11.0"
        assert info.os == "darwin"


class TestUsageStats:
    """Test UsageStats dataclass."""

    def test_create_usage_stats(self):
        """Test creating usage stats."""
        stats = UsageStats(
            total_scans=100,
            scans_with_threats=25,
        )

        assert stats.total_scans == 100
        assert stats.scans_with_threats == 25


class TestUsageTracker:
    """Test usage tracker."""

    @pytest.fixture
    def tracker(self, tmp_path: Path) -> UsageTracker:
        """Create test tracker."""
        return UsageTracker(data_dir=tmp_path)

    def test_init_creates_install_info(self, tmp_path: Path):
        """Test that initialization creates installation info."""
        UsageTracker(data_dir=tmp_path)

        install_file = tmp_path / "install.json"
        assert install_file.exists()

        # Load and verify
        with open(install_file) as f:
            data = json.load(f)
            assert "installation_id" in data
            assert "installed_at" in data
            assert "python_version" in data

    def test_installation_id_persistent(self, tmp_path: Path):
        """Test that installation ID persists across instances."""
        tracker1 = UsageTracker(data_dir=tmp_path)
        install_id1 = tracker1.get_install_info().installation_id

        # Create new tracker instance
        tracker2 = UsageTracker(data_dir=tmp_path)
        install_id2 = tracker2.get_install_info().installation_id

        # Should be same ID
        assert install_id1 == install_id2

    def test_record_first_scan(self, tracker: UsageTracker):
        """Test recording first scan."""
        tracker.record_first_scan()

        stats = tracker.get_usage_stats()

        assert stats.first_scan_at is not None
        assert stats.time_to_first_scan_seconds is not None
        assert stats.time_to_first_scan_seconds >= 0

    def test_record_first_scan_idempotent(self, tracker: UsageTracker):
        """Test that recording first scan multiple times doesn't change it."""
        tracker.record_first_scan()
        first_time = tracker.get_usage_stats().first_scan_at

        # Record again
        tracker.record_first_scan()
        second_time = tracker.get_usage_stats().first_scan_at

        # Should be same
        assert first_time == second_time

    def test_record_scan(self, tracker: UsageTracker):
        """Test recording a scan."""
        tracker.record_scan(found_threats=False)

        stats = tracker.get_usage_stats()

        assert stats.total_scans == 1
        assert stats.scans_with_threats == 0
        assert stats.last_scan_at is not None

    def test_record_scan_with_threats(self, tracker: UsageTracker):
        """Test recording scan with threats."""
        tracker.record_scan(found_threats=True)

        stats = tracker.get_usage_stats()

        assert stats.total_scans == 1
        assert stats.scans_with_threats == 1

    def test_record_multiple_scans(self, tracker: UsageTracker):
        """Test recording multiple scans."""
        tracker.record_scan(found_threats=False)
        tracker.record_scan(found_threats=True)
        tracker.record_scan(found_threats=True)

        stats = tracker.get_usage_stats()

        assert stats.total_scans == 3
        assert stats.scans_with_threats == 2

    def test_record_command(self, tracker: UsageTracker):
        """Test recording command usage."""
        tracker.record_command("scan")
        tracker.record_command("config")

        stats = tracker.get_usage_stats()

        assert "scan" in stats.commands_used
        assert "config" in stats.commands_used
        assert len(stats.commands_used) == 2

    def test_record_command_idempotent(self, tracker: UsageTracker):
        """Test that same command recorded multiple times only stored once."""
        tracker.record_command("scan")
        tracker.record_command("scan")

        stats = tracker.get_usage_stats()

        assert stats.commands_used.count("scan") == 1

    def test_record_feature(self, tracker: UsageTracker):
        """Test recording feature enablement."""
        tracker.record_feature("l2_detection")
        tracker.record_feature("telemetry")

        stats = tracker.get_usage_stats()

        assert "l2_detection" in stats.features_enabled
        assert "telemetry" in stats.features_enabled

    def test_get_dau(self, tracker: UsageTracker):
        """Test DAU (Daily Active User) check."""
        # Before any scans
        assert tracker.get_dau() is False

        # After scan today
        tracker.record_scan()
        assert tracker.get_dau() is True

    def test_get_wau(self, tracker: UsageTracker):
        """Test WAU (Weekly Active User) check."""
        # Before any scans
        assert tracker.get_wau() is False

        # After scan
        tracker.record_scan()
        assert tracker.get_wau() is True

    def test_get_mau(self, tracker: UsageTracker):
        """Test MAU (Monthly Active User) check."""
        # Before any scans
        assert tracker.get_mau() is False

        # After scan
        tracker.record_scan()
        assert tracker.get_mau() is True

    def test_get_activation_metrics(self, tracker: UsageTracker):
        """Test activation metrics."""
        tracker.record_scan(found_threats=True)
        tracker.record_scan(found_threats=False)

        metrics = tracker.get_activation_metrics()

        assert "installed_at" in metrics
        assert "first_scan_at" in metrics
        assert "time_to_first_scan_seconds" in metrics
        assert metrics["total_scans"] == 2
        assert metrics["scans_with_threats"] == 1
        assert metrics["threat_detection_rate"] == 0.5

    def test_get_retention_metrics(self, tracker: UsageTracker):
        """Test retention metrics."""
        tracker.record_scan()

        metrics = tracker.get_retention_metrics()

        assert "days_since_install" in metrics
        assert "retention_7d" in metrics
        assert "retention_30d" in metrics
        assert "total_active_days" in metrics
        assert "dau" in metrics
        assert "wau" in metrics
        assert "mau" in metrics

    def test_export_for_telemetry(self, tracker: UsageTracker):
        """Test exporting for telemetry."""
        tracker.record_scan(found_threats=True)
        tracker.record_command("scan")
        tracker.record_feature("l2_detection")

        export = tracker.export_for_telemetry()

        # Should include installation info
        assert "installation_id" in export
        assert "python_version" in export
        assert "os" in export

        # Should include metrics
        assert "activation" in export
        assert "retention" in export
        assert "commands_used" in export
        assert "features_enabled" in export

        # Should NOT include PII
        assert "api_key" not in str(export)
        assert "prompt" not in str(export)

    def test_persistence_across_instances(self, tmp_path: Path):
        """Test that usage stats persist across tracker instances."""
        # First instance
        tracker1 = UsageTracker(data_dir=tmp_path)
        tracker1.record_scan(found_threats=True)
        tracker1.record_command("scan")

        # Second instance
        tracker2 = UsageTracker(data_dir=tmp_path)
        stats = tracker2.get_usage_stats()

        # Should have persisted data
        assert stats.total_scans == 1
        assert "scan" in stats.commands_used


class TestGetTracker:
    """Test global tracker singleton."""

    def test_get_tracker_returns_instance(self):
        """Test that get_tracker returns a tracker."""
        tracker = get_tracker()

        assert isinstance(tracker, UsageTracker)

    def test_get_tracker_returns_singleton(self):
        """Test that get_tracker returns same instance."""
        tracker1 = get_tracker()
        tracker2 = get_tracker()

        # Should be same object
        assert tracker1 is tracker2


class TestPrivacy:
    """Test privacy requirements."""

    def test_no_pii_in_install_file(self, tmp_path: Path):
        """Test that installation file contains no PII."""
        UsageTracker(data_dir=tmp_path)

        install_file = tmp_path / "install.json"
        with open(install_file) as f:
            content = f.read()

            # Should not contain PII
            assert "password" not in content.lower()
            assert "secret" not in content.lower()
            assert "token" not in content.lower()

    def test_no_pii_in_usage_file(self, tmp_path: Path):
        """Test that usage file contains no PII."""
        tracker = UsageTracker(data_dir=tmp_path)
        tracker.record_scan()

        usage_file = tmp_path / "usage.json"
        with open(usage_file) as f:
            content = f.read()

            # Should not contain PII
            assert "prompt" not in content.lower()
            assert "api_key" not in content.lower()

    def test_export_contains_no_pii(self, tracker: UsageTracker):
        """Test that telemetry export contains no PII."""
        tracker.record_scan()

        export = tracker.export_for_telemetry()
        export_str = str(export)

        # Should not contain PII
        assert "prompt" not in export_str.lower()
        assert "password" not in export_str.lower()
        assert "secret" not in export_str.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
