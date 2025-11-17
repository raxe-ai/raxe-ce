"""File-based suppression repository (.raxeignore files).

This infrastructure layer module handles ALL file I/O operations:
- Reading .raxeignore files
- Writing .raxeignore files
- Parsing suppression entries
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from raxe.domain.suppression import AuditEntry, Suppression

logger = logging.getLogger(__name__)


class FileSuppressionRepository:
    """Repository that loads/saves suppressions from .raxeignore files.

    Handles:
    - File I/O operations
    - File parsing/formatting
    - Directory creation
    - Logging

    Does NOT handle:
    - Audit logging (use SQLiteSuppressionRepository)
    """

    def __init__(self, config_path: Path | None = None):
        """Initialize file repository.

        Args:
            config_path: Path to .raxeignore file (default: ./.raxeignore)
        """
        if config_path is None:
            config_path = Path.cwd() / ".raxeignore"

        self.config_path = Path(config_path)
        self._suppressions: dict[str, Suppression] = {}

    def load_suppressions(self) -> list[Suppression]:
        """Load suppressions from .raxeignore file.

        File format:
            # Comment lines start with #
            pi-001  # Inline reason
            jb-*  # Suppress all jailbreak rules

            # Blank lines are ignored
            *-injection  # Suppress all injection rules

        Returns:
            List of Suppression objects
        """
        if not self.config_path.exists():
            logger.debug(f"Suppression file not found: {self.config_path}")
            return []

        suppressions = []
        with open(self.config_path, encoding="utf-8") as f:
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
                    logger.warning(f"Empty pattern at line {line_num} in {self.config_path}")
                    continue

                # Create suppression
                try:
                    suppression = Suppression(
                        pattern=pattern,
                        reason=reason,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        created_by=f"file:{self.config_path.name}",
                    )
                    suppressions.append(suppression)
                except ValueError as e:
                    logger.warning(f"Invalid suppression at line {line_num}: {e}")

        logger.info(f"Loaded {len(suppressions)} suppressions from {self.config_path}")
        return suppressions

    def save_suppression(self, suppression: Suppression) -> None:
        """Save a single suppression (adds to in-memory cache).

        Note: This only updates the in-memory cache.
        Call save_all_suppressions() to persist to file.

        Args:
            suppression: Suppression to save
        """
        self._suppressions[suppression.pattern] = suppression

    def remove_suppression(self, pattern: str) -> bool:
        """Remove a suppression from in-memory cache.

        Note: This only updates the in-memory cache.
        Call save_all_suppressions() to persist to file.

        Args:
            pattern: Pattern to remove

        Returns:
            True if removed, False if not found
        """
        if pattern in self._suppressions:
            del self._suppressions[pattern]
            return True
        return False

    def save_all_suppressions(self, suppressions: list[Suppression]) -> None:
        """Replace all suppressions and write to .raxeignore file.

        Args:
            suppressions: List of suppressions to save
        """
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("# RAXE Suppression File (.raxeignore)\n")
            f.write("# Format: <pattern>  # <reason>\n")
            f.write("# Supports wildcards: pi-*, *-injection\n")
            f.write("#\n")
            f.write("# Auto-generated - DO NOT EDIT MANUALLY\n")
            f.write(f"# Generated at: {datetime.now(timezone.utc).isoformat()}\n\n")

            for suppression in sorted(suppressions, key=lambda s: s.pattern):
                f.write(f"{suppression.pattern}  # {suppression.reason}\n")

        logger.info(f"Saved {len(suppressions)} suppressions to {self.config_path}")

    def log_audit(self, entry: AuditEntry) -> None:
        """Log audit entry (NO-OP for file repository).

        File repository doesn't support audit logging.
        Use SQLiteSuppressionRepository or CompositeSuppressionRepository.

        Args:
            entry: Audit entry to log (ignored)
        """
        # NO-OP: File repository doesn't do audit logging
        pass

    def get_audit_log(
        self,
        limit: int = 100,
        pattern: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get audit log entries (empty for file repository).

        File repository doesn't support audit logging.
        Use SQLiteSuppressionRepository or CompositeSuppressionRepository.

        Args:
            limit: Maximum entries to return (ignored)
            pattern: Filter by pattern (ignored)
            action: Filter by action (ignored)

        Returns:
            Empty list (no audit log)
        """
        return []
