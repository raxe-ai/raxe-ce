"""Composite suppression repository (file + SQLite).

This infrastructure layer module combines:
- FileSuppressionRepository: .raxeignore file storage
- SQLiteSuppressionRepository: Audit log persistence
"""
import logging
from pathlib import Path
from typing import Any

from raxe.domain.suppression import AuditEntry, Suppression
from raxe.infrastructure.suppression.file_repository import FileSuppressionRepository
from raxe.infrastructure.suppression.sqlite_repository import (
    SQLiteSuppressionRepository,
)

logger = logging.getLogger(__name__)


class CompositeSuppressionRepository:
    """Repository that combines file storage + SQLite audit logging.

    This is the default repository that provides full functionality:
    - Load/save suppressions from .raxeignore (FileSuppressionRepository)
    - Log audit entries to SQLite (SQLiteSuppressionRepository)

    This is what the old SuppressionManager did, but with clean separation.
    """

    def __init__(
        self,
        config_path: Path | None = None,
        db_path: Path | None = None,
    ):
        """Initialize composite repository.

        Args:
            config_path: Path to .raxeignore file (default: ./.raxeignore)
            db_path: Path to SQLite database (default: ~/.raxe/suppressions.db)
        """
        self.file_repo = FileSuppressionRepository(config_path=config_path)
        self.sqlite_repo = SQLiteSuppressionRepository(db_path=db_path)

        logger.debug(
            f"Initialized composite repository: "
            f"file={self.file_repo.config_path}, db={self.sqlite_repo.db_path}"
        )

    def load_suppressions(self) -> list[Suppression]:
        """Load suppressions from .raxeignore file.

        Returns:
            List of Suppression objects
        """
        return self.file_repo.load_suppressions()

    def save_suppression(self, suppression: Suppression) -> None:
        """Save a suppression to file repository.

        Note: This only updates the in-memory cache.
        Call save_all_suppressions() to persist to file.

        Args:
            suppression: Suppression to save
        """
        self.file_repo.save_suppression(suppression)

    def remove_suppression(self, pattern: str) -> bool:
        """Remove a suppression from file repository.

        Note: This only updates the in-memory cache.
        Call save_all_suppressions() to persist to file.

        Args:
            pattern: Pattern to remove

        Returns:
            True if removed, False if not found
        """
        return self.file_repo.remove_suppression(pattern)

    def save_all_suppressions(self, suppressions: list[Suppression]) -> None:
        """Replace all suppressions and write to .raxeignore file.

        Args:
            suppressions: List of suppressions to save
        """
        self.file_repo.save_all_suppressions(suppressions)

    def log_audit(self, entry: AuditEntry) -> None:
        """Log audit entry to SQLite database.

        Args:
            entry: Audit entry to log
        """
        self.sqlite_repo.log_audit(entry)

    def get_audit_log(
        self,
        limit: int = 100,
        pattern: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get audit log entries from SQLite database.

        Args:
            limit: Maximum entries to return
            pattern: Filter by pattern (optional)
            action: Filter by action (added/removed/applied, optional)

        Returns:
            List of audit log entries as dictionaries
        """
        return self.sqlite_repo.get_audit_log(
            limit=limit,
            pattern=pattern,
            action=action,
        )

    @property
    def config_path(self) -> Path:
        """Get the config file path (for backward compatibility)."""
        return self.file_repo.config_path

    @property
    def db_path(self) -> Path:
        """Get the database path (for backward compatibility)."""
        return self.sqlite_repo.db_path
