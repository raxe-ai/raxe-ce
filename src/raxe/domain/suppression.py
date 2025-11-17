"""Suppression system for managing false positives.

This module provides:
- .raxeignore file support (like .gitignore)
- Programmatic suppression via API
- SQLite audit logging of all suppressions
- Wildcard pattern matching (pi-*, *-injection)

Example .raxeignore:
    # Suppress specific rules
    pi-001  # Reason: False positive in documentation
    jb-regex-basic  # Too sensitive for our use case

    # Wildcard patterns
    pi-*  # Suppress all prompt injection rules
    *-injection  # Suppress all injection detection
"""
import fnmatch
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Suppression:
    """A single suppression entry.

    Attributes:
        pattern: Rule ID pattern (supports wildcards: pi-*, *-injection)
        reason: Human-readable reason for suppression
        created_at: When suppression was created (ISO format)
        created_by: Who created the suppression (optional)
        expires_at: When suppression expires (ISO format, optional)
    """
    pattern: str
    reason: str
    created_at: str
    created_by: str | None = None
    expires_at: str | None = None

    def __post_init__(self) -> None:
        """Validate suppression."""
        if not self.pattern:
            raise ValueError("Pattern cannot be empty")
        if not self.reason:
            raise ValueError("Reason cannot be empty")

    def matches(self, rule_id: str) -> bool:
        """Check if this suppression matches a rule ID.

        Supports wildcards:
        - pi-* matches pi-001, pi-002, etc.
        - *-injection matches pi-injection, jb-injection, etc.
        - pi-00* matches pi-001, pi-002, etc.

        Args:
            rule_id: Rule ID to check

        Returns:
            True if pattern matches rule ID
        """
        return fnmatch.fnmatch(rule_id, self.pattern)

    def is_expired(self) -> bool:
        """Check if suppression has expired.

        Returns:
            True if expires_at is set and in the past
        """
        if not self.expires_at:
            return False

        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > expiry
        except ValueError:
            logger.warning(f"Invalid expiry date format: {self.expires_at}")
            return False


