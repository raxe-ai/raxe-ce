"""
MSSP Audit Trail Logger.

Logs every MSSP webhook delivery for compliance and debugging.
Stores audit records in JSON file format.

Audit records include:
- What data fields were sent
- Delivery status (success/failure)
- HTTP status code
- Timestamp and identifiers
"""

import json
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class MSSPAuditRecord:
    """Record of an MSSP webhook delivery.

    Attributes:
        audit_id: Unique identifier for this audit record
        event_id: Event ID from the scan event
        timestamp: ISO8601 timestamp of delivery attempt
        mssp_id: MSSP/Partner identifier
        customer_id: Customer identifier
        data_mode: Privacy mode (full or privacy_safe)
        data_fields_sent: List of fields included in webhook
        delivery_status: success, failed, or circuit_open
        http_status_code: HTTP response code (null if no response)
        error_message: Error description if failed
        attempts: Number of delivery attempts
        destination_url: Webhook URL (domain only for security)
    """

    audit_id: str
    event_id: str | None
    timestamp: str
    mssp_id: str
    customer_id: str | None
    data_mode: str
    data_fields_sent: list[str]
    delivery_status: str
    http_status_code: int | None = None
    error_message: str | None = None
    attempts: int = 1
    destination_url: str | None = None


@dataclass
class MSSPAuditLoggerConfig:
    """Configuration for MSSP audit logger.

    Attributes:
        log_directory: Directory to store audit logs
        max_file_size_mb: Max size of each log file before rotation
        max_files: Maximum number of log files to keep
        enabled: Whether audit logging is enabled
    """

    log_directory: str = field(default_factory=lambda: "~/.raxe/audit")
    max_file_size_mb: int = 10
    max_files: int = 10
    enabled: bool = True


