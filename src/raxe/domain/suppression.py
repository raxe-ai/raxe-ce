"""Suppression system for managing false positives - Domain Layer (PURE).

This module provides the PURE business logic for suppressions:
- Value objects (Suppression)
- Pure matching logic
- Repository protocol (no implementation)
- Manager orchestration (accepts repositories via DI)

NO I/O operations in this layer:
- NO database calls
- NO file operations
- NO network requests
- NO logging (pass results up to application layer)
"""
import fnmatch
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Suppression:
    """A single suppression entry (Value Object - Immutable).

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

    def is_expired(self, *, current_time: datetime | None = None) -> bool:
        """Check if suppression has expired.

        Args:
            current_time: Current time for testing (default: now)

        Returns:
            True if expires_at is set and in the past
        """
        if not self.expires_at:
            return False

        try:
            expiry = datetime.fromisoformat(self.expires_at)
            now = current_time or datetime.now(timezone.utc)
            return now > expiry
        except ValueError:
            # Invalid date format - treat as expired
            return False


@dataclass(frozen=True)
class AuditEntry:
    """Audit log entry for suppression actions (Value Object - Immutable).

    Attributes:
        pattern: Pattern that was added/removed/applied
        reason: Reason for action
        action: Action type (added, removed, applied)
        created_at: When action occurred (ISO format)
        scan_id: Scan ID (for applied actions, optional)
        rule_id: Rule ID (for applied actions, optional)
        created_by: Who performed the action (optional)
        metadata: Additional metadata (optional)
    """
    pattern: str
    reason: str
    action: str
    created_at: str
    scan_id: int | None = None
    rule_id: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate audit entry."""
        if self.action not in ("added", "removed", "applied"):
            raise ValueError(f"Invalid action: {self.action}")


