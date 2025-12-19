"""Suppression system for managing false positives - Domain Layer (PURE).

This module provides the PURE business logic for suppressions:
- Value objects (Suppression, SuppressionAction, SuppressionCheckResult)
- Pure matching logic (check_suppressions function)
- Repository protocol (no implementation)
- Manager orchestration (accepts repositories via DI)

NO I/O operations in this layer:
- NO database calls
- NO file operations
- NO network requests
- NO logging (pass results up to application layer)
"""
import fnmatch
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

# =============================================================================
# Security Limits (HARDENED)
# =============================================================================
# These limits prevent denial-of-service and resource exhaustion attacks.

MAX_PATTERN_LENGTH: int = 256
"""Maximum allowed length for suppression patterns.

Prevents ReDoS attacks and excessive memory usage from maliciously long patterns.
"""

MAX_REASON_LENGTH: int = 500
"""Maximum allowed length for suppression reasons.

Prevents storage bloat and ensures reasons remain human-readable.
"""

MAX_SUPPRESSIONS: int = 1000
"""Maximum number of suppressions allowed.

Prevents performance degradation from excessive suppression rules.
"""


class SuppressionAction(Enum):
    """Action to take when a suppression matches a detection.

    Attributes:
        SUPPRESS: Remove detection from results entirely (default behavior)
        FLAG: Keep detection in results but mark it as flagged for review
        LOG: Keep detection in results, intended for logging/metrics only
    """

    SUPPRESS = "SUPPRESS"
    FLAG = "FLAG"
    LOG = "LOG"


# Known valid family prefixes for wildcard validation
# These match the RuleFamily enum values (case-insensitive)
VALID_FAMILY_PREFIXES = frozenset({
    "pi",     # Prompt Injection
    "jb",     # Jailbreak
    "pii",    # PII/Data Leak
    "cmd",    # Command Injection
    "enc",    # Encoding/Obfuscation Attacks
    "rag",    # RAG-specific Attacks
    "hc",     # Harmful Content
    "sec",    # Security
    "qual",   # Quality
    "custom", # User-defined
})


class SuppressionValidationError(ValueError):
    """Raised when suppression validation fails.

    This is a domain exception for invalid suppression configuration.
    """

    pass


def _validate_pattern(pattern: str) -> None:
    """Validate suppression pattern (PURE - raises on invalid).

    Rules:
    1. Pattern cannot be empty
    2. Pattern cannot be bare wildcard '*' (must have family prefix)
    3. Wildcards must have a valid family prefix (e.g., 'pi-*', not '*-injection')

    Args:
        pattern: The pattern to validate

    Raises:
        SuppressionValidationError: If pattern is invalid
    """
    if not pattern:
        raise SuppressionValidationError("Pattern cannot be empty")

    # Reject bare wildcards
    if pattern == "*":
        raise SuppressionValidationError(
            "Bare wildcard '*' not allowed. Use a family prefix like 'pi-*' or 'jb-*'"
        )

    # If pattern contains wildcard, validate it has proper structure
    if "*" in pattern:
        # Pattern must start with a valid family prefix before any wildcard
        # Valid: pi-*, jb-*, pi-00*, pi-*-basic
        # Invalid: *-injection, *pi-001, *

        # Check if pattern starts with wildcard (suffix-only pattern)
        if pattern.startswith("*"):
            raise SuppressionValidationError(
                f"Pattern '{pattern}' starts with wildcard. "
                f"Wildcards must have a family prefix like 'pi-*' or 'jb-*'"
            )

        # Extract the prefix before the first hyphen or wildcard
        prefix_match = re.match(r"^([a-zA-Z]+)", pattern)
        if not prefix_match:
            raise SuppressionValidationError(
                f"Pattern with wildcard must start with a family prefix. "
                f"Valid prefixes: {', '.join(sorted(VALID_FAMILY_PREFIXES))}"
            )

        prefix = prefix_match.group(1).lower()
        if prefix not in VALID_FAMILY_PREFIXES:
            raise SuppressionValidationError(
                f"Unknown family prefix '{prefix}'. "
                f"Valid prefixes: {', '.join(sorted(VALID_FAMILY_PREFIXES))}"
            )


