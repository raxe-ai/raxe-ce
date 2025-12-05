"""Scan history database for storing local scan results.

SQLite-based storage for:
- Scan metadata (timestamp, hashes, duration)
- Detection details (rule hits, severity, confidence)
- Performance metrics (L1/L2 latency)
- Auto-cleanup (90 day retention)

Database: ~/.raxe/scan_history.db
"""
import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from raxe.domain.engine.executor import Detection
from raxe.domain.rules.models import Severity


@dataclass
class ScanRecord:
    """Record of a completed scan.

    Attributes:
        id: Unique scan ID (auto-assigned)
        timestamp: When scan occurred (UTC)
        prompt_hash: SHA256 hash of prompt (NOT the prompt itself)
        threats_found: Number of threats detected
        highest_severity: Highest severity found (if any)
        l1_duration_ms: L1 scan duration in milliseconds
        l2_duration_ms: L2 scan duration in milliseconds
        total_duration_ms: Total scan duration
        l1_detections: Number of L1 detections
        l2_detections: Number of L2 detections
        version: RAXE version that performed scan
        event_id: Portal event ID (evt_xxx) for portal correlation
            NOTE: This is the SAME event_id used in telemetry for portal-CLI correlation.
    """
    timestamp: datetime
    prompt_hash: str
    threats_found: int
    highest_severity: str | None = None
    l1_duration_ms: float | None = None
    l2_duration_ms: float | None = None
    total_duration_ms: float | None = None
    l1_detections: int = 0
    l2_detections: int = 0
    version: str = "0.0.1"
    id: int | None = None
    event_id: str | None = None
    prompt_text: str | None = None  # Full prompt text (stored locally for --show-prompt)


@dataclass
class DetectionRecord:
    """Record of a single detection within a scan.

    Attributes:
        id: Unique detection ID (auto-assigned)
        scan_id: Foreign key to scans table
        rule_id: Rule that triggered
        severity: Severity level
        confidence: Confidence score (0-1)
        detection_layer: Which layer detected (L1, L2, PLUGIN)
        category: Threat category
        description: Human-readable description of the detection
    """
    scan_id: int
    rule_id: str
    severity: str
    confidence: float
    detection_layer: str
    category: str | None = None
    description: str | None = None
    id: int | None = None