class SuppressionRepository(Protocol):
    """Repository interface for suppression persistence (PURE - NO IMPLEMENTATION).

    This is a Protocol (interface) that defines what operations are needed.
    Infrastructure layer provides concrete implementations.
    """

    def load_suppressions(self) -> list[Suppression]:
        """Load all suppressions from storage.

        Returns:
            List of Suppression objects
        """
        ...

    def save_suppression(self, suppression: Suppression) -> None:
        """Save a suppression to storage.

        Args:
            suppression: Suppression to save
        """
        ...

    def remove_suppression(self, pattern: str) -> bool:
        """Remove a suppression from storage.

        Args:
            pattern: Pattern to remove

        Returns:
            True if removed, False if not found
        """
        ...

    def save_all_suppressions(self, suppressions: list[Suppression]) -> None:
        """Replace all suppressions in storage.

        Args:
            suppressions: List of suppressions to save
        """
        ...

    def log_audit(self, entry: AuditEntry) -> None:
        """Log an audit entry.

        Args:
            entry: Audit entry to log
        """
        ...

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
            List of audit log entries as dictionaries
        """
        ...


class SuppressionManager:
    """Manages suppressions for false positive handling (PURE ORCHESTRATION).

    This class contains ONLY pure business logic - no I/O operations.
    All persistence is delegated to the injected repository.

    Features:
    - Check if rules are suppressed
    - Add/remove suppressions (delegates to repository)
    - Track active suppressions in memory
    - Wildcard pattern support
    """

    def __init__(
        self,
        repository: SuppressionRepository,
        *,
        auto_load: bool = True,
    ):
        """Initialize suppression manager with dependency injection.

        Args:
            repository: Repository for persistence (injected)
            auto_load: Automatically load suppressions from repository on init
        """
        self._repository = repository
        self._suppressions: dict[str, Suppression] = {}

        # Auto-load from repository if requested
        if auto_load:
            self._load_from_repository()

    def _load_from_repository(self) -> None:
        """Load suppressions from repository into memory."""
        suppressions = self._repository.load_suppressions()
        for suppression in suppressions:
            self._suppressions[suppression.pattern] = suppression

    def add_suppression(
        self,
        pattern: str,
        reason: str,
        *,
        created_by: str | None = None,
        expires_at: str | None = None,
        log_to_audit: bool = True,
    ) -> Suppression:
        """Add a suppression.

        Args:
            pattern: Rule ID pattern (supports wildcards)
            reason: Reason for suppression
            created_by: Who created it (default: "api")
            expires_at: When it expires (ISO format, optional)
            log_to_audit: Whether to log to audit (default: True)

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

        # Persist to repository
        self._repository.save_suppression(suppression)

        # Log to audit
        if log_to_audit:
            audit_entry = AuditEntry(
                pattern=pattern,
                reason=reason,
                action="added",
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by=created_by,
            )
            self._repository.log_audit(audit_entry)

        return suppression

    def remove_suppression(
        self,
        pattern: str,
        *,
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

        # Remove from repository
        self._repository.remove_suppression(pattern)

        # Log to audit
        audit_entry = AuditEntry(
            pattern=pattern,
            reason=suppression.reason,
            action="removed",
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
        )
        self._repository.log_audit(audit_entry)

        return True

    def is_suppressed(
        self, rule_id: str, *, current_time: datetime | None = None
    ) -> tuple[bool, str]:
        """Check if a rule is suppressed (PURE LOGIC).

        Args:
            rule_id: Rule ID to check
            current_time: Current time for testing (default: now)

        Returns:
            Tuple of (is_suppressed, reason)
            - If suppressed: (True, "Reason for suppression")
            - If not suppressed: (False, "")
        """
        # Check all active suppressions
        for suppression in self._suppressions.values():
            # Skip expired suppressions
            if suppression.is_expired(current_time=current_time):
                continue

            # Check if pattern matches
            if suppression.matches(rule_id):
                return True, suppression.reason

        return False, ""

    def log_suppression_applied(
        self,
        rule_id: str,
        reason: str,
        *,
        scan_id: int | None = None,
    ) -> None:
        """Log that a suppression was applied during a scan.

        Args:
            rule_id: Rule ID that was suppressed
            reason: Reason for suppression
            scan_id: Scan ID (if applicable)
        """
        audit_entry = AuditEntry(
            pattern=rule_id,
            reason=reason,
            action="applied",
            created_at=datetime.now(timezone.utc).isoformat(),
            scan_id=scan_id,
            rule_id=rule_id,
        )
        self._repository.log_audit(audit_entry)

    def get_suppressions(self, *, current_time: datetime | None = None) -> list[Suppression]:
        """Get all active suppressions (PURE LOGIC).

        Args:
            current_time: Current time for testing (default: now)

        Returns:
            List of Suppression objects (excluding expired ones)
        """
        return [
            s for s in self._suppressions.values()
            if not s.is_expired(current_time=current_time)
        ]

    def get_suppression(self, pattern: str) -> Suppression | None:
        """Get a specific suppression by pattern (PURE LOGIC).

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
        """Get audit log entries (delegates to repository).

        Args:
            limit: Maximum entries to return
            pattern: Filter by pattern (optional)
            action: Filter by action (added/removed/applied, optional)

        Returns:
            List of audit log entries
        """
        return self._repository.get_audit_log(
            limit=limit,
            pattern=pattern,
            action=action,
        )

    def get_statistics(self, *, current_time: datetime | None = None) -> dict[str, Any]:
        """Get suppression statistics (delegates to repository + pure logic).

        Args:
            current_time: Current time for testing (default: now)

        Returns:
            Dictionary with statistics
        """
        active_suppressions = self.get_suppressions(current_time=current_time)

        # Get audit counts from repository
        audit_log = self._repository.get_audit_log(limit=10000)  # Get all

        action_counts: dict[str, int] = {}
        for entry in audit_log:
            action = entry["action"]
            action_counts[action] = action_counts.get(action, 0) + 1

        # Count recent applications (last 30 days)
        from datetime import timedelta
        cutoff = (current_time or datetime.now(timezone.utc)) - timedelta(days=30)
        cutoff_str = cutoff.isoformat()
        recent_applications = sum(
            1 for entry in audit_log
            if entry["action"] == "applied" and entry["created_at"] >= cutoff_str
        )

        return {
            "total_active": len(active_suppressions),
            "total_added": action_counts.get("added", 0),
            "total_removed": action_counts.get("removed", 0),
            "total_applied": action_counts.get("applied", 0),
            "recent_applications_30d": recent_applications,
        }

    def clear_all(self, *, created_by: str | None = None) -> int:
        """Clear all suppressions.

        Args:
            created_by: Who cleared them (for audit)

        Returns:
            Number of suppressions cleared
        """
        count = len(self._suppressions)

        # Log removals
        for pattern, suppression in list(self._suppressions.items()):
            audit_entry = AuditEntry(
                pattern=pattern,
                reason=suppression.reason,
                action="removed",
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by=created_by,
            )
            self._repository.log_audit(audit_entry)

        # Clear from repository
        self._suppressions.clear()
        self._repository.save_all_suppressions([])

        return count

    def reload(self) -> int:
        """Reload suppressions from repository.

        Returns:
            Number of suppressions loaded
        """
        self._suppressions.clear()
        self._load_from_repository()
        return len(self._suppressions)

    def save_to_file(self, path: Path | None = None) -> int:
        """Save current suppressions to file (backward compatibility).

        Args:
            path: Path to save to (default: repository's config path)

        Returns:
            Number of suppressions saved
        """
        suppressions = list(self._suppressions.values())
        self._repository.save_all_suppressions(suppressions)
        return len(suppressions)
