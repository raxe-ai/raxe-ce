"""SQLite-based suppression repository (audit logging).

This infrastructure layer module handles ALL SQLite I/O operations:
- Database connection management
- Table creation and migrations
- Audit log persistence
- Query execution
"""
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from raxe.domain.suppression import AuditEntry, Suppression

logger = logging.getLogger(__name__)


class SQLiteSuppressionRepository:
    """Repository that stores audit logs in SQLite database.

    Handles:
    - SQLite database operations
    - Audit log persistence
    - Query execution
    - Schema management

    Does NOT handle:
    - File I/O for .raxeignore (use FileSuppressionRepository)
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize SQLite repository.

        Args:
            db_path: Path to SQLite database (default: ~/.raxe/suppressions.db)
        """
        if db_path is None:
            db_path = Path.home() / ".raxe" / "suppressions.db"

        self.db_path = Path(db_path)

        # Initialize database schema
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database for audit logging."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create suppressions audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppression_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                reason TEXT NOT NULL,
                action TEXT NOT NULL,
                scan_id INTEGER,
                rule_id TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT,
                metadata TEXT
            )
        """)

        # Create indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_pattern
            ON suppression_audit(pattern)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_action
            ON suppression_audit(action)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_created_at
            ON suppression_audit(created_at)
        """)

        conn.commit()
        conn.close()

        logger.debug(f"Initialized suppression database: {self.db_path}")

    def load_suppressions(self) -> list[Suppression]:
        """Load suppressions (NO-OP for SQLite repository).

        SQLite repository only handles audit logging, not suppression storage.
        Use FileSuppressionRepository or CompositeSuppressionRepository.

        Returns:
            Empty list (no suppressions stored)
        """
        return []

    def save_suppression(self, suppression: Suppression) -> None:
        """Save suppression (NO-OP for SQLite repository).

        SQLite repository only handles audit logging, not suppression storage.
        Use FileSuppressionRepository or CompositeSuppressionRepository.

        Args:
            suppression: Suppression to save (ignored)
        """
        # NO-OP: SQLite repository only does audit logging
        pass

    def remove_suppression(self, pattern: str) -> bool:
        """Remove suppression (NO-OP for SQLite repository).

        SQLite repository only handles audit logging, not suppression storage.
        Use FileSuppressionRepository or CompositeSuppressionRepository.

        Args:
            pattern: Pattern to remove (ignored)

        Returns:
            False (no suppressions stored)
        """
        return False

    def save_all_suppressions(self, suppressions: list[Suppression]) -> None:
        """Save all suppressions (NO-OP for SQLite repository).

        SQLite repository only handles audit logging, not suppression storage.
        Use FileSuppressionRepository or CompositeSuppressionRepository.

        Args:
            suppressions: List of suppressions to save (ignored)
        """
        # NO-OP: SQLite repository only does audit logging
        pass

    def log_audit(self, entry: AuditEntry) -> None:
        """Log audit entry to database.

        Args:
            entry: Audit entry to log
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO suppression_audit (
                    pattern, reason, action, scan_id, rule_id, created_at, created_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.pattern,
                entry.reason,
                entry.action,
                entry.scan_id,
                entry.rule_id,
                entry.created_at,
                entry.created_by,
                json.dumps(entry.metadata) if entry.metadata else None,
            ))

            conn.commit()
            logger.debug(f"Logged audit entry: {entry.action} {entry.pattern}")

        except sqlite3.Error as e:
            logger.error(f"Failed to log audit entry: {e}")
            raise

        finally:
            conn.close()

    def get_audit_log(
        self,
        limit: int = 100,
        pattern: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get audit log entries from database.

        Args:
            limit: Maximum entries to return
            pattern: Filter by pattern (optional)
            action: Filter by action (added/removed/applied, optional)

        Returns:
            List of audit log entries as dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Build query
            query = "SELECT * FROM suppression_audit WHERE 1=1"
            params: list[Any] = []

            if pattern:
                query += " AND pattern = ?"
                params.append(pattern)

            if action:
                query += " AND action = ?"
                params.append(action)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert to dicts
            results = []
            for row in rows:
                entry = dict(row)
                # Parse metadata JSON
                if entry.get("metadata"):
                    try:
                        entry["metadata"] = json.loads(entry["metadata"])
                    except json.JSONDecodeError:
                        entry["metadata"] = None
                results.append(entry)

            return results

        except sqlite3.Error as e:
            logger.error(f"Failed to get audit log: {e}")
            return []

        finally:
            conn.close()