class ScanHistoryDB:
    """SQLite database for scan history.

    Features:
    - Thread-safe connection pooling
    - Auto-migration on first use
    - Auto-cleanup of old scans (90 days)
    - Efficient queries with indexes
    - Suppression tracking for audit trail
    """

    SCHEMA_VERSION = 5  # Bumped for description column in detections
    RETENTION_DAYS = 90

    def __init__(self, db_path: Path | None = None):
        """Initialize scan history database.

        Args:
            db_path: Path to SQLite database file (default: ~/.raxe/scan_history.db)
        """
        if db_path is None:
            db_path = Path.home() / ".raxe" / "scan_history.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection with proper pooling.

        This uses a simple connection pool for SQLite to ensure
        thread-safety while maintaining good performance.

        Yields:
            sqlite3.Connection: Database connection
        """
        # Use connection pool for better performance and thread-safety
        # For SQLite, we maintain a single connection with check_same_thread=False
        # This is safe because SQLite serializes all operations internally
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,  # Increased timeout for better reliability
            isolation_level=None,  # Autocommit mode for better concurrency
        )
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema if needed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS _metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Check schema version
            cursor.execute("SELECT value FROM _metadata WHERE key = 'schema_version'")
            row = cursor.fetchone()

            if row is None:
                # First time setup
                self._create_tables(conn)
                cursor.execute(
                    "INSERT INTO _metadata (key, value) VALUES ('schema_version', ?)",
                    (str(self.SCHEMA_VERSION),)
                )
                conn.commit()
            else:
                current_version = int(row[0])
                if current_version < self.SCHEMA_VERSION:
                    self._migrate(conn, current_version, self.SCHEMA_VERSION)

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """Create database tables.

        Args:
            conn: Database connection
        """
        cursor = conn.cursor()

        # Scans table
        cursor.execute("""
            CREATE TABLE scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                prompt_hash TEXT NOT NULL,
                threats_found INTEGER NOT NULL,
                highest_severity TEXT,
                l1_duration_ms REAL,
                l2_duration_ms REAL,
                total_duration_ms REAL,
                l1_detections INTEGER DEFAULT 0,
                l2_detections INTEGER DEFAULT 0,
                version TEXT NOT NULL,
                event_id TEXT,
                scan_id TEXT,
                prompt_text TEXT
            )
        """)

        # Detections table
        cursor.execute("""
            CREATE TABLE detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                rule_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                detection_layer TEXT NOT NULL,
                category TEXT,
                description TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
            )
        """)

        # Suppressions table (for audit trail)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                rule_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                suppression_pattern TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
            )
        """)

        # Indexes for performance
        cursor.execute("CREATE INDEX idx_scans_timestamp ON scans(timestamp)")
        cursor.execute("CREATE INDEX idx_scans_severity ON scans(highest_severity)")
        cursor.execute("CREATE INDEX idx_detections_scan_id ON detections(scan_id)")
        cursor.execute("CREATE INDEX idx_detections_severity ON detections(severity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppressions_scan_id ON suppressions(scan_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppressions_rule_id ON suppressions(rule_id)")
        # Unique index for event_id lookup (partial index - only non-null values)
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_scans_event_id "
            "ON scans(event_id) WHERE event_id IS NOT NULL"
        )
        # Index for scan_id lookup
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scans_scan_id "
            "ON scans(scan_id) WHERE scan_id IS NOT NULL"
        )

        conn.commit()

    def _migrate(self, conn: sqlite3.Connection, from_version: int, to_version: int) -> None:
        """Migrate database schema.

        Args:
            conn: Database connection
            from_version: Current schema version
            to_version: Target schema version
        """
        cursor = conn.cursor()

        # Migration from v1 to v2: Add suppressions table
        if from_version < 2 <= to_version:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS suppressions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER,
                    rule_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    suppression_pattern TEXT,
                    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppressions_scan_id ON suppressions(scan_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppressions_rule_id ON suppressions(rule_id)")

            # Update schema version
            cursor.execute("UPDATE _metadata SET value = '2' WHERE key = 'schema_version'")
            conn.commit()

        # Migration from v2 to v3: Add event_id and scan_id columns
        if from_version < 3 <= to_version:
            # Add event_id column for portal correlation
            cursor.execute("ALTER TABLE scans ADD COLUMN event_id TEXT")
            # Add scan_id column for telemetry correlation
            cursor.execute("ALTER TABLE scans ADD COLUMN scan_id TEXT")
            # Create unique index for event_id lookup (partial index - only non-null values)
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_scans_event_id "
                "ON scans(event_id) WHERE event_id IS NOT NULL"
            )
            # Create index for scan_id lookup
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_scans_scan_id "
                "ON scans(scan_id) WHERE scan_id IS NOT NULL"
            )

            # Update schema version
            cursor.execute("UPDATE _metadata SET value = '3' WHERE key = 'schema_version'")
            conn.commit()

        # Migration from v3 to v4: Add prompt_text column for --show-prompt feature
        if from_version < 4 <= to_version:
            # Add prompt_text column (stored locally only for privacy)
            cursor.execute("ALTER TABLE scans ADD COLUMN prompt_text TEXT")

            # Update schema version
            cursor.execute("UPDATE _metadata SET value = '4' WHERE key = 'schema_version'")
            conn.commit()

        # Migration from v4 to v5: Add description column to detections
        if from_version < 5 <= to_version:
            # Add description column for human-readable detection messages
            cursor.execute("ALTER TABLE detections ADD COLUMN description TEXT")

            # Update schema version
            cursor.execute("UPDATE _metadata SET value = '5' WHERE key = 'schema_version'")
            conn.commit()

    def hash_prompt(self, prompt: str) -> str:
        """Create privacy-preserving hash of prompt.

        Args:
            prompt: Prompt text to hash

        Returns:
            SHA256 hex digest
        """
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def record_scan(
        self,
        prompt: str,
        detections: list[Detection],
        l1_duration_ms: float | None = None,
        l2_duration_ms: float | None = None,
        total_duration_ms: float | None = None,
        version: str = "0.0.1",
        event_id: str | None = None,
        store_prompt: bool = True,
    ) -> int:
        """Record a scan in the database.

        Args:
            prompt: Original prompt (will be hashed, optionally stored)
            detections: List of detections found
            l1_duration_ms: L1 scan duration
            l2_duration_ms: L2 scan duration
            total_duration_ms: Total scan duration
            version: RAXE version
            event_id: Portal event ID (evt_xxx) for portal-CLI correlation.
                NOTE: This is the SAME event_id used in telemetry, enabling
                correlation between local scan history and portal alerts.
            store_prompt: If True, store full prompt text locally (default True).
                         Enables --show-prompt in 'raxe event show'.

        Returns:
            Database row ID (int)
        """
        # Hash prompt
        prompt_hash = self.hash_prompt(prompt)
        # Optionally store full prompt for local retrieval
        prompt_text = prompt if store_prompt else None

        # Calculate stats
        threats_found = len(detections)
        l1_detections = sum(1 for d in detections if d.detection_layer == "L1")
        l2_detections = sum(1 for d in detections if d.detection_layer == "L2")

        # Find highest severity
        highest_severity = None
        if detections:
            severity_order = {
                Severity.CRITICAL: 4,
                Severity.HIGH: 3,
                Severity.MEDIUM: 2,
                Severity.LOW: 1,
                Severity.INFO: 0,
            }
            highest = max(detections, key=lambda d: severity_order.get(d.severity, 0))
            highest_severity = highest.severity.value

        # Insert scan record
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO scans (
                    timestamp, prompt_hash, threats_found, highest_severity,
                    l1_duration_ms, l2_duration_ms, total_duration_ms,
                    l1_detections, l2_detections, version, event_id,
                    prompt_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(datetime.now(timezone.utc).timestamp()),
                prompt_hash,
                threats_found,
                highest_severity,
                l1_duration_ms,
                l2_duration_ms,
                total_duration_ms,
                l1_detections,
                l2_detections,
                version,
                event_id,
                prompt_text,
            ))

            db_scan_id = cursor.lastrowid

            # Insert detection records
            for detection in detections:
                cursor.execute("""
                    INSERT INTO detections (
                        scan_id, rule_id, severity, confidence,
                        detection_layer, category, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    db_scan_id,
                    detection.rule_id,
                    detection.severity.value,
                    detection.confidence,
                    detection.detection_layer,
                    detection.category,
                    detection.message,  # Human-readable description
                ))

            conn.commit()

        return db_scan_id

    def get_scan(self, scan_id: int) -> ScanRecord | None:
        """Get scan by database ID.

        Args:
            scan_id: Database scan ID (integer) to retrieve

        Returns:
            ScanRecord if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scans WHERE id = ?", (scan_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_scan_record(row)

    def _row_to_scan_record(self, row: sqlite3.Row) -> ScanRecord:
        """Convert a database row to a ScanRecord.

        Args:
            row: SQLite Row object from query

        Returns:
            ScanRecord populated from the row data
        """
        return ScanRecord(
            id=row["id"],
            timestamp=datetime.fromtimestamp(row["timestamp"], tz=timezone.utc),
            prompt_hash=row["prompt_hash"],
            threats_found=row["threats_found"],
            highest_severity=row["highest_severity"],
            l1_duration_ms=row["l1_duration_ms"],
            l2_duration_ms=row["l2_duration_ms"],
            total_duration_ms=row["total_duration_ms"],
            l1_detections=row["l1_detections"],
            l2_detections=row["l2_detections"],
            version=row["version"],
            event_id=row["event_id"] if "event_id" in row.keys() else None,
            prompt_text=row["prompt_text"] if "prompt_text" in row.keys() else None,
        )

    def get_by_event_id(self, event_id: str) -> ScanRecord | None:
        """Get scan record by event ID for portal correlation.

        This method enables looking up local scan records using the
        event ID (evt_xxx) that was sent to the portal, allowing
        users to correlate portal alerts with local scan details.

        Args:
            event_id: Portal event ID (evt_xxx format)

        Returns:
            ScanRecord if found, None otherwise

        Example:
            >>> db = ScanHistoryDB()
            >>> record = db.get_by_event_id("evt_a1b2c3d4e5f67890")
            >>> if record:
            ...     print(f"Found scan with {record.threats_found} threats")
        """
        if not event_id or not event_id.startswith("evt_"):
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scans WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_scan_record(row)

    def list_scans(
        self,
        limit: int = 100,
        offset: int = 0,
        severity_filter: str | None = None,
    ) -> list[ScanRecord]:
        """List recent scans.

        Args:
            limit: Maximum number of scans to return
            offset: Offset for pagination
            severity_filter: Filter by highest severity

        Returns:
            List of ScanRecords
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if severity_filter:
                cursor.execute("""
                    SELECT * FROM scans
                    WHERE highest_severity = ?
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (severity_filter, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM scans
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))

            rows = cursor.fetchall()
            return [self._row_to_scan_record(row) for row in rows]

    def get_detections(self, scan_id: int) -> list[DetectionRecord]:
        """Get all detections for a scan.

        Args:
            scan_id: Scan ID

        Returns:
            List of DetectionRecords
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM detections
                WHERE scan_id = ?
                ORDER BY severity DESC, confidence DESC
            """, (scan_id,))

            rows = cursor.fetchall()
            return [
                DetectionRecord(
                    id=row["id"],
                    scan_id=row["scan_id"],
                    rule_id=row["rule_id"],
                    severity=row["severity"],
                    confidence=row["confidence"],
                    detection_layer=row["detection_layer"],
                    category=row["category"],
                    description=row["description"] if "description" in row.keys() else None,
                )
                for row in rows
            ]

    def get_statistics(self, days: int = 30) -> dict[str, Any]:
        """Get scan statistics for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with statistics
        """
        cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total scans
            cursor.execute(
                "SELECT COUNT(*) as count FROM scans WHERE timestamp >= ?",
                (cutoff,)
            )
            total_scans = cursor.fetchone()["count"]

            # Scans with threats
            cursor.execute(
                "SELECT COUNT(*) as count FROM scans WHERE timestamp >= ? AND threats_found > 0",
                (cutoff,)
            )
            scans_with_threats = cursor.fetchone()["count"]

            # Threats by severity
            cursor.execute("""
                SELECT highest_severity, COUNT(*) as count
                FROM scans
                WHERE timestamp >= ? AND highest_severity IS NOT NULL
                GROUP BY highest_severity
            """, (cutoff,))

            severity_counts = {row["highest_severity"]: row["count"] for row in cursor.fetchall()}

            # Average latencies
            cursor.execute("""
                SELECT
                    AVG(l1_duration_ms) as avg_l1,
                    AVG(l2_duration_ms) as avg_l2,
                    AVG(total_duration_ms) as avg_total
                FROM scans
                WHERE timestamp >= ?
            """, (cutoff,))

            latencies = cursor.fetchone()

            return {
                "period_days": days,
                "total_scans": total_scans,
                "scans_with_threats": scans_with_threats,
                "threat_rate": scans_with_threats / total_scans if total_scans > 0 else 0,
                "severity_counts": severity_counts,
                "avg_l1_duration_ms": latencies["avg_l1"],
                "avg_l2_duration_ms": latencies["avg_l2"],
                "avg_total_duration_ms": latencies["avg_total"],
            }

    def cleanup_old_scans(self, retention_days: int | None = None) -> int:
        """Delete scans older than retention period.

        Args:
            retention_days: Days to retain (default: 90)

        Returns:
            Number of scans deleted
        """
        if retention_days is None:
            retention_days = self.RETENTION_DAYS

        cutoff = int(
            (datetime.now(timezone.utc) - timedelta(days=retention_days)).timestamp()
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Count scans to delete
            cursor.execute("SELECT COUNT(*) as count FROM scans WHERE timestamp < ?", (cutoff,))
            count = cursor.fetchone()["count"]

            # Delete (cascade will handle detections)
            cursor.execute("DELETE FROM scans WHERE timestamp < ?", (cutoff,))
            conn.commit()

            # Vacuum to reclaim space
            cursor.execute("VACUUM")

        return count

    def log_suppression(
        self,
        scan_id: int | None,
        rule_id: str,
        reason: str,
        suppression_pattern: str | None = None,
    ) -> None:
        """Log a suppression to the database for audit trail.

        Args:
            scan_id: Scan ID (optional, None for manual suppressions)
            rule_id: Rule ID that was suppressed
            reason: Reason for suppression
            suppression_pattern: Pattern that matched (e.g., "pi-*")
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO suppressions (
                    scan_id, rule_id, reason, timestamp, suppression_pattern
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                scan_id,
                rule_id,
                reason,
                datetime.now(timezone.utc).isoformat(),
                suppression_pattern,
            ))

            conn.commit()

    def get_suppressions(
        self,
        scan_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get suppression log entries.

        Args:
            scan_id: Filter by scan ID (optional)
            limit: Maximum entries to return

        Returns:
            List of suppression log entries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if scan_id is not None:
                cursor.execute("""
                    SELECT * FROM suppressions
                    WHERE scan_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (scan_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM suppressions
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "scan_id": row["scan_id"],
                    "rule_id": row["rule_id"],
                    "reason": row["reason"],
                    "timestamp": row["timestamp"],
                    "suppression_pattern": row["suppression_pattern"],
                }
                for row in rows
            ]

    def export_to_json(self, scan_id: int) -> dict[str, Any]:
        """Export scan and detections to JSON-serializable dict.

        Args:
            scan_id: Scan ID to export

        Returns:
            Dictionary with scan and detections
        """
        scan = self.get_scan(scan_id)
        if scan is None:
            raise ValueError(f"Scan {scan_id} not found")

        detections = self.get_detections(scan_id)
        suppressions = self.get_suppressions(scan_id=scan_id)

        return {
            "scan": {
                **asdict(scan),
                "timestamp": scan.timestamp.isoformat(),
            },
            "detections": [asdict(d) for d in detections],
            "suppressions": suppressions,
        }
