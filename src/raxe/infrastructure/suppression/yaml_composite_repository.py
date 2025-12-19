"""Composite suppression repository (YAML + SQLite).

This infrastructure layer module combines:
- YamlSuppressionRepository: .raxe/suppressions.yaml file storage
- SQLiteSuppressionRepository: Audit log persistence

This is the recommended repository for new projects as it provides
the full YAML format with action overrides, expiration dates, and
proper audit logging.
"""

import logging
from pathlib import Path
from typing import Any

from raxe.domain.suppression import AuditEntry, Suppression
from raxe.infrastructure.suppression.sqlite_repository import (
    SQLiteSuppressionRepository,
)
from raxe.infrastructure.suppression.yaml_repository import (
    DEFAULT_SUPPRESSIONS_PATH,
    YamlSuppressionRepository,
)

logger = logging.getLogger(__name__)


class YamlCompositeSuppressionRepository:
    """Repository that combines YAML storage + SQLite audit logging.

    This is the recommended repository for new projects as it provides:
    - Full YAML format with action overrides (SUPPRESS, FLAG, LOG)
    - Expiration dates with proper validation
    - Schema versioning
    - SQLite audit logging for compliance

    This is what should be used for projects adopting the new
    .raxe/suppressions.yaml format.
    """

    def __init__(
        self,
        yaml_path: Path | None = None,
        db_path: Path | None = None,
    ) -> None:
        """Initialize composite repository.

        Args:
            yaml_path: Path to suppressions.yaml file
                      (default: ./.raxe/suppressions.yaml)
            db_path: Path to SQLite database
                    (default: ~/.raxe/suppressions.db)
        """
        if yaml_path is None:
            yaml_path = Path.cwd() / DEFAULT_SUPPRESSIONS_PATH

        self.yaml_repo = YamlSuppressionRepository(config_path=yaml_path)
        self.sqlite_repo = SQLiteSuppressionRepository(db_path=db_path)

        logger.debug(
            "yaml_composite_repository_initialized",
            extra={
                "yaml_path": str(self.yaml_repo.config_path),
                "db_path": str(self.sqlite_repo.db_path),
            },
        )

    def load_suppressions(self) -> list[Suppression]:
        """Load suppressions from .raxe/suppressions.yaml file.

        Returns:
            List of Suppression objects
        """
        return self.yaml_repo.load_suppressions()

    def save_suppression(self, suppression: Suppression) -> None:
        """Save a suppression to YAML repository.

        Note: This only updates the in-memory cache.
        Call save_all_suppressions() to persist to file.

        Args:
            suppression: Suppression to save
        """
        self.yaml_repo.save_suppression(suppression)

    def remove_suppression(self, pattern: str) -> bool:
        """Remove a suppression from YAML repository.

        Note: This only updates the in-memory cache.
        Call save_all_suppressions() to persist to file.

        Args:
            pattern: Pattern to remove

        Returns:
            True if removed, False if not found
        """
        return self.yaml_repo.remove_suppression(pattern)

    def save_all_suppressions(self, suppressions: list[Suppression]) -> None:
        """Replace all suppressions and write to .raxe/suppressions.yaml file.

        Args:
            suppressions: List of suppressions to save
        """
        self.yaml_repo.save_all_suppressions(suppressions)

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
        """Get the YAML config file path (for backward compatibility)."""
        return self.yaml_repo.config_path

    @property
    def db_path(self) -> Path:
        """Get the database path (for backward compatibility)."""
        return self.sqlite_repo.db_path

    @property
    def file_exists(self) -> bool:
        """Check if the YAML configuration file exists.

        Returns:
            True if file exists, False otherwise
        """
        return self.yaml_repo.file_exists