def _validate_iso_datetime(value: str, field_name: str) -> None:
    """Validate ISO datetime format (PURE - raises on invalid).

    Args:
        value: The datetime string to validate
        field_name: Name of field for error messages

    Raises:
        SuppressionValidationError: If format is invalid
    """
    try:
        datetime.fromisoformat(value)
    except ValueError as e:
        raise SuppressionValidationError(
            f"{field_name} must be valid ISO format, got '{value}': {e}"
        ) from e


@dataclass(frozen=True)
class Suppression:
    """A single suppression entry (Value Object - Immutable).

    Suppressions allow managing false positives by matching detection rule IDs
    against patterns and taking specified actions.

    Validation Rules:
    - Pattern cannot be empty
    - Pattern cannot be bare wildcard '*'
    - Wildcards must have valid family prefix (pi-*, jb-*, etc.)
    - Reason is REQUIRED and cannot be empty
    - Dates must be valid ISO format if provided

    Attributes:
        pattern: Rule ID pattern (supports wildcards: pi-*, jb-*-basic)
        reason: Human-readable reason for suppression (REQUIRED)
        action: What to do when suppression matches (default: SUPPRESS)
        expires_at: When suppression expires (ISO format, optional)
        created_at: When suppression was created (ISO format, optional)
        created_by: Who created the suppression (optional)
    """

    pattern: str
    reason: str
    action: SuppressionAction = SuppressionAction.SUPPRESS
    expires_at: str | None = None
    created_at: str | None = None
    created_by: str | None = None

    def __post_init__(self) -> None:
        """Validate suppression after construction.

        Raises:
            SuppressionValidationError: If any field fails validation
        """
        # Validate pattern (no bare wildcards, must have family prefix)
        _validate_pattern(self.pattern)

        # Security: Validate pattern length limit
        if len(self.pattern) > MAX_PATTERN_LENGTH:
            raise SuppressionValidationError(
                f"Pattern exceeds maximum length of {MAX_PATTERN_LENGTH}"
            )

        # Validate reason is not empty
        if not self.reason or not self.reason.strip():
            raise SuppressionValidationError("Reason cannot be empty")

        # Security: Validate reason length limit
        if len(self.reason) > MAX_REASON_LENGTH:
            raise SuppressionValidationError(
                f"Reason exceeds maximum length of {MAX_REASON_LENGTH}"
            )

        # Validate dates if present
        if self.expires_at:
            _validate_iso_datetime(self.expires_at, "expires_at")

        if self.created_at:
            _validate_iso_datetime(self.created_at, "created_at")

    def matches(self, rule_id: str) -> bool:
        """Check if this suppression matches a rule ID.

        Supports wildcards:
        - pi-* matches pi-001, pi-002, etc.
        - pi-00* matches pi-001, pi-002, etc.
        - jb-*-basic matches jb-regex-basic, jb-pattern-basic, etc.

        Note: Bare wildcards (*) and suffix-only wildcards (*-injection)
        are not allowed and will fail validation at construction time.

        Args:
            rule_id: Rule ID to check

        Returns:
            True if pattern matches rule ID
        """
        return fnmatch.fnmatch(rule_id, self.pattern)

    def is_expired(self, *, current_time: datetime | None = None) -> bool:
        """Check if suppression has expired.

        Security: Uses FAIL-CLOSED approach. If the expiration date cannot be
        parsed (should not happen due to __post_init__ validation), the
        suppression is treated as EXPIRED to prevent bypassing security controls.

        Args:
            current_time: Current time for testing (default: now)

        Returns:
            True if expires_at is set and in the past, or if date is invalid
        """
        if not self.expires_at:
            return False

        try:
            expiry = datetime.fromisoformat(self.expires_at)
            # Ensure timezone-aware comparison
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            now = current_time or datetime.now(timezone.utc)
            return now > expiry
        except ValueError:
            # FAIL CLOSED - invalid date = expired (security hardening)
            # This prevents suppressions with malformed dates from being active
            return True