class MSSPAuditLogger:
    """Logger for MSSP webhook delivery audit trail.

    Creates JSON-formatted audit logs for compliance and debugging.
    Supports log rotation and configurable retention.

    Example:
        >>> logger = MSSPAuditLogger()
        >>> logger.log_delivery(
        ...     event_id="evt_abc123",
        ...     mssp_id="mssp_partner",
        ...     customer_id="cust_acme",
        ...     data_mode="full",
        ...     data_fields_sent=["prompt", "matched_text"],
        ...     delivery_status="success",
        ...     http_status_code=200,
        ... )
    """

    def __init__(self, config: MSSPAuditLoggerConfig | None = None) -> None:
        """Initialize audit logger.

        Args:
            config: Logger configuration
        """
        self.config = config or MSSPAuditLoggerConfig()
        self._lock = threading.Lock()
        self._ensure_log_directory()

    def _ensure_log_directory(self) -> None:
        """Create log directory if it doesn't exist."""
        if not self.config.enabled:
            return

        log_dir = Path(self.config.log_directory).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)

    def _get_current_log_file(self) -> Path:
        """Get current log file path.

        Returns:
            Path to current log file
        """
        log_dir = Path(self.config.log_directory).expanduser()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return log_dir / f"mssp_audit_{today}.jsonl"

    def _generate_audit_id(self) -> str:
        """Generate unique audit ID.

        Returns:
            Audit ID with aud_ prefix
        """
        return f"aud_{secrets.token_hex(8)}"

    def log_delivery(
        self,
        mssp_id: str,
        data_mode: str,
        data_fields_sent: list[str],
        delivery_status: str,
        event_id: str | None = None,
        customer_id: str | None = None,
        http_status_code: int | None = None,
        error_message: str | None = None,
        attempts: int = 1,
        destination_url: str | None = None,
    ) -> str:
        """Log an MSSP webhook delivery.

        Args:
            mssp_id: MSSP/Partner identifier
            data_mode: Privacy mode (full or privacy_safe)
            data_fields_sent: List of fields included in webhook
            delivery_status: success, failed, or circuit_open
            event_id: Event ID from the scan event
            customer_id: Customer identifier
            http_status_code: HTTP response code
            error_message: Error description if failed
            attempts: Number of delivery attempts
            destination_url: Webhook URL (will extract domain only)

        Returns:
            Audit ID of the created record
        """
        if not self.config.enabled:
            return ""

        # Extract domain only from URL for security
        safe_destination = None
        if destination_url:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(destination_url)
                safe_destination = f"{parsed.scheme}://{parsed.netloc}/..."
            except Exception:
                safe_destination = "<redacted>"

        record = MSSPAuditRecord(
            audit_id=self._generate_audit_id(),
            event_id=event_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            mssp_id=mssp_id,
            customer_id=customer_id,
            data_mode=data_mode,
            data_fields_sent=data_fields_sent,
            delivery_status=delivery_status,
            http_status_code=http_status_code,
            error_message=error_message,
            attempts=attempts,
            destination_url=safe_destination,
        )

        self._write_record(record)
        return record.audit_id

    def _write_record(self, record: MSSPAuditRecord) -> None:
        """Write audit record to log file.

        Args:
            record: Audit record to write
        """
        with self._lock:
            log_file = self._get_current_log_file()

            # Check if rotation needed
            if log_file.exists():
                size_mb = log_file.stat().st_size / (1024 * 1024)
                if size_mb >= self.config.max_file_size_mb:
                    self._rotate_logs()

            # Write record as JSON line
            with open(log_file, "a") as f:
                json.dump(asdict(record), f, separators=(",", ":"))
                f.write("\n")

    def _rotate_logs(self) -> None:
        """Rotate log files, removing oldest if over max_files."""
        log_dir = Path(self.config.log_directory).expanduser()
        log_files = sorted(log_dir.glob("mssp_audit_*.jsonl"))

        # Remove oldest files if over limit
        while len(log_files) >= self.config.max_files:
            oldest = log_files.pop(0)
            oldest.unlink()

    def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """Delete audit log files older than retention period.

        Args:
            retention_days: Days to retain logs (default: 90)

        Returns:
            Number of files deleted
        """
        if not self.config.enabled:
            return 0

        from datetime import timedelta

        log_dir = Path(self.config.log_directory).expanduser()
        if not log_dir.exists():
            return 0

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = 0

        for log_file in log_dir.glob("mssp_audit_*.jsonl"):
            try:
                # Extract date from filename: mssp_audit_YYYY-MM-DD.jsonl
                date_str = log_file.stem.replace("mssp_audit_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

                if file_date < cutoff_date:
                    log_file.unlink()
                    deleted += 1
            except (ValueError, OSError):
                # Skip files with invalid date format or deletion errors
                continue

        return deleted

    def get_recent_records(
        self,
        limit: int = 100,
        mssp_id: str | None = None,
        customer_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent audit records.

        Args:
            limit: Maximum number of records to return
            mssp_id: Filter by MSSP ID
            customer_id: Filter by customer ID

        Returns:
            List of audit records as dicts
        """
        if not self.config.enabled:
            return []

        records: list[dict[str, Any]] = []
        log_dir = Path(self.config.log_directory).expanduser()

        # Read from most recent files first
        log_files = sorted(log_dir.glob("mssp_audit_*.jsonl"), reverse=True)

        for log_file in log_files:
            if len(records) >= limit:
                break

            try:
                with open(log_file) as f:
                    for line in f:
                        if len(records) >= limit:
                            break

                        record = json.loads(line.strip())

                        # Apply filters
                        if mssp_id and record.get("mssp_id") != mssp_id:
                            continue
                        if customer_id and record.get("customer_id") != customer_id:
                            continue

                        records.append(record)
            except Exception:
                continue

        return records[:limit]

    def get_stats(
        self,
        mssp_id: str | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get audit statistics.

        Args:
            mssp_id: Filter by MSSP ID
            days: Number of days to include

        Returns:
            Statistics dict
        """
        records = self.get_recent_records(limit=10000, mssp_id=mssp_id)

        total = len(records)
        successful = sum(1 for r in records if r.get("delivery_status") == "success")
        failed = sum(1 for r in records if r.get("delivery_status") == "failed")
        circuit_open = sum(1 for r in records if r.get("delivery_status") == "circuit_open")

        return {
            "total_deliveries": total,
            "successful": successful,
            "failed": failed,
            "circuit_open": circuit_open,
            "success_rate": (successful / total * 100) if total > 0 else 0,
        }


# Global singleton instance
_audit_logger: MSSPAuditLogger | None = None
_logger_lock = threading.Lock()


def get_mssp_audit_logger() -> MSSPAuditLogger:
    """Get the global MSSP audit logger instance.

    Returns:
        Singleton MSSPAuditLogger instance
    """
    global _audit_logger

    if _audit_logger is None:
        with _logger_lock:
            if _audit_logger is None:
                _audit_logger = MSSPAuditLogger()

    return _audit_logger


def log_mssp_delivery(
    mssp_id: str,
    data_mode: str,
    data_fields_sent: list[str],
    delivery_status: str,
    **kwargs: Any,
) -> str:
    """Convenience function to log MSSP delivery.

    Args:
        mssp_id: MSSP/Partner identifier
        data_mode: Privacy mode
        data_fields_sent: Fields included in webhook
        delivery_status: success, failed, or circuit_open
        **kwargs: Additional fields (event_id, customer_id, etc.)

    Returns:
        Audit ID
    """
    logger = get_mssp_audit_logger()
    return logger.log_delivery(
        mssp_id=mssp_id,
        data_mode=data_mode,
        data_fields_sent=data_fields_sent,
        delivery_status=delivery_status,
        **kwargs,
    )
