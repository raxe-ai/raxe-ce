"""YAML-based suppression repository (.raxe/suppressions.yaml).

This infrastructure layer module handles ALL YAML file I/O operations:
- Reading .raxe/suppressions.yaml files
- Writing .raxe/suppressions.yaml files
- Parsing suppression entries with full validation
- Error handling with graceful degradation

File format (v1.0):
```yaml
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Known false positive in authentication flow"
    expires: "2025-06-01"

  - pattern: "jb-*"
    action: FLAG
    reason: "Under investigation by security team"

  - pattern: "enc-003"
    action: LOG
    reason: "Monitoring for false positive rate"
    expires: "2025-03-01"
```
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from raxe.domain.suppression import (
    AuditEntry,
    Suppression,
    SuppressionAction,
    SuppressionValidationError,
)

logger = logging.getLogger(__name__)

# Schema version supported by this repository
SUPPORTED_SCHEMA_VERSION = "1.0"

# Default location for suppressions YAML file
DEFAULT_SUPPRESSIONS_PATH = ".raxe/suppressions.yaml"


class YamlSuppressionRepository:
    """Repository that loads/saves suppressions from .raxe/suppressions.yaml files.

    This repository provides a more structured YAML format compared to the
    legacy .raxeignore file format. It supports:
    - Explicit version control
    - Action overrides (SUPPRESS, FLAG, LOG)
    - Expiration dates
    - Better validation and error messages

    Handles:
    - YAML file I/O operations
    - Schema validation
    - Graceful error handling (invalid entries logged and skipped)
    - Directory creation

    Does NOT handle:
    - Audit logging (use SQLiteSuppressionRepository for that)
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize YAML repository.

        Args:
            config_path: Path to suppressions.yaml file.
                        Default: ./.raxe/suppressions.yaml
        """
        if config_path is None:
            config_path = Path.cwd() / DEFAULT_SUPPRESSIONS_PATH

        self.config_path = Path(config_path)
        self._suppressions: dict[str, Suppression] = {}

    def load_suppressions(self) -> list[Suppression]:
        """Load suppressions from .raxe/suppressions.yaml file.

        Returns:
            List of valid Suppression objects. Invalid entries are logged
            and skipped. If the file doesn't exist, returns empty list.

        Note:
            This method does not raise exceptions for missing files or
            invalid entries. It logs warnings and continues gracefully.
        """
        if not self.config_path.exists():
            logger.debug(
                "suppression_yaml_not_found",
                extra={"path": str(self.config_path)},
            )
            return []

        try:
            # Import yaml here to avoid dependency issues if not installed
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "yaml_module_not_available",
                extra={
                    "message": "PyYAML not installed, cannot load suppressions.yaml"
                },
            )
            return []

        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.warning(
                "yaml_parse_error",
                extra={
                    "path": str(self.config_path),
                    "error": str(e),
                },
            )
            return []
        except OSError as e:
            logger.warning(
                "yaml_file_read_error",
                extra={
                    "path": str(self.config_path),
                    "error": str(e),
                },
            )
            return []

        if data is None:
            logger.debug(
                "yaml_file_empty",
                extra={"path": str(self.config_path)},
            )
            return []

        return self._parse_yaml_data(data)

    def _parse_yaml_data(self, data: dict[str, Any]) -> list[Suppression]:
        """Parse YAML data into Suppression objects.

        Args:
            data: Parsed YAML data dictionary

        Returns:
            List of valid Suppression objects
        """
        # Validate schema version
        version = data.get("version", "1.0")
        if version != SUPPORTED_SCHEMA_VERSION:
            logger.warning(
                "yaml_unsupported_version",
                extra={
                    "version": version,
                    "supported": SUPPORTED_SCHEMA_VERSION,
                    "path": str(self.config_path),
                },
            )
            # Continue anyway - try to parse what we can

        suppressions_data = data.get("suppressions", [])
        if not isinstance(suppressions_data, list):
            logger.warning(
                "yaml_invalid_suppressions_field",
                extra={
                    "type": type(suppressions_data).__name__,
                    "path": str(self.config_path),
                },
            )
            return []

        suppressions: list[Suppression] = []
        for idx, entry in enumerate(suppressions_data):
            suppression = self._parse_suppression_entry(entry, idx)
            if suppression is not None:
                suppressions.append(suppression)

        logger.info(
            "yaml_suppressions_loaded",
            extra={
                "count": len(suppressions),
                "path": str(self.config_path),
            },
        )
        return suppressions

    def _parse_suppression_entry(
        self,
        entry: Any,
        index: int,
    ) -> Suppression | None:
        """Parse a single suppression entry from YAML.

        Args:
            entry: Raw entry data from YAML
            index: Index in the suppressions list (for error messages)

        Returns:
            Suppression object if valid, None if invalid
        """
        if not isinstance(entry, dict):
            logger.warning(
                "yaml_invalid_entry_type",
                extra={
                    "index": index,
                    "type": type(entry).__name__,
                    "path": str(self.config_path),
                },
            )
            return None

        # Extract and validate pattern (required)
        pattern = entry.get("pattern")
        if not pattern:
            logger.warning(
                "yaml_missing_pattern",
                extra={
                    "index": index,
                    "path": str(self.config_path),
                },
            )
            return None

        pattern = str(pattern).strip()

        # Validate pattern is not bare wildcard
        if pattern == "*":
            logger.warning(
                "yaml_bare_wildcard_forbidden",
                extra={
                    "index": index,
                    "pattern": pattern,
                    "path": str(self.config_path),
                    "hint": "Use family prefix like 'pi-*' instead of '*'",
                },
            )
            return None

        # Extract and validate reason (required)
        reason = entry.get("reason")
        if not reason:
            logger.warning(
                "yaml_missing_reason",
                extra={
                    "index": index,
                    "pattern": pattern,
                    "path": str(self.config_path),
                },
            )
            return None

        reason = str(reason).strip()

        # Extract and validate action (optional, default: SUPPRESS)
        action = SuppressionAction.SUPPRESS
        action_str = entry.get("action")
        if action_str is not None:
            action_str = str(action_str).strip().upper()
            try:
                action = SuppressionAction(action_str)
            except ValueError:
                valid_actions = [a.value for a in SuppressionAction]
                logger.warning(
                    "yaml_invalid_action",
                    extra={
                        "index": index,
                        "pattern": pattern,
                        "action": action_str,
                        "valid_actions": valid_actions,
                        "path": str(self.config_path),
                    },
                )
                return None

        # Extract and validate expires (optional)
        expires_at: str | None = None
        expires_str = entry.get("expires")
        if expires_str is not None:
            expires_at = self._parse_expiration_date(expires_str, index, pattern)
            if expires_str is not None and expires_at is None:
                # Invalid date format - skip this entry
                return None

        # Create suppression
        try:
            suppression = Suppression(
                pattern=pattern,
                reason=reason,
                action=action,
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by=f"yaml:{self.config_path.name}",
            )
            return suppression
        except SuppressionValidationError as e:
            logger.warning(
                "yaml_suppression_validation_failed",
                extra={
                    "index": index,
                    "pattern": pattern,
                    "error": str(e),
                    "path": str(self.config_path),
                },
            )
            return None

    def _parse_expiration_date(
        self,
        expires_str: Any,
        index: int,
        pattern: str,
    ) -> str | None:
        """Parse and validate expiration date.

        Args:
            expires_str: Raw expiration date string
            index: Entry index for error messages
            pattern: Pattern for error messages

        Returns:
            ISO format date string if valid, None if invalid
        """
        expires_str = str(expires_str).strip()

        # Try parsing as ISO date (YYYY-MM-DD)
        try:
            # Parse as date only (no time)
            expiry_date = datetime.strptime(expires_str, "%Y-%m-%d")
            # Convert to end of day UTC
            expiry_datetime = expiry_date.replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            return expiry_datetime.isoformat()
        except ValueError:
            pass

        # Try parsing as full ISO datetime
        try:
            expiry_datetime = datetime.fromisoformat(expires_str)
            # Ensure timezone aware
            if expiry_datetime.tzinfo is None:
                expiry_datetime = expiry_datetime.replace(tzinfo=timezone.utc)
            return expiry_datetime.isoformat()
        except ValueError:
            pass

        logger.warning(
            "yaml_invalid_expiration_date",
            extra={
                "index": index,
                "pattern": pattern,
                "expires": expires_str,
                "hint": "Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS",
                "path": str(self.config_path),
            },
        )
        return None

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
        """Replace all suppressions and write to .raxe/suppressions.yaml file.

        Args:
            suppressions: List of suppressions to save
        """
        try:
            import yaml
        except ImportError:
            logger.error(
                "yaml_module_not_available",
                extra={
                    "message": "PyYAML not installed, cannot save suppressions.yaml"
                },
            )
            return

        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Build YAML data structure
        data: dict[str, Any] = {
            "version": SUPPORTED_SCHEMA_VERSION,
            "suppressions": [],
        }

        for suppression in sorted(suppressions, key=lambda s: s.pattern):
            entry: dict[str, Any] = {
                "pattern": suppression.pattern,
                "reason": suppression.reason,
            }

            # Only include action if not default
            if suppression.action != SuppressionAction.SUPPRESS:
                entry["action"] = suppression.action.value

            # Convert expires_at back to date format if possible
            if suppression.expires_at:
                entry["expires"] = self._format_expiration_date(suppression.expires_at)

            data["suppressions"].append(entry)

        # Write YAML file with header comment
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("# RAXE Suppressions Configuration\n")
            f.write("# Format: .raxe/suppressions.yaml\n")
            f.write("# Documentation: https://docs.raxe.ai/suppressions\n")
            f.write("#\n")
            f.write(f"# Generated at: {datetime.now(timezone.utc).isoformat()}\n")
            f.write("# DO NOT EDIT MANUALLY unless you know what you're doing\n")
            f.write("\n")
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info(
            "yaml_suppressions_saved",
            extra={
                "count": len(suppressions),
                "path": str(self.config_path),
            },
        )

    def _format_expiration_date(self, iso_datetime: str) -> str:
        """Format ISO datetime back to simple date if possible.

        Args:
            iso_datetime: ISO format datetime string

        Returns:
            YYYY-MM-DD format if time is end of day, otherwise full ISO
        """
        try:
            dt = datetime.fromisoformat(iso_datetime)
            # If it's end of day, just return the date
            if dt.hour == 23 and dt.minute == 59 and dt.second == 59:
                return dt.strftime("%Y-%m-%d")
            return iso_datetime
        except ValueError:
            return iso_datetime

    def log_audit(self, entry: AuditEntry) -> None:
        """Log audit entry (NO-OP for YAML repository).

        YAML repository doesn't support audit logging.
        Use SQLiteSuppressionRepository or CompositeSuppressionRepository.

        Args:
            entry: Audit entry to log (ignored)
        """
        # NO-OP: YAML repository doesn't do audit logging
        pass

    def get_audit_log(
        self,
        limit: int = 100,
        pattern: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get audit log entries (NO-OP for YAML repository).

        YAML repository doesn't support audit logging.
        Use SQLiteSuppressionRepository or CompositeSuppressionRepository.

        Args:
            limit: Maximum entries to return (ignored)
            pattern: Filter by pattern (ignored)
            action: Filter by action (ignored)

        Returns:
            Empty list (no audit log stored)
        """
        return []

    @property
    def file_exists(self) -> bool:
        """Check if the configuration file exists.

        Returns:
            True if file exists, False otherwise
        """
        return self.config_path.exists()