class SuppressionManager:
    """Manages suppressions for false positive handling.

    Features:
    - Load from .raxeignore file
    - Programmatic API for adding/removing suppressions
    - SQLite audit logging
    - Wildcard pattern support
    """

    def __init__(
        self,
        config_path: Path | None = None,
        db_path: Path | None = None,
        auto_load: bool = True,
    ):
        """Initialize suppression manager.

        Args:
            config_path: Path to .raxeignore file (default: ./.raxeignore)
            db_path: Path to SQLite database (default: ~/.raxe/suppressions.db)
            auto_load: Automatically load suppressions from file on init
        """
        # Default paths
        if config_path is None:
            config_path = Path.cwd() / ".raxeignore"
        if db_path is None:
            db_path = Path.home() / ".raxe" / "suppressions.db"

        self.config_path = Path(config_path)
        self.db_path = Path(db_path)

        # In-memory suppressions (loaded from file + programmatic)
        self._suppressions: dict[str, Suppression] = {}

        # Initialize database
        self._init_database()

        # Auto-load from file if exists
        if auto_load and self.config_path.exists():
            self.load_from_file()

    def _init_database(self) -> None:
        """Initialize SQLite database for audit logging."""
        import sqlite3

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
                action TEXT NOT NULL,  -- 'added', 'removed', 'applied'
                scan_id INTEGER,
                rule_id TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT,
                metadata TEXT  -- JSON for additional context
            )
        """)

        # Create index for efficient queries
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

    def load_from_file(self, path: Path | None = None) -> int:
        """Load suppressions from .raxeignore file.

        File format:
            # Comment lines start with #
            pi-001  # Inline reason
            jb-*  # Suppress all jailbreak rules

            # Blank lines are ignored
            *-injection  # Suppress all injection rules

        Args:
            path: Path to file (default: self.config_path)

        Returns:
            Number of suppressions loaded
        """
        if path is None:
            path = self.config_path

        if not path.exists():
            logger.debug(f"Suppression file not found: {path}")
            return 0

        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()

                # Skip blank lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse line: pattern # reason
                pattern, _, reason = line.partition("#")
                pattern = pattern.strip()
                reason = reason.strip() or "Suppressed via .raxeignore"

                if not pattern:
                    logger.warning(f"Empty pattern at line {line_num} in {path}")
                    continue

                # Add suppression
                try:
                    self.add_suppression(
                        pattern=pattern,
                        reason=reason,
                        created_by=f"file:{path.name}",
                        log_to_db=False,  # Don't log file loads
                    )
                    count += 1
                except ValueError as e:
                    logger.warning(f"Invalid suppression at line {line_num}: {e}")

        logger.info(f"Loaded {count} suppressions from {path}")
        return count

    def save_to_file(self, path: Path | None = None) -> int:
        """Save current suppressions to .raxeignore file.

        Args:
            path: Path to file (default: self.config_path)

        Returns:
            Number of suppressions saved
        """
        if path is None:
            path = self.config_path

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write("# RAXE Suppression File (.raxeignore)\n")
            f.write("# Format: <pattern>  # <reason>\n")
            f.write("# Supports wildcards: pi-*, *-injection\n")
            f.write("#\n")
            f.write("# Auto-generated - DO NOT EDIT MANUALLY\n")
            f.write(f"# Generated at: {datetime.now(timezone.utc).isoformat()}\n\n")

            for suppression in sorted(self._suppressions.values(), key=lambda s: s.pattern):
                f.write(f"{suppression.pattern}  # {suppression.reason}\n")

        return len(self._suppressions)

    def add_suppression(
        self,
        pattern: str,
        reason: str,
        created_by: str | None = None,
        expires_at: str | None = None,
        log_to_db: bool = True,
    ) -> Suppression:
        """Add a suppression programmatically.

        Args:
            pattern: Rule ID pattern (supports wildcards)
            reason: Reason for suppression
            created_by: Who created it (default: "api")
            expires_at: When it expires (ISO format, optional)
            log_to_db: Whether to log to database (default: True)

        Returns:
            Created Suppression object

        Raises:
            ValueError: If pattern or reason is invalid
        """
        suppression = Suppression(
            pattern=pattern,
            reason=reason,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by or "api",
            expires_at=expires_at,
        )

        # Store in memory
        self._suppressions[pattern] = suppression

        # Log to database
        if log_to_db:
            self._log_audit(
                pattern=pattern,
                reason=reason,
                action="added",
                created_by=created_by,
            )

        logger.info(f"Added suppression: {pattern} - {reason}")
        return suppression

    def remove_suppression(
        self,
        pattern: str,
        created_by: str | None = None,
    ) -> bool:
        """Remove a suppression.

        Args:
            pattern: Pattern to remove (exact match)
            created_by: Who removed it (for audit)

        Returns:
            True if removed, False if not found
        """
        if pattern not in self._suppressions:
            return False

        suppression = self._suppressions.pop(pattern)

        # Log to database
        self._log_audit(
            pattern=pattern,
            reason=suppression.reason,
            action="removed",
            created_by=created_by,
        )

        logger.info(f"Removed suppression: {pattern}")
        return True

    def is_suppressed(self, rule_id: str) -> tuple[bool, str]:
        """Check if a rule is suppressed.

        Args:
            rule_id: Rule ID to check

        Returns:
            Tuple of (is_suppressed, reason)
            - If suppressed: (True, "Reason for suppression")
            - If not suppressed: (False, "")
        """
        # Check all active suppressions
        for suppression in self._suppressions.values():
            # Skip expired suppressions
            if suppression.is_expired():
                continue

            # Check if pattern matches
            if suppression.matches(rule_id):
                return True, suppression.reason

        return False, ""

    def log_suppression(
        self,
        scan_id: int | None,
        rule_id: str,
        reason: str,
    ) -> None:
        """Log that a suppression was applied during a scan.

        Args:
            scan_id: Scan ID (if applicable)
            rule_id: Rule ID that was suppressed
            reason: Reason for suppression
        """
        self._log_audit(
            pattern=rule_id,
            reason=reason,
            action="applied",
            scan_id=scan_id,
            rule_id=rule_id,
        )

    def _log_audit(
        self,
        pattern: str,
        reason: str,
        action: str,
        scan_id: int | None = None,
        rule_id: str | None = None,
        created_by: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log audit event to database.

        Args:
            pattern: Pattern that was added/removed/applied
            reason: Reason for action
            action: Action type (added, removed, applied)
            scan_id: Scan ID (for applied actions)
            rule_id: Rule ID (for applied actions)
            created_by: Who performed the action
            metadata: Additional metadata (JSON)
        """
        import json
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO suppression_audit (
                pattern, reason, action, scan_id, rule_id, created_at, created_by, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern,
            reason,
            action,
            scan_id,
            rule_id,
            datetime.now(timezone.utc).isoformat(),
            created_by,
            json.dumps(metadata) if metadata else None,
        ))

        conn.commit()
        conn.close()

    def get_suppressions(self) -> list[Suppression]:
        """Get all active suppressions.

        Returns:
            List of Suppression objects (excluding expired ones)
        """
        return [
            s for s in self._suppressions.values()
            if not s.is_expired()
        ]

    def get_suppression(self, pattern: str) -> Suppression | None:
        """Get a specific suppression by pattern.

        Args:
            pattern: Pattern to look up (exact match)

        Returns:
            Suppression if found, None otherwise
        """
        return self._suppressions.get(pattern)

    def get_audit_log(
        self,
        limit: int = 100,
        pattern: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get audit log entries.

        Args:
            limit: Maximum entries to return
            pattern: Filter by pattern (optional)
            action: Filter by action (added/removed/applied, optional)

        Returns:
            List of audit log entries
        """
        import json
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

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

        conn.close()
        return results

    def get_statistics(self) -> dict[str, Any]:
        """Get suppression statistics.

        Returns:
            Dictionary with statistics
        """
        import sqlite3

        active_suppressions = self.get_suppressions()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Count by action
        cursor.execute("""
            SELECT action, COUNT(*) as count
            FROM suppression_audit
            GROUP BY action
        """)
        action_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Count applications in last 30 days
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM suppression_audit
            WHERE action = 'applied' AND created_at >= ?
        """, (cutoff,))
        recent_applications = cursor.fetchone()[0]

        conn.close()

        return {
            "total_active": len(active_suppressions),
            "total_added": action_counts.get("added", 0),
            "total_removed": action_counts.get("removed", 0),
            "total_applied": action_counts.get("applied", 0),
            "recent_applications_30d": recent_applications,
        }

    def clear_all(self, created_by: str | None = None) -> int:
        """Clear all suppressions.

        Args:
            created_by: Who cleared them (for audit)

        Returns:
            Number of suppressions cleared
        """
        count = len(self._suppressions)

        # Log removals
        for pattern, suppression in list(self._suppressions.items()):
            self._log_audit(
                pattern=pattern,
                reason=suppression.reason,
                action="removed",
                created_by=created_by,
            )

        self._suppressions.clear()
        logger.info(f"Cleared {count} suppressions")
        return count