@dataclass(frozen=True)
class SuppressionCheckResult:
    """Result of checking suppressions for a rule (Value Object - Immutable).

    Used by check_suppressions() and SuppressionManager.check_suppression()
    to return complete information about whether a rule is suppressed.

    The application layer can use this to:
    - Log warnings for expired suppressions encountered
    - Take appropriate action based on SuppressionAction
    - Track suppression metrics

    Attributes:
        is_suppressed: True if an active (non-expired) suppression matched
        action: The action to take (SUPPRESS, FLAG, or LOG)
        reason: The reason from the matching suppression
        matched_pattern: The pattern that matched (for audit)
        expired_matches: List of expired suppressions that matched (for logging)
    """

    is_suppressed: bool
    action: SuppressionAction = SuppressionAction.SUPPRESS
    reason: str = ""
    matched_pattern: str = ""
    expired_matches: list[Suppression] = field(default_factory=list)


def check_suppressions(
    rule_id: str,
    suppressions: list[Suppression],
    *,
    current_time: datetime | None = None,
) -> SuppressionCheckResult:
    """Check if a rule ID matches any suppression (PURE FUNCTION).

    This is a pure function that takes data and returns data.
    No I/O, no side effects, easily testable.

    The function returns expired matches separately so the application
    layer can log warnings about them without violating domain purity.

    Args:
        rule_id: Rule ID to check
        suppressions: List of suppressions to check against
        current_time: Current time for expiration check (default: now)

    Returns:
        SuppressionCheckResult with match info and any expired matches
    """
    expired_matches: list[Suppression] = []

    for suppression in suppressions:
        if not suppression.matches(rule_id):
            continue

        # Pattern matched - check expiration
        if suppression.is_expired(current_time=current_time):
            # Track expired match for potential logging by caller
            expired_matches.append(suppression)
        else:
            # Found active match - return immediately
            return SuppressionCheckResult(
                is_suppressed=True,
                action=suppression.action,
                reason=suppression.reason,
                matched_pattern=suppression.pattern,
                expired_matches=expired_matches,
            )

    # No active match found
    return SuppressionCheckResult(
        is_suppressed=False,
        expired_matches=expired_matches,
    )


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
    - Check if rules are suppressed with action-based handling
    - Add/remove suppressions (delegates to repository)
    - Track active suppressions in memory
    - Wildcard pattern support with family prefix requirement
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
        action: SuppressionAction = SuppressionAction.SUPPRESS,
        created_by: str | None = None,
        expires_at: str | None = None,
        log_to_audit: bool = True,
    ) -> Suppression:
        """Add a suppression.

        Args:
            pattern: Rule ID pattern (supports wildcards with family prefix)
            reason: Reason for suppression (REQUIRED)
            action: What action to take when matched (default: SUPPRESS)
            created_by: Who created it (default: "api")
            expires_at: When it expires (ISO format, optional)
            log_to_audit: Whether to log to audit (default: True)

        Returns:
            Created Suppression object

        Raises:
            SuppressionValidationError: If pattern or reason is invalid
            ValueError: If maximum suppression limit is reached
        """
        # Security: Check maximum suppressions limit (only for new patterns)
        if pattern not in self._suppressions and len(self._suppressions) >= MAX_SUPPRESSIONS:
            raise ValueError(
                f"Maximum suppression limit ({MAX_SUPPRESSIONS}) reached"
            )

        suppression = Suppression(
            pattern=pattern,
            reason=reason,
            action=action,
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
                metadata={"suppression_action": action.value},
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

    def check_suppression(
        self,
        rule_id: str,
        *,
        current_time: datetime | None = None,
    ) -> SuppressionCheckResult:
        """Check if a rule is suppressed and get full result info (PURE LOGIC).

        This is the recommended method for checking suppressions as it returns
        complete information including action and expired matches.

        Args:
            rule_id: Rule ID to check
            current_time: Current time for testing (default: now)

        Returns:
            SuppressionCheckResult with full match info
        """
        return check_suppressions(
            rule_id,
            list(self._suppressions.values()),
            current_time=current_time,
        )

    def is_suppressed(
        self, rule_id: str, *, current_time: datetime | None = None
    ) -> tuple[bool, str]:
        """Check if a rule is suppressed (PURE LOGIC).

        Backward-compatible method that returns simple tuple.
        For new code, prefer check_suppression() which returns full info.

        Args:
            rule_id: Rule ID to check
            current_time: Current time for testing (default: now)

        Returns:
            Tuple of (is_suppressed, reason)
            - If suppressed: (True, "Reason for suppression")
            - If not suppressed: (False, "")
        """
        result = self.check_suppression(rule_id, current_time=current_time)
        return result.is_suppressed, result.reason

    def log_suppression_applied(
        self,
        rule_id: str,
        reason: str,
        *,
        scan_id: int | None = None,
        action: SuppressionAction = SuppressionAction.SUPPRESS,
    ) -> None:
        """Log that a suppression was applied during a scan.

        Args:
            rule_id: Rule ID that was suppressed
            reason: Reason for suppression
            scan_id: Scan ID (if applicable)
            action: The action that was taken
        """
        audit_entry = AuditEntry(
            pattern=rule_id,
            reason=reason,
            action="applied",
            created_at=datetime.now(timezone.utc).isoformat(),
            scan_id=scan_id,
            rule_id=rule_id,
            metadata={"suppression_action": action.value},
        )
        self._repository.log_audit(audit_entry)

    def get_suppressions(
        self, *, current_time: datetime | None = None
    ) -> list[Suppression]:
        """Get all active suppressions (PURE LOGIC).

        Args:
            current_time: Current time for testing (default: now)

        Returns:
            List of Suppression objects (excluding expired ones)
        """
        return [
            s
            for s in self._suppressions.values()
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

    def get_statistics(
        self, *, current_time: datetime | None = None
    ) -> dict[str, Any]:
        """Get suppression statistics (delegates to repository + pure logic).

        Args:
            current_time: Current time for testing (default: now)

        Returns:
            Dictionary with statistics including counts by action type
        """
        active_suppressions = self.get_suppressions(current_time=current_time)

        # Get audit counts from repository
        audit_log = self._repository.get_audit_log(limit=10000)  # Get all

        action_counts: dict[str, int] = {}
        for entry in audit_log:
            audit_action = entry["action"]
            action_counts[audit_action] = action_counts.get(audit_action, 0) + 1

        # Count recent applications (last 30 days)
        cutoff = (current_time or datetime.now(timezone.utc)) - timedelta(days=30)
        cutoff_str = cutoff.isoformat()
        recent_applications = sum(
            1
            for entry in audit_log
            if entry["action"] == "applied" and entry["created_at"] >= cutoff_str
        )

        # Count by suppression action type
        by_action_type: dict[str, int] = {}
        for supp in active_suppressions:
            by_action_type[supp.action.value] = (
                by_action_type.get(supp.action.value, 0) + 1
            )

        return {
            "total_active": len(active_suppressions),
            "total_added": action_counts.get("added", 0),
            "total_removed": action_counts.get("removed", 0),
            "total_applied": action_counts.get("applied", 0),
            "recent_applications_30d": recent_applications,
            "by_action_type": by_action_type,
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

    @property
    def config_path(self) -> Path | None:
        """Get config path from repository (if available).

        Returns:
            Path to config file, or None if repository doesn't expose it
        """
        return getattr(self._repository, "config_path", None)
