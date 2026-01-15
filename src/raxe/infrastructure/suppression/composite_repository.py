"""Composite suppression repository (YAML + SQLite).

This infrastructure layer module combines:
- YamlSuppressionRepository: .raxe/suppressions.yaml file storage
- SQLiteSuppressionRepository: Audit log persistence

Note: The legacy .raxeignore file format has been deprecated in v1.0.
Use .raxe/suppressions.yaml instead. See UPDATE.md for migration guide.
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


class CompositeSuppressionRepository:
    """Repository that combines YAML storage + SQLite audit logging.

    This repository provides:
    - Load/save suppressions from .raxe/suppressions.yaml (YamlSuppressionRepository)
    - Log audit entries to SQLite (SQLiteSuppressionRepository)

    This is the recommended repository for new projects as it provides:
    - Full YAML format with action overrides (SUPPRESS, FLAG, LOG)
    - Expiration dates with proper validation
    - Schema versioning
    - SQLite audit logging for compliance
    """

    def __init__(
        self,
        config_path: Path | None = None,
        db_path: Path | None = None,
    ):
        """Initialize composite repository.

        Args:
            config_path: Path to suppressions.yaml file.
                        Default: ./.raxe/suppressions.yaml
            db_path: Path to SQLite database (default: ~/.raxe/suppressions.db)
        """
        if config_path is None:
            config_path = Path.cwd() / DEFAULT_SUPPRESSIONS_PATH

        self.yaml_repo = YamlSuppressionRepository(config_path=config_path)
        self.sqlite_repo = SQLiteSuppressionRepository(db_path=db_path)

        logger.debug(
            "composite_repository_initialized",
            extra={
                "config_path": str(self.yaml_repo.config_path),
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
        """Get the config file path (for backward compatibility)."""
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
