"""Tests for MSSP audit logger retention and cleanup."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from raxe.infrastructure.audit.mssp_audit_logger import (
    MSSPAuditLogger,
    MSSPAuditLoggerConfig,
)


@pytest.fixture
def temp_audit_dir(tmp_path: Path) -> Path:
    """Create temporary audit log directory."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    return audit_dir


@pytest.fixture
def audit_logger(temp_audit_dir: Path) -> MSSPAuditLogger:
    """Create audit logger with temp directory."""
    config = MSSPAuditLoggerConfig(
        log_directory=str(temp_audit_dir),
        max_file_size_mb=10,
        max_files=10,
        enabled=True,
    )
    return MSSPAuditLogger(config)


def create_old_log_file(audit_dir: Path, days_old: int) -> Path:
    """Create a log file with a date N days in the past."""
    date = datetime.now(timezone.utc) - timedelta(days=days_old)
    filename = f"mssp_audit_{date.strftime('%Y-%m-%d')}.jsonl"
    log_file = audit_dir / filename

    # Write a sample record
    record = {
        "audit_id": f"aud_test_{days_old}",
        "event_id": "evt_test",
        "timestamp": date.isoformat(),
        "mssp_id": "mssp_test",
        "customer_id": "cust_test",
        "data_mode": "full",
        "data_fields_sent": ["prompt"],
        "delivery_status": "success",
    }
    with open(log_file, "w") as f:
        json.dump(record, f)
        f.write("\n")

    return log_file


class TestMSSPAuditLoggerCleanup:
    """Tests for cleanup_old_logs method."""

    def test_cleanup_deletes_old_files(self, audit_logger: MSSPAuditLogger, temp_audit_dir: Path):
        """Test that old log files are deleted."""
        # Create files of various ages
        create_old_log_file(temp_audit_dir, 100)  # Very old, should be deleted
        create_old_log_file(temp_audit_dir, 95)  # Old, should be deleted
        create_old_log_file(temp_audit_dir, 30)  # Recent, should be kept
        create_old_log_file(temp_audit_dir, 5)  # Very recent, should be kept

        # Verify all files exist
        assert len(list(temp_audit_dir.glob("mssp_audit_*.jsonl"))) == 4

        # Run cleanup with 90 day retention
        deleted = audit_logger.cleanup_old_logs(retention_days=90)

        # Should delete 2 files (100 and 95 days old)
        assert deleted == 2

        # Should have 2 files remaining
        remaining = list(temp_audit_dir.glob("mssp_audit_*.jsonl"))
        assert len(remaining) == 2

    def test_cleanup_with_no_old_files(self, audit_logger: MSSPAuditLogger, temp_audit_dir: Path):
        """Test cleanup when no files are old enough to delete."""
        create_old_log_file(temp_audit_dir, 10)
        create_old_log_file(temp_audit_dir, 20)

        deleted = audit_logger.cleanup_old_logs(retention_days=90)

        assert deleted == 0
        assert len(list(temp_audit_dir.glob("mssp_audit_*.jsonl"))) == 2

    def test_cleanup_empty_directory(self, audit_logger: MSSPAuditLogger, temp_audit_dir: Path):
        """Test cleanup on empty directory."""
        deleted = audit_logger.cleanup_old_logs(retention_days=90)
        assert deleted == 0

    def test_cleanup_respects_retention_days(
        self, audit_logger: MSSPAuditLogger, temp_audit_dir: Path
    ):
        """Test that retention_days parameter is respected."""
        create_old_log_file(temp_audit_dir, 35)
        create_old_log_file(temp_audit_dir, 25)
        create_old_log_file(temp_audit_dir, 15)

        # With 30 day retention, only the 35-day file should be deleted
        deleted = audit_logger.cleanup_old_logs(retention_days=30)
        assert deleted == 1

        # 2 files should remain
        assert len(list(temp_audit_dir.glob("mssp_audit_*.jsonl"))) == 2

    def test_cleanup_handles_invalid_filenames(
        self, audit_logger: MSSPAuditLogger, temp_audit_dir: Path
    ):
        """Test that files with invalid date format are skipped."""
        # Create valid file
        create_old_log_file(temp_audit_dir, 100)

        # Create invalid filename
        invalid_file = temp_audit_dir / "mssp_audit_invalid.jsonl"
        invalid_file.write_text("{}")

        # Should only delete the valid old file
        deleted = audit_logger.cleanup_old_logs(retention_days=90)
        assert deleted == 1

        # Invalid file should still exist
        assert invalid_file.exists()

    def test_cleanup_disabled_logger(self, temp_audit_dir: Path):
        """Test that cleanup returns 0 when logger is disabled."""
        config = MSSPAuditLoggerConfig(
            log_directory=str(temp_audit_dir),
            enabled=False,
        )
        logger = MSSPAuditLogger(config)

        # Create an old file
        create_old_log_file(temp_audit_dir, 100)

        # Should not delete anything when disabled
        deleted = logger.cleanup_old_logs(retention_days=90)
        assert deleted == 0

        # File should still exist
        assert len(list(temp_audit_dir.glob("mssp_audit_*.jsonl"))) == 1


class TestMSSPAuditLoggerDeliveryLogging:
    """Tests for log_delivery method."""

    def test_log_delivery_creates_record(self, audit_logger: MSSPAuditLogger, temp_audit_dir: Path):
        """Test that log_delivery creates an audit record."""
        audit_id = audit_logger.log_delivery(
            mssp_id="mssp_test",
            data_mode="full",
            data_fields_sent=["prompt", "matched_text"],
            delivery_status="success",
            customer_id="cust_test",
            http_status_code=200,
        )

        assert audit_id.startswith("aud_")

        # Verify file was created
        log_files = list(temp_audit_dir.glob("mssp_audit_*.jsonl"))
        assert len(log_files) == 1

        # Verify record content
        with open(log_files[0]) as f:
            record = json.loads(f.read().strip())
            assert record["audit_id"] == audit_id
            assert record["mssp_id"] == "mssp_test"
            assert record["data_mode"] == "full"
            assert record["delivery_status"] == "success"

    def test_log_delivery_redacts_url(self, audit_logger: MSSPAuditLogger, temp_audit_dir: Path):
        """Test that webhook URLs are redacted for security."""
        audit_logger.log_delivery(
            mssp_id="mssp_test",
            data_mode="full",
            data_fields_sent=["prompt"],
            delivery_status="success",
            destination_url="https://secret.endpoint.com/webhook/abc123",
        )

        # Read the record
        log_files = list(temp_audit_dir.glob("mssp_audit_*.jsonl"))
        with open(log_files[0]) as f:
            record = json.loads(f.read().strip())

        # URL should be redacted to domain only
        assert record["destination_url"] == "https://secret.endpoint.com/..."


class TestMSSPAuditLoggerStats:
    """Tests for get_stats method."""

    def test_get_stats_calculates_success_rate(self, audit_logger: MSSPAuditLogger):
        """Test that stats correctly calculates success rate."""
        # Log some deliveries
        for _ in range(8):
            audit_logger.log_delivery(
                mssp_id="mssp_test",
                data_mode="full",
                data_fields_sent=["prompt"],
                delivery_status="success",
            )

        for _ in range(2):
            audit_logger.log_delivery(
                mssp_id="mssp_test",
                data_mode="full",
                data_fields_sent=["prompt"],
                delivery_status="failed",
            )

        stats = audit_logger.get_stats()

        assert stats["total_deliveries"] == 10
        assert stats["successful"] == 8
        assert stats["failed"] == 2
        assert stats["success_rate"] == 80.0
